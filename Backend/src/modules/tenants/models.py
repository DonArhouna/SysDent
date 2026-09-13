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
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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

    module: Mapped[str] = mapped_column(String(50), nullable=False) # PATIENTS, CONSULTATIONS, FACTURATION, STOCKS, ADMIN
    action: Mapped[str] = mapped_column(String(50), nullable=False) # READ, CREATE, UPDATE, DELETE, EXPORT, SIGN
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("module", "action", name="uq_permission_module_action"),)


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
    __tablename__ = "sessions_utilisateurs"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_revoque: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

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
    allaitement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diabete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Hypertension
    allergies: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tabac: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alcool: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    autres_conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="etat_general")


class AntecedentMedical(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "antecedents_medicaux"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id", ondelete="CASCADE"), nullable=False)
    type_antecedent: Mapped[str] = mapped_column(String(100), nullable=False) # CHIRURGICAL, CARDIO, RESPIRATOIRE, ALLERGIE
    description: Mapped[str] = mapped_column(Text, nullable=False)
    en_cours: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    traitement_associe: Mapped[str | None] = mapped_column(Text, nullable=True)

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="antecedents")


# ==============================================================================
# ODONTOGRAMME & SOINS DENTAIRES
# ==============================================================================

class Odontogramme(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "odontogrammes"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id", ondelete="CASCADE"), unique=True, nullable=False)
    systeme_notation: Mapped[str] = mapped_column(String(20), default="FDI", nullable=False) # FDI (11-48), UNIVERSAL (1-32)
    snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True) # Cache JSON des 32 dents pour rendu UI rapide

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="odontogramme")
    dents: Mapped[list["Dent"]] = relationship("Dent", back_populates="odontogramme", cascade="all, delete-orphan")


class Dent(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "dents"

    odontogramme_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("odontogrammes.id", ondelete="CASCADE"), nullable=False)
    numero_fdi: Mapped[int] = mapped_column(Integer, nullable=False, index=True) # 11 à 48
    etat_actuel: Mapped[str] = mapped_column(String(50), default="SAINE", nullable=False) # SAINE, CARIEE, OBTUREE, COURONNE, ABSENTE, IMPLANT, FRACTUREE
    mobilite: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # 0 à 3
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    odontogramme: Mapped[Odontogramme] = relationship("Odontogramme", back_populates="dents")
    __table_args__ = (UniqueConstraint("odontogramme_id", "numero_fdi", name="uq_dent_odontogramme_fdi"),)


# ==============================================================================
# CONSULTATIONS & ACTES
# ==============================================================================

class Consultation(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "consultations"

    dossier_medical_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossiers_medicaux.id"), nullable=False)
    praticien_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("praticiens.id"), nullable=False)
    cabinet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cabinets.id"), nullable=False)
    motif: Mapped[str] = mapped_column(String(255), nullable=False)
    anamnese: Mapped[str | None] = mapped_column(Text, nullable=True)
    examen_endobuccal: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_principal: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_traitement: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut: Mapped[StatutConsultationEnum] = mapped_column(Enum(StatutConsultationEnum), default=StatutConsultationEnum.PLANIFIEE, nullable=False)
    date_consultation: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    duree_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    dossier_medical: Mapped[DossierMedical] = relationship("DossierMedical", back_populates="consultations")
    actes_realises: Mapped[list["ActeRealise"]] = relationship("ActeRealise", back_populates="consultation", cascade="all, delete-orphan")


class ActeNomenclature(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "actes_nomenclature"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True) # e.g. DT01, ENDO02, EXT01
    libelle: Mapped[str] = mapped_column(String(200), nullable=False)
    categorie: Mapped[str] = mapped_column(String(100), nullable=False) # SOINS, PROTHESE, CHIRURGIE, ORTHO
    tarif_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    duree_estimee_min: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ActeRealise(TenantBase, UUIDMixin, TimestampMixin):
    __tablename__ = "actes_realises"

    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False)
    acte_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actes_nomenclature.id"), nullable=False)
    dent_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face: Mapped[str | None] = mapped_column(String(20), nullable=True) # M, D, O, V, L
    tarif_applique: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantite: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    consultation: Mapped[Consultation] = relationship("Consultation", back_populates="actes_realises")
    acte: Mapped[ActeNomenclature] = relationship("ActeNomenclature")


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
