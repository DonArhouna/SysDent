"""
Schémas du module Cabinets & Ressources (D2A).

Règles couvertes implicitement par la structure des données :
  RG09 — chaque acte et chaque rendez-vous est rattaché à un cabinet et à un
         praticien identifiés (traçabilité médico-légale)

Deux notions distinctes que le frontend ne doit pas confondre :
  - `horaires_ouverture` du cabinet : quand le **bâtiment** est ouvert ;
  - `Disponibilite` d'un praticien : quand **ce praticien** travaille.
"""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
import uuid
from pydantic import Field, field_validator, model_validator
from src.common.disponibilite import (
    CONSULTATION,
    JOURS_COURTS,
    TYPES_PLAGE,
    PlageInvalide,
    minutes_de,
    valider_plage,
)
from src.common.schemas import BaseSchema


# ==============================================================================
# CABINET
# ==============================================================================

class HorairesCabinet(BaseSchema):
    """
    Horaires d'ouverture d'un site, par jour de semaine.

    Un jour non déclaré est fermé : c'est le cas par défaut d'un cabinet neuf,
    qui doit ouvrir explicitement ses horaires plutôt que d'en hériter d'une
    valeur implicite. Un frontend peut rendre ce formulaire directement.
    """

    #: Clés attendues : "0"…"6" (lundi → dimanche). Les jours absents sont fermés.
    jours: Dict[str, List[List[str]]] = Field(
        default_factory=dict,
        description='Ex: {"0": [["08:00","12:00"],["14:00","18:00"]], "6": []}',
    )

    @field_validator("jours")
    @classmethod
    def valider_cles(cls, v: Dict[str, List[List[str]]]) -> Dict[str, List[List[str]]]:
        for cle, plages in v.items():
            if cle not in {str(i) for i in range(7)}:
                raise ValueError(
                    f"Clé de jour invalide : {cle!r}. Attendu : \"0\" (lundi) à \"6\" (dimanche)."
                )
            for plage in plages:
                if len(plage) != 2:
                    raise ValueError(f"Plage malformedée : {plage!r}. Attendu [\"HH:MM\", \"HH:MM\"].")
        return v


class CabinetUpdate(BaseSchema):
    """Modification d'un site. Tous les champs sont facultatifs."""

    nom: Optional[str] = Field(None, min_length=2, max_length=150)
    adresse: Optional[str] = None
    ville: Optional[str] = Field(None, max_length=100)
    telephone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=150)
    logo_url: Optional[str] = Field(None, max_length=500)
    horaires_ouverture: Optional[Dict[str, Any]] = None
    actif: Optional[bool] = None


class CabinetResume(BaseSchema):
    """Vue compacte pour les listes et les sélecteurs."""

    id: uuid.UUID
    nom: str
    ville: Optional[str] = None
    actif: bool


class CabinetResponse(BaseSchema):
    id: uuid.UUID
    nom: str
    adresse: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    horaires_ouverture: Optional[Dict[str, Any]] = None
    actif: bool
    created_at: datetime

    nb_salles: int = 0
    nb_fauteuils_actifs: int = 0
    nb_praticiens_actifs: int = 0


# ==============================================================================
# SALLE
# ==============================================================================

class SalleCreate(BaseSchema):
    nom: str = Field(..., min_length=1, max_length=100, description="Ex: Salle 1, Bloc opératoire")
    etage: Optional[str] = Field(None, max_length=50)

    @field_validator("nom", "etage")
    @classmethod
    def normaliser(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class SalleUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    etage: Optional[str] = Field(None, max_length=50)


class SalleResponse(BaseSchema):
    id: uuid.UUID
    cabinet_id: uuid.UUID
    nom: str
    etage: Optional[str] = None
    nb_fauteuils: int = 0
    nb_fauteuils_actifs: int = 0


# ==============================================================================
# FAUTEUIL
# ==============================================================================

class FauteuilCreate(BaseSchema):
    numero: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Libellé interne : F1, Fauteuil 3, Unit Nord…",
    )
    equipements: Optional[List[str]] = Field(
        None,
        max_length=30,
        description="Ex: [\"radiologie\", \"micromoteur\", \"compresseur\"]",
    )

    @field_validator("numero")
    @classmethod
    def normaliser(cls, v: str) -> str:
        return v.strip()


class FauteuilUpdate(BaseSchema):
    numero: Optional[str] = Field(None, min_length=1, max_length=50)
    equipements: Optional[List[str]] = Field(None, max_length=30)
    actif: Optional[bool] = None


class FauteuilResponse(BaseSchema):
    id: uuid.UUID
    salle_id: uuid.UUID
    numero: str
    equipements: Optional[List[str]] = None
    actif: bool
    nom_salle: Optional[str] = None
    cabinet_id: Optional[uuid.UUID] = None
    cabinet_nom: Optional[str] = None


# ==============================================================================
# PRATICIEN
# ==============================================================================

class PraticienCreate(BaseSchema):
    """
    Rattachement d'un compte utilisateur au métier de praticien.

    Le compte doit exister au préalable : un praticien est toujours un
    utilisateur authentifié, jamais une identité sans accès. C'est ce qui rend
    l'attribution d'une ordonnance ou d'une consultation traçable jusqu'à une
    personne physique.
    """

    utilisateur_id: uuid.UUID
    titre: str = Field("Dr", max_length=50)
    specialite: str = Field("Chirurgien-Dentiste", max_length=100)
    numero_ordre: Optional[str] = Field(
        None,
        max_length=50,
        description="Numéro d'inscription à l'ordre professionnel.",
    )
    signature_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = None
    cabinet_id: Optional[uuid.UUID] = Field(
        None, description="Site de rattachement initial. Facultatif."
    )


class PraticienUpdate(BaseSchema):
    titre: Optional[str] = Field(None, max_length=50)
    specialite: Optional[str] = Field(None, max_length=100)
    numero_ordre: Optional[str] = Field(None, max_length=50)
    signature_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = None


class PraticienResponse(BaseSchema):
    id: uuid.UUID
    utilisateur_id: uuid.UUID
    titre: str
    specialite: str
    numero_ordre: Optional[str] = None
    signature_url: Optional[str] = None
    bio: Optional[str] = None

    # Identité du compte porteur, pour l'affichage dans les listes.
    prenom: Optional[str] = None
    nom: Optional[str] = None
    email: Optional[str] = None
    compte_actif: bool = True

    cabinets: List[uuid.UUID] = []
    nb_disponibilites: int = 0


class RattachementCreate(BaseSchema):
    """Rattachement d'un praticien à un site, sur une période."""

    date_debut: Optional[date] = None
    date_fin: Optional[date] = None

    @model_validator(mode="after")
    def verifier_periode(self):
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValueError(
                f"La date de fin ({self.date_fin}) ne peut pas précéder la date de début "
                f"({self.date_debut})."
            )
        return self


class RattachementResponse(BaseSchema):
    id: uuid.UUID
    cabinet_id: uuid.UUID
    cabinet_nom: Optional[str] = None
    praticien_id: uuid.UUID
    date_debut: date
    date_fin: Optional[date] = None
    actif: bool


# ==============================================================================
# DISPONIBILITÉS
# ==============================================================================

class DisponibiliteCreate(BaseSchema):
    """
    Une plage de travail d'un praticien.

    Récurrente (`jour_semaine`) ou exceptionnelle (`date_specifique`), ou les
    deux — une plage d'exception s'ajoute alors à la récurrence du même jour.
    """

    jour_semaine: Optional[int] = Field(
        None, ge=0, le=6, description="0 = lundi … 6 = dimanche. Absent = plage d'exception."
    )
    date_specifique: Optional[date] = Field(None, description="Jour précis (congé, remplacement).")
    heure_debut: time
    heure_fin: time
    cabinet_id: Optional[uuid.UUID] = Field(
        None, description="Site concerné. Absent = valable pour tous les sites du praticien."
    )
    type: str = Field(CONSULTATION, description=f"Un de {TYPES_PLAGE}")
    actif: bool = True

    @model_validator(mode="after")
    def valider_plage_horaire(self):
        # On délègue au vocabulaire partagé : les messages d'erreur s'adressent
        # directement le praticien, pas le développeur.
        try:
            valider_plage(
                heure_debut=self.heure_debut,
                heure_fin=self.heure_fin,
                jour_semaine=self.jour_semaine,
                date_specifique=self.date_specifique,
                type_plage=self.type,
            )
        except PlageInvalide as exc:
            raise ValueError(f"{exc.message}") from exc
        return self

    @property
    def duree_minutes(self) -> int:
        return minutes_de(self.heure_fin) - minutes_de(self.heure_debut)


class DisponibiliteResponse(BaseSchema):
    id: uuid.UUID
    praticien_id: uuid.UUID
    cabinet_id: Optional[uuid.UUID] = None
    jour_semaine: Optional[int] = None
    date_specifique: Optional[date] = None
    heure_debut: time
    heure_fin: time
    type: str
    actif: bool
    duree_minutes: int = 0

    # Libellés précalculés : le frontend affiche ces plages dans un agenda, il
    # n'a pas à refaire la conversion ni le calcul de durée.
    libelle_jour: Optional[str] = None
    plage: Optional[str] = None


class CreneauxResponse(BaseSchema):
    """
    Créneaux réellement proposables au patient pour une date.

    C'est le calcul que le module Agenda consommera pour proposer des horaires
    au secrétariat. Il est exposé dès maintenant parce que le secrétariat en a
    besoin pour répondre au téléphone, avant même que le module Agenda existe.
    """

    date: date
    praticien_id: uuid.UUID
    cabinet_id: Optional[uuid.UUID] = None
    creneaux: List[List[str]] = Field(
        default_factory=list,
        description='Paires ["HH:MM", "HH:MM"]. 30 min par défaut.',
    )
    duree_minutes: int = 30
    nb_plages_consultation: int = 0
    nb_plages_bloquantes: int = 0
    avertissement: Optional[str] = None


class ReferentielJoursResponse(BaseSchema):
    """
    Jours de la semaine et types de plage, pour peupler un formulaire.

    Contrat explicite plutôt que de laisser le frontend deviner la convention
    (0 = lundi ?) et les libellés français.
    """

    jours: List[Dict[str, Any]]
    types_plage: List[Dict[str, Any]]
    duree_creneau_minutes: int
