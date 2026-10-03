from datetime import date, datetime, time, timezone
from decimal import Decimal
import enum
import uuid
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.common.base_model import TenantBase, TimestampMixin, UUIDMixin


# ==============================================================================
# ENUMS APPLICATIFS
# ==============================================================================

class SexeEnum(str, enum.Enum):
    M = "M"
    F = "F"
    AUTRE = "AUTRE"


class TypePieceIdentiteEnum(str, enum.Enum):
    CNI = "CNI"
    PASSEPORT = "PASSEPORT"
    PERMIS = "PERMIS"
    AUTRE = "AUTRE"


class StatutConsultationEnum(str, enum.Enum):
    PLANIFIEE = "PLANIFIEE"
    EN_ATTENTE = "EN_ATTENTE"
    EN_COURS = "EN_COURS"
    TERMINEE = "TERMINEE"
    ANNULEE = "ANNULEE"


class StatutFactureEnum(str, enum.Enum):
    BROUILLON = "BROUILLON"
    EMISE = "EMISE"
    PARTIELLEMENT_PAYEE = "PARTIELLEMENT_PAYEE"
    PAYEE = "PAYEE"
    ANNULEE = "ANNULEE"


class ModePaiementEnum(str, enum.Enum):
    ESPECES = "ESPECES"
    CARTE_BANCAIRE = "CARTE_BANCAIRE"
    CHEQUE = "CHEQUE"
    VIREMENT = "VIREMENT"
    MOBILE_MONEY = "MOBILE_MONEY" # Wave, Orange Money, Free Money
    ASSURANCE = "ASSURANCE"


class TypeMouvementStockEnum(str, enum.Enum):
    ENTREE = "ENTREE"
    SORTIE_CONSULTATION = "SORTIE_CONSULTATION"
    PERTE_PEREMPTION = "PERTE_PEREMPTION"
    AJUSTEMENT_INVENTAIRE = "AJUSTEMENT_INVENTAIRE"


# ==============================================================================
# UTILISATEURS, GROUPES & RBAC
# ==============================================================================

class Role(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"

    nom: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) # e.g. ADMIN_CABINET, PRATICIEN, SECRETAIRE, ASSISTANT, COMPTABLE
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    niveau_hierarchie: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    utilisateurs: Mapped[list["Utilisateur"]] = relationship("Utilisateur", back_populates="role")
    permission_roles: Mapped[list["PermissionRole"]] = relationship("PermissionRole", back_populates="role", cascade="all, delete-orphan")


class Permission(TenantBase, UUIDMixin):
    __tablename__ = "permissions"

    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # PATIENTS, CONSULTATIONS, FACTURATION, STOCK, AUDIT, ADMIN
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # READ, CREATE, UPDATE, DELETE, EXPORT, SIGN
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("module", "action", name="uq_permission_module_action"),)

    def __str__(self) -> str:
        return f"{self.module}:{self.action}"


class PermissionRole(TenantBase, UUIDMixin):
    __tablename__ = "permission_roles"

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), default="CABINET_LOCAL", nullable=False) # GLOBAL, CABINET_LOCAL, PROPRE_DOSSIER

    role: Mapped[Role] = relationship("Role", back_populates="permission_roles")
    permission: Mapped[Permission] = relationship("Permission")


class Utilisateur(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "utilisateurs"

    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    mot_de_passe: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deux_facteurs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    secret_2fa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dernier_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped[Role] = relationship("Role", back_populates="utilisateurs")
    praticien_profil: Mapped["Praticien | None"] = relationship("Praticien", back_populates="utilisateur", uselist=False)
    sessions: Mapped[list["SessionUser"]] = relationship("SessionUser", back_populates="utilisateur", cascade="all, delete-orphan")


class SessionUser(TenantBase, UUIDMixin, TimestampMixin):
    """
    Session persistée d'un utilisateur (rotation et révocation des refresh tokens).

    Tant que cette table n'était pas utilisée, un refresh token valide restait
    utilisable jusqu'à son expiration (7 jours) même après un logout ou une
    révocation de rôle. Le stockage en base rend la session révocable (RG12 du
    regles.md : « Session expire après inactivité »).
    """

    __tablename__ = "sessions_utilisateurs"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_revoque: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    derniere_activite: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    utilisateur: Mapped[Utilisateur] = relationship("Utilisateur", back_populates="sessions")


# ==============================================================================
# STRUCTURE DU CABINET & ÉQUIPEMENTS
# ==============================================================================

class Cabinet(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "cabinets"

    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    ville: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    horaires_ouverture: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    salles: Mapped[list["Salle"]] = relationship("Salle", back_populates="cabinet", cascade="all, delete-orphan")
    praticiens_rattaches: Mapped[list["CabinetPraticien"]] = relationship(
        "CabinetPraticien", back_populates="cabinet", cascade="all, delete-orphan"
    )
    disponibilites: Mapped[list["Disponibilite"]] = relationship(
        "Disponibilite", back_populates="cabinet", cascade="all, delete-orphan"
    )


class Salle(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "salles"

    cabinet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    etage: Mapped[str | None] = mapped_column(String(50), nullable=True)

    cabinet: Mapped[Cabinet] = relationship("Cabinet", back_populates="salles")
    fauteuils: Mapped[list["Fauteuil"]] = relationship("Fauteuil", back_populates="salle", cascade="all, delete-orphan")


class Fauteuil(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "fauteuils"

    salle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("salles.id", ondelete="CASCADE"), nullable=False)
    numero: Mapped[str] = mapped_column(String(50), nullable=False)
    equipements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    salle: Mapped[Salle] = relationship("Salle", back_populates="fauteuils")


class Praticien(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "praticiens"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="CASCADE"), unique=True, nullable=False)
    titre: Mapped[str] = mapped_column(String(50), default="Dr", nullable=False)
    specialite: Mapped[str] = mapped_column(String(100), default="Chirurgien-Dentiste", nullable=False)
    numero_ordre: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    signature_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    utilisateur: Mapped[Utilisateur] = relationship("Utilisateur", back_populates="praticien_profil")
    rattachements: Mapped[list["CabinetPraticien"]] = relationship(
        "CabinetPraticien", back_populates="praticien", cascade="all, delete-orphan"
    )
    disponibilites: Mapped[list["Disponibilite"]] = relationship(
        "Disponibilite", back_populates="praticien", cascade="all, delete-orphan"
    )


class CabinetPraticien(TenantBase, UUIDMixin, TimestampMixin):
    """
    Rattachement d'un praticien à un cabinet, avec sa période d'activité.

    Le modèle du MLD est `cabinet_praticiens`. Il est indispensable dès qu'une
    société possède plusieurs cabinets : un praticien peut tourner entre deux
    sites, et il neConsultait alors que dans ceux où il est rattaché actif.

    `date_fin` n'est pas une date d'expiration programmée mais la date à laquelle
    le rattachement a pris fin : le praticien qui quitte le cabinet y reste
    rattaché pour que ses consultations passées restent attribuables.
    """

    __tablename__ = "cabinet_praticiens"
    __table_args__ = (
        # Un praticien ne peut être rattaché qu'une fois à un site. La
        # vérification applicative seule laisserait passer un doublon créé par
        # une requête concurrente ou un script de reprise de données.
        UniqueConstraint("cabinet_id", "praticien_id", name="uq_cabinet_praticien"),
    )

    cabinet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=False, index=True)
    praticien_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("praticiens.id", ondelete="CASCADE"), nullable=False, index=True)
    date_debut: Mapped[date] = mapped_column(Date, default=lambda: date.today(), nullable=False)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    cabinet: Mapped[Cabinet] = relationship("Cabinet", back_populates="praticiens_rattaches")
    praticien: Mapped[Praticien] = relationship("Praticien", back_populates="rattachements")


class Disponibilite(TenantBase, UUIDMixin, TimestampMixin):
    """
    Plage horaire de travail d'un praticien dans un cabinet (MLD `disponibilites`).

    Deux notions distinctes coexistent et ne doivent pas être confondues :
      - `Cabinet.horaires_ouverture` : quand le **bâtiment** est ouvert.
      - `Disponibilite` : quand **ce praticien** travaille dans ce cabinet.

    L'agenda du pôle 2 ne retiendra que l'intersection des deux : un créneau
    proposable au patient est dans les horaires du cabinet ET dans la
    disponibilité du praticien.

    `jour_semaine` (0 = lundi … 6 = dimanche) décrit une plage récurrente ;
    `date_specifique` la remplace pour un jour donné (congé, formation,
    remplacement). Les deux ne sont pas exclusifs : une ligne avec les deux
    renseignés est une plage d'exception qui s'ajoute à la récurrence.
    """

    __tablename__ = "disponibilites"

    praticien_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("praticiens.id", ondelete="CASCADE"), nullable=False, index=True)
    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cabinets.id", ondelete="CASCADE"), nullable=True, index=True)
    jour_semaine: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, index=True)  # 0=lundi … 6=dimanche
    date_specifique: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    heure_debut: Mapped[time] = mapped_column(Time, nullable=False)
    heure_fin: Mapped[time] = mapped_column(Time, nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="CONSULTATION", nullable=False)  # CONSULTATION, URGENCE, BLOCKING (indisponibilité)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    praticien: Mapped[Praticien] = relationship("Praticien", back_populates="disponibilites")
    cabinet: Mapped[Cabinet | None] = relationship("Cabinet", back_populates="disponibilites")


# ==============================================================================
# PATIENTS & DOSSIER MÉDICAL
# ==============================================================================

class Patient(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "patients"

    numero_dossier: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    date_naissance: Mapped[date] = mapped_column(Date, nullable=False)
    sexe: Mapped[SexeEnum] = mapped_column(Enum(SexeEnum), nullable=False)
    type_piece_identite: Mapped[TypePieceIdentiteEnum | None] = mapped_column(Enum(TypePieceIdentiteEnum), nullable=True)
    numero_piece_identite: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    ville: Mapped[str | None] = mapped_column(String(100), default="Dakar", nullable=True)
    telephone_1: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    telephone_2: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    profession: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employeur: Mapped[str | None] = mapped_column(String(150), nullable=True)
    groupe_sanguin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True) # Recommandation, Réseaux, Passage...
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    dossier_medical: Mapped["DossierMedical | None"] = relationship("DossierMedical", back_populates="patient", uselist=False, cascade="all, delete-orphan")


class DossierMedical(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "dossiers_medicaux"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), unique=True, nullable=False)
    notes_confidentielles: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship("Patient", back_populates="dossier_medical")
    etat_general: Mapped["EtatGeneral | None"] = relationship("EtatGeneral", back_populates="dossier_medical", uselist=False, cascade="all, delete-orphan")
    antecedents: Mapped[list["AntecedentMedical"]] = relationship("AntecedentMedical", back_populates="dossier_medical", cascade="all, delete-orphan")
    odontogramme: Mapped["Odontogramme | None"] = relationship("Odontogramme", back_populates="dossier_medical", uselist=False, cascade="all, delete-orphan")
    consultations: Mapped[list["Consultation"]] = relationship("Consultation", back_populates="dossier_medical")


class EtatGeneral(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "etats_generaux"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id", ondelete="CASCADE"), unique=True, nullable=False)
    grossesse: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grossesse_terme: Mapped[str | None] = mapped_column(String(50), nullable=True) # ex: "32 SA" / "8 mois" (RG04)
    allaitement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diabete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diabete_type: Mapped[str | None] = mapped_column(String(50), nullable=True) # type1 | type2 | gestationnel (RG04)
    hta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Hypertension
    allergies: Mapped[list | None] = mapped_column(JSONB, nullable=True) # [{"substance", "reaction", "severite"}]
    tabac: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alcool: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    autres_conditions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    examens_complementaires: Mapped[list | None] = mapped_column(JSONB, nullable=True) # [{"type", "date", "resultat", "fichier_url"}]

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="etat_general")


class AntecedentMedical(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "antecedents_medicaux"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id", ondelete="CASCADE"), nullable=False)
    type_antecedent: Mapped[str] = mapped_column(String(100), nullable=False) # CHIRURGICAL, CARDIO, RESPIRATOIRE, ALLERGIE
    description: Mapped[str] = mapped_column(Text, nullable=False)
    date_survenue: Mapped[date | None] = mapped_column(Date, nullable=True) # NULL si la date n'est pas connue
    en_cours: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    traitement_associe: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="antecedents")


# ==============================================================================
# COMPTEURS DE NUMÉROTATION (RG01 — numéro de dossier patient, RG08)
# ==============================================================================

class Compteur(TenantBase):
    """
    Compteur de numérotation par type de document et par année.

    L'atomicité est assurée en base par `INSERT ... ON CONFLICT DO UPDATE ...
    RETURNING` (voir `src/common/numerotation.py`) : une simple lecture puis
    incrément en Python laisserait passer deux requêtes concurrentes.
    """

    __tablename__ = "compteurs"

    compteur: Mapped[str] = mapped_column(String(50), primary_key=True) # PATIENT_DOSSIER, FACTURE, DEVIS...
    annee: Mapped[int] = mapped_column(Integer, primary_key=True) # 0 pour les compteurs journaliers
    valeur: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ==============================================================================
# ODONTOGRAMME & SOINS DENTAIRES
# ==============================================================================

class Odontogramme(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "odontogrammes"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id", ondelete="CASCADE"), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="ADULTE", nullable=False) # ADULTE (32 dents), ENFANT (20 dents), MIXTE (RG11)
    systeme_notation: Mapped[str] = mapped_column(String(20), default="FDI", nullable=False) # FDI (11-48), UNIVERSAL (1-32)
    snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True) # Cache JSON des dents pour rendu UI rapide

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="odontogramme")
    dents: Mapped[list["Dent"]] = relationship("Dent", back_populates="odontogramme", cascade="all, delete-orphan")


class Dent(TenantBase, UUIDMixin, TimestampMixin):
    """
    Une dent de l'odontogramme.

    `etat_actuel` est le dernier état connu ; l'historique complet vit dans
    `EtatDentHistorique` (RG10 : toute modification est horodatée avec le
    praticien et la consultation). Conserver l'état courant ici permet un rendu
    immédiat sans parcourir l'historique.
    """

    __tablename__ = "dents"

    odontogramme_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("odontogrammes.id", ondelete="CASCADE"), nullable=False)
    numero_fdi: Mapped[int] = mapped_column(Integer, nullable=False, index=True) # 11-48 définitives, 51-85 lait
    numero_universal: Mapped[int | None] = mapped_column(Integer, nullable=True) # 1 à 32 (permanentes uniquement)
    etat_actuel: Mapped[str] = mapped_column(String(50), default="SAINE", nullable=False, index=True)
    mobilite: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # 0 à 3 (évaluation parodontale)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    odontogramme: Mapped[Odontogramme] = relationship("Odontogramme", back_populates="dents")
    faces: Mapped[list["FaceDent"]] = relationship("FaceDent", back_populates="dent", cascade="all, delete-orphan")
    historique: Mapped[list["EtatDentHistorique"]] = relationship(
        "EtatDentHistorique", back_populates="dent", cascade="all, delete-orphan"
    )
    chartings: Mapped[list["ChartingParodontal"]] = relationship(
        "ChartingParodontal", back_populates="dent", cascade="all, delete-orphan"
    )
    __table_args__ = (UniqueConstraint("odontogramme_id", "numero_fdi", name="uq_dent_odontogramme_fdi"),)


class FaceDent(TenantBase, UUIDMixin, TimestampMixin):
    """
    État d'une face Dentaire (5 faces par dent).

    Permet de localiser une lésion : une carie de la face occlusale de la 26
    n'est pas la même fiche clinique qu'une atteinte de la face distale.
    """

    __tablename__ = "faces_dents"

    dent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dents.id", ondelete="CASCADE"), nullable=False, index=True)
    face: Mapped[str] = mapped_column(String(20), nullable=False) # MESIAL, DISTAL, VESTIBULAIRE, LINGUAL_PALATIN, OCCLUSAL_INCISAL
    etat: Mapped[str] = mapped_column(String(50), default="SAINE", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    dent: Mapped[Dent] = relationship("Dent", back_populates="faces")
    __table_args__ = (UniqueConstraint("dent_id", "face", name="uq_face_dent"),)


class EtatDentHistorique(TenantBase, UUIDMixin):
    """
    Trace horodatée de tout changement d'état d'une dent (RG10).

    Chaque ligne est un état CONSTATÉ, pas une action : un même état peut être
    reconstaté à des dates différentes. C'est ce qui permet de reconstituer
    l'évolution d'une dent et de justifier médicalement un traitement.
    """

    __tablename__ = "etats_dents_historique"

    date_constat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    dent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dents.id", ondelete="CASCADE"), nullable=False, index=True)
    etat: Mapped[str] = mapped_column(String(50), nullable=False)
    etat_precedent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    face: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True)
    praticien_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("praticiens.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    dent: Mapped[Dent] = relationship("Dent", back_populates="historique")


class ChartingParodontal(TenantBase, UUIDMixin, TimestampMixin):
    """
    Charting parodontal d'une dent : sondage en 6 points et indices associés.

    `sondages` est un JSONB : [{"site": "MV", "profondeur": 3}, ...] selon le
    dictionnaire §5.2. On conserve l'ensemble des mesures d'un même relevé
    comme une seule ligne, ce qui garantit qu'elles sont contemporaries.
    """

    __tablename__ = "chartings_parodontaux"

    dent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dents.id", ondelete="CASCADE"), nullable=False, index=True)
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True)
    date_examen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    sondages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    nac: Mapped[int | None] = mapped_column(Integer, nullable=True) # niveau d'attachement clinique (0 à 3)
    recession: Mapped[int | None] = mapped_column(Integer, nullable=True) # recession gingivale en mm
    saignement_bop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # saignement au sondage
    suppuration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mobilite: Mapped[int | None] = mapped_column(Integer, nullable=True) # 0 à 3
    furcation: Mapped[int | None] = mapped_column(Integer, nullable=True) # 0 à 3
    plaque_ipv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # indice de plaque visible / présent
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    dent: Mapped[Dent] = relationship("Dent", back_populates="chartings")


# ==============================================================================
# CONSULTATIONS & ACTES
# ==============================================================================

class MotifConsultationEnum(str, enum.Enum):
    """Motifs prévus par le CDC (Étape 4 du parcours patient)."""

    DOULEUR = "DOULEUR"
    CONTROLE = "CONTROLE"
    URGENCE = "URGENCE"
    ESTHETIQUE = "ESTHETIQUE"
    SUIVI = "SUIVI"
    PROTHESE = "PROTHESE"
    ORTHODONTIE = "ORTHODONTIE"
    AUTRE = "AUTRE"


class Consultation(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "consultations"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id"), nullable=False, index=True)
    praticien_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("praticiens.id"), nullable=False, index=True)
    cabinet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cabinets.id"), nullable=False)
    # Fauteuil occupé par le soin. Facultatif : une consultation saisie en
    # urgence ou une reprise de dossier ancienne peut n'avoir pas de fauteuil
    # renseigné. `ondelete=SET NULL` ne s'applique qu'aux fauteuils jamais
    # utilisés — un fauteuil utilisé est désactivé, jamais supprimé (cf. service).
    fauteuil_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("fauteuils.id", ondelete="SET NULL"), nullable=True, index=True)
    # UNIQUE, et non simple index : une consultation ne peut être ouverte que
    # depuis UN rendez-vous. Deux lignes pointant le même rendez-vous
    # signeraient un soin compté deux fois.
    rendez_vous_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    motif: Mapped[str] = mapped_column(String(255), nullable=False)
    motif_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_motif: Mapped[MotifConsultationEnum] = mapped_column(
        Enum(MotifConsultationEnum), default=MotifConsultationEnum.AUTRE, nullable=False
    )
    anamnese: Mapped[str | None] = mapped_column(Text, nullable=True)
    examen_exobuccal: Mapped[str | None] = mapped_column(Text, nullable=True)
    examen_endobuccal: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_principal: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostics_differentiels: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    codes_cim10: Mapped[list | None] = mapped_column(JSONB, nullable=True) # ["K02.1", "K05.0"]
    plan_traitement: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommandations: Mapped[str | None] = mapped_column(Text, nullable=True)
    prochain_rdv_prevu: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[StatutConsultationEnum] = mapped_column(Enum(StatutConsultationEnum), default=StatutConsultationEnum.PLANIFIEE, nullable=False, index=True)
    date_consultation: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    duree_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="consultations")
    fauteuil: Mapped["Fauteuil | None"] = relationship("Fauteuil")
    rendez_vous_source: Mapped["RendezVous | None"] = relationship(
        "RendezVous", back_populates="consultation"
    )
    actes_realises: Mapped[list["ActeRealise"]] = relationship("ActeRealise", back_populates="consultation", cascade="all, delete-orphan")


class ActeNomenclature(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "actes_nomenclature"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True) # e.g. DT01, ENDO02, EXT01
    libelle: Mapped[str] = mapped_column(String(200), nullable=False)
    categorie: Mapped[str] = mapped_column(String(100), nullable=False, index=True) # SOINS, PROTHESE, CHIRURGIE, ORTHO
    tarif_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    duree_estimee_min: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Un acte est rattaché à une dent.when il s'agit d'un soin unitaire (DETART,
    # CARIE, EXT). Si la nomenclature est une prestation globale (CONSULTATION,
    # RADIO PANO), ce booléen est à False et dent_numero reste nul.
    unitaire: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ActeRealise(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "actes_realises"

    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False)
    acte_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actes_nomenclature.id"), nullable=False)
    dent_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face: Mapped[str | None] = mapped_column(String(20), nullable=True) # M, D, O, V, L
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tarif figé au moment de la saisie : une révision de la nomenclature ne doit
    # pas modifier rétroactivement ce qui a été facturé au patient.
    tarif_applique: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    consultation: Mapped[Consultation] = relationship("Consultation", back_populates="actes_realises")
    acte: Mapped[ActeNomenclature] = relationship("ActeNomenclature")


# ==============================================================================
# RENDEZ-VOUS & AGENDA (RG09)
# ==============================================================================

class StatutRendezVousEnum(str, enum.Enum):
    """Cycle de vie d'un rendez-vous (CDC). Miroir du statut de consultation."""

    PLANIFIE = "PLANIFIE"
    CONFIRME = "CONFIRME"
    EN_SALLE_ATTENTE = "EN_SALLE_ATTENTE"
    EN_CONSULTATION = "EN_CONSULTATION"
    TERMINEE = "TERMINEE"
    ANNULE = "ANNULE"
    ABSENT = "ABSENT"


class MotifBlocageFauteuilEnum(str, enum.Enum):
    """Pourquoi un fauteuil est occupé sur une plage."""

    RENDEZ_VOUS = "RENDEZ_VOUS"
    MAINTENANCE = "MAINTENANCE"
    REPARATION = "REPARATION"
    RESERVATION = "RESERVATION"


class RendezVous(TenantBase, UUIDMixin, TimestampMixin):
    """
    Rendez-vous patient, rattaché à un praticien et, éventuellement, à un fauteuil.

    **L'intervalle est porté par deux colonnes** (`debut`, `fin`), pas par un
    début + une durée. C'est ce qui permet dposer une contrainte d'exclusion
    GiST sur `tstzrange(debut, fin, '[)')` : PostgreSQL garantit alors
    qu'un praticien ne peut pas avoir deux rendez-vous qui se chevauchent, même
    si deux secrétaires valident en même temps. Une durée dérivée serait une
    expression, qu'une contrainte d'exclusion n'accepte pas, et la garantie
    retomberait dans le code applicatif — avec sa fenêtre de course.

    `statut` est un ENUM PostgreSQL ici, contrairement aux statuts de dents :
    la contrainte d'exclusion doit comparer la colonne, et une valeur texte
    libre donnerait l'illusion d'une garantie. Les transitions autorisées sont
    dans `src/common/rendezvous.py`, pas dans la base : la base ne connaît pas
    les chemins métier.
    """

    __tablename__ = "rendez_vous"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cabinet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cabinets.id"), nullable=False, index=True
    )
    praticien_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("praticiens.id"), nullable=False, index=True
    )
    debut: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    motif: Mapped[str] = mapped_column(String(255), nullable=False)
    type_motif: Mapped[MotifConsultationEnum] = mapped_column(
        Enum(MotifConsultationEnum), default=MotifConsultationEnum.AUTRE, nullable=False
    )
    statut: Mapped[StatutRendezVousEnum] = mapped_column(
        Enum(StatutRendezVousEnum),
        default=StatutRendezVousEnum.PLANIFIE,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    motif_annulation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_statut: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # `__table_args__` est déclaré APRÈS les colonnes : la contrainte cite
    # leurs noms, qui ne sont pas encore dans la portée de la classe si elle
    # figure plus haut.
    __table_args__ = (
        ExcludeConstraint(
            (praticien_id, "="),
            (func.tstzrange(debut, fin, "[)"), "&&"),
            using="gist",
            # `where` : les trois statuts TERMINAUX sortent du périmètre. Un
            # rendez-vous terminé, annulé ou manqué ne réserve plus son créneau.
            # La valeur est dupliquée côté Python (`STATUTS_EXCLUS_DU_CONFLIT`)
            # et doit rester alignée : c'est la seule règle qui doit l'être,
            # d'où ce rappel.
            where=text("statut NOT IN ('ANNULE', 'ABSENT', 'TERMINEE')"),
            name="ex_rendez_vous_praticien",
        ),
    )

    patient: Mapped[Patient] = relationship("Patient")
    cabinet: Mapped[Cabinet] = relationship("Cabinet")
    praticien: Mapped[Praticien] = relationship("Praticien")
    creneaux_fauteuil: Mapped[list["CreneauFauteuil"]] = relationship(
        "CreneauFauteuil", back_populates="rendez_vous", cascade="all, delete-orphan"
    )
    # Relation inverse, déclarée depuis la consultation. Elle n'apporte rien à la
    # base — `consultations.rendez_vous_id` est UNIQUE et fait autorité — mais
    # elle évite à l'agenda de résoudre l'identifiant de consultation par une
    # requête par ligne.
    consultation: Mapped["Consultation | None"] = relationship(
        "Consultation", back_populates="rendez_vous_source", uselist=False
    )


class CreneauFauteuil(TenantBase, UUIDMixin, TimestampMixin):
    """
    Occupation d'un fauteuil sur une plage horaire — toutes causes confondues.

    ⚠️ Table unique pour l'occupation, et c'est délibéré. Un rendez-vous pose
    une ligne `motif = RENDEZ_VOUS` avec `rendez_vous_id` renseigné ; un fauteuil
    hors service en pose une avec `rendez_vous_id = NULL` et un motif de
    maintenance. La contrainte d'exclusion porte donc sur CETTE table, et couvre
    les deux cas d'un seul coup.

    Répartir l'occupation entre `rendez_vous.fauteuil_id` et cette table
    obligerait à vérifier les conflits de fauteuil dans le code, à croiser deux
    tables, et rouvrirait la même fenêtre de course qu'on vient de fermer.

    `rendez_vous_id` est `SET NULL` : supprimer un rendez-vous libère son
    fauteuil sans intervention, et le motif d'indisponibilité reste en place.
    """

    __tablename__ = "creneaux_fauteuil"

    fauteuil_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fauteuils.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rendez_vous_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True, index=True
    )
    debut: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    motif: Mapped[MotifBlocageFauteuilEnum] = mapped_column(
        Enum(MotifBlocageFauteuilEnum),
        default=MotifBlocageFauteuilEnum.RENDEZ_VOUS,
        nullable=False,
    )
    motif_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        # Pas de `where` ici, contrairement à `RendezVous` : un fauteuil hors
        # service doit rester bloqué même s'il n'a aucun rendez-vous.
        ExcludeConstraint(
            (fauteuil_id, "="),
            (func.tstzrange(debut, fin, "[)"), "&&"),
            using="gist",
            name="ex_creneau_fauteuil",
        ),
    )

    fauteuil: Mapped[Fauteuil] = relationship("Fauteuil")
    rendez_vous: Mapped[RendezVous | None] = relationship(
        "RendezVous", back_populates="creneaux_fauteuil"
    )


# ==============================================================================
# ORDONNANCES & PRESCRIPTIONS (RG07, RG08)
# ==============================================================================

class MedicamentReferentiel(TenantBase, UUIDMixin, TimestampMixin):
    """
    Référentiel médicamenteux du cabinet.

    `contre_indications` porte les règles sous forme de données :
    ``[{"condition": "ALLERGIE_PENICILLINE", "gravite": "INTERDIT", "message": "..."}]``

    C'est un choix structurant : les règles vivent en base et non dans le code.
    Un pharmacien peut ajouter une règle sans redéploiement, et deux cabinets
    peuvent avoir des idiosyncrasies de prescribing différentes. Le moteur de
    lecture est dans `src/common/ordonnance.py`.
    """

    __tablename__ = "medicaments"

    nom_commercial: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    dci: Mapped[str] = mapped_column(String(150), nullable=False, index=True) # dénomination commune internationale
    forme: Mapped[str] = mapped_column(String(50), default="COMPRIME", nullable=False) # COMPRIME, SIROP, GEL, COLLUTAIRE, POMMADE
    dosage: Mapped[str | None] = mapped_column(String(50), nullable=True) # 500mg, 2,5%
    classe_therapeutique: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    contre_indications: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    precautions: Mapped[str | None] = mapped_column(Text, nullable=True)
    posologie_adulte: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lignes: Mapped[list["LignePrescription"]] = relationship("LignePrescription", back_populates="medicament")


class Prescription(TenantBase, UUIDMixin, TimestampMixin):
    """
    Ordonnance émise lors d'une consultation.

    `signe` verrouille l'ordonnance : une ordonnance signée est un acte médical
    opposable, elle ne se modifie plus (on en émet une nouvelle). C'est ce qui
    distingue une prescription d'une note de service.
    """

    __tablename__ = "prescriptions"

    numero: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True)
    praticien_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("praticiens.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    date_ordonnance: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    notes_generales: Mapped[str | None] = mapped_column(Text, nullable=True)
    signe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_signature: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Alertes de contre-indication relevées au moment de la prescription, avec
    # la justification donnée par le praticien. Un snapshotted fige ce qui a été
    # signalé : le référentiel peut évoluer, l'acte passé reste attesté.
    alertes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    consultation: Mapped[Consultation] = relationship("Consultation")
    lignes: Mapped[list["LignePrescription"]] = relationship(
        "LignePrescription", back_populates="prescription", cascade="all, delete-orphan"
    )


class LignePrescription(TenantBase, UUIDMixin, TimestampMixin):
    """
    Ligne d'ordonnance : un médicament, sa posologie, sa durée.

    `medicament_id` est facultatif : un cabinet doit pouvoir prescrire un produit
    qui n'est pas encore au référentiel (produit local, préparation). Le texte
    libre `medicament_texte` porte alors l'information, et aucune
    contre-indication automatique ne peut être évaluée — ce qui doit rester
    visible, pas silencieux.
    """

    __tablename__ = "lignes_prescription"

    prescription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    medicament_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("medicaments.id", ondelete="SET NULL"), nullable=True)
    medicament_texte: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posologie: Mapped[str] = mapped_column(String(255), nullable=False, default="1 comprimé matin et soir")
    duree: Mapped[str | None] = mapped_column(String(100), nullable=True) # ex: "7 jours"
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantite: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Justification obligatoire d'une prescription en cas de simple précaution.
    justification_precaution: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription: Mapped[Prescription] = relationship("Prescription", back_populates="lignes")
    medicament: Mapped["MedicamentReferentiel | None"] = relationship("MedicamentReferentiel", back_populates="lignes")


# ==============================================================================
# FACTURATION & PAIEMENTS
# ==============================================================================

class Facture(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "factures"

    numero: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True) # e.g. FAC-2026-0001
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    cabinet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cabinets.id"), nullable=False)
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id"), nullable=True)
    montant_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    montant_tva: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    montant_paye: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    montant_restant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    statut: Mapped[StatutFactureEnum] = mapped_column(Enum(StatutFactureEnum), default=StatutFactureEnum.EMISE, nullable=False)
    date_emission: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    date_echeance: Mapped[date | None] = mapped_column(Date, nullable=True)

    lignes: Mapped[list["LigneFacture"]] = relationship("LigneFacture", back_populates="facture", cascade="all, delete-orphan")
    paiements: Mapped[list["Paiement"]] = relationship("Paiement", back_populates="facture", cascade="all, delete-orphan")


class LigneFacture(TenantBase, UUIDMixin):
    __tablename__ = "lignes_facture"

    facture_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures.id", ondelete="CASCADE"), nullable=False)
    acte_realise_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("actes_realises.id"), nullable=True)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    facture: Mapped[Facture] = relationship("Facture", back_populates="lignes")


class Paiement(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "paiements"

    facture_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factures.id", ondelete="CASCADE"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mode: Mapped[ModePaiementEnum] = mapped_column(Enum(ModePaiementEnum), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True) # Ref transaction Wave/OM/Chèque
    recu_numero: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    date_paiement: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    facture: Mapped[Facture] = relationship("Facture", back_populates="paiements")


# ==============================================================================
# AUDIT TRAIL LOCAL (TENANT)
# ==============================================================================

class AuditLogTenant(TenantBase, UUIDMixin):
    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. PATIENT_VIEW, ODONTOGRAM_UPDATE, INVOICE_VOID
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
