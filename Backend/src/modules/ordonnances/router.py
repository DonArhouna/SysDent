"""
Routes API du module Ordonnances (D1D).

Toutes les routes sont authentifiées, scopées au cabinet du JWT, protégées par
permission RBAC et journalisées.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from src.modules.audit.services import AuditService
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.ordonnances.schemas import (
    AlertePrescription,
    ControleContreIndication,
    ControleContreIndicationResponse,
    LignePrescriptionCreate,
    LignePrescriptionResponse,
    MedicamentCreate,
    MedicamentResponse,
    OrdonnanceCreate,
    OrdonnanceResponse,
    OrdonnanceUpdate,
)
from src.modules.ordonnances.services import MedicamentService, OrdonnanceService
from src.modules.tenants.models import Prescription, Utilisateur

router = APIRouter(prefix="/ordonnances", tags=["Ordonnances & Prescriptions"])
medicaments_router = APIRouter(prefix="/ordonnances/medicaments", tags=["Référentiel Médicamenteux"])


def _ctx(request: Request):
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


def _vers_reponse(prescription: Prescription) -> OrdonnanceResponse:
    lignes = [
        LignePrescriptionResponse(
            id=ligne.id,
            medicament_id=ligne.medicament_id,
            medicament_texte=ligne.medicament_texte,
            nom_commercial=ligne.medicament.nom_commercial if ligne.medicament else None,
            dci=ligne.medicament.dci if ligne.medicament else None,
            posologie=ligne.posologie,
            duree=ligne.duree,
            instructions=ligne.instructions,
            quantite=ligne.quantite,
            justification_precaution=ligne.justification_precaution,
        )
        for ligne in prescription.lignes
    ]
    return OrdonnanceResponse(
        id=prescription.id,
        numero=prescription.numero,
        consultation_id=prescription.consultation_id,
        patient_id=prescription.patient_id,
        praticien_id=prescription.praticien_id,
        date_ordonnance=prescription.date_ordonnance,
        notes_generales=prescription.notes_generales,
        signe=prescription.signe,
        date_signature=prescription.date_signature,
        lignes=lignes,
        alertes=[AlertePrescription(**a) for a in (prescription.alertes or [])],
        nb_lignes=len(lignes),
    )


# ==============================================================================
# RÉFÉRENTIEL MÉDICAMENTEUX
# ==============================================================================

@medicaments_router.get("", response_model=APIResponse[List[MedicamentResponse]])
async def list_medicaments(
    q: Optional[str] = Query(None, description="Recherche par nom commercial ou DCI"),
    forme: Optional[str] = Query(None, description="COMPRIME, BADEROUCHE, CAROUCHE..."),
    classe: Optional[str] = Query(None, description="Classe thérapeutique (AINS, ANTIBIOTIQUE...)"),
    inclure_inactifs: bool = Query(False, description="Inclure les médicaments retirés"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:READ")),
):
    """Référentiel médicamenteux du cabinet, avec les règles de contre-indication."""
    medicaments, _ = await MedicamentService.rechercher(
        db, q=q, forme=forme, classe=classe, inclure_inactifs=inclure_inactifs, limit=200
    )
    return APIResponse(
        data=[MedicamentResponse.model_validate(m, from_attributes=True) for m in medicaments]
    )


@medicaments_router.post("", response_model=APIResponse[MedicamentResponse], status_code=status.HTTP_201_CREATED)
async def create_medicament(
    data: MedicamentCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:CREATE")),
):
    """
    Ajoute un médicament au référentiel du cabinet.

    Ajouter un médicament ET ses règles de contre-indication est une opération
    de données : le moteur de contrôle n'a pas à être modifié.
    """
    ip, ua = _ctx(request)
    medicament = await MedicamentService.creer(db, data)

    await AuditService.log_action(
        db=db,
        action="MEDICAMENT_CREATE",
        resource_type="Medicament",
        resource_id=str(medicament.id),
        user_id=current_user.id if current_user else None,
        user_email=current_user.email if current_user else None,
        changes={
            "nom_commercial": medicament.nom_commercial,
            "dci": medicament.dci,
            "nb_regles": len(medicament.contre_indications or []),
        },
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()

    return APIResponse(
        message="Médicament ajouté au référentiel.",
        data=MedicamentResponse.model_validate(medicament, from_attributes=True),
    )


# ==============================================================================
# CONTRÔLE À BLANC (UC8)
# ==============================================================================

@router.post("/controle", response_model=APIResponse[ControleContreIndicationResponse])
async def controler_prescription(
    data: ControleContreIndication,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:READ")),
):
    """
    Vérifie si une prescription serait possible, sans rien enregistrer.

    Cas d'usage réel : le praticien hésite avant de saisir la posologie. Répondre
    tout de suite évite d'avoir à corriger une ordonnance émise.
    """
    ligne = LignePrescriptionCreate(
        medicament_id=data.medicament_id,
        medicament_texte=data.medicament_texte,
        posologie=data.posologie,
        duree=data.duree,
        instructions=data.instructions,
        quantite=data.quantite,
        justification_precaution=data.justification_precaution,
    )
    resultat = await OrdonnanceService.controler_possibilite(db, data.patient_id, ligne)
    return APIResponse(data=resultat)


# ==============================================================================
# ORDONNANCES
# ==============================================================================

@router.post("", response_model=APIResponse[OrdonnanceResponse], status_code=status.HTTP_201_CREATED)
async def creer_ordonnance(
    data: OrdonnanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:CREATE")),
):
    """
    Émet une ordonnance pour une consultation (UC7 du CDC).

    Une contre-indication formelle (RG08) fait échouer la requête. Une simple
    précaution exige une justification écrite, conservée au dossier.
    """
    ip, ua = _ctx(request)
    prescription = await OrdonnanceService.creer(
        db, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message=f"Ordonnance {prescription.numero} émise.",
        data=_vers_reponse(prescription),
    )


@router.get("", response_model=APIResponse[List[OrdonnanceResponse]])
async def list_ordonnances(
    patient_id: Optional[uuid.UUID] = Query(None, description="Filtrer par patient"),
    consultation_id: Optional[uuid.UUID] = Query(None, description="Filtrer par consultation"),
    limite: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:READ")),
):
    """Ordonnances du cabinet, de la plus récente à la plus ancienne."""
    prescriptions = await OrdonnanceService.lister(
        db, patient_id=patient_id, consultation_id=consultation_id, limite=limite
    )
    return APIResponse(data=[_vers_reponse(p) for p in prescriptions])


@router.get("/{prescription_id}", response_model=APIResponse[OrdonnanceResponse])
async def get_ordonnance(
    prescription_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:READ")),
):
    """Détail d'une ordonnance."""
    prescription = await OrdonnanceService.obtenir(db, prescription_id)
    return APIResponse(data=_vers_reponse(prescription))


@router.post("/{prescription_id}/signer", response_model=APIResponse[OrdonnanceResponse])
async def signer_ordonnance(
    prescription_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:SIGN")),
):
    """
    Signe l'ordonnance : elle devient non modifiable.

    Une ordonnance signée est un acte médical opposable. On ne la dé-signe pas,
    on en émet une nouvelle.
    """
    ip, ua = _ctx(request)
    prescription = await OrdonnanceService.signer(
        db, prescription_id, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Ordonnance signée.", data=_vers_reponse(prescription))


@router.patch("/{prescription_id}", response_model=APIResponse[OrdonnanceResponse])
async def update_ordonnance(
    prescription_id: uuid.UUID,
    data: OrdonnanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:UPDATE")),
):
    """Modifie les notes d'une ordonnance non signée."""
    ip, ua = _ctx(request)
    prescription = await OrdonnanceService.modifier(
        db, prescription_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Ordonnance mise à jour.", data=_vers_reponse(prescription))


@router.post("/{prescription_id}/lignes", response_model=APIResponse[OrdonnanceResponse])
async def ajouter_ligne(
    prescription_id: uuid.UUID,
    ligne: LignePrescriptionCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:UPDATE")),
):
    """
    Ajoute une ligne à une ordonnance non signée.

    Le contrôle de contre-indication est refait intégralement : l'état du
    patient a pu changer depuis l'émission.
    """
    ip, ua = _ctx(request)
    prescription = await OrdonnanceService.ajouter_ligne(
        db, prescription_id, ligne, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Ligne ajoutée.", data=_vers_reponse(prescription))


@router.delete("/{prescription_id}/lignes/{ligne_id}", response_model=APIResponse[OrdonnanceResponse])
async def supprimer_ligne(
    prescription_id: uuid.UUID,
    ligne_id: uuid.UUID,
    request: Request,
    motif: Optional[str] = Query(None, description="Motif de la suppression (conservé en audit)"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ORDONNANCES:UPDATE")),
):
    """Supprime une ligne d'une ordonnance non signée, avec trace en audit."""
    ip, ua = _ctx(request)
    prescription = await OrdonnanceService.supprimer_ligne(
        db, prescription_id, ligne_id, current_user, motif=motif, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Ligne supprimée.", data=_vers_reponse(prescription))
