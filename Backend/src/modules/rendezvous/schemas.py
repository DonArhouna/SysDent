"""
Schémas du module Rendez-vous (D2B).

Règles couvertes :
  RG09 — chaque rendez-vous est rattaché à un patient, un praticien et un site
         identifiés, et à un créneau qui ne peut être Reserved qu'une fois

Le contrat le plus important pour le frontend est `ConflitRendezVousResponse` :
l'API ne répond pas seulement « conflit », elle dit **avec qui** le créneau est
occupé. Un secrétariat qui reçoit « 09:00 est pris » ne peut rien faire d'utile ;
celui qui reçoit « Mme Diop, détartrage, 09:00-09:30 » sait qu'il faut proposer
09:30.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import Field, field_validator, model_validator
from src.common.rendezvous import (
    DUREE_MAX_MINUTES,
    DUREE_MIN_MINUTES,
    DUREE_MINUTES_POSSIBLES,
    DUREE_PAR_DEFAUT_MINUTES,
    MOTIFS_BLOCAGE,
    STATUTS,
    borne_horaire,
)
from src.common.schemas import BaseSchema


# ==============================================================================
# CRÉNEAU
# ==============================================================================

class Creneau(BaseSchema):
    """
    Un intervalle horaire.

    `debut` et `fin` sont deux instants complets, pas une heure du jour : un
    cabinet multi-site ou un praticien en vacation doit pouvoir reasonner sur la
    date ET l'heure sans arbiter entre « lundi 09:00 » et « 09:00 de lundi ».
    """

    debut: datetime
    fin: datetime

    @model_validator(mode="after")
    def verifier_ordre(self):
        if self.fin <= self.debut:
            raise ValueError(
                f"La fin du créneau ({self.fin.isoformat()}) doit être postérieure à "
                f"son début ({self.debut.isoformat()})."
            )
        duree = int((self.fin - self.debut).total_seconds() // 60)
        if duree < DUREE_MIN_MINUTES:
            raise ValueError(
                f"Un rendez-vous dure au moins {DUREE_MIN_MINUTES} minutes "
                f"(reçu {duree})."
            )
        if duree > DUREE_MAX_MINUTES:
            raise ValueError(
                f"Un rendez-vous ne dure pas plus de "
                f"{DUREE_MAX_MINUTES // 60} h (reçu {duree // 60} h). "
                "Au-delà, il faut plusieurs rendez-vous."
            )
        return self

    @property
    def duree_minutes(self) -> int:
        return int((self.fin - self.debut).total_seconds() // 60)


# ==============================================================================
# RENDEZ-VOUS
# ==============================================================================

class RendezVousCreate(BaseSchema):
    """
    Prise de rendez-vous (UC9 « Prendre rendez-vous »).

    Le praticien est désigné par identifiant, jamais « le premier trouvé » :
    un cabinet multi-praticien doit savoir de qui il s'agit.
    """

    patient_id: uuid.UUID
    praticien_id: uuid.UUID
    debut: datetime
    duree_minutes: int = Field(
        DUREE_PAR_DEFAUT_MINUTES,
        ge=DUREE_MIN_MINUTES,
        le=DUREE_MAX_MINUTES,
        description=f"Valeurs usuelles : {DUREE_MINUTES_POSSIBLES}. Toute durée ≥ {DUREE_MIN_MINUTES} est acceptée.",
    )
    motif: str = Field(..., min_length=2, max_length=255)
    type_motif: str = Field("AUTRE", max_length=20)
    cabinet_id: Optional[uuid.UUID] = Field(
        None,
        description="Site concerné. Absent = le site de rattachement du praticien.",
    )
    fauteuil_id: Optional[uuid.UUID] = Field(
        None,
        description="Fauteuil réservé. Absent = rendez-vous sans fauteuil (visite d'évaluation, urgences).",
    )
    statut: str = Field("PLANIFIE", description="Permet de créer directement en CONFIRME.")
    notes: Optional[str] = None

    @field_validator("statut")
    @classmethod
    def verifier_statut(cls, v: str) -> str:
        normalise = v.strip().upper()
        if normalise not in STATUTS:
            raise ValueError(f"Statut inconnu : {v!r}. Attendu parmi {STATUTS}.")
        # On ne crée pas un rendez-vous « terminé » ou « annulé » : c'est un
        # résultat, jamais une intention de saisie.
        if normalise in ("TERMINEE", "ANNULE", "ABSENT", "EN_CONSULTATION"):
            raise ValueError(
                f"Un rendez-vous ne se crée pas au statut {normalise}. "
                "Créez-le planifié ou confirmé, puis faites évoluer son statut."
            )
        return normalise

    @model_validator(mode="after")
    def verifier_creneau(self):
        from datetime import timedelta

        creneau = Creneau(debut=self.debut, fin=self.debut + timedelta(minutes=self.duree_minutes))
        hors_bornes = borne_horaire(creneau.debut, creneau.fin)
        if hors_bornes:
            raise ValueError(hors_bornes)
        return self

    @property
    def fin(self) -> datetime:
        from datetime import timedelta

        return self.debut + timedelta(minutes=self.duree_minutes)


class RendezVousUpdate(BaseSchema):
    """Modifications permises tant que le rendez-vous n'a pas commencé."""

    motif: Optional[str] = Field(None, min_length=2, max_length=255)
    type_motif: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    fauteuil_id: Optional[uuid.UUID] = None
    motif_annulation: Optional[str] = Field(None, max_length=255)


class ChangementStatut(BaseSchema):
    """Mouvement dans le cycle de vie d'un rendez-vous."""

    statut: str
    motif: Optional[str] = Field(
        None,
        max_length=255,
        description="Obligatoire en pratique pour ANNULE (raison de l'annulation).",
    )

    @field_validator("statut")
    @classmethod
    def normaliser(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def verifier_transition_possible(self):
        # La vérification complète a besoin du statut courant, connu du service.
        # On se limite ici aux statuts terminaux, qui exigent un motif.
        if self.statut == "ANNULE" and not (self.motif or "").strip():
            raise ValueError(
                "Indiquez la raison de l'annulation : un rendez-vous annulé sans "
                "motif est inexploitable six mois plus tard."
            )
        return self


class Planifier(BaseSchema):
    """
    Report d'un rendez-vous à un autre créneau.

    Plutôt qu'un `PATCH` de `debut` : un report déplace aussi le fauteuil et
    libère l'ancien créneau, c'est une opération atomique à part entière.
    """

    debut: datetime
    duree_minutes: int = Field(
        DUREE_PAR_DEFAUT_MINUTES, ge=DUREE_MIN_MINUTES, le=DUREE_MAX_MINUTES
    )
    fauteuil_id: Optional[uuid.UUID] = None
    motif_report: Optional[str] = Field(
        None, max_length=255, description="Motif du report, conservé au dossier."
    )


# ==============================================================================
# BLOCAGE DE FAUTEUIL
# ==============================================================================

class BlocageFauteuilCreate(BaseSchema):
    """
    Immobilise un fauteuil sur une plage, sans rendez-vous.

    Le cas réel : un fauteuil au compresseur en panne. Il ne peut plus être
    proposé, et cela doit se voir dans l'agenda comme n'importe quel autre
    rendez-vous — c'est pourquoi l'occupation tient dans la MÊME table.
    """

    fauteuil_id: uuid.UUID
    debut: datetime
    duree_minutes: int = Field(60, ge=5, le=1440)
    motif: str = Field(..., description=f"Un de {MOTIFS_BLOCAGE}")
    motif_detail: Optional[str] = Field(None, max_length=255)

    @field_validator("motif")
    @classmethod
    def verifier_motif(cls, v: str) -> str:
        normalise = v.strip().upper()
        if normalise not in MOTIFS_BLOCAGE:
            raise ValueError(f"Motif inconnu : {v!r}. Attendu parmi {MOTIFS_BLOCAGE}.")
        if normalise == "RENDEZ_VOUS":
            raise ValueError(
                "« RENDEZ_VOUS » est posé automatiquement par le module. "
                "Déclarez une maintenance, une réparation ou une réservation interne."
            )
        return normalise

    @model_validator(mode="after")
    def verifier_creneau(self):
        from datetime import timedelta

        creneau = Creneau(debut=self.debut, fin=self.debut + timedelta(minutes=self.duree_minutes))
        hors_bornes = borne_horaire(creneau.debut, creneau.fin)
        if hors_bornes:
            raise ValueError(hors_bornes)
        return self


# ==============================================================================
# RÉPONSES
# ==============================================================================

class ConflitRendezVous(BaseSchema):
    """
    Description d'un créneau déjà occupé.

    Contenu pour que le secrétariat puisse agir : qui, quoi, sur quelle
    ressource, et depuis quand. Un simple « conflit » est inexploitable.
    """

    ressource: str = Field(..., description="PRATICIEN ou FAUTEUIL")
    motif: Optional[str] = Field(None, description="Motif du rendez-vous concurrent")
    patient_nom: Optional[str] = None
    patient_prenom: Optional[str] = None
    numero_dossier: Optional[str] = None
    debut: datetime
    fin: datetime
    statut: Optional[str] = None
    #: Le niveau de détail est adapté à la demande : au minimum `debut`/`fin`.
    id: Optional[uuid.UUID] = None


class RendezVousResponse(BaseSchema):
    id: uuid.UUID
    patient_id: uuid.UUID
    cabinet_id: uuid.UUID
    praticien_id: uuid.UUID
    debut: datetime
    fin: datetime
    duree_minutes: int
    motif: str
    type_motif: str
    statut: str
    statut_libelle: str
    notes: Optional[str] = None
    motif_annulation: Optional[str] = None
    date_statut: datetime

    fauteuil_id: Optional[uuid.UUID] = None
    consultation_id: Optional[uuid.UUID] = None

    # Identité pré-jointe : un agenda se lit, il ne résout pas N+1 requêtes.
    patient_nom: Optional[str] = None
    patient_prenom: Optional[str] = None
    numero_dossier: Optional[str] = None
    patient_telephone: Optional[str] = None
    praticien_nom: Optional[str] = None
    praticien_titre: Optional[str] = None
    cabinet_nom: Optional[str] = None
    fauteuil_numero: Optional[str] = None

    #: Renseigné quand le créneau est hors des disponibilités déclarées.
    hors_disponibilites: bool = False
    #: Les prochaines transitions autorisées, pour n'afficher que celles-là.
    transitions_possibles: List[str] = []


class CreneauLibre(BaseSchema):
    debut: datetime
    fin: datetime


class AgendaResponse(BaseSchema):
    """
    Journée d'agenda, prête à afficher.

    Renvoie les rendez-vous ET les indisponibilités de fauteuil dans la même
    liste : un écran de planning qui n'affiche pas un fauteuil en réparation
    propose un créneau qu'on ne pourra pas honorer.
    """

    date: datetime
    cabinet_id: Optional[uuid.UUID] = None
    rendez_vous: List[RendezVousResponse] = []
    indisponibilites: List[Dict[str, Any]] = []
    nb_rendez_vous: int = 0
    nb_annules: int = 0


class StatutRendezVousResponse(BaseSchema):
    """Rappel du cycle de vie, pour l'UI (évite de le redéfinir côté client)."""

    statuts: List[Dict[str, Any]]
    transitions: Dict[str, List[str]]
    motifs_blocage: List[Dict[str, Any]]
    duree_par_defaut_minutes: int
    durees_possibles: List[int]
