from datetime import datetime, timezone
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.common.base_model import Base, TimestampMixin, UUIDMixin


class Societe(Base, UUIDMixin, TimestampMixin):
    """
    Table centrale dans la DB Master représentant une structure / cabinet juridique / groupe de cliniques.
    Chaque société possède son propre dossier (Base de données PostgreSQL dédiée).
    """
    __tablename__ = "societes"

    nom: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    ninea: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adresse_siege: Mapped[str | None] = mapped_column(Text, nullable=True)
    ville: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pays: Mapped[str] = mapped_column(String(100), default="Sénégal", nullable=False)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    site_web: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant_db: Mapped["TenantDB"] = relationship("TenantDB", back_populates="societe", uselist=False, cascade="all, delete-orphan")


class TenantDB(Base, UUIDMixin, TimestampMixin):
    """
    Paramètres de connexion à la base de données dédiée d'un Tenant (Dossier).
    """
    __tablename__ = "tenants_db"

    societe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societes.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    db_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    db_host: Mapped[str] = mapped_column(String(150), default="localhost", nullable=False)
    db_port: Mapped[int] = mapped_column(Integer, default=5432, nullable=False)
    db_user: Mapped[str] = mapped_column(String(100), default="postgres", nullable=False)
    db_password: Mapped[str] = mapped_column(String(200), nullable=False)
    statut: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False) # ACTIVE, PROVISIONING, SUSPENDED, ARCHIVED
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)

    societe: Mapped[Societe] = relationship("Societe", back_populates="tenant_db")


class UtilisateurIndex(Base, UUIDMixin, TimestampMixin):
    """
    Index de routage email -> société, en base Master.

    Le login tenant consistait à parcourir TOUTES les bases de cabinets actives
    pour trouver l'utilisateur portant l'email : coût O(n.tenants) et une
    tentative de connexion sur chaque base, y compris celles d'autres clients.
    Cet index rend le login en une seule requête Master, sans jamais toucher aux
    bases d'un cabinet qui n'est pas concerné.

    L'email est la clé : deux cabinets ne peuvent pas partager le même compte,
    ce qui est la règle pour un déploiement multi-tenant.
    """

    __tablename__ = "utilisateur_index"

    email: Mapped[str] = mapped_column(String(150), primary_key=True)
    societe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    utilisateur_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    societe: Mapped[Societe] = relationship("Societe")


class SuperAdmin(Base, UUIDMixin, TimestampMixin):
    """
    Comptes d'administration globale du système (Accès Console Master).
    """
    __tablename__ = "super_admins"

    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    mot_de_passe: Mapped[str] = mapped_column(String(255), nullable=False)
    nom_complet: Mapped[str] = mapped_column(String(150), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Verrouillage progressif après N échecs de connexion (anti force brute).
    tentatives_echouees: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verrouille_jusqua: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dernier_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SuperAdminSession(Base, UUIDMixin, TimestampMixin):
    """
    Sessions persistées du Super Admin (révocables).

    Sans cette table, un access token de console Master restait valide jusqu'à
    15 minutes et un refresh token 7 jours, sans possibilité de révoquer un
    compte compromis.
    """

    __tablename__ = "super_admin_sessions"

    super_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("super_admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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

    super_admin: Mapped[SuperAdmin] = relationship("SuperAdmin")


class AuditLogGlobal(Base, UUIDMixin):
    """
    Journalisation des opérations critiques sur le serveur Master (provisionnement, suspension, backups).
    """
    __tablename__ = "audit_logs_global"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    auteur_email: Mapped[str] = mapped_column(String(150), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. TENANT_CREATE, TENANT_MIGRATE, TENANT_SUSPEND
    cible_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
