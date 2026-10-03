import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import EmailStr, Field, field_validator, model_validator
from src.common.schemas import BaseSchema
from src.modules.tenants.models import SexeEnum, TypePieceIdentiteEnum


# ==============================================================================
# ÉTAT GÉNÉRAL & ANTÉCÉDENTS (RG02)
# ==============================================================================

class Allergie(BaseSchema):
    """Entrée de la liste `allergies` (JSONB) de l'état général (dictionnaire §5.2)."""

    substance: str = Field(..., min_length=2, max_length=150, description="Ex: Pénicilline, Latex, Iode")
    reaction: Optional[str] = Field(None, max_length=500, description="Manifestation observée")
    severite: str = Field("legere", description="legere | moderee | grave")


class ExamenComplementaire(BaseSchema):
    """Entrée de la liste `examens_complementaires` (JSONB) (dictionnaire §5.2)."""

    type: str = Field(..., max_length=150, description="Ex: NFS, Glycémie, Radio panoramique")
    date: Optional[date] = None
    resultat: Optional[str] = None
    fichier_url: Optional[str] = None


class EtatGeneralBase(BaseSchema):
    grossesse: bool = Field(False, description="Patiente enceinte (RG04 : bloque certains médicaments)")
    grossesse_terme: Optional[str] = Field(
        None, max_length=50, description="Terme de grossesse (ex: 32 SA / 8 mois)"
    )
    allaitement: bool = Field(False, description="Allaitement en cours (RG04)")
    diabete: bool = Field(False, description="Diabète connu (RG04 : précautions anesthésiques)")
    diabete_type: Optional[str] = Field(
        None, max_length=50, description="type1 | type2 | gestationnel"
    )
    hta: bool = Field(False, description="Hypertension artérielle")
    tabac: bool = Field(False)
    alcool: bool = Field(False)
    allergies: Optional[List[Allergie]] = None
    autres_conditions: Optional[List[str]] = None
    examens_complementaires: Optional[List[ExamenComplementaire]] = None

    @field_validator("diabete_type")
    @classmethod
    def valider_type_diabete(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # On accepte les libellés métier que le praticien saisit réellement
        # (« diabète gestationnel », « TYPE 1 », « type_2 ») et on les ramène à
        # une valeur de référence stockée.
        normalise = v.strip().lower().replace(" ", "_").replace("-", "_").replace("é", "e")
        valides = {"type1", "type_1", "type2", "type_2", "gestationnel"}
        if normalise not in valides:
            raise ValueError(f"diabete_type doit être l'un de {sorted(valides)} ou NULL.")
        return normalise.replace("type_1", "type1").replace("type_2", "type2")

    @model_validator(mode="after")
    def coherence_grossesse(self):
        # Incohérence bloquante : grossesse + grossesse_terme renseigné mais pas de grossesse.
        if self.grossesse_terme and not self.grossesse:
            raise ValueError("grossesse_terme ne peut être renseigné que si grossesse est vrai.")
        return self


class EtatGeneralCreate(EtatGeneralBase):
    pass


class EtatGeneralUpdate(BaseSchema):
    """Mise à jour partielle : uniquement les champs explicitement transmis sont modifiés."""

    grossesse: Optional[bool] = None
    grossesse_terme: Optional[str] = Field(None, max_length=50)
    allaitement: Optional[bool] = None
    diabete: Optional[bool] = None
    diabete_type: Optional[str] = Field(None, max_length=50)
    hta: Optional[bool] = None
    tabac: Optional[bool] = None
    alcool: Optional[bool] = None
    allergies: Optional[List[Allergie]] = None
    autres_conditions: Optional[List[str]] = None
    examens_complementaires: Optional[List[ExamenComplementaire]] = None


class EtatGeneralResponse(BaseSchema):
    id: uuid.UUID
    dossier_medical_id: uuid.UUID
    grossesse: bool
    grossesse_terme: Optional[str] = None
    allaitement: bool
    diabete: bool
    diabete_type: Optional[str] = None
    hta: bool
    tabac: bool
    alcool: bool
    allergies: Optional[List[Dict[str, Any]]] = None
    autres_conditions: Optional[List[str]] = None
    examens_complementaires: Optional[List[Dict[str, Any]]] = None
    # Horodatage de la dernière mise à jour (RG02 : à vérifier à chaque consultation)
    a_jour_le: Optional[datetime] = Field(
        None, description="Dernier contrôle de l'état général. À vérifier à chaque consultation (RG02)."
    )


class AntecedentMedicalCreate(BaseSchema):
    type_antecedent: str = Field(
        ...,
        max_length=100,
        description="CHIRURGICAL | CARDIO | RESPIRATOIRE | ALLERGIE | DIABETE | HTA | FAMILIAL | DENTAIRE",
    )
    description: str = Field(..., min_length=2, description="Description de l'antécédent")
    date_survenue: Optional[date] = Field(None, description="Date de survenue (nullable si non précisée)")
    en_cours: bool = Field(False, description="L'antécédent est-il toujours actif ?")
    traitement_associe: Optional[str] = Field(None, description="Traitement en cours")
    notes: Optional[str] = None

    @field_validator("type_antecedent")
    @classmethod
    def normaliser_type(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")


class AntecedentMedicalUpdate(BaseSchema):
    type_antecedent: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, min_length=2)
    date_survenue: Optional[date] = None
    en_cours: Optional[bool] = None
    traitement_associe: Optional[str] = None
    notes: Optional[str] = None


class AntecedentMedicalResponse(BaseSchema):
    id: uuid.UUID
    dossier_medical_id: uuid.UUID
    type_antecedent: str
    description: str
    date_survenue: Optional[date] = None
    en_cours: bool
    traitement_associe: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# ==============================================================================
# PATIENT (RG01)
# ==============================================================================

class PatientBase(BaseSchema):
    prenom: str = Field(..., min_length=1, max_length=100)
    nom: str = Field(..., min_length=1, max_length=100)
    date_naissance: date = Field(..., description="Date de naissance (RG : search par date naissance)")
    sexe: SexeEnum = SexeEnum.F
    telephone_1: str = Field(..., min_length=6, max_length=30, description="Téléphone principal (recherche patient)")
    type_piece_identite: Optional[TypePieceIdentiteEnum] = None
    numero_piece_identite: Optional[str] = Field(None, max_length=100)
    adresse: Optional[str] = None
    ville: Optional[str] = Field("Dakar", max_length=100)
    telephone_2: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr] = None
    profession: Optional[str] = Field(None, max_length=100)
    employeur: Optional[str] = Field(None, max_length=150)
    groupe_sanguin: Optional[str] = Field(None, max_length=10)
    source: Optional[str] = Field(None, max_length=100, description="Recommandation, Réseaux, Passage...")
    notes: Optional[str] = None

    @field_validator("prenom", "nom")
    @classmethod
    def normaliser_noms(cls, v: str) -> str:
        return v.strip()

    @field_validator("telephone_1", "telephone_2")
    @classmethod
    def normaliser_telephone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        compact = re.sub(r"[\s.\-()]", "", v.strip())
        if len(compact) < 6:
            raise ValueError("Numéro de téléphone trop court (6 caractères minimum).")
        return compact


class PatientCreate(PatientBase):
    """
    Création d'un dossier patient (Étape 1 du workflow CDC).

    Le `numero_dossier` n'est pas fourni : il est généré par le service (RG01).
    Les antécédents peuvent être créés dans le même appel que l'identité.
    """

    etat_general: Optional[EtatGeneralCreate] = Field(
        None, description="État général (Étape 2 du CDC). Créé avec le dossier si fourni."
    )
    antecedents: Optional[List[AntecedentMedicalCreate]] = Field(
        None, description="Antécédents médicaux (Étape 3 du CDC)."
    )


class PatientUpdate(BaseSchema):
    """Mise à jour administrative. Les champs non transmis restent inchangés."""

    prenom: Optional[str] = Field(None, min_length=1, max_length=100)
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    date_naissance: Optional[date] = None
    sexe: Optional[SexeEnum] = None
    telephone_1: Optional[str] = Field(None, min_length=6, max_length=30)
    telephone_2: Optional[str] = Field(None, max_length=30)
    type_piece_identite: Optional[TypePieceIdentiteEnum] = None
    numero_piece_identite: Optional[str] = Field(None, max_length=100)
    adresse: Optional[str] = None
    ville: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    profession: Optional[str] = Field(None, max_length=100)
    employeur: Optional[str] = Field(None, max_length=150)
    groupe_sanguin: Optional[str] = Field(None, max_length=10)
    source: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

    @field_validator("telephone_1", "telephone_2")
    @classmethod
    def normaliser_telephone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        compact = re.sub(r"[\s.\-()]", "", v.strip())
        if len(compact) < 6:
            raise ValueError("Numéro de téléphone trop court (6 caractères minimum).")
        return compact


class PatientArchive(BaseSchema):
    motif: Optional[str] = Field(
        None, description="Motif de l'archivage (conservé dans l'audit médico-légal)."
    )


class PatientResponse(BaseSchema):
    id: uuid.UUID
    numero_dossier: str
    prenom: str
    nom: str
    date_naissance: date
    sexe: SexeEnum
    type_piece_identite: Optional[TypePieceIdentiteEnum] = None
    numero_piece_identite: Optional[str] = None
    photo_url: Optional[str] = None
    adresse: Optional[str] = None
    ville: Optional[str] = None
    telephone_1: str
    telephone_2: Optional[str] = None
    email: Optional[str] = None
    profession: Optional[str] = None
    employeur: Optional[str] = None
    groupe_sanguin: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    actif: bool
    archive: bool
    created_at: datetime
    updated_at: datetime


class PatientDossierCompletResponse(PatientResponse):
    """Fiche patient complète : identité + état général + antécédents + alertes."""

    dossier_medical_id: uuid.UUID
    etat_general: Optional[EtatGeneralResponse] = None
    antecedents: List[AntecedentMedicalResponse] = []
    alertes: List["AlerteMedicale"] = []
    nb_consultations: int = 0
    derniere_consultation: Optional[datetime] = None


class AlerteMedicale(BaseSchema):
    """
    Alerte clinique calculée à la volée (RG03, RG04).

    Le seuil de gravité est fixé par la clinique, pas déduit du modèle :
    toute grossesse est un signal, toute allergie grave est un signal.
    """

    code: str = Field(..., description="ALLERGIE | GROSSESSE | ALLAITEMENT | DIABETE | HTA | ANTECEDENT_CARDIAQUE | ANTECEDENT_ACTIF")
    niveau: str = Field(..., description="INFO | MODERE | GRAVE")
    message: str
    source: str = Field(..., description="ETAT_GENERAL ou ANTECEDENT")


class RecherchePatients(BaseSchema):
    """Paramètres de recherche multicritères (§4.2 : recherche multicritère)."""

    q: Optional[str] = Field(
        None,
        description="Recherche libre sur nom, prénom, numéro de dossier et téléphone.",
    )
    nom: Optional[str] = None
    date_naissance: Optional[date] = None
    telephone: Optional[str] = None
    numero_dossier: Optional[str] = None
    include_archives: bool = Field(False, description="Inclure les dossiers archivés dans les résultats.")
    uniquement_archives: bool = Field(
        False, description="Ne renvoyer que les dossiers archivés. Ignoré si include_archives est vrai."
    )


# Résolution de la forward-reference de PatientDossierCompletResponse.
PatientDossierCompletResponse.model_rebuild()
