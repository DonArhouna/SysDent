"""
Schémas du module Facturation & Caisse (D2C).

Règles couvertes :
  RG07 — `montant_restant` est TOUJOURS recalculé : `total - payé`. Le client
         ne fournit jamais un montant de facture, seulement des lignes.
  RG08 — un plan d'échelonnement génère ses échéances côté serveur.
  RG14 — un devis accepté se convertit en facture sans ressaisie.

La devise est le franc CFA (XOF), convention de tout le projet : aucun champ
`devise` dans les schémas, les montants sont des `Decimal` à 2 décimales.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, model_validator

from src.common.schemas import BaseSchema
from src.modules.tenants.models import (
    FrequenceEchelonnementEnum,
    ModePaiementEnum,
    StatutDevisEnum,
    StatutEcheanceEnum,
    StatutFactureEnum,
)

# Durée de validité par défaut d'un devis (CDC : un devis ne vit pas indéfiniment).
VALIDITE_DEVIS_JOURS = 30


# ==============================================================================
# FACTURE — création
# ==============================================================================

class LigneFactureEntree(BaseSchema):
    """Ligne d'une facture émise hors consultation (vente libre)."""

    designation: str = Field(..., min_length=2, max_length=255, description="Libellé affiché sur la facture")
    quantite: int = Field(1, ge=1, le=999)
    prix_unitaire: Decimal = Field(..., ge=0, description="Prix unitaire en FCFA")


class FactureLibreCreate(BaseSchema):
    """
    Émission d'une facture hors consultation (produit, forfait, prestation directe).

    Pour une facture issue d'une consultation, passer par
    `POST /factures/consultation/{consultation_id}` : les lignes y sont
    importées des actes réalisés, jamais ressaisies.
    """

    patient_id: uuid.UUID
    cabinet_id: Optional[uuid.UUID] = Field(
        None, description="Site émetteur. Optionnel si le tenant n'a qu'un cabinet actif."
    )
    praticien_id: Optional[uuid.UUID] = Field(
        None, description="Praticien d'origine du soin, si pertinent (facture de prothèse...)"
    )
    date_echeance: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)
    lignes: List[LigneFactureEntree] = Field(..., min_length=1, description="Au moins une ligne")

    @model_validator(mode="after")
    def normaliser_lignes(self) -> "FactureLibreCreate":
        for ligne in self.lignes:
            ligne.designation = ligne.designation.strip()
        return self


class FactureConsultationCreate(BaseSchema):
    """Options d'émission depuis une consultation (le total vient des actes)."""

    date_echeance: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)


# ==============================================================================
# FACTURE — lecture
# ==============================================================================

class LigneFactureResponse(BaseSchema):
    id: uuid.UUID
    acte_realise_id: Optional[uuid.UUID] = None
    designation: str
    quantite: int
    prix_unitaire: Decimal
    montant: Decimal


class PaiementResponse(BaseSchema):
    id: uuid.UUID
    facture_id: uuid.UUID
    montant: Decimal
    mode: ModePaiementEnum
    reference: Optional[str] = None
    recu_numero: str
    date_paiement: datetime
    echeance_id: Optional[uuid.UUID] = None


class EcheanceResponse(BaseSchema):
    id: uuid.UUID
    numero: int
    montant_prevu: Decimal
    montant_paye: Decimal
    date_prevue: date
    date_paiement: Optional[datetime] = None
    paiement_id: Optional[uuid.UUID] = None
    statut: StatutEcheanceEnum


class PlanEchelonnementResponse(BaseSchema):
    id: uuid.UUID
    facture_id: uuid.UUID
    montant_total: Decimal
    nombre_echeances: int
    date_debut: date
    frequence: FrequenceEchelonnementEnum
    notes: Optional[str] = None
    actif: bool
    echeances: List[EcheanceResponse] = []


class FactureResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    patient_id: uuid.UUID
    cabinet_id: uuid.UUID
    consultation_id: Optional[uuid.UUID] = None
    praticien_id: Optional[uuid.UUID] = None
    montant_total: Decimal
    montant_tva: Decimal
    montant_paye: Decimal
    montant_restant: Decimal
    statut: StatutFactureEnum
    date_emission: date
    date_echeance: Optional[date] = None
    lignes: List[LigneFactureResponse] = []
    paiements: List[PaiementResponse] = []


class PlanEchelonnementCreate(BaseSchema):
    """RG08 : les échéances sont générées par le service, jamais envoyées par le client."""

    nombre_echeances: int = Field(..., ge=2, le=36, description="Nombre de versements (2 à 36)")
    date_debut: date = Field(..., description="Date de la première échéance")
    frequence: FrequenceEchelonnementEnum = FrequenceEchelonnementEnum.MENSUEL
    notes: Optional[str] = Field(None, max_length=2000)


class PaiementCreate(BaseSchema):
    """Encaissement d'une facture. `echeance_id` cible une échéance d'un plan (RG08)."""

    montant: Decimal = Field(..., gt=0, description="Montant encaissé en FCFA")
    mode: ModePaiementEnum
    reference: Optional[str] = Field(
        None, max_length=100, description="Référence transaction (Wave, Orange Money, chèque...)"
    )
    echeance_id: Optional[uuid.UUID] = Field(
        None,
        description=(
            "Si fourni : le paiement règle l'échéance indiquée. Le montant doit "
            "correspondre exactement au reste dû sur cette échéance."
        ),
    )


# ==============================================================================
# DEVIS
# ==============================================================================

class LigneDevisEntree(BaseSchema):
    """Ligne d'un devis : acte de nomenclature ou prestation libre."""

    acte_id: Optional[uuid.UUID] = Field(
        None, description="Acte de la nomenclature (traçabilité du plan de traitement)"
    )
    designation: str = Field(..., min_length=2, max_length=255)
    dent_numero: Optional[int] = Field(None, ge=11, le=85, description="Numéro FDI si la ligne porte sur une dent")
    quantite: int = Field(1, ge=1, le=999)
    prix_unitaire: Decimal = Field(..., ge=0)


class DevisCreate(BaseSchema):
    patient_id: uuid.UUID
    praticien_id: Optional[uuid.UUID] = None
    cabinet_id: Optional[uuid.UUID] = None
    date_validite: Optional[date] = Field(
        None, description=f"Par défaut : aujourd'hui + {VALIDITE_DEVIS_JOURS} jours"
    )
    notes: Optional[str] = Field(None, max_length=2000)
    lignes: List[LigneDevisEntree] = Field(..., min_length=1)

    @model_validator(mode="after")
    def normaliser_lignes(self) -> "DevisCreate":
        for ligne in self.lignes:
            ligne.designation = ligne.designation.strip()
        return self


class DevisStatutUpdate(BaseSchema):
    """Transition du cycle de vie du devis. Voir `referentiel` du router."""

    statut: StatutDevisEnum
    signature_patient: bool = Field(
        False, description="Signature du patient, requise pour marquer un devis ACCEPTE"
    )


class LigneDevisResponse(BaseSchema):
    id: uuid.UUID
    acte_id: Optional[uuid.UUID] = None
    designation: str
    dent_numero: Optional[int] = None
    quantite: int
    prix_unitaire: Decimal
    montant: Decimal


class DevisResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    patient_id: uuid.UUID
    praticien_id: Optional[uuid.UUID] = None
    cabinet_id: Optional[uuid.UUID] = None
    montant_total: Decimal
    statut: StatutDevisEnum
    date_validite: Optional[date] = None
    signature_patient: bool
    date_signature: Optional[datetime] = None
    notes: Optional[str] = None
    facture_id: Optional[uuid.UUID] = None
    lignes: List[LigneDevisResponse] = []
