from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Conventions de nommage pour contraintes & index PostgreSQL
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe de base déclarative pour les modèles de la base MASTER (societes, tenants_db, super_admins, audit_logs_global)."""
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class TenantBase(DeclarativeBase):
    """
    Classe de base déclarative pour les modèles du schéma TENANT (patients, consultations, facturation...).
    Séparée de `Base` car les deux jeux de modèles finissent chargés dans le même process (master/services.py
    importe des modèles tenant) : un seul registre de métadonnées partagé ferait créer les tables tenant dans
    la base Master (et vice-versa) au premier `metadata.create_all`.
    """
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class PlatformBase(DeclarativeBase):
    """
    Classe de base déclarative des modèles de la PLATEFORME (backoffice éditeur).

    Troisième registre de métadonnées, après `Base` (master) et `TenantBase`
    (bases clients). Le même raisonnement que `TenantBase` s'applique, avec une
    contrainte supplémentaire : ces modèles vivent dans une base à part
    (`sysdent_platform`, décision D1), et aucune migration de la base master ou
    d'une base client ne doit pouvoir les voir.
    """
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class UUIDMixin:
    """Mixin ajoutant une clé primaire UUID v4."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """Mixin ajoutant les champs d'audit created_at et updated_at avec fuseau horaire UTC."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
