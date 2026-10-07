"""
Schémas du module Consultations & Actes (D1B).

Règles couvertes :
  RG02 — l'état général est vérifié à chaque nouvelle consultation
  RG05 (RG12 du regles.md de Analyse) — traçabilité des modifications cliniques
  RG07 — le total des actes réalisés est calculé, jamais saisi à la main

La numérotation FDI et les faces sont validées par `src/common/dentaire.py`,
référentiel partagé avec le module Odontogramme.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from pydantic import Field, field_validator, model_validator
from src.common.dentaire import valider_face, valider_numero_dent
from src.common.schemas import BaseSchema
from src.modules.tenants.models import MotifConsultationEnum, StatutConsultationEnum

_CIM10_RE = re.compile(r"^[A-Z][0-9]{2}(\.[0-9A-Z]{1,3})?$")


def valider_code_cim10(code: str) -> str:
    """Valide un code CIM-10 (ex: K02.1, K05.0, A09)."""
    code = code.strip().upper()
    if not _CIM10_RE.match(code):
        raise ValueError(f"Code CIM-10 invalide : {code}. Format attendu : lettre + 2 chiffres, ex. K02.1")
    return code


# ==============================================================================
# CONSULTATION
# ==============================================================================

class ConsultationCreate(BaseSchema):
    """Démarrage d'une consultation (Étape 4 du CDC)."""

    patient_id: uuid.UUID = Field(..., description="Patient concerné (le dossier médical est résolu côté service)")
    motif: str = Field(..., min_length=2, max_length=255, description="Motif en clair saisi par le praticien")
    type_motif: MotifConsultationEnum = Field(
        MotifConsultationEnum.AUTRE, description="Catégorie de motif (Étape 4 du CDC)"
    )
    motif_detail: Optional[str] = Field(None, description="Précision libre du motif")
    anamnese: Optional[str] = None
    cabinet_id: Optional[uuid.UUID] = Field(
        None, description="Cabinet de realization. Par défaut, l'unique cabinet du tenant."
    )
    duree_minutes: int = Field(30, ge=5, le=480, description="Durée prévue de la séance")
    date_consultation: Optional[datetime] = Field(
        None, description="Par défaut, maintenant. Permet la saisie différée (consultation d'urgence)."
    )


class ConsultationUpdate(BaseSchema):
    """Mise à jour clinique. Interdite sur une consultation terminée ou annulée."""

    motif: Optional[str] = Field(None, min_length=2, max_length=255)
    type_motif: Optional[MotifConsultationEnum] = None
    motif_detail: Optional[str] = None
    anamnese: Optional[str] = None
    examen_exobuccal: Optional[str] = None
    examen_endobuccal: Optional[str] = None
    diagnostic_principal: Optional[str] = None
    diagnostics_differentiels: Optional[List[str]] = None
    codes_cim10: Optional[List[str]] = None
    plan_traitement: Optional[str] = None
    recommandations: Optional[str] = None
    prochain_rdv_prevu: Optional[date] = None
    duree_minutes: Optional[int] = Field(None, ge=5, le=480)

    @field_validator("codes_cim10")
    @classmethod
    def valider_codes_cim10(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        codes = [valider_code_cim10(c) for c in v]
        # Déduplication en conservant l'ordre : deux diagnostics peuvent relever
        # du même code (ex. K05.0 code deux fois), la fiche reste lisible.
        return list(dict.fromkeys(codes))


class ConsultationTerminer(BaseSchema):
    """Clôture de la consultation (Étape 6 du CDC)."""

    diagnostic_principal: Optional[str] = Field(
        None, description="Obligatoire si absent de la consultation : on ne clôt pas sans diagnostic."
    )
    plan_traitement: Optional[str] = None
    recommandations: Optional[str] = None
    codes_cim10: Optional[List[str]] = None
    prochain_rdv_prevu: Optional[date] = None

    @field_validator("codes_cim10")
    @classmethod
    def valider_codes_cim10(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return list(dict.fromkeys([valider_code_cim10(c) for c in v]))


class ConsultationAnnuler(BaseSchema):
    motif_annulation: str = Field(
        ..., min_length=2, description="Motif de l'annulation (obligatoire : engage la responsabilité du cabinet)"
    )


class ActeRealiseCreate(BaseSchema):
    """Saisie d'un acte réalisé. Le tarif est résolu côté service (nomenclature + praticien)."""

    acte_id: uuid.UUID = Field(..., description="Acte de la nomenclature")
    dent_numero: Optional[int] = Field(None, description="Numéro FDI si l'acte porte sur une dent")
    face: Optional[str] = Field(None, description="MESIAL | DISTAL | VESTIBULAIRE | LINGUAL_PALATIN | OCCLUSAL_INCISAL")
    description: Optional[str] = Field(None, description="Libellé retenu pour la facture")
    quantite: int = Field(1, ge=1, le=32)
    notes: Optional[str] = None
    tarif_applique: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Forfait non prévu (accord commercial). Sinon, tarif de la nomenclature.",
    )

    @field_validator("dent_numero")
    @classmethod
    def valider_dent(cls, v: Optional[int]) -> Optional[int]:
        return valider_numero_dent(v)

    @field_validator("face")
    @classmethod
    def _valider_face(cls, v: Optional[str]) -> Optional[str]:
        return valider_face(v)

    @model_validator(mode="after")
    def coherence_dent_face(self):
        # Une face n'a de sens que sur une dent identifiée.
        if self.face and self.dent_numero is None:
            raise ValueError("Une face ne peut être précisée sans numéro de dent.")
        return self


class ActeRealiseUpdate(BaseSchema):
    dent_numero: Optional[int] = None
    face: Optional[str] = None
    description: Optional[str] = None
    quantite: Optional[int] = Field(None, ge=1, le=32)
    notes: Optional[str] = None
    tarif_applique: Optional[Decimal] = Field(None, ge=0)

    @field_validator("dent_numero")
    @classmethod
    def valider_dent(cls, v: Optional[int]) -> Optional[int]:
        return valider_numero_dent(v)

    @field_validator("face")
    @classmethod
    def _valider_face(cls, v: Optional[str]) -> Optional[str]:
        return valider_face(v)


class ActeRealiseResponse(BaseSchema):
    id: uuid.UUID
    consultation_id: uuid.UUID
    acte_id: uuid.UUID
    code_acte: str = Field(..., description="Code de la nomenclature (dénormalisé pour l'affichage)")
    libelle_acte: str
    dent_numero: Optional[int] = None
    face: Optional[str] = None
    description: Optional[str] = None
    tarif_applique: Decimal
    quantite: int
    notes: Optional[str] = None
    montant: Decimal = Field(..., description="tarif_applique × quantite (RG07 : calculé, jamais saisi)")
    created_at: datetime


class ConsultationResponse(BaseSchema):
    id: uuid.UUID
    dossier_medical_id: uuid.UUID
    patient_id: uuid.UUID
    patient_numero_dossier: Optional[str] = None
    # Compte authentifie qui a realise l'episode de soin : c'est lui la
    # tracabilite. Toujours present.
    auteur_id: uuid.UUID
    auteur_email: Optional[str] = None
    # Profil `Praticien` : attribution reglementaire FACULTATIVE. Absent
    # quand l'auteur n'est pas inscrit a l'Ordre, ce qui est legitime.
    praticien_id: Optional[uuid.UUID] = None
    cabinet_id: uuid.UUID
    motif: str
    type_motif: MotifConsultationEnum
    motif_detail: Optional[str] = None
    anamnese: Optional[str] = None
    examen_exobuccal: Optional[str] = None
    examen_endobuccal: Optional[str] = None
    diagnostic_principal: Optional[str] = None
    diagnostics_differentiels: Optional[List[str]] = None
    codes_cim10: Optional[List[str]] = None
    plan_traitement: Optional[str] = None
    recommandations: Optional[str] = None
    prochain_rdv_prevu: Optional[date] = None
    statut: StatutConsultationEnum
    date_consultation: datetime
    duree_minutes: int
    created_at: datetime
    updated_at: datetime


class ConsultationDetailResponse(ConsultationResponse):
    """Consultation avec ses actes, son total et les alertes cliniques du patient."""

    actes: List[ActeRealiseResponse] = []
    total_actes: Decimal = Decimal("0.00")
    nb_actes: int = 0
    duree_reelle_minutes: Optional[int] = None
    # RG02 : l'état général doit être vérifié à chaque consultation. On remonte
    # un rappel plutôt qu'un blocage — un praticien peut avoir une raison clinique
    # de consulter sans mise à jour de l'état général.
    etat_general_a_verifier: bool = False
    alertes: List["AlerteConsultation"] = []


class AlerteConsultation(BaseSchema):
    code: str
    niveau: str
    message: str


class RechercheConsultations(BaseSchema):
    patient_id: Optional[uuid.UUID] = None
    #: Compte authentifie qui a realise l'episode de soin.
    auteur_id: Optional[uuid.UUID] = None
    #: Profil `Praticien` : ne filtre plus que les auteurs inscrits a l'Ordre.
    praticien_id: Optional[uuid.UUID] = None
    statut: Optional[StatutConsultationEnum] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None


ConsultationDetailResponse.model_rebuild()
