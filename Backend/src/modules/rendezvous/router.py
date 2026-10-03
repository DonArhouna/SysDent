"""
Routes API du module Rendez-vous (D2B).

Toutes les routes sont authentifiées, scopées au cabinet du JWT et protégées par
permission RBAC.

Deux conventions de permissions, à connaître :
  `AGENDA:*`      agir sur un rendez-vous (prendre, confirmer, annuler…)
  `DISPONIBILITES:READ`  consulter les créneaux libres

Cette séparation reprend celle du D2A : le secrétariat programme des rendez-vous
mais ne modifie pas les horaires de travail des praticiens.
"""

import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.disponibilite import DUREE_CRENEAU_MINUTES
from src.common.rendezvous import (
    DUREE_MINUTES_POSSIBLES,
    DUREE_PAR_DEFAUT_MINUTES,
    LIBELLES_MOTIF_BLOCAGE,
    LIBELLES_STATUT,
    MOTIFS_BLOCAGE,
    STATUTS,
    transitions_possibles,
)
from src.common.schemas import APIResponse
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.rendezvous.schemas import (
    AgendaResponse,
    BlocageFauteuilCreate,
    CreneauLibre,
    RendezVousCreate,
    RendezVousResponse,
    RendezVousUpdate,
    StatutRendezVousResponse,
)
from src.modules.rendezvous.services import (
    CreneauFauteuilService,
    CreneauService,
    RendezVousService,
)
from src.modules.tenants.models import Utilisateur

router = APIRouter(prefix="/rendez-vous", tags=["Rendez-vous & Agenda"])


def _ctx(request: Request):
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# ==============================================================================
# RÉFÉRENTIEL
# ==============================================================================

@router.get("/referentiel", response_model=APIResponse[StatutRendezVousResponse])
async def get_referentiel(
    _: bool = Depends(require_permissions("AGENDA:READ")),
):
    """
    Cycle de vie, motifs de blocage et durées usuelles.

    Publier le graphe des transitions évite que le frontend invente un bouton
    « Terminer » sur un rendez-vous planifié, et montre au secrétariat
    uniquement les actions réellement possibles.
    """
    return APIResponse(
        data={
            "statuts": [
                {"code": code, "libelle": LIBELLES_STATUT[code],
                 "terminal": code in ("TERMINEE", "ANNULE", "ABSENT")}
                for code in STATUTS
            ],
            "transitions": {
                code: sorted(transitions_possibles(code)) for code in STATUTS
            },
            "motifs_blocage": [
                {"code": code, "libelle": LIBELLES_MOTIF_BLOCAGE[code]}
                for code in MOTIFS_BLOCAGE
            ],
            "duree_par_defaut_minutes": DUREE_PAR_DEFAUT_MINUTES,
            "durees_possibles": list(DUREE_MINUTES_POSSIBLES),
        }
    )


# ==============================================================================
# CRÉNEAUX LIBRES
# ==============================================================================

@router.get("/creneaux-libres", response_model=APIResponse[List[CreneauLibre]])
async def lister_creneaux_libres(
    praticien_id: uuid.UUID,
    date_: date = Query(..., alias="date", description="Date visée au format YYYY-MM-DD"),
    duree_minutes: int = Query(
        DUREE_CRENEAU_MINUTES, ge=5, le=240, description="Durée du rendez-vous envisagé"
    ),
    cabinet_id: Optional[uuid.UUID] = Query(None),
    exclure_rendez_vous: Optional[uuid.UUID] = Query(
        None, description="Rendez-vous en cours de report : son créneau reste proposé."
    ),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:READ")),
):
    """
    Créneaux réellement disponibles : heures déclarées **moins** ce qui est déjà
    pris (rendez-vous du praticien, fauteuils immobilisés).

    ⚠️ Complète `GET /praticiens/{id}/creneaux` du module D2A, qui ne connaît que
    les heures déclarées. C'est cette route qu'un écran de prise de rendez-vous
    doit appeler.
    """
    creneaux = await CreneauService.libres(
        db,
        praticien_id,
        date_,
        cabinet_id=cabinet_id,
        duree_minutes_=duree_minutes,
        exclure_id=exclure_rendez_vous,
    )
    return APIResponse(data=creneaux)


# ==============================================================================
# RENDEZ-VOUS
# ==============================================================================

@router.post("", response_model=APIResponse[RendezVousResponse], status_code=status.HTTP_201_CREATED)
async def creer_rendez_vous(
    data: RendezVousCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:CREATE")),
):
    """
    Prend un rendez-vous (UC9).

    **422 `CRENEAU_DEJA_OCCUPE`** si le créneau est pris. Le champ
    `error.details.conflits` nomme l'obstacle (avec qui, pour quel motif) : le
    frontend doit le montrer, et proposer d'autres horaires.

    Un créneau hors disponibilités déclarées est **accepté** ; la réponse porte
    alors `hors_disponibilites: true` pour que l'interface le signale.
    """
    ip, ua = _ctx(request)
    rendez_vous, hors_disponibilites = await RendezVousService.creer(
        db, data, current_user, client_ip=ip, user_agent=ua
    )

    message = f"Rendez-vous pris le {rendez_vous.debut:%d/%m/%Y à %H:%M}."
    if hors_disponibilites:
        message += (
            " Attention : ce créneau est hors des disponibilités déclarées du "
            "praticien."
        )
    return APIResponse(
        message=message,
        data=RendezVousService._vers_reponse(
            rendez_vous, hors_disponibilites=hors_disponibilites
        ),
    )


@router.get("", response_model=APIResponse[List[RendezVousResponse]])
async def lister_rendez_vous(
    patient_id: Optional[uuid.UUID] = Query(None),
    praticien_id: Optional[uuid.UUID] = Query(None),
    cabinet_id: Optional[uuid.UUID] = Query(None),
    fauteuil_id: Optional[uuid.UUID] = Query(None),
    du: Optional[datetime] = Query(None, description="Inclut les rendez-vous finissant après"),
    au: Optional[datetime] = Query(None, description="Inclut les rendez-vous débutant avant"),
    statut: Optional[List[str]] = Query(None, description="Filtrer par statut(s)"),
    limite: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:READ")),
):
    """
    Rendez-vous du cabinet, du plus ancien au plus récent.

    `du` / `au` filtrent sur l'INTERVALLE (et non sur un instant) : un
    rendez-vous de 14h30 à 15h est bien renvoyé pour `du=14h00`.
    """
    rendez_vous = await RendezVousService.lister(
        db,
        patient_id=patient_id,
        praticien_id=praticien_id,
        cabinet_id=cabinet_id,
        fauteuil_id=fauteuil_id,
        du=du,
        au=au,
        statuts=statut,
        limite=limite,
    )
    return APIResponse(data=[RendezVousService._vers_reponse(r) for r in rendez_vous])


@router.get("/agenda", response_model=APIResponse[AgendaResponse])
async def get_agenda(
    date_: date = Query(..., alias="date"),
    cabinet_id: Optional[uuid.UUID] = Query(None),
    praticien_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:READ")),
):
    """
    Journée d'agenda.

    Renvoie les rendez-vous ET les indisponibilités de fauteuil dans la même
    réponse : un planning qui ignore un fauteuil au compresseur en panne
    propose un créneau qu'on ne pourra pas honorer.
    """
    agenda = await RendezVousService.agenda(
        db, date_, cabinet_id=cabinet_id, praticien_id=praticien_id
    )
    return APIResponse(data=agenda)


@router.get("/{rendez_vous_id}", response_model=APIResponse[RendezVousResponse])
async def get_rendez_vous(
    rendez_vous_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:READ")),
):
    rendez_vous = await RendezVousService.obtenir(db, rendez_vous_id)
    return APIResponse(data=RendezVousService._vers_reponse(rendez_vous))


@router.patch("/{rendez_vous_id}", response_model=APIResponse[RendezVousResponse])
async def update_rendez_vous(
    rendez_vous_id: uuid.UUID,
    data: RendezVousUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:UPDATE")),
):
    """Corrige le motif, les notes, ou change le fauteuil tant que rien n'a commencé."""
    ip, ua = _ctx(request)
    rendez_vous = await RendezVousService.modifier(
        db, rendez_vous_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Rendez-vous mis à jour.", data=RendezVousService._vers_reponse(rendez_vous))


@router.post("/{rendez_vous_id}/planifier", response_model=APIResponse[RendezVousResponse])
async def planifier_rendez_vous(
    rendez_vous_id: uuid.UUID,
    request: Request,
    debut: datetime = Query(..., description="Nouvelle date/heure de début"),
    duree_minutes: int = Query(DUREE_PAR_DEFAUT_MINUTES, ge=5, le=480),
    fauteuil_id: Optional[uuid.UUID] = Query(None),
    motif_report: Optional[str] = Query(None, max_length=255),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:UPDATE")),
):
    """
    Reporte un rendez-vous à un autre créneau.

    Opération atomique : l'ancien créneau est libéré et le nouveau réservé. Le
    fauteuil se déplace avec, sauf indication contraire.
    """
    ip, ua = _ctx(request)
    rendez_vous = await RendezVousService.planifier(
        db,
        rendez_vous_id,
        debut,
        duree_minutes,
        current_user,
        fauteuil_id=fauteuil_id,
        motif_report=motif_report,
        client_ip=ip,
        user_agent=ua,
    )
    return APIResponse(
        message=f"Rendez-vous déplacé au {rendez_vous.debut:%d/%m/%Y à %H:%M}.",
        data=RendezVousService._vers_reponse(rendez_vous),
    )


@router.post("/{rendez_vous_id}/statut", response_model=APIResponse[RendezVousResponse])
async def changer_statut(
    rendez_vous_id: uuid.UUID,
    request: Request,
    statut: str = Query(..., description=f"Un de {STATUTS}"),
    motif: Optional[str] = Query(None, max_length=255),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:UPDATE")),
):
    """
    Fait avancer le rendez-vous : confirmer, appeler en salle d'attente, passer
    en consultation, terminer, annuler, marquer absent.

    **422 `TRANSITION_INTERDITE`** si le chemin n'existe pas. `error.details`
    indique les transitions possibles.

    Un rendez-vous annulé ou manqué **libère son créneau automatiquement** : la
    contrainte d'exclusion ignore ces statuts.
    """
    ip, ua = _ctx(request)
    rendez_vous = await RendezVousService.changer_statut(
        db, rendez_vous_id, statut, current_user, motif=motif, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message=f"Rendez-vous {LIBELLES_STATUT[rendez_vous.statut.value].lower()}.",
        data=RendezVousService._vers_reponse(rendez_vous),
    )


@router.post("/{rendez_vous_id}/consultation", status_code=status.HTTP_201_CREATED)
async def demarrer_consultation(
    rendez_vous_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:CREATE")),
):
    """
    Ouvre la consultation quand le patient passe en salle.

    C'est le SEUL endroit où `consultations.rendez_vous_id` et
    `consultations.fauteuil_id` sont posés : le fauteuil vient de l'occupation du
    rendez-vous, donc l'agenda et le dossier médical ne peuvent pas diverger sur
    le lieu du soin.

    Le rendez-vous devient `EN_CONSULTATION` et sera `TERMINEE` par le module
    Consultations à la clôture du soin.
    """
    from src.modules.rendezvous.router import _serialiser_consultation

    ip, ua = _ctx(request)
    consultation = await RendezVousService.demarrer_consultation(
        db, rendez_vous_id, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message="Consultation ouverte depuis le rendez-vous.",
        data=_serialiser_consultation(consultation),
    )


# ==============================================================================
# BLOCAGE DE FAUTEUIL
# ==============================================================================

@router.post("/fauteuils/blocage", status_code=status.HTTP_201_CREATED)
async def bloquer_fauteuil(
    data: BlocageFauteuilCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:UPDATE")),
):
    """
    Immobilise un fauteuil sans rendez-vous (panne, entretien).

    ⚠️ `422 CRENEAU_DEJA_OCCUPE` si un rendez-vous occupe déjà le fauteuil sur
    cette plage : il faut d'abord déplacer ou annuler ce rendez-vous, pas
    supprimer son occupation.
    """
    ip, ua = _ctx(request)
    occupation = await CreneauFauteuilService.creer(
        db, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message=(
            f"Fauteuil immobilisé du {occupation.debut:%d/%m %H:%M} "
            f"au {occupation.fin:%H:%M} ({occupation.motif.value})."
        ),
        data={
            "id": str(occupation.id),
            "fauteuil_id": str(occupation.fauteuil_id),
            "debut": occupation.debut,
            "fin": occupation.fin,
            "motif": occupation.motif.value,
            "motif_libelle": LIBELLES_MOTIF_BLOCAGE[occupation.motif.value],
            "motif_detail": occupation.motif_detail,
        },
    )


@router.delete("/fauteuils/blocage/{creneau_id}", status_code=status.HTTP_204_NO_CONTENT)
async def debloquer_fauteuil(
    creneau_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("AGENDA:UPDATE")),
):
    """
    Remet un fauteuil en service.

    **422 `OCCUPATION_LIEE_A_UN_RDV`** si le créneau appartient à un rendez-vous :
    c'est le rendez-vous qu'il faut annuler ou déplacer, sinon le fauteuil
    resterait réservé sans que personne ne le sache.
    """
    await CreneauFauteuilService.supprimer(db, creneau_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _serialiser_consultation(consultation) -> dict:
    """
    Sérialise la consultation issue d'un rendez-vous.

    Volontairement minimal : la ressource complète est
    `GET /consultations/{id}`. Cette route ne renvoie que ce qu'il faut pour
    afficher « soins démarrés » et enchaîner.
    """
    return {
        "id": str(consultation.id),
        "dossier_medical_id": str(consultation.dossier_medical_id),
        "praticien_id": str(consultation.praticien_id),
        "cabinet_id": str(consultation.cabinet_id),
        "fauteuil_id": str(consultation.fauteuil_id) if consultation.fauteuil_id else None,
        "rendez_vous_id": str(consultation.rendez_vous_id) if consultation.rendez_vous_id else None,
        "statut": consultation.statut.value,
        "date_consultation": consultation.date_consultation,
        "duree_minutes": consultation.duree_minutes,
    }
