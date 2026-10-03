"""
Routes API du module Cabinets & Ressources (D2A).

Toutes les routes sont authentifiées, scopées au cabinet du JWT et protégées par
permission RBAC.

Hiérarchie des URL, et pourquoi :
  /cabinets/{id}/salles/{id}/fauteuils  — un fauteuil appartient à une salle, qui
  appartient à un cabinet. Refléter cette hiérarchie dans les URL évite qu'un
  frontend se retrouve à valider à la main que les trois identifiants sont
  cohérents entre eux.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.disponibilite import DUREE_CRENEAU_MINUTES
from src.common.schemas import APIResponse
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.cabinets.schemas import (
    CabinetResponse,
    CabinetUpdate,
    CreneauxResponse,
    DisponibiliteCreate,
    DisponibiliteResponse,
    FauteuilCreate,
    FauteuilResponse,
    FauteuilUpdate,
    PraticienCreate,
    PraticienResponse,
    PraticienUpdate,
    RattachementCreate,
    RattachementResponse,
    ReferentielJoursResponse,
    SalleCreate,
    SalleResponse,
    SalleUpdate,
)
from src.modules.cabinets.services import (
    CabinetService,
    DisponibiliteService,
    FauteuilService,
    PraticienService,
    SalleService,
    referentiel_jours,
    vers_reponse_disponibilite,
    vers_reponse_praticien,
)
from src.modules.tenants.models import Utilisateur

router = APIRouter(tags=["Cabinets & Ressources"])


def _ctx(request: Request):
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# ==============================================================================
# RÉFÉRENTIEL (à charger en premier par le frontend : aucun accès en écriture)
# ==============================================================================

@router.get("/referentiel/disponibilites", response_model=APIResponse[ReferentielJoursResponse])
async def get_referentiel_disponibilites(
    _: bool = Depends(require_permissions("DISPONIBILITES:READ")),
):
    """
    Jours de la semaine, types de plage et durée de créneau.

    Publier la convention « 0 = lundi » évite que le frontend la redécouvre et
    diverge du backend — c'est le genre d'écart qui ne se voit qu'en production,
    le lundi matin.
    """
    return APIResponse(data=referentiel_jours())


# ==============================================================================
# CABINETS (SITES)
# ==============================================================================

@router.get("/cabinets", response_model=APIResponse[List[CabinetResponse]])
async def lister_cabinets(
    inclure_inactifs: bool = Query(False),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:READ")),
):
    """Sites de la société, avec leurs compteurs de salles, fauteuils et praticiens."""
    cabinets = await CabinetService.lister(db, inclure_inactifs=inclure_inactifs)
    reponses = []
    for cabinet in cabinets:
        compteurs = await CabinetService._compteurs(db, cabinet.id)
        reponses.append(_cabinet_reponse(cabinet, compteurs))
    return APIResponse(data=reponses)


@router.get("/cabinets/{cabinet_id}", response_model=APIResponse[CabinetResponse])
async def get_cabinet(
    cabinet_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:READ")),
):
    cabinet = await CabinetService.obtenir(db, cabinet_id)
    compteurs = await CabinetService._compteurs(db, cabinet.id)
    return APIResponse(data=_cabinet_reponse(cabinet, compteurs))


@router.patch("/cabinets/{cabinet_id}", response_model=APIResponse[CabinetResponse])
async def update_cabinet(
    cabinet_id: uuid.UUID,
    data: CabinetUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:UPDATE")),
):
    """Modifie un site (adresse, téléphone, horaires d'ouverture, activation)."""
    ip, ua = _ctx(request)
    cabinet = await CabinetService.modifier(
        db, cabinet_id, data, current_user, client_ip=ip, user_agent=ua
    )
    compteurs = await CabinetService._compteurs(db, cabinet.id)
    return APIResponse(
        message="Site mis à jour.", data=_cabinet_reponse(cabinet, compteurs)
    )


# ==============================================================================
# SALLES
# ==============================================================================

@router.get("/cabinets/{cabinet_id}/salles", response_model=APIResponse[List[SalleResponse]])
async def lister_salles(
    cabinet_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:READ")),
):
    """Salles d'un site, avec le nombre de fauteuils par salle."""
    await CabinetService.obtenir(db, cabinet_id)
    lignes = await SalleService.lister(db, cabinet_id)
    return APIResponse(
        data=[
            SalleResponse(
                id=salle.id,
                cabinet_id=salle.cabinet_id,
                nom=salle.nom,
                etage=salle.etage,
                nb_fauteuils=total,
                nb_fauteuils_actifs=actifs,
            )
            for salle, total, actifs in lignes
        ]
    )


@router.post(
    "/cabinets/{cabinet_id}/salles",
    response_model=APIResponse[SalleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_salle(
    cabinet_id: uuid.UUID,
    data: SalleCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:CREATE")),
):
    """Crée une salle dans un site."""
    ip, ua = _ctx(request)
    salle = await SalleService.creer(db, cabinet_id, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(
        message="Salle créée.",
        data=SalleResponse(
            id=salle.id,
            cabinet_id=salle.cabinet_id,
            nom=salle.nom,
            etage=salle.etage,
        ),
    )


@router.patch(
    "/cabinets/{cabinet_id}/salles/{salle_id}", response_model=APIResponse[SalleResponse]
)
async def update_salle(
    cabinet_id: uuid.UUID,
    salle_id: uuid.UUID,
    data: SalleUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:UPDATE")),
):
    salle = await SalleService.obtenir(db, salle_id)
    if salle.cabinet_id != cabinet_id:
        from src.core.exceptions import EntityNotFoundException

        raise EntityNotFoundException("Salle", salle_id)
    await SalleService.modifier(db, salle_id, data, current_user)
    return APIResponse(message="Salle mise à jour.", data=await _salle_enrichie(db, salle_id))


@router.delete(
    "/cabinets/{cabinet_id}/salles/{salle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def supprimer_salle(
    cabinet_id: uuid.UUID,
    salle_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:DELETE")),
):
    """
    Supprime une salle **vide**.

    Une salle qui contient encore des fauteuils est refusée : il faut d'abord
    les désactiver un par un.
    """
    from src.core.exceptions import EntityNotFoundException

    salle = await SalleService.obtenir(db, salle_id)
    if salle.cabinet_id != cabinet_id:
        raise EntityNotFoundException("Salle", salle_id)

    ip, ua = _ctx(request)
    await SalleService.supprimer(db, salle_id, current_user, client_ip=ip, user_agent=ua)
    return None


# ==============================================================================
# FAUTEUILS
# ==============================================================================

@router.get("/cabinets/{cabinet_id}/fauteuils", response_model=APIResponse[List[FauteuilResponse]])
async def lister_fauteuils(
    cabinet_id: uuid.UUID,
    inclure_inactifs: bool = Query(False),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:READ")),
):
    """
    Fauteuils d'un site, toutes salles confondues.

    C'est la vue qu'un écran de planning consomme : placer un patient demande
    de savoir quel fauteuil est libre, pas dans quelle salle il se trouve.
    """
    lignes = await FauteuilService.lister(
        db, cabinet_id=cabinet_id, inclure_inactifs=inclure_inactifs
    )
    return APIResponse(data=[_fauteuil_reponse(f, salle_nom, cabinet_nom) for f, salle_nom, cabinet_nom in lignes])


@router.post(
    "/salles/{salle_id}/fauteuils",
    response_model=APIResponse[FauteuilResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_fauteuil(
    salle_id: uuid.UUID,
    data: FauteuilCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:CREATE")),
):
    """Ajoute un fauteuil dans une salle."""
    ip, ua = _ctx(request)
    fauteuil = await FauteuilService.creer(
        db, salle_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Fauteuil créé.", data=_fauteuil_reponse(fauteuil))


@router.patch("/fauteuils/{fauteuil_id}", response_model=APIResponse[FauteuilResponse])
async def update_fauteuil(
    fauteuil_id: uuid.UUID,
    data: FauteuilUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:UPDATE")),
):
    """Renomme un fauteuil, ajuste ses équipements, ou l'active / désactive."""
    fauteuil = await FauteuilService.modifier(db, fauteuil_id, data, current_user)
    return APIResponse(message="Fauteuil mis à jour.", data=_fauteuil_reponse(fauteuil))


@router.post("/fauteuils/{fauteuil_id}/reactiver", response_model=APIResponse[FauteuilResponse])
async def reactiver_fauteuil(
    fauteuil_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:UPDATE")),
):
    """Remet en service un fauteuil désactivé."""
    fauteuil = await FauteuilService.reactiver(db, fauteuil_id, current_user)
    return APIResponse(message="Fauteuil remis en service.", data=_fauteuil_reponse(fauteuil))


@router.delete("/fauteuils/{fauteuil_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_fauteuil(
    fauteuil_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CABINETS:DELETE")),
):
    """
    Supprime un fauteuil **jamais utilisé**.

    Un fauteuil ayant servi à une consultation est refusé
    (`FAUTEUIL_UTILISE`) : le désactiver préserve l'historique du lieu du soin.
    """
    ip, ua = _ctx(request)
    await FauteuilService.supprimer(db, fauteuil_id, current_user, client_ip=ip, user_agent=ua)
    return None


# ==============================================================================
# PRATICIENS
# ==============================================================================

@router.get("/praticiens", response_model=APIResponse[List[PraticienResponse]])
async def lister_praticiens(
    cabinet_id: Optional[uuid.UUID] = Query(None, description="Restreindre à un site"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:READ")),
):
    """
    Praticiens du cabinet, triés par nom de famille.

    `cabinet_id` ne renvoie que ceux rattachés **activement** à ce site : c'est
    la liste que l'agenda doit proposer.
    """
    praticiens = await PraticienService.lister(db, cabinet_id=cabinet_id)
    return APIResponse(data=[vers_reponse_praticien(p) for p in praticiens])


@router.get("/praticiens/{praticien_id}", response_model=APIResponse[PraticienResponse])
async def get_praticien(
    praticien_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:READ")),
):
    praticien = await PraticienService.obtenir(db, praticien_id)
    return APIResponse(data=vers_reponse_praticien(praticien))


@router.post(
    "/praticiens", response_model=APIResponse[PraticienResponse], status_code=status.HTTP_201_CREATED
)
async def creer_praticien(
    data: PraticienCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:CREATE")),
):
    """
    Rattache un compte existant au métier de praticien.

    Le compte doit déjà exister : un praticien sans compte ne pourrait rien
    signer, or c'est la signature qui rend un acte opposable.
    """
    ip, ua = _ctx(request)
    praticien = await PraticienService.creer(db, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(
        message="Praticien enregistré.",
        data=vers_reponse_praticien(await PraticienService.obtenir(db, praticien.id)),
    )


@router.patch("/praticiens/{praticien_id}", response_model=APIResponse[PraticienResponse])
async def update_praticien(
    praticien_id: uuid.UUID,
    data: PraticienUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:UPDATE")),
):
    """Modifie la fiche professionnelle (titre, spécialité, numéro d'ordre, bio)."""
    await PraticienService.modifier(db, praticien_id, data, current_user)
    return APIResponse(
        message="Praticien mis à jour.",
        data=vers_reponse_praticien(await PraticienService.obtenir(db, praticien_id)),
    )


@router.get(
    "/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement",
    response_model=APIResponse[RattachementResponse],
)
async def get_rattachement(
    cabinet_id: uuid.UUID,
    praticien_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:READ")),
):
    """Rattachement d'un praticien à un site (actif ou clôturé)."""
    from src.core.exceptions import EntityNotFoundException
    from sqlalchemy import select
    from src.modules.tenants.models import CabinetPraticien

    cabinet = await CabinetService.obtenir(db, cabinet_id)
    rattachement = (
        await db.execute(
            select(CabinetPraticien).where(
                CabinetPraticien.cabinet_id == cabinet_id,
                CabinetPraticien.praticien_id == praticien_id,
            )
        )
    ).scalar_one_or_none()
    if rattachement is None:
        raise EntityNotFoundException("Rattachement", praticien_id)

    return APIResponse(
        data=RattachementResponse(
            id=rattachement.id,
            cabinet_id=rattachement.cabinet_id,
            cabinet_nom=cabinet.nom,
            praticien_id=rattachement.praticien_id,
            date_debut=rattachement.date_debut,
            date_fin=rattachement.date_fin,
            actif=rattachement.actif,
        )
    )


@router.post(
    "/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement",
    response_model=APIResponse[RattachementResponse],
)
async def rattacher_praticien(
    cabinet_id: uuid.UUID,
    praticien_id: uuid.UUID,
    data: RattachementCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:UPDATE")),
):
    """Rattache un praticien à un site, ou rouvre un rattachement clôturé."""
    ip, ua = _ctx(request)
    cabinet = await CabinetService.obtenir(db, cabinet_id)
    rattachement = await PraticienService.rattacher(
        db, cabinet_id, praticien_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message="Praticien rattaché.",
        data=RattachementResponse(
            id=rattachement.id,
            cabinet_id=rattachement.cabinet_id,
            cabinet_nom=cabinet.nom,
            praticien_id=rattachement.praticien_id,
            date_debut=rattachement.date_debut,
            date_fin=rattachement.date_fin,
            actif=rattachement.actif,
        ),
    )


@router.delete(
    "/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detacher_praticien(
    cabinet_id: uuid.UUID,
    praticien_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PRATICIENS:UPDATE")),
):
    """
    Clôt le rattachement d'un praticien à un site.

    La ligne n'est pas supprimée : `date_fin` est renseignée et le
    rattachement devient inactif. Les consultations passées restent attribuables.
    """
    await PraticienService.detacher(db, cabinet_id, praticien_id, current_user)
    return None


# ==============================================================================
# DISPONIBILITÉS
# ==============================================================================

@router.get(
    "/praticiens/{praticien_id}/disponibilites",
    response_model=APIResponse[List[DisponibiliteResponse]],
)
async def lister_disponibilites(
    praticien_id: uuid.UUID,
    cabinet_id: Optional[uuid.UUID] = Query(
        None, description="Filtrer par site (inclut les plages tous-sites)"
    ),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("DISPONIBILITES:READ")),
):
    """Plages horaires déclarées par un praticien, récurrentes et exceptions."""
    await PraticienService.obtenir(db, praticien_id)
    disponibilites = await DisponibiliteService.lister(db, praticien_id, cabinet_id=cabinet_id)
    return APIResponse(data=[vers_reponse_disponibilite(d) for d in disponibilites])


@router.post(
    "/praticiens/{praticien_id}/disponibilites",
    response_model=APIResponse[DisponibiliteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_disponibilite(
    praticien_id: uuid.UUID,
    data: DisponibiliteCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("DISPONIBILITES:CREATE")),
):
    """
    Déclare une plage de travail.

    `type=BLOCKING` déclare une indisponibilité (congé, formation) qui RETIRE
    des créneaux ; `CONSULTATION` en crée. Les deux ne se confondent pas : un
    créneau réservé aux urgences n'est pas une absence.
    """
    ip, ua = _ctx(request)
    disponibilite = await DisponibiliteService.creer(
        db, praticien_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message="Disponibilité enregistrée.",
        data=vers_reponse_disponibilite(disponibilite),
    )


@router.delete("/disponibilites/{disponibilite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_disponibilite(
    disponibilite_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("DISPONIBILITES:DELETE")),
):
    """Retire une plage déclarée."""
    ip, ua = _ctx(request)
    await DisponibiliteService.supprimer(
        db, disponibilite_id, current_user, client_ip=ip, user_agent=ua
    )
    return None


@router.get(
    "/praticiens/{praticien_id}/creneaux", response_model=APIResponse[CreneauxResponse]
)
async def lister_creneaux(
    praticien_id: uuid.UUID,
    date: str = Query(..., description="Date visée au format YYYY-MM-DD"),
    cabinet_id: Optional[uuid.UUID] = Query(None),
    duree_minutes: int = Query(DUREE_CRENEAU_MINUTES, ge=5, le=240),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("DISPONIBILITES:READ")),
):
    """
    Créneaux qu'on peut proposer au patient pour une date donnée.

    C'est le calcul dont le module Agenda (D2B) aura besoin pour placer un
    rendez-vous. Il est exposé dès maintenant parce que le secrétariat en a
    besoin au téléphone, pour répondre à un patient qui demande « quand puis-je
    venir ? ».

    Les plages `BLOCKING` sont déjà retirées du résultat. **Les rendez-vous déjà
    pris ne le sont pas** : à ce stade, aucun autre module ne les connaît. C'est
    D2B qui effectuera ce retranchement.
    """
    from datetime import date as date_cls

    try:
        jour = date_cls.fromisoformat(date)
    except ValueError:
        from src.core.exceptions import AppException

        raise AppException(
            f"Date invalide : {date!r}. Format attendu : YYYY-MM-DD.",
            code="DATE_INVALIDE",
            status_code=422,
        ) from None

    resultat = await DisponibiliteService.creneaux(
        db,
        praticien_id,
        jour,
        cabinet_id=cabinet_id,
        duree_minutes=duree_minutes,
    )
    return APIResponse(data=resultat)


# ==============================================================================
# HELPERS DE SÉRIALISATION
# ==============================================================================

def _cabinet_reponse(cabinet, compteurs: dict) -> CabinetResponse:
    """
    Construit la réponse d'un site avec ses compteurs.

    On fusionne les deux dictionnaires avant de valider, et non après : le schéma
    porte déjà `nb_salles` / `nb_fauteuils_actifs` / `nb_praticiens_actifs` avec
    une valeur par défaut, et `**model_dump(), **compteurs` lèverait « got multiple
    values for keyword argument ». L'union `|` entre un modèle Pydantic et un
    dict n'est pas supportée non plus.
    """
    donnees = CabinetResponse.model_validate(cabinet, from_attributes=True).model_dump()
    donnees.update(compteurs)
    return CabinetResponse(**donnees)


def _fauteuil_reponse(fauteuil, nom_salle: Optional[str] = None, nom_cabinet: Optional[str] = None) -> FauteuilResponse:
    """
    Sérialise un fauteuil, en complétant salle et cabinet si on les connaît.

    La relation `fauteuil.salle` n'est pas chargée dans tous les chemins
    (liste avec jointure, création simple) : on n'y touche pas pour éviter un
    lazy-load asynchrone, on transmet ce que l'appelant a déjà chargé.
    """
    return FauteuilResponse(
        id=fauteuil.id,
        salle_id=fauteuil.salle_id,
        numero=fauteuil.numero,
        equipements=fauteuil.equipements,
        actif=fauteuil.actif,
        nom_salle=nom_salle,
        cabinet_nom=nom_cabinet,
    )


async def _salle_enrichie(db: AsyncSession, salle_id: uuid.UUID) -> SalleResponse:
    """Recharge une salle avec ses compteurs de fauteuils."""
    lignes = await SalleService.lister(db, (await SalleService.obtenir(db, salle_id)).cabinet_id)
    for salle, total, actifs in lignes:
        if salle.id == salle_id:
            return SalleResponse(
                id=salle.id,
                cabinet_id=salle.cabinet_id,
                nom=salle.nom,
                etage=salle.etage,
                nb_fauteuils=total,
                nb_fauteuils_actifs=actifs,
            )
    salle = await SalleService.obtenir(db, salle_id)
    return SalleResponse(id=salle.id, cabinet_id=salle.cabinet_id, nom=salle.nom, etage=salle.etage)
