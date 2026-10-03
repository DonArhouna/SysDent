"""
Routes API du module Patients & Dossier Médical (§4.2 du rapport).

Toutes les routes sont :
  - authentifiées (JWT bearer ou cookie HttpOnly) via `get_current_user`,
  - scopées au cabinet du JWT via `get_tenant_db` (isolation multi-tenant),
  - protégées par permission RBAC `PATIENTS:*`,
  - tracées dans l'audit médico-légal du cabinet (RG12).

Note RBAC : le format de permission produit par `AuthService` est
"MODULE:ACTION" (ex: "PATIENTS:READ"). Les gardes utilisent ce même format.
"""

from datetime import date
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.patients.schemas import (
    AntecedentMedicalCreate,
    AntecedentMedicalResponse,
    AntecedentMedicalUpdate,
    EtatGeneralCreate,
    EtatGeneralResponse,
    EtatGeneralUpdate,
    PatientArchive,
    PatientCreate,
    PatientDossierCompletResponse,
    PatientResponse,
    PatientUpdate,
    RecherchePatients,
)
from src.modules.patients.services import AntecedentService, EtatGeneralService, PatientService
from src.modules.tenants.models import Utilisateur

router = APIRouter(prefix="/patients", tags=["Patients & Dossier Médical"])


def _request_context(request: Request):
    """Extrait l'IP et l'User-Agent pour le journal d'audit."""
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# ==============================================================================
# PATIENTS — CRUD & RECHERCHE (UC1, UC2, UC3, UC12)
# ==============================================================================

@router.post("", response_model=APIResponse[PatientResponse], status_code=status.HTTP_201_CREATED)
async def create_patient(
    data: PatientCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:CREATE")),
):
    """Crée un dossier patient avec numéro auto-généré (UC1, Étape 1 du CDC)."""
    ip, ua = _request_context(request)
    patient = await PatientService.creer_patient(db, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(
        message=f"Dossier {patient.numero_dossier} créé avec succès.",
        data=patient,
    )


@router.get("", response_model=PaginatedResponse[PatientResponse])
async def list_patients(
    request: Request,
    q: Optional[str] = Query(None, description="Recherche libre (nom, prénom, N° dossier, tél.)"),
    nom: Optional[str] = Query(None, description="Filtrer par nom"),
    telephone: Optional[str] = Query(None, description="Filtrer par téléphone"),
    numero_dossier: Optional[str] = Query(None, description="Filtrer par numéro de dossier exact"),
    date_naissance: Optional[date] = Query(None, description="Filtrer par date de naissance"),
    include_archives: bool = Query(False, description="Inclure les dossiers archivés"),
    uniquement_archives: bool = Query(False, description="Ne renvoyer que les dossiers archivés"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:READ")),
):
    """Recherche multicritère paginée des dossiers patients (UC2)."""
    _ = _request_context(request)  # contexte réservé à la traçabilité des searches sensibles
    filtres = RecherchePatients(
        q=q,
        nom=nom,
        telephone=telephone,
        numero_dossier=numero_dossier,
        date_naissance=date_naissance,
        include_archives=include_archives,
        uniquement_archives=uniquement_archives,
    )
    params = PaginationParams(page=page, limit=limit)
    patients, total = await PatientService.rechercher(db, filtres, params.offset, params.limit)
    return paginate(items=patients, total_records=total, params=params)


@router.get("/{patient_id}", response_model=APIResponse[PatientResponse])
async def get_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:READ")),
):
    """Récupère l'identité administrative d'un dossier patient (UC2)."""
    patient = await PatientService.obtenir_patient(db, patient_id)
    return APIResponse(data=patient)


@router.get("/{patient_id}/dossier", response_model=APIResponse[PatientDossierCompletResponse])
async def get_patient_dossier(
    patient_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:READ")),
):
    """
    Fiche dossier médical complète : identité + état général + antécédents +
    alertes cliniques calculées (UC5 « Consulter dossier médical »).
    """
    ip, ua = _request_context(request)
    resultat = await PatientService.obtenir_dossier_complet(
        db, patient_id, current_user, client_ip=ip, user_agent=ua
    )

    etat_general = resultat["etat_general"]
    reponse = PatientDossierCompletResponse(
        **{
            k: v
            for k, v in vars(resultat["patient"]).items()
            if k in PatientDossierCompletResponse.model_fields
        },
        dossier_medical_id=resultat["patient"].dossier_medical.id,
        etat_general=EtatGeneralResponse.model_validate(etat_general, from_attributes=True)
        if etat_general
        else None,
        antecedents=[
            AntecedentMedicalResponse.model_validate(a, from_attributes=True)
            for a in resultat["antecedents"]
        ],
        alertes=resultat["alertes"],
        nb_consultations=resultat["nb_consultations"],
        derniere_consultation=resultat["derniere_consultation"],
    )
    return APIResponse(data=reponse)


@router.patch("/{patient_id}", response_model=APIResponse[PatientResponse])
async def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Met à jour les informations administratives du dossier (UC3)."""
    ip, ua = _request_context(request)
    patient = await PatientService.modifier_patient(
        db, patient_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Dossier patient mis à jour.", data=patient)


@router.post("/{patient_id}/archiver", response_model=APIResponse[PatientResponse])
async def archive_patient(
    patient_id: uuid.UUID,
    data: PatientArchive,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Archive un dossier sans le supprimer (UC12)."""
    ip, ua = _request_context(request)
    patient = await PatientService.archiver_patient(
        db, patient_id, data.motif, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Dossier archivé.", data=patient)


@router.post("/{patient_id}/reactiver", response_model=APIResponse[PatientResponse])
async def reactivate_patient(
    patient_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Réactive un dossier archivé."""
    ip, ua = _request_context(request)
    patient = await PatientService.reactiver_patient(
        db, patient_id, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Dossier réactivé.", data=patient)


# ==============================================================================
# ÉTAT GÉNÉRAL (UC6, Étape 2 du CDC, RG02)
# ==============================================================================

@router.get("/{patient_id}/etat-general", response_model=APIResponse[Optional[EtatGeneralResponse]])
async def get_etat_general(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:READ")),
):
    """Lit l'état général du patient (allergies, grossesse, diabète, HTA)."""
    etat = await EtatGeneralService.obtenir(db, patient_id)
    return APIResponse(
        data=EtatGeneralResponse.model_validate(etat, from_attributes=True) if etat else None
    )


@router.put("/{patient_id}/etat-general", response_model=APIResponse[EtatGeneralResponse])
async def upsert_etat_general(
    patient_id: uuid.UUID,
    data: EtatGeneralCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Crée ou met à jour l'état général du patient (Étape 2 du CDC)."""
    ip, ua = _request_context(request)
    etat = await EtatGeneralService.enregistrer(db, patient_id, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(message="État général enregistré.", data=etat)


@router.patch("/{patient_id}/etat-general", response_model=APIResponse[EtatGeneralResponse])
async def patch_etat_general(
    patient_id: uuid.UUID,
    data: EtatGeneralUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Mise à jour partielle de l'état général (vérification à chaque consultation, RG02)."""
    ip, ua = _request_context(request)
    etat = await EtatGeneralService.modifier(db, patient_id, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(message="État général mis à jour.", data=etat)


# ==============================================================================
# ANTÉCÉDENTS MÉDICAUX (UC7, Étape 3 du CDC)
# ==============================================================================

@router.get("/{patient_id}/antecedents", response_model=APIResponse[List[AntecedentMedicalResponse]])
async def list_antecedents(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:READ")),
):
    """Liste les antécédents médicaux du patient (antécédents en cours d'abord)."""
    antecedents = await AntecedentService.lister(db, patient_id)
    return APIResponse(
        data=[AntecedentMedicalResponse.model_validate(a, from_attributes=True) for a in antecedents]
    )


@router.post(
    "/{patient_id}/antecedents",
    response_model=APIResponse[AntecedentMedicalResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_antecedent(
    patient_id: uuid.UUID,
    data: AntecedentMedicalCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Ajoute un antécédent médical (UC7)."""
    ip, ua = _request_context(request)
    antecedent = await AntecedentService.ajouter(
        db, patient_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Antécédent médical ajouté.", data=antecedent)


@router.patch("/antecedents/{antecedent_id}", response_model=APIResponse[AntecedentMedicalResponse])
async def update_antecedent(
    antecedent_id: uuid.UUID,
    data: AntecedentMedicalUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("PATIENTS:UPDATE")),
):
    """Met à jour un antécédent médical (clôture, précision du traitement)."""
    ip, ua = _request_context(request)
    antecedent = await AntecedentService.modifier(
        db, antecedent_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Antécédent médical mis à jour.", data=antecedent)
