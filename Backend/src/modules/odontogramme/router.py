"""
Routes API de l'Odontogramme (D1C).

Toutes les routes sont authentifiées, scopées au cabinet du JWT, protégées par
permission RBAC et journalisées dans l'audit médico-légal du cabinet.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.dentaire import ETATS_ATTENTION, ETATS_SOIGNES, FACES_COURTES, FACES_DENT
from src.common.schemas import APIResponse
from src.modules.audit.services import AuditService
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.odontogramme.schemas import (
    ChartingParodontalCreate,
    ChartingParodontalResponse,
    DentMiseAJour,
    DentResponse,
    DentsMiseAJourLot,
    EtatHistoriqueResponse,
    FaceDentResponse,
    FaceMiseAJour,
    FacesMiseAJour,
    HistoriqueDentResponse,
    OdontogrammeCreer,
    OdontogrammeResponse,
)
from src.modules.odontogramme.services import LIBELLES_ETATS, OdontogrammeService
from src.modules.tenants.models import Odontogramme, Utilisateur

router = APIRouter(prefix="/odontogramme", tags=["Odontogramme"])


def _ctx(request: Request):
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


def _dent_vers_reponse(dent) -> DentResponse:
    faces = [
        FaceDentResponse(
            face=f.face,
            face_courte=FACES_COURTES.get(f.face, f.face[:1]),
            etat=f.etat,
            notes=f.notes,
        )
        for f in sorted(dent.faces, key=lambda x: FACES_DENT.index(x.face) if x.face in FACES_DENT else 99)
    ]
    return DentResponse(
        id=dent.id,
        numero_fdi=dent.numero_fdi,
        numero_universal=dent.numero_universal,
        etat_actuel=dent.etat_actuel,
        etat_libelle=LIBELLES_ETATS.get(dent.etat_actuel),
        mobilite=dent.mobilite,
        notes=dent.notes,
        faces=faces,
        a_alerte=dent.etat_actuel in ETATS_ATTENTION,
    )


def _odontogramme_vers_reponse(odontogramme: Odontogramme) -> OdontogrammeResponse:
    synthese = OdontogrammeService.synthese(odontogramme)
    return OdontogrammeResponse(
        id=odontogramme.id,
        patient_id=(
            odontogramme.dossier_medical.patient_id if odontogramme.dossier_medical else None
        ),
        dossier_medical_id=odontogramme.dossier_medical_id,
        type=odontogramme.type,
        systeme_notation=odontogramme.systeme_notation,
        nb_dents=synthese["nb_dents"],
        dents=sorted(
            (_dent_vers_reponse(d) for d in odontogramme.dents), key=lambda d: d.numero_fdi
        ),
        nb_dents_soignees=synthese["nb_dents_soignees"],
        nb_dents_a_traiter=synthese["nb_dents_a_traiter"],
        nb_dents_absentes=synthese["nb_dents_absentes"],
        resume=synthese["resume"],
    )


# ==============================================================================
# CONSULTATION DE L'ODONTOGRAMME
# ==============================================================================

@router.get("/patients/{patient_id}", response_model=APIResponse[OdontogrammeResponse])
async def get_odontogramme(
    patient_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:READ")),
):
    """
    Odontogramme complet du patient (32 dents adulte, 20 dents enfant — RG11).

    L'odontogramme est généré à la première lecture s'il n'existe pas encore.
    """
    ip, ua = _ctx(request)
    odontogramme = await OdontogrammeService.obtenir_ou_creer(
        db, patient_id, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(data=_odontogramme_vers_reponse(odontogramme))


@router.post("/patients/{patient_id}", response_model=APIResponse[OdontogrammeResponse])
async def creer_odontogramme(
    patient_id: uuid.UUID,
    data: OdontogrammeCreer,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:UPDATE")),
):
    """
    Crée explicitement l'odontogramme d'un patient (choix adulte/enfant, RG11).

    Idempotent : si l'odontogramme existe déjà, il est renvoyé tel quel. On ne
    réécrit jamais un odontogramme en cours d'utilisation, cela effacerait
    l'historique dentaire du patient.
    """
    ip, ua = _ctx(request)
    odontogramme = await OdontogrammeService.creer_ou_obtenir(
        db,
        patient_id,
        type_odontogramme=data.type,
        systeme_notation=data.systeme_notation,
        auteur=current_user,
        client_ip=ip,
        user_agent=ua,
    )
    return APIResponse(message="Odontogramme disponible.", data=_odontogramme_vers_reponse(odontogramme))


@router.get("/patients/{patient_id}/dent/{numero_fdi}", response_model=APIResponse[DentResponse])
async def get_dent(
    patient_id: uuid.UUID,
    numero_fdi: int,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:READ")),
):
    """État courant d'une dent, avec ses faces."""
    odontogramme = await OdontogrammeService.obtenir_ou_creer(db, patient_id)
    dent = next((d for d in odontogramme.dents if d.numero_fdi == numero_fdi), None)
    if dent is None:
        from src.core.exceptions import EntityNotFoundException

        raise EntityNotFoundException("Dent", numero_fdi)
    return APIResponse(data=_dent_vers_reponse(dent))


# ==============================================================================
# MISE À JOUR DE L'ÉTAT DENTAIRE (RG10)
# ==============================================================================

@router.patch("/patients/{patient_id}/dent", response_model=APIResponse[OdontogrammeResponse])
async def update_dent(
    patient_id: uuid.UUID,
    data: DentMiseAJour,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:UPDATE")),
):
    """
    Change l'état d'une dent et écrit la ligne d'historique (RG10).

    L'ancien état, la date, le praticien et la consultation sont conservés.
    """
    ip, ua = _ctx(request)
    odontogramme = await OdontogrammeService.mettre_a_jour_dent(
        db, patient_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message=f"Dent {data.numero_fdi} mise à jour.", data=_odontogramme_vers_reponse(odontogramme))


@router.patch("/patients/{patient_id}/dents", response_model=APIResponse[OdontogrammeResponse])
async def update_dents(
    patient_id: uuid.UUID,
    data: DentsMiseAJourLot,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:UPDATE")),
):
    """
    Met à jour plusieurs dents en une transaction (détartrage multi-dents).

    Soit toutes les dents sont mises à jour, soit aucune : un lot partiellement
    appliqué laisserait l'odontogramme incohérent avec la consultation.
    """
    ip, ua = _ctx(request)
    odontogramme = await OdontogrammeService.mettre_a_jour_dents(
        db, patient_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message=f"{len(data.dents)} dent(s) mise(s) à jour.",
        data=_odontogramme_vers_reponse(odontogramme),
    )


@router.put("/patients/{patient_id}/dent/{numero_fdi}/faces", response_model=APIResponse[OdontogrammeResponse])
async def update_faces(
    patient_id: uuid.UUID,
    numero_fdi: int,
    data: FacesMiseAJour,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:UPDATE")),
):
    """Met à jour les faces d'une dent (lésion localisée)."""
    ip, ua = _ctx(request)
    odontogramme = await OdontogrammeService.mettre_a_jour_faces(
        db, patient_id, numero_fdi, data.faces, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message=f"Faces de la dent {numero_fdi} mises à jour.",
        data=_odontogramme_vers_reponse(odontogramme),
    )


# ==============================================================================
# HISTORIQUE (RG10)
# ==============================================================================

@router.get(
    "/patients/{patient_id}/dent/{numero_fdi}/historique",
    response_model=APIResponse[HistoriqueDentResponse],
)
async def get_historique_dent(
    patient_id: uuid.UUID,
    numero_fdi: int,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:READ")),
):
    """Historique horodaté d'une dent : qui a constaté quoi, et quand (RG10)."""
    resultat = await OdontogrammeService.historique_dent(db, patient_id, numero_fdi)
    return APIResponse(
        data=HistoriqueDentResponse(
            dent=_dent_vers_reponse(resultat["dent"]),
            historique=[
                EtatHistoriqueResponse(
                    id=h.id,
                    dent_id=h.dent_id,
                    date_constat=h.date_constat,
                    etat=h.etat,
                    etat_precedent=h.etat_precedent,
                    face=h.face,
                    consultation_id=h.consultation_id,
                    praticien_id=h.praticien_id,
                    notes=h.notes,
                )
                for h in resultat["historique"]
            ],
        )
    )


@router.get(
    "/patients/{patient_id}/historique",
    response_model=APIResponse[List[EtatHistoriqueResponse]],
)
async def get_historique_global(
    patient_id: uuid.UUID,
    limite: int = Query(100, ge=1, le=500, description="Nombre de lignes maxi"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:READ")),
):
    """Historique du patient toutes dents confondues, du plus récent au plus ancien."""
    lignes = await OdontogrammeService.historique_global(db, patient_id, limite=limite)
    return APIResponse(
        data=[
            EtatHistoriqueResponse(
                id=h.id,
                dent_id=h.dent_id,
                date_constat=h.date_constat,
                etat=h.etat,
                etat_precedent=h.etat_precedent,
                face=h.face,
                consultation_id=h.consultation_id,
                praticien_id=h.praticien_id,
                notes=h.notes,
            )
            for h in lignes
        ]
    )


# ==============================================================================
# CHARTING PARODONTAL
# ==============================================================================

@router.post(
    "/patients/{patient_id}/charting",
    response_model=APIResponse[ChartingParodontalResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_charting(
    patient_id: uuid.UUID,
    data: ChartingParodontalCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:UPDATE")),
):
    """Enregistre un relevé parodontal : sondage en 6 points et indices associés."""
    ip, ua = _ctx(request)
    releve = await OdontogrammeService.enregistrer_charting(
        db, patient_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message="Relevé parodontal enregistré.",
        data=ChartingParodontalResponse.model_validate(releve, from_attributes=True),
    )


@router.get(
    "/patients/{patient_id}/charting",
    response_model=APIResponse[List[ChartingParodontalResponse]],
)
async def list_chartings(
    patient_id: uuid.UUID,
    dent_id: Optional[uuid.UUID] = Query(None, description="Filtrer par dent"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:READ")),
):
    """Relevés parodontaux du patient, du plus récent au plus ancien."""
    releves = await OdontogrammeService.lister_chartings(db, patient_id, dent_id)
    return APIResponse(
        data=[ChartingParodontalResponse.model_validate(r, from_attributes=True) for r in releves]
    )


# ==============================================================================
# RÉFÉRENTIEL (alimente le composant SVG)
# ==============================================================================

@router.get("/referentiel/etats", response_model=APIResponse[dict])
async def referentiel_etats(
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ODONTOGRAMME:READ")),
):
    """
    Catalogue des états et des faces, avec leur code couleur.

    Le frontend ne doit pas coder en dur ces listes : un état odontologique
    ajouté côté backend doit apparaître sans modification du composant SVG.
    """
    from src.common.dentaire import ETATS_DENT, FACES_DENT

    # Palette du CDC : vert sain, rouge carie, bleu soigné, gris absent, or couronne.
    COULEURS = {
        "SAINE": "#22C55E",
        "A_TRAITER": "#EAB308",
        "CARIE_DEBUTANTE": "#F97316",
        "CARIE_AVANCEE": "#EF4444",
        "CARIE_PROFONDE": "#B91C1C",
        "CARIE_SOUS_PLOMBAGE": "#7F1D1D",
        "ABSENTE_EXTRACTEE": "#9CA3AF",
        "ABSENTE_CONGENITALE": "#9CA3AF",
        "SUPERNUMERAIRE": "#A78BFA",
        "INCLUSE": "#A78BFA",
    }
    couleur_soignee = "#3B82F6"
    couleur_couronne = "#EAB308"

    etats = []
    for etat in ETATS_DENT:
        couleur = COULEURS.get(etat)
        if couleur is None:
            couleur = couleur_couronne if "COURONNE" in etat or "BRIDGE" in etat else couleur_soignee
        etats.append(
            {
                "code": etat,
                "libelle": LIBELLES_ETATS.get(etat, etat.replace("_", " ").capitalize()),
                "couleur": couleur,
                "categorie": (
                    "SOIGNEE" if etat in ETATS_SOIGNES
                    else "ATTENTION" if etat in ETATS_ATTENTION
                    else "SAINE" if etat == "SAINE"
                    else "AUTRE"
                ),
            }
        )

    return APIResponse(
        data={
            "etats": etats,
            "faces": [{"code": f, "court": FACES_COURTES[f]} for f in FACES_DENT],
        }
    )
