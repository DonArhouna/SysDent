"""
Schémas du module Odontogramme (D1C).

Règles couvertes :
  RG10 — chaque modification de dent est horodatée avec le praticien et la consultation
  RG11 — un odontogramme adulte comprend 32 dents, un enfant 20 dents
  RG12 — traçabilité médico-légale des modifications de l'état dentaire

La validation FDI et des faces vient de `src/common/dentaire.py`, référentiel
partagé avec le module Consultations.
"""

from datetime import date, datetime
from typing import List, Optional
import uuid
from pydantic import Field, computed_field, field_validator
from src.common.dentaire import (
    DENTS_LAIT_ENFANT,
    DENTS_PERMANENTES_ADULTE,
    ETAT_SAINE,
    ETATS_DENT,
    FACES_COURTES,
    FACES_DENT,
    PROFONDEUR_SONDAGE_MAX,
    PROFONDEUR_SONDAGE_MIN,
    SITES_SONDAGE,
    valider_etat_dent,
    valider_face,
    valider_numero_dent,
    valider_site_sondage,
)
from src.common.schemas import BaseSchema

TYPE_ADULTE = "ADULTE"
TYPE_ENFANT = "ENFANT"
TYPE_MIXTE = "MIXTE"

TYPES_ODONTOGRAMME = (TYPE_ADULTE, TYPE_ENFANT, TYPE_MIXTE)


# ==============================================================================
# CONSULTATION DE L'ODONTOGRAMME
# ==============================================================================

class DentResponse(BaseSchema):
    """État courant d'une dent, prêt pour le rendu du composant SVG."""

    id: uuid.UUID
    numero_fdi: int
    numero_universal: Optional[int] = None
    etat_actuel: str
    etat_libelle: Optional[str] = None
    mobilite: int = 0
    notes: Optional[str] = None
    faces: List["FaceDentResponse"] = []
    a_alerte: bool = False


class FaceDentResponse(BaseSchema):
    face: str
    face_courte: str
    etat: str
    notes: Optional[str] = None


class OdontogrammeResponse(BaseSchema):
    id: uuid.UUID
    patient_id: uuid.UUID
    dossier_medical_id: uuid.UUID
    type: str
    systeme_notation: str
    nb_dents: int
    dents: List[DentResponse]
    # Synthèse : ce qu'un praticien doit voir sans parcourir les 32 dents.
    nb_dents_soignees: int = 0
    nb_dents_a_traiter: int = 0
    nb_dents_absentes: int = 0
    resume: str = ""


class OdontogrammeCreer(BaseSchema):
    """
    Génération explicite d'un odontogramme.

    Par défaut l'odontogramme est créé automatiquement à la première lecture :
    cette route sert aux cas de reprise (patient créé avant D1C) et au choix
    explicite du nombre de dents (RG11).
    """

    type: str = Field(TYPE_ADULTE, description="ADULTE (32 dents), ENFANT (20 dents) ou MIXTE")
    systeme_notation: str = Field("FDI", description="FDI (par défaut) ou UNIVERSAL")

    @field_validator("type")
    @classmethod
    def valider_type(cls, v: str) -> str:
        normalise = v.strip().upper()
        if normalise not in TYPES_ODONTOGRAMME:
            raise ValueError(f"Type d'odontogramme invalide : {v}. Attendu : {', '.join(TYPES_ODONTOGRAMME)}.")
        return normalise

    @field_validator("systeme_notation")
    @classmethod
    def valider_notation(cls, v: str) -> str:
        normalise = v.strip().upper()
        if normalise not in ("FDI", "UNIVERSAL"):
            raise ValueError("Notation invalide : attendu FDI ou UNIVERSAL.")
        return normalise


# ==============================================================================
# MISE À JOUR D'UNE DENT (RG10)
# ==============================================================================

class DentMiseAJour(BaseSchema):
    """
    Changement d'état d'une dent, identifiée par son numéro FDI.

    Utilisé pour la mise à jour unitaire comme pour le lot : un seul schéma
    évite que les deux chemins n'appliquent des règles différentes.

    Le nouvel état est obligatoire : c'est lui qui sera historisé (RG10).
    Répéter l'état courant n'est pas une erreur — un constat se confirme — mais
    l'historique conserve la ligne, avec un état antérieur identique.
    """

    numero_fdi: int = Field(..., description="Numéro FDI de la dent (11-48 définitives, 51-85 lait)")
    etat: str = Field(..., description=f"État de la dent. Valeurs : {len(ETATS_DENT)} (dictionnaire §5.1)")
    face: Optional[str] = Field(None, description="Face concernée, si la lésion est localisée")
    consultation_id: Optional[uuid.UUID] = Field(
        None, description="Consultation à l'origine du constat (traçabilité RG10)"
    )
    praticien_id: Optional[uuid.UUID] = Field(
        None, description="Praticien auteur. Par défaut, le praticien de l'utilisateur connecté."
    )
    mobilite: Optional[int] = Field(None, ge=0, le=3)
    notes: Optional[str] = None
    date_constat: Optional[datetime] = Field(
        None, description="Par défaut, maintenant. Permet de rectifier un constat daté."
    )

    @field_validator("numero_fdi")
    @classmethod
    def valider_fdi(cls, v: int) -> int:
        return valider_numero_dent(v)

    @field_validator("etat")
    @classmethod
    def valider_etat(cls, v: str) -> str:
        return valider_etat_dent(v)

    @field_validator("face")
    @classmethod
    def valider_face(cls, v: Optional[str]) -> Optional[str]:
        return valider_face(v)


class DentsMiseAJourLot(BaseSchema):
    """
    Mise à jour de plusieurs dents en une seule requête.

    Utile au cabinet : un rendez-vous de détartrage touche souvent six dents
    d'un coup. Sans ce point d'entrée, il faudrait six requêtes et six
    écritures d'historique quasi identiques.
    """

    dents: List[DentMiseAJour] = Field(..., min_length=1, max_length=32)
    consultation_id: Optional[uuid.UUID] = Field(
        None, description="Consultation commune à toutes les dents du lot"
    )
    praticien_id: Optional[uuid.UUID] = Field(
        None, description="Praticien commun à toutes les dents du lot"
    )

    @field_validator("dents")
    @classmethod
    def verifier_dents(cls, v: List[DentMiseAJour]) -> List[DentMiseAJour]:
        fdis = [d.numero_fdi for d in v]
        doublons = sorted({n for n in fdis if fdis.count(n) > 1})
        if doublons:
            raise ValueError(
                f"Dents en double dans la même requête : {doublons}. "
                "Regrouper les modifications d'une même dent."
            )
        return v


# ==============================================================================
# FACES
# ==============================================================================

class FaceMiseAJour(BaseSchema):
    face: str
    etat: str = Field(..., description=f"État de la face. Valeurs : {len(ETATS_DENT)}")
    notes: Optional[str] = None

    @field_validator("face")
    @classmethod
    def valider_face(cls, v: str) -> str:
        return valider_face(v)

    @field_validator("etat")
    @classmethod
    def valider_etat(cls, v: str) -> str:
        return valider_etat_dent(v)


class FacesMiseAJour(BaseSchema):
    """Mise à jour des faces d'une dent en une requête."""

    faces: List[FaceMiseAJour] = Field(..., min_length=1, max_length=5)

    @field_validator("faces")
    @classmethod
    def verifier_faces(cls, v: List[FaceMiseAJour]) -> List[FaceMiseAJour]:
        noms = [f.face for f in v]
        doublons = {n for n in noms if noms.count(n) > 1}
        if doublons:
            raise ValueError(f"Faces en double : {sorted(doublons)}")
        return v


# ==============================================================================
# HISTORIQUE (RG10)
# ==============================================================================

class EtatHistoriqueResponse(BaseSchema):
    id: uuid.UUID
    dent_id: uuid.UUID
    date_constat: datetime
    etat: str
    etat_precedent: Optional[str] = None
    face: Optional[str] = None
    consultation_id: Optional[uuid.UUID] = None
    praticien_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class HistoriqueDentResponse(BaseSchema):
    dent: DentResponse
    historique: List[EtatHistoriqueResponse]


# ==============================================================================
# CHARTING PARODONTAL
# ==============================================================================

class SiteSondage(BaseSchema):
    """Mesure en un point du sondage parodontal (6 points par dent)."""

    site: str = Field(..., description=f"Site : {' | '.join(SITES_SONDAGE)}")
    profondeur: int = Field(
        ...,
        ge=PROFONDEUR_SONDAGE_MIN,
        le=PROFONDEUR_SONDAGE_MAX,
        description="Profondeur en millimètres",
    )

    @field_validator("site")
    @classmethod
    def valider_site(cls, v: str) -> str:
        return valider_site_sondage(v)


class ChartingParodontalCreate(BaseSchema):
    """Relevé parodental d'une dent (Étape 6 du CDC)."""

    dent_id: uuid.UUID
    consultation_id: Optional[uuid.UUID] = None
    sondages: Optional[List[SiteSondage]] = Field(
        None, description="Sondage en 6 points. Omettre un site = non mesuré."
    )
    nac: Optional[int] = Field(None, ge=0, le=3, description="Niveau d'attachement clinique")
    recession: Optional[int] = Field(None, ge=0, le=15, description="Récession gingivale en mm")
    saignement_bop: bool = Field(False, description="Saignement au sondage")
    suppuration: bool = Field(False, description="Suppuration")
    mobilite: Optional[int] = Field(None, ge=0, le=3)
    furcation: Optional[int] = Field(None, ge=0, le=3, description="Furcation 0 à 3")
    plaque_ipv: bool = Field(False, description="Plaque visible / présence de plaque")
    notes: Optional[str] = None

    @field_validator("sondages")
    @classmethod
    def verifier_sites(cls, v: Optional[List[SiteSondage]]) -> Optional[List[SiteSondage]]:
        if v is None:
            return None
        sites = [s.site for s in v]
        doublons = {s for s in sites if sites.count(s) > 1}
        if doublons:
            raise ValueError(f"Sites de sondage en double : {sorted(doublons)}")
        manquants = set(SITES_SONDAGE) - set(sites)
        if manquants:
            raise ValueError(
                f"Sondage incomplet : il manque {sorted(manquants)}. "
                "Les 6 points sont attendus, ou le champ doit être omis entièrement."
            )
        return v


class ChartingParodontalResponse(BaseSchema):
    id: uuid.UUID
    dent_id: uuid.UUID
    consultation_id: Optional[uuid.UUID] = None
    date_examen: datetime
    sondages: Optional[List[dict]] = None
    nac: Optional[int] = None
    recession: Optional[int] = None
    saignement_bop: bool
    suppuration: bool
    mobilite: Optional[int] = None
    furcation: Optional[int] = None
    plaque_ipv: bool
    notes: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def profondeur_moyenne(self) -> Optional[float]:
        """Profondeur moyenne de sondage : indicateur de suivi parodontal."""
        if not self.sondages:
            return None
        valeurs = [s.get("profondeur") for s in self.sondages if s.get("profondeur") is not None]
        if not valeurs:
            return None
        return round(sum(valeurs) / len(valeurs), 2)


DentResponse.model_rebuild()
