"""
Routes API du module Consultations & Actes (D1B du rapport).

Toutes les routes sont authentifiées, scopées au cabinet du JWT, protégées par
permission RBAC et journalisées. Le format des permissions est "MODULE:ACTION".
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, BaseSchema, PaginatedResponse
from src.modules.audit.services import AuditService
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.consultations.schemas import (
    ActeRealiseCreate,
    ActeRealiseResponse,
    ActeRealiseUpdate,
    ConsultationAnnuler,
    ConsultationCreate,
    ConsultationDetailResponse,
    ConsultationResponse,
    ConsultationTerminer,
    ConsultationUpdate,
    RechercheConsultations,
)
from src.modules.consultations.services import (
    ActeRealiseService,
    ConsultationService,
    NomenclatureService,
)
from src.modules.tenants.models import ActeNomenclature, Consultation, Utilisateur

router = APIRouter(prefix="/consultations", tags=["Consultations & Actes"])
nomenclature_router = APIRouter(prefix="/nomenclature/actes", tags=["Nomenclature des Actes"])


def _ctx(request: Request):
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


def _vers_reponse(consultation: Consultation) -> ConsultationResponse:
    patient = consultation.dossier_medical.patient if consultation.dossier_medical else None
    return ConsultationResponse(
        id=consultation.id,
        dossier_medical_id=consultation.dossier_medical_id,
        patient_id=patient.id if patient else None,
        patient_numero_dossier=patient.numero_dossier if patient else None,
        auteur_id=consultation.auteur_id,
    auteur_email=consultation.auteur_email,
    praticien_id=consultation.praticien_id,
        cabinet_id=consultation.cabinet_id,
        motif=consultation.motif,
        type_motif=consultation.type_motif,
        motif_detail=consultation.motif_detail,
        anamnese=consultation.anamnese,
        examen_exobuccal=consultation.examen_exobuccal,
        examen_endobuccal=consultation.examen_endobuccal,
        diagnostic_principal=consultation.diagnostic_principal,
        diagnostics_differentiels=consultation.diagnostics_differentiels,
        codes_cim10=consultation.codes_cim10,
        plan_traitement=consultation.plan_traitement,
        recommandations=consultation.recommandations,
        prochain_rdv_prevu=consultation.prochain_rdv_prevu,
        statut=consultation.statut,
        date_consultation=consultation.date_consultation,
        duree_minutes=consultation.duree_minutes,
        created_at=consultation.created_at,
        updated_at=consultation.updated_at,
    )


def _acte_vers_reponse(acte, acte_nomenclature: Optional[ActeNomenclature] = None) -> ActeRealiseResponse:
    nomenclature = acte_nomenclature if acte_nomenclature is not None else getattr(acte, "acte", None)
    return ActeRealiseResponse(
        id=acte.id,
        consultation_id=acte.consultation_id,
        acte_id=acte.acte_id,
        code_acte=nomenclature.code,
        libelle_acte=nomenclature.libelle,
        dent_numero=acte.dent_numero,
        face=acte.face,
        description=acte.description,
        tarif_applique=acte.tarif_applique,
        quantite=acte.quantite,
        notes=acte.notes,
        montant=(Decimal(acte.tarif_applique) * acte.quantite).quantize(Decimal("0.01")),
        created_at=acte.created_at,
    )


# ==============================================================================
# CONSULTATIONS (UC1 Démarrer, UC3 Poser diagnostic, UC6 Réaliser des actes)
# ==============================================================================

@router.post("", response_model=APIResponse[ConsultationResponse], status_code=status.HTTP_201_CREATED)
async def demarrer_consultation(
    data: ConsultationCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:CREATE")),
):
    """Démarre une consultation pour un patient (Étape 4 du CDC)."""
    ip, ua = _ctx(request)
    consultation = await ConsultationService.demarrer(db, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(message="Consultation démarrée.", data=_vers_reponse(consultation))


@router.get("", response_model=PaginatedResponse[ConsultationResponse])
async def list_consultations(
    patient_id: Optional[uuid.UUID] = Query(None, description="Filtrer par patient"),
    praticien_id: Optional[uuid.UUID] = Query(None, description="Filtrer par profil praticien"),
    auteur_id: Optional[uuid.UUID] = Query(
        None, description="Filtrer par auteur du soin (compte authentifie)"
    ),
    statut: Optional[str] = Query(None, description="PLANIFIEE | EN_ATTENTE | EN_COURS | TERMINEE | ANNULEE"),
    date_debut: Optional[datetime] = Query(None, description="Début de la période (ISO 8601)"),
    date_fin: Optional[datetime] = Query(None, description="Fin de la période (ISO 8601)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:READ")),
):
    """Liste paginée des consultations du cabinet."""
    from src.modules.tenants.models import StatutConsultationEnum

    filtres = RechercheConsultations(
        patient_id=patient_id,
        praticien_id=praticien_id,
        auteur_id=auteur_id,
        statut=StatutConsultationEnum(statut) if statut else None,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    params = PaginationParams(page=page, limit=limit)
    consultations, total = await ConsultationService.rechercher(db, filtres, params.offset, params.limit)
    return paginate(items=[_vers_reponse(c) for c in consultations], total_records=total, params=params)


@router.get("/{consultation_id}", response_model=APIResponse[ConsultationResponse])
async def get_consultation(
    consultation_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:READ")),
):
    """Détail d'une consultation."""
    consultation = await ConsultationService._charger(db, consultation_id)
    return APIResponse(data=_vers_reponse(consultation))


@router.get("/{consultation_id}/detail", response_model=APIResponse[ConsultationDetailResponse])
async def get_consultation_detail(
    consultation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:READ")),
):
    """
    Consultation complète : actes, total facturable, durée réelle et alertes
    cliniques du patient (RG02 : l'état général est-il à jour ?).
    """
    ip, ua = _ctx(request)
    resultat = await ConsultationService.detail(db, consultation_id, current_user, client_ip=ip, user_agent=ua)
    consultation = resultat["consultation"]

    data = _vers_reponse(consultation).model_dump()
    data["actes"] = [_acte_vers_reponse(a).model_dump() for a in consultation.actes_realises]
    data["total_actes"] = resultat["total"]
    data["nb_actes"] = len(consultation.actes_realises)
    data["duree_reelle_minutes"] = resultat["duree_reelle_minutes"]
    data["etat_general_a_verifier"] = resultat["etat_general_a_verifier"]
    data["alertes"] = resultat["alertes"]

    return APIResponse(data=ConsultationDetailResponse(**data))


@router.patch("/{consultation_id}", response_model=APIResponse[ConsultationResponse])
async def update_consultation(
    consultation_id: uuid.UUID,
    data: ConsultationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:UPDATE")),
):
    """Met à jour l'examen clinique et le diagnostic (Étape 5 du CDC)."""
    ip, ua = _ctx(request)
    consultation = await ConsultationService.mettre_a_jour(
        db, consultation_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Consultation mise à jour.", data=_vers_reponse(consultation))


@router.post("/{consultation_id}/terminer", response_model=APIResponse[ConsultationDetailResponse])
async def terminer_consultation(
    consultation_id: uuid.UUID,
    data: ConsultationTerminer,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:UPDATE")),
):
    """Clôture la consultation. Un diagnostic principal est obligatoire (Étape 6)."""
    ip, ua = _ctx(request)
    await ConsultationService.terminer(db, consultation_id, data, current_user, client_ip=ip, user_agent=ua)

    resultat = await ConsultationService.detail(db, consultation_id, current_user, client_ip=ip, user_agent=ua)
    consultation = resultat["consultation"]
    reponse = _vers_reponse(consultation).model_dump()
    reponse["actes"] = [_acte_vers_reponse(a).model_dump() for a in consultation.actes_realises]
    reponse["total_actes"] = resultat["total"]
    reponse["nb_actes"] = len(consultation.actes_realises)
    reponse["duree_reelle_minutes"] = resultat["duree_reelle_minutes"]
    reponse["etat_general_a_verifier"] = resultat["etat_general_a_verifier"]
    reponse["alertes"] = resultat["alertes"]

    return APIResponse(message="Consultation terminée.", data=ConsultationDetailResponse(**reponse))


@router.post("/{consultation_id}/annuler", response_model=APIResponse[ConsultationResponse])
async def annuler_consultation(
    consultation_id: uuid.UUID,
    data: ConsultationAnnuler,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:UPDATE")),
):
    """
    Annule une consultation. Refusé si des actes ont été saisis : un acte réalisé
    est un acte physique, il se facture ou se corrige, il ne s'efface pas.
    """
    ip, ua = _ctx(request)
    consultation = await ConsultationService.annuler(
        db, consultation_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message="Consultation annulée.", data=_vers_reponse(consultation))


# ==============================================================================
# ACTES RÉALISÉS (UC6)
# ==============================================================================

@router.get("/{consultation_id}/actes", response_model=APIResponse[List[ActeRealiseResponse]])
async def list_actes(
    consultation_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:READ")),
):
    """Liste les actes réalisés sur la consultation, avec leur montant."""
    actes = await ActeRealiseService.lister(db, consultation_id)
    return APIResponse(data=[_acte_vers_reponse(a) for a in actes])


@router.get("/{consultation_id}/total", response_model=APIResponse[dict])
async def total_consultation(
    consultation_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:READ")),
):
    """
    Total facturable de la consultation (RG07).

    Point d'entrée du pôle facturation : la facture sera générée à partir de ce
    montant, jamais ressaisi par la secrétaire.
    """
    await ConsultationService._charger(db, consultation_id)
    actes = await ActeRealiseService.lister(db, consultation_id)
    total = await ActeRealiseService.total_consultation(db, consultation_id)
    return APIResponse(
        data={
            "consultation_id": consultation_id,
            "total_actes": total,
            "nb_actes": len(actes),
            "devise": "XOF",
        }
    )


@router.post(
    "/{consultation_id}/actes",
    response_model=APIResponse[ActeRealiseResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_acte(
    consultation_id: uuid.UUID,
    data: ActeRealiseCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:UPDATE")),
):
    """Saisit un acte réalisé. Le tarif est résolu depuis la nomenclature."""
    ip, ua = _ctx(request)
    acte = await ActeRealiseService.ajouter(db, consultation_id, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(message="Acte enregistré.", data=_acte_vers_reponse(acte))


@router.patch("/actes/{acte_id}", response_model=APIResponse[ActeRealiseResponse])
async def update_acte(
    acte_id: uuid.UUID,
    data: ActeRealiseUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:UPDATE")),
):
    """Corrige un acte réalisé (quantité, dent, tarif négocié)."""
    ip, ua = _ctx(request)
    acte = await ActeRealiseService.modifier(db, acte_id, data, current_user, client_ip=ip, user_agent=ua)
    return APIResponse(message="Acte mis à jour.", data=_acte_vers_reponse(acte))


@router.delete("/actes/{acte_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acte(
    acte_id: uuid.UUID,
    request: Request,
    motif: Optional[str] = Query(None, description="Motif de la suppression (conservé en audit)"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:UPDATE")),
):
    """Supprime un acte saisi par erreur. La trace d'audit est conservée."""
    ip, ua = _ctx(request)
    await ActeRealiseService.supprimer(db, acte_id, current_user, motif=motif, client_ip=ip, user_agent=ua)
    return None


# ==============================================================================
# NOMENCLATURE DES ACTES
# ==============================================================================

class ActeNomenclatureCreate(BaseSchema):
    """Création d'un acte de nomenclature (tarification du cabinet)."""

    code: str = Field(..., min_length=2, max_length=50, description="Code de l'acte (DT01, EXT01...)")
    libelle: str = Field(..., min_length=2, max_length=200)
    categorie: str = Field(..., min_length=2, max_length=100, description="SOINS, PROTHESE, CHIRURGIE, ORTHO...")
    tarif_base: Decimal = Field(..., ge=0, description="Tarif de référence en FCFA")
    duree_estimee_min: int = Field(30, ge=1, le=480)
    unitaire: bool = Field(
        False, description="Soin portant sur une dent : le numéro FDI sera alors obligatoire."
    )


@nomenclature_router.get("", response_model=PaginatedResponse[dict])
async def list_nomenclature(
    q: Optional[str] = Query(None, description="Recherche par code ou libellé"),
    categorie: Optional[str] = Query(None, description="Filtrer par catégorie"),
    inclure_inactifs: bool = Query(False, description="Inclure les actes retirés de la nomenclature"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:READ")),
):
    """Nomenclature des actes dentaires du cabinet."""
    params = PaginationParams(page=page, limit=limit)
    actes, total = await NomenclatureService.lister(
        db, q=q, categorie=categorie, inclure_inactifs=inclure_inactifs, offset=params.offset, limit=params.limit
    )
    items = [
        {
            "id": str(a.id),
            "code": a.code,
            "libelle": a.libelle,
            "categorie": a.categorie,
            "tarif_base": a.tarif_base,
            "duree_estimee_min": a.duree_estimee_min,
            "unitaire": a.unitaire,
            "actif": a.actif,
        }
        for a in actes
    ]
    return paginate(items=items, total_records=total, params=params)


@nomenclature_router.post("", response_model=APIResponse[dict], status_code=status.HTTP_201_CREATED)
async def create_acte_nomenclature(
    data: ActeNomenclatureCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("CONSULTATIONS:CREATE")),
):
    """Ajoute un acte à la nomenclature du cabinet (tarifs selon acte et praticien)."""
    ip, ua = _ctx(request)
    acte = await NomenclatureService.creer(
        db,
        code=data.code,
        libelle=data.libelle,
        categorie=data.categorie,
        tarif_base=data.tarif_base,
        duree_estimee_min=data.duree_estimee_min,
        unitaire=data.unitaire,
        auteur=current_user,
    )
    return APIResponse(
        message="Acte ajouté à la nomenclature.",
        data={
            "id": str(acte.id),
            "code": acte.code,
            "libelle": acte.libelle,
            "categorie": acte.categorie,
            "tarif_base": acte.tarif_base,
            "duree_estimee_min": acte.duree_estimee_min,
            "unitaire": acte.unitaire,
            "actif": acte.actif,
        },
    )
