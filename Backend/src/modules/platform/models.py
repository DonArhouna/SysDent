"""
Modèles de la PLATEFORME (backoffice éditeur) — base `sysdent_platform`.

Séparés de `src/modules/master/models.py` (base master) et de
`src/modules/tenants/models.py` (bases clients) par trois raisons :

1. **Étanchéité physique** : aucun `JOIN` n'est possible entre ces tables et
   celles d'un cabinet. Le personnel de la plateforme ne peut structurellement
   pas lire un dossier patient, même par erreur de requête (décision D1).
2. **Durée de vie** : les tables d'identité de l'éditeur (utilisateurs, rôles,
   sessions) n'ont rien à voir du cycle de vie d'un cabinet. Un cabinet
   supprimé ne doit jamais emporter le compte de l'agent qui le portait.
3. **Journal immuable** : `journal_audit_plateforme` est append-only et doit
   survivre à tout, y compris à la disparition d'un tenant.

Les identifiants de tenant y sont des **UUID sans clé étrangère SQL** : le tenant
est une ligne de `societes` dans la base master, dans une AUTRE base. La
référence est applicative et contrôlée (`PlateformeTenantService`), pas
transactionnelle — c'est la contrepartie assumée de la décision D1.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import enum
import uuid
from sqlalchemy import (
    Boolean,
    Column,
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.common.base_model import PlatformBase, TimestampMixin, UUIDMixin


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# ÉNUMS
# ==============================================================================


class StatutUtilisateurPlateforme(str, enum.Enum):
    ACTIF = "ACTIF"
    DESACTIF = "DESACTIF"
    VERROUILLE = "VERROUILLE"


class StatutTenant(str, enum.Enum):
    """Machine à états du cycle de vie d'un cabinet (Phase B.2)."""

    ESSAI = "ESSAI"
    ACTIF = "ACTIF"
    SUSPENDU = "SUSPENDU"
    RESILIE = "RESILIE"


class PeriodeFacturation(str, enum.Enum):
    MENSUEL = "MENSUEL"
    ANNUEL = "ANNUEL"
    GRATUIT = "GRATUIT"


class StatutAbonnement(str, enum.Enum):
    ESSAI = "ESSAI"
    ACTIF = "ACTIF"
    SUSPENDU = "SUSPENDU"
    EXPIRE = "EXPIRE"
    RESILIE = "RESILIE"


class StatutFacturePlateforme(str, enum.Enum):
    BROUILLON = "BROUILLON"
    EMISE = "EMISE"
    PAYEE = "PAYEE"
    EN_RETARD = "EN_RETARD"
    ANNULEE = "ANNULEE"


class StatutAccesSupport(str, enum.Enum):
    ACTIF = "ACTIF"
    EXPIRE = "EXPIRE"
    REVOQUE = "REVOQUE"


class TypeGabarit(str, enum.Enum):
    ACTES = "ACTES"
    MEDICAMENTS = "MEDICAMENTS"
    FORMULAIRE = "FORMULAIRE"
    PARAMETRES = "PARAMETRES"
    ROLES = "ROLES"


class UsageJeton(str, enum.Enum):
    VERIFICATION_EMAIL = "VERIFICATION_EMAIL"
    VERIFICATION_TELEPHONE = "VERIFICATION_TELEPHONE"
    INVITATION_ADMIN = "INVITATION_ADMIN"
    REINITIALISATION_ACCES = "REINITIALISATION_ACCES"
    REPLACEMENT_ADMIN = "REPLACEMENT_ADMIN"
    # Défi 2FA : jeton opaque à 5 minutes émis entre la vérification du mot de
    # passe et la saisie du code TOTP. Consommé une seule fois, haché en base.
    CHALLENGE_2FA = "CHALLENGE_2FA"


class StatutInscription(str, enum.Enum):
    EN_ATTENTE_VERIFICATION = "EN_ATTENTE_VERIFICATION"
    VERIFIE = "VERIFIE"
    ACTIF = "ACTIF"
    REJETE = "REJETE"
    ERREUR = "ERREUR"


class StatutMigrationTenant(str, enum.Enum):
    EN_COURS = "EN_COURS"
    SUCCES = "SUCCES"
    ECHEC = "ECHEC"
    IGNORE = "IGNORE"


class StatutExport(str, enum.Enum):
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"
    ECHEC = "ECHEC"
    SUPPRIME = "SUPPRIME"


class TypeAnnonce(str, enum.Enum):
    INFO = "INFO"
    MAINTENANCE = "MAINTENANCE"
    NOUVEAUTE = "NOUVEAUTE"
    ALERTE = "ALERTE"


# ==============================================================================
# TABLE D'ASSOCIATION — plusieurs rôles par utilisateur
# ==============================================================================

role_permissions = Table(
    "role_permissions",
    PlatformBase.metadata,
    Column("role_id", ForeignKey("roles_plateforme.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions_plateforme.id", ondelete="CASCADE"), primary_key=True),
)

utilisateur_roles = Table(
    "utilisateur_roles",
    PlatformBase.metadata,
    Column("utilisateur_id", ForeignKey("utilisateurs_plateforme.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles_plateforme.id", ondelete="CASCADE"), primary_key=True),
)


# ==============================================================================
# IDENTITÉ PLATEFORME (Phase A)
# ==============================================================================


class PermissionPlateforme(PlatformBase, UUIDMixin):
    """
    Permission de la console, namespace `platform.*`.

    Le format est `platform.<ressource>.<action>` — distinct du `MODULE:ACTION`
    des cabinets. Deux catalogues qui ne se ressemblent pas rendent impossible
    qu'un droitthoughtread de l'un soit lu comme un droit de l'autre.
    """

    __tablename__ = "permissions_plateforme"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    ressource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    # `sensible=True` : l'action touche un secret, un droit ou une donnée
    # personnelle. Le journal d'audit la trace en plus du journal générique.
    sensible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RolePlateforme(PlatformBase, UUIDMixin, TimestampMixin):
    """Rôle de la console éditeur. `systeme=True` = non supprimable."""

    __tablename__ = "roles_plateforme"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    libelle: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    niveau_hierarchie: Mapped[int] = mapped_column(SmallInteger, default=10, nullable=False)
    systeme: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions: Mapped[list[PermissionPlateforme]] = relationship(
        "PermissionPlateforme", secondary=role_permissions, lazy="selectin"
    )
    utilisateurs: Mapped[list["UtilisateurPlateforme"]] = relationship(
        "UtilisateurPlateforme", secondary=utilisateur_roles, back_populates="roles"
    )


class UtilisateurPlateforme(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Compte de l'équipe éditrice.

    Table dédiée, JAMAIS partagée avec les utilisateurs d'un cabinet : pas de
    même table, pas de même base, pas de même clé de signature.
    """

    __tablename__ = "utilisateurs_plateforme"

    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    mot_de_passe: Mapped[str] = mapped_column(String(255), nullable=False)
    prenom: Mapped[str] = mapped_column(String(80), nullable=False)
    nom: Mapped[str] = mapped_column(String(80), nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    statut: Mapped[StatutUtilisateurPlateforme] = mapped_column(
        Enum(StatutUtilisateurPlateforme, name="statut_utilisateur_plateforme"),
        default=StatutUtilisateurPlateforme.ACTIF,
        nullable=False,
        index=True,
    )
    motif_desactivation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Second facteur, OBLIGATOIRE ──────────────────────────────────────────
    deux_facteurs_actif: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Secret TOTP CHIFFRÉ (Fernet), jamais en clair : une lecture de la base ne
    # doit pas suffire à fabriquer un code d'authentification.
    secret_2fa_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    deux_facteurs_confirme_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tentatives_echouees: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verrouille_jusqua: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dernier_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cree_par: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    roles: Mapped[list[RolePlateforme]] = relationship(
        "RolePlateforme", secondary=utilisateur_roles, lazy="selectin", back_populates="utilisateurs"
    )
    sessions: Mapped[list["SessionPlateforme"]] = relationship(
        "SessionPlateforme", back_populates="utilisateur", cascade="all, delete-orphan"
    )


class SessionPlateforme(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Session persistée de l'éditeur : rotation du refresh et révocation.

    Le refresh token est stocké **haché** (SHA-256), pas en clair : contrairement
    à `sessions_utilisateurs` côté cabinet, une fuite de la base plateforme ne
    donne pas des jetons rejouables.
    """

    __tablename__ = "sessions_plateforme"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs_plateforme.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_revoque: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    derniere_activite: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False
    )

    utilisateur: Mapped[UtilisateurPlateforme] = relationship(
        "UtilisateurPlateforme", back_populates="sessions"
    )


# ==============================================================================
# CYCLE DE VIE DES TENANTS (Phase B)
# ==============================================================================


class TenantPlateforme(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Vue métier d'un cabinet, ancrée sur `societes.id` de la base master.

    L'identité (nom, contacts, NINEA) reste dans `societes` : il n'y a qu'une
    seule source de vérité pour « qui est ce cabinet ». Cette table n'ajoute que
    ce qui est du ressort de l'éditeur : statut de cycle de vie, dates d'essai,
    archivable, préférences régionales.

    `statut_metier` est la levier utilisé par l'application cliente pour refuser
    la connexion (Phase B.3) ; `tenants_db.statut` côté master reste le levier
    technique d'ouverture de la base. Les deux sont posés ensemble par le service.
    """

    __tablename__ = "tenants_plateforme"

    # Pas de ForeignKey : `societes` vit dans la base master (Autre univers).
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, index=True)

    statut_metier: Mapped[StatutTenant] = mapped_column(
        Enum(StatutTenant, name="statut_tenant"), default=StatutTenant.ESSAI, nullable=False, index=True
    )
    archivable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    motif_statut: Mapped[str | None] = mapped_column(Text, nullable=True)

    date_debut_essai: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_fin_essai: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    date_activation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_suspension: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_resiliation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Préférences de présentation gérées par l'éditeur (Phase B.1).
    langue: Mapped[str] = mapped_column(String(5), default="fr", nullable=False)
    fuseau_horaire: Mapped[str] = mapped_column(String(50), default="Africa/Dakar", nullable=False)
    devise: Mapped[str] = mapped_column(String(3), default="XOF", nullable=False)
    pays: Mapped[str] = mapped_column(String(100), default="Sénégal", nullable=False)

    # Suivi de l'administrateur initial (Phase B.5) — on ne stocke JAMAIS son
    # mot de passe : uniquement l'email et l'état de son accès.
    admin_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    admin_acces_reinitialise_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class StatutTenantHistorique(PlatformBase, UUIDMixin):
    """Trace horodatée de chaque transition de statut, avec son motif."""

    __tablename__ = "statuts_tenant_historique"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    statut_precedent: Mapped[str] = mapped_column(String(20), nullable=False)
    statut_nouveau: Mapped[str] = mapped_column(String(20), nullable=False)
    motif: Mapped[str] = mapped_column(Text, nullable=False)
    auteur_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    auteur_email: Mapped[str] = mapped_column(String(150), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MigrationTenant(PlatformBase, UUIDMixin):
    """
    Journal des applications de migrations sur un tenant.

    `alembic_version` dans la base du cabinet reste la source de vérité de
    l'état ; cette table garde ce qu'elle ne peut pas contenir : QUI a lancé,
    QUAND, COMBIEN DE TEMPS et l'erreur survenue (Phase B.7).
    """

    __tablename__ = "migrations_tenant"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_nom: Mapped[str | None] = mapped_column(String(150), nullable=True)
    revision_avant: Mapped[str | None] = mapped_column(String(40), nullable=True)
    revision_apres: Mapped[str | None] = mapped_column(String(40), nullable=True)
    statut: Mapped[StatutMigrationTenant] = mapped_column(
        Enum(StatutMigrationTenant, name="statut_migration_tenant"),
        default=StatutMigrationTenant.EN_COURS,
        nullable=False,
        index=True,
    )
    duree_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
    lance_par: Mapped[str | None] = mapped_column(String(150), nullable=True)


class ExportTenant(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Demande d'export complet d'un cabinet (Phase B.8).

    `chemin_chiffre` ne contient QUE le chemin d'un fichier déjà chiffré : la
    clé elle-même n'est jamais stockée ici (elle est remise une seule fois à
    l'agent demandeur, hors base).
    """

    __tablename__ = "exports_tenant"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type_export: Mapped[str] = mapped_column(String(30), default="COMPLET", nullable=False)
    statut: Mapped[StatutExport] = mapped_column(
        Enum(StatutExport, name="statut_export"), default=StatutExport.EN_COURS, nullable=False
    )
    chemin_chiffre: Mapped[str | None] = mapped_column(Text, nullable=True)
    taille_octets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expire_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demande_par: Mapped[str] = mapped_column(String(150), nullable=False)
    motif: Mapped[str] = mapped_column(Text, nullable=False)
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)


# ==============================================================================
# PLANS, ABONNEMENTS, FACTURATION (Phase C)
# ==============================================================================


class Plan(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Plan commercial.

    `quotas` et `features` sont des JSONB volontairement : ce sont des données
    de configuration, pas de la structure. `version` est incrémenté à chaque
    modification ; l'abonnement fige sa propre copie (`Abonnement.plan_fige`),
    donc changer un plan ne réécrit pas rétroactivement les contrats en cours.
    """

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prix: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    periodicite: Mapped[PeriodeFacturation] = mapped_column(
        Enum(PeriodeFacturation, name="periode_facturation"),
        default=PeriodeFacturation.MENSUEL,
        nullable=False,
    )
    devise: Mapped[str] = mapped_column(String(3), default="XOF", nullable=False)

    quotas: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # `plan_defaut=True` : appliqué par le script de rattrapage aux cabinets
    # existants qui n'ont pas encore d'abonnement (cf. §9 de l'état des lieux).
    plan_defaut: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # Durée d'essai proposée à l'onboarding public, en jours.
    jours_essai: Mapped[int] = mapped_column(Integer, default=14, nullable=False)


class PlanRevision(PlatformBase, UUIDMixin):
    """Instantané immuable d'une version de plan, conservé pour l'audit."""

    __tablename__ = "plan_revisions"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    instantane: Mapped[dict] = mapped_column(JSONB, nullable=False)
    motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    auteur: Mapped[str] = mapped_column(String(150), nullable=False)


class Abonnement(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Abonnement d'un cabinet — un seul par tenant (contrainte d'unicité).

    `plan_fige` conserve le quota, le prix et les fonctionnalités au moment de
    la souscription. C'est ce qui rend la version des plans inoffensive : le
    contrat continue de s'appliquer même après une hausse de tarif.
    """

    __tablename__ = "abonnements"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    statut: Mapped[StatutAbonnement] = mapped_column(
        Enum(StatutAbonnement, name="statut_abonnement"),
        default=StatutAbonnement.ESSAI,
        nullable=False,
        index=True,
    )
    plan_fige: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    date_debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, nullable=False)
    date_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_debut_essai: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_fin_essai: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    renouvellement_auto: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    numero_abonnement: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)


class AbonnementHistorique(PlatformBase, UUIDMixin):
    """Historique des changements de plan / statut d'un abonnement."""

    __tablename__ = "abonnement_historique"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False, index=True
    )
    abonnement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("abonnements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    avant: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    apres: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    auteur: Mapped[str] = mapped_column(String(150), nullable=False)


class FacturePlateforme(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Facture de l'éditeur adressée au cabinet (hors TVA, hors-regulation).

    `reference_externe` est le point d'accroche d'un futur prestataire de
    paiement : le statut est alors réconcilié depuis une notification signée,
    jamais déduit d'un retour de navigateur.
    """

    __tablename__ = "factures_plateforme"

    numero: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    abonnement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("abonnements.id", ondelete="SET NULL"), nullable=True
    )
    lignes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    devise: Mapped[str] = mapped_column(String(3), default="XOF", nullable=False)
    statut: Mapped[StatutFacturePlateforme] = mapped_column(
        Enum(StatutFacturePlateforme, name="statut_facture_plateforme"),
        default=StatutFacturePlateforme.BROUILLON,
        nullable=False,
        index=True,
    )
    periode_debut: Mapped[date | None] = mapped_column(Date, nullable=True)
    periode_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_emission: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_echeance: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    date_paiement: Mapped[date | None] = mapped_column(Date, nullable=True)
    moyen_paiement: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_externe: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# ==============================================================================
# ACCÈS SUPPORT (Phase D)
# ==============================================================================


class AccesSupport(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Demande d'accès au dossier d'un cabinet par un agent de la plateforme.

    Chaque ligne est révocable INDÉPENDAMMENT et c'est ce qui permet de
    répondre « qui a accès, là, maintenant ? » sans analyser les journaux.
    """

    __tablename__ = "acces_support"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agent_email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    motif: Mapped[str] = mapped_column(Text, nullable=False)
    ticket: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    lecture_seule: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    statut: Mapped[StatutAccesSupport] = mapped_column(
        Enum(StatutAccesSupport, name="statut_acces_support"),
        default=StatutAccesSupport.ACTIF,
        nullable=False,
        index=True,
    )
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoque_par: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revoque_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motif_revoque: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # Le tenant est-il informé de l'accès ? Configurable, et tracé dans tous les cas.
    admin_notifie: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# ==============================================================================
# SUPERVISION (Phase E)
# ==============================================================================


class JournalAuditPlateforme(PlatformBase, UUIDMixin):
    """
    Journal d'audit de la console — APPEND-ONLY.

    Aucune route ne permet la modification ou la suppression d'une entrée, et la
    migration Alembic installe un déclencheur PostgreSQL qui lève une exception
    sur `UPDATE`/`DELETE`, y compris pour un script ou un `psql` maladroit.
    L'application ne dispose d'aucun `session.delete()` sur cette table : c'est
    une contrainte de base, pas une discipline de code.
    """

    __tablename__ = "journal_audit_plateforme"

    horodatage: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False, index=True
    )
    acteur_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    acteur_email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    type_cible: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    cible_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    avant: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    apres: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    motif: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class StatsTenant(PlatformBase, UUIDMixin):
    """
    Agrégats d'usage par tenant et par jour (Phase E.1).

    Une seule ligne (tenant, jour) : la consultation de supervision ne fait donc
    jamais de requête sur les bases clients, et le coût par requête est
    borné par le nombre de tenants, pas par le nombre de patients.
    """

    __tablename__ = "stats_tenant"

    __table_args__ = (UniqueConstraint("tenant_id", "jour", name="uq_stats_tenant_jour"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    jour: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    utilisateurs_actifs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sites: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    praticiens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    patients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rendez_vous_periode: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stockage_octets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sms_envoyes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    factures_creees: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    derniere_activite: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calcule_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_maintenant, nullable=False
    )


class Annonce(PlatformBase, UUIDMixin, TimestampMixin):
    """Annonce plateforme affichée en bannière par l'application cliente."""

    __tablename__ = "annonces"

    titre: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type_annonce: Mapped[TypeAnnonce] = mapped_column(
        Enum(TypeAnnonce, name="type_annonce"), default=TypeAnnonce.INFO, nullable=False
    )
    debut: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Ciblage : liste de codes de plans et/ou liste d'UUID de tenants. Vide = tous.
    plans_cibles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tenants_cibles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    cree_par: Mapped[str | None] = mapped_column(String(150), nullable=True)


# ==============================================================================
# GABARITS DE SEMIS & ONBOARDING (Phases B.6 et F)
# ==============================================================================


class GabaritSemis(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Gabarit versionné copié dans chaque nouveau cabinet (Phase B.6).

    Remplace le code en dur : `FORMULAIRE_DENTAIRE` et la matrice RBAC étaient
    figés dans le dépôt, ce qui rendait impossible de corriger la nomenclature de
    base d'un client sans redéploiement. Ici, l'équipe éditrice publie une
    version et les prochains cabinets la reçoivent — les cabinets déjà
    provisionnés ne bougent pas, ce qui est le comportement attendu.
    """

    __tablename__ = "gabarits_semis"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_gabarit_code_version"),)

    code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    type_gabarit: Mapped[TypeGabarit] = mapped_column(
        Enum(TypeGabarit, name="type_gabarit"), default=TypeGabarit.PARAMETRES, nullable=False, index=True
    )
    libelle: Mapped[str] = mapped_column(String(120), nullable=False)
    contenu: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    cree_par: Mapped[str | None] = mapped_column(String(150), nullable=True)


class JetonUsageUnique(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Jeton à usage unique (vérification e-mail/téléphone, invitation admin).

    Le jeton n'est stocké que **haché** (SHA-256) : une lecture de la base ne
    permet ni de vérifier une adresse ni de prendre la main sur un cabinet.
    """

    __tablename__ = "jetons_usage_unique"

    usage: Mapped[UsageJeton] = mapped_column(
        Enum(UsageJeton, name="usage_jeton"), nullable=False, index=True
    )
    hash_jeton: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cible_type: Mapped[str] = mapped_column(String(40), nullable=False)
    cible_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    utilise: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    utilise_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)


class InscriptionOnboarding(PlatformBase, UUIDMixin, TimestampMixin):
    """
    Demande d'inscription publique (Phase F).

    Tant que `email_verifie` est faux, le cabinet existe côté plateforme mais sa
    connexion côté client est refusée : un cabinet ne doit pas pouvoir se
    servir d'une adresse qui n'est pas la sienne.
    """

    __tablename__ = "inscriptions_onboarding"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    statut: Mapped[StatutInscription] = mapped_column(
        Enum(StatutInscription, name="statut_inscription"),
        default=StatutInscription.EN_ATTENTE_VERIFICATION,
        nullable=False,
        index=True,
    )
    email_verifie: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telephone_verifie: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    verifie_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)