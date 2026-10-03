"""
Schémas du module Ordonnances (D1D).

Règles couvertes :
  RG07 — les allergies déclenchent des alertes automatiques
  RG08 — les contre-indications bloquent certains médicaments

Le contrôle est fait côté service : le schéma valide la forme des règles, pas
leur applicabilité au patient. Ce qui est « interdit » dépend de l'état
clinique, que seul le service connaît.
"""

from datetime import date, datetime
from typing import List, Optional
import uuid
from pydantic import Field, field_validator, model_validator
from src.common.ordonnance import GRAVITES, INTERDIT
from src.common.schemas import BaseSchema


class RegleContreIndication(BaseSchema):
    """Règle déclarée sur un médicament du référentiel."""

    condition: str = Field(
        ...,
        min_length=2,
        max_length=60,
        description="Condition clinique code (GROSSESSE, ALLERGIE_PENICILLINE...)",
    )
    gravite: str = Field(INTERDIT, description="INTERDIT (bloque) ou PRECAUTION (justification requise)")
    message: str = Field(..., min_length=5, description="Message destiné au praticien")

    @field_validator("condition")
    @classmethod
    def normaliser_condition(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("gravite")
    @classmethod
    def verifier_gravite(cls, v: str) -> str:
        normalise = v.strip().upper()
        if normalise not in GRAVITES:
            raise ValueError(f"gravite doit être l'un de {GRAVITES}.")
        return normalise


class MedicamentCreate(BaseSchema):
    """Ajout d'un médicament au référentiel du cabinet."""

    nom_commercial: str = Field(..., min_length=2, max_length=150)
    dci: str = Field(..., min_length=2, max_length=150, description="Dénomination commune internationale")
    forme: str = Field("COMPRIME", min_length=2, max_length=50)
    dosage: Optional[str] = Field(None, max_length=50)
    classe_therapeutique: Optional[str] = Field(None, max_length=50)
    posologie_adulte: Optional[str] = Field(None, max_length=255)
    precautions: Optional[str] = None
    contre_indications: List[RegleContreIndication] = []


class MedicamentResponse(BaseSchema):
    id: uuid.UUID
    nom_commercial: str
    dci: str
    forme: str
    dosage: Optional[str] = None
    classe_therapeutique: Optional[str] = None
    posologie_adulte: Optional[str] = None
    precautions: Optional[str] = None
    contre_indications: Optional[List[dict]] = None
    actif: bool


class LignePrescriptionCreate(BaseSchema):
    """
    Ligne d'ordonnance.

    `medicament_id` ou `medicament_texte` : au moins l'un des deux. Un produit
    hors référentiel reste saisissable (produit local, préparation), mais alors
    aucune contre-indication automatique ne peut être évaluée — le service le
    signale explicitement.
    """

    medicament_id: Optional[uuid.UUID] = Field(None, description="Médicament du référentiel")
    medicament_texte: Optional[str] = Field(
        None, max_length=255, description="Libellé libre si le produit n'est pas au référentiel"
    )
    posologie: str = Field("1 comprimé matin et soir", min_length=2, max_length=255)
    duree: Optional[str] = Field(None, max_length=100, description="Ex: 7 jours")
    instructions: Optional[str] = None
    quantite: int = Field(1, ge=1, le=100)
    justification_precaution: Optional[str] = Field(
        None,
        description="Obligatoire si le médicament déclenche une simple précaution (RG08).",
    )

    @model_validator(mode="after")
    def verifier_medicament(self):
        if self.medicament_id is None and not (self.medicament_texte or "").strip():
            raise ValueError(
                "Indiquez `medicament_id` (référentiel) ou `medicament_texte` "
                "(produit hors référentiel)."
            )
        return self


class ControleContreIndication(LignePrescriptionCreate):
    """
    Corps du contrôle à blanc : une ligne d'ordonnance, plus le patient visé.

    `patient_id` est ici et non en query string parce qu'un contrôle à blanc
    EST une proposition d'ordonnance : tout ce qui la décrit doit tenir dans le
    même corps, sinon le frontend risque de contrôler pour un patient et
    prescrire pour un autre.
    """

    patient_id: uuid.UUID


class OrdonnanceCreate(BaseSchema):
    """Émission d'une ordonnance (UC7 « Rédiger ordonnance »)."""

    patient_id: uuid.UUID
    consultation_id: uuid.UUID
    lignes: List[LignePrescriptionCreate] = Field(..., min_length=1, max_length=20)
    notes_generales: Optional[str] = Field(
        None, description="Consignes générales (ex: inicioure un bain de bouche chlorhexidine)"
    )

    @field_validator("lignes")
    @classmethod
    def verifier_doublons(cls, v: List[LignePrescriptionCreate]) -> List[LignePrescriptionCreate]:
        ids = [l.medicament_id for l in v if l.medicament_id is not None]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError(
                f"Médicament présent plusieurs fois dans la même ordonnance : {doublons}. "
                "Regrouvez en une seule ligne avec la quantité ou la durée voulue."
            )
        return v


class OrdonnanceUpdate(BaseSchema):
    """Modification d'une ordonnance NON signée."""

    notes_generales: Optional[str] = None


class AlertePrescription(BaseSchema):
    """Alerte de contre-indication ou d'interaction."""

    code: str
    gravite: str = Field(..., description="INTERDIT ou PRECAUTION")
    message: str
    condition: str = Field("", description="Condition clinique en cause, vide si interaction")


class LignePrescriptionResponse(BaseSchema):
    id: uuid.UUID
    medicament_id: Optional[uuid.UUID] = None
    medicament_texte: Optional[str] = None
    nom_commercial: Optional[str] = None
    dci: Optional[str] = None
    posologie: str
    duree: Optional[str] = None
    instructions: Optional[str] = None
    quantite: int
    justification_precaution: Optional[str] = None


class OrdonnanceResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    consultation_id: uuid.UUID
    patient_id: uuid.UUID
    praticien_id: uuid.UUID
    date_ordonnance: datetime
    notes_generales: Optional[str] = None
    signe: bool
    date_signature: Optional[datetime] = None
    lignes: List[LignePrescriptionResponse] = []
    alertes: List[AlertePrescription] = []
    nb_lignes: int = 0


class ControleContreIndicationResponse(BaseSchema):
    """Résultat du contrôle à blanc (UC8)."""

    prescription_possible: bool
    justification_requise: bool
    alertes: List[AlertePrescription] = []
    conditions_actives: List[dict] = Field(
        default_factory=list,
        description="État clinique du patient ayant déclenché ces règles",
    )
