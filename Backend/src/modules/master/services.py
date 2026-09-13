import asyncio
import re
import uuid
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from src.core.config import settings
from src.core.database import tenant_db_manager
from src.core.exceptions import AppException, BusinessRuleViolationException, EntityNotFoundException
from src.core.migrations import upgrade_tenant_to_head
from src.core.security import encrypt_secret, get_password_hash
from src.modules.master.models import AuditLogGlobal, Societe, TenantDB
from src.modules.master.schemas import SocieteCreate, SocieteUpdate
from src.modules.tenants.models import Role, Utilisateur

logger = structlog.get_logger(__name__)


def sanitize_db_name(name: str) -> str:
    """Génère un nom de base PostgreSQL valide et sécurisé."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower().strip())
    return f"sysdent_tenant_{clean[:30]}_{uuid.uuid4().hex[:6]}"


async def _create_physical_database(db_name: str) -> None:
    """
    Exécute un CREATE DATABASE réel sur le serveur PostgreSQL des tenants.
    CREATE DATABASE ne peut pas tourner dans une transaction : on utilise une connexion
    autocommit, courte durée de vie, vers la base de maintenance `postgres`.
    """
    maintenance_url = (
        f"postgresql+asyncpg://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
        f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/postgres"
    )
    admin_engine: AsyncEngine = create_async_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            )
            if not exists.scalar_one_or_none():
                # db_name provient uniquement de sanitize_db_name() ([a-z0-9_] + uuid) : pas d'injection possible.
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("tenant_database_created", db_name=db_name)
    finally:
        await admin_engine.dispose()


async def _bootstrap_tenant_schema_and_admin(societe_id: uuid.UUID, db_name: str, data: SocieteCreate) -> None:
    """Crée le schéma applicatif sur la nouvelle base tenant (via Alembic) et le premier compte administrateur du cabinet."""
    tenant_sync_url = (
        f"postgresql+psycopg2://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
        f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/{db_name}"
    )
    # Alembic est synchrone : on l'exécute dans un thread pour ne pas bloquer l'event loop asyncio.
    await asyncio.to_thread(upgrade_tenant_to_head, tenant_sync_url)

    tenant_db_manager.get_or_create_engine(
        tenant_id=str(societe_id),
        db_name=db_name,
        host=settings.TENANT_DB_HOST,
        port=settings.TENANT_DB_PORT,
        user=settings.TENANT_DB_USER,
        password=settings.TENANT_DB_PASSWORD,
    )
    session_factory = tenant_db_manager.get_session_factory(str(societe_id))
    async with session_factory() as tenant_session:
        admin_role = Role(
            nom="ADMIN_CABINET",
            description="Administrateur du cabinet (accès complet)",
            niveau_hierarchie=1,
        )
        tenant_session.add(admin_role)
        await tenant_session.flush()

        admin_user = Utilisateur(
            email=data.admin_email.lower(),
            mot_de_passe=get_password_hash(data.admin_password),
            role_id=admin_role.id,
            prenom=data.admin_prenom,
            nom=data.admin_nom,
            actif=True,
        )
        tenant_session.add(admin_user)
        await tenant_session.commit()


class MasterTenantService:
    @staticmethod
    async def create_societe_and_provision_tenant(
        session: AsyncSession,
        data: SocieteCreate,
        client_ip: str = "unknown",
    ) -> Societe:
        # Vérification si NINEA existe déjà
        if data.ninea:
            stmt = select(Societe).where(Societe.ninea == data.ninea)
            res = await session.execute(stmt)
            if res.scalar_one_or_none():
                raise BusinessRuleViolationException("Une société avec ce numéro NINEA existe déjà.")

        # 1. Création de l'entité Société dans Master
        societe = Societe(
            nom=data.nom,
            ninea=data.ninea,
            logo_url=data.logo_url,
            adresse_siege=data.adresse_siege,
            ville=data.ville,
            pays=data.pays or "Sénégal",
            telephone=data.telephone,
            email=data.email,
            site_web=data.site_web,
            actif=True,
        )
        session.add(societe)
        await session.flush()

        # 2. Définition du nom et paramètres de la base de données dédiée
        db_name = sanitize_db_name(data.nom)
        tenant_db = TenantDB(
            societe_id=societe.id,
            db_name=db_name,
            db_host=settings.TENANT_DB_HOST,
            db_port=settings.TENANT_DB_PORT,
            db_user=settings.TENANT_DB_USER,
            db_password=encrypt_secret(settings.TENANT_DB_PASSWORD),
            statut="PROVISIONING",
            schema_version="1.0.0",
        )
        session.add(tenant_db)

        # 3. Log d'audit Master
        audit = AuditLogGlobal(
            auteur_email="system@sysdent.pro",
            action="TENANT_PROVISION_INIT",
            cible_id=str(societe.id),
            details={"nom": societe.nom, "db_name": db_name, "admin_email": data.admin_email},
            ip_address=client_ip,
        )
        session.add(audit)

        await session.commit()
        await session.refresh(societe)

        # 4. Provisionnement réel : création de la base physique, du schéma et de l'admin cabinet.
        # Fait après le commit ci-dessus pour que la Société existe déjà en base même si cette
        # étape échoue (statut reste "PROVISIONING", visible et reprenable manuellement).
        try:
            await _create_physical_database(db_name)
            await _bootstrap_tenant_schema_and_admin(societe.id, db_name, data)
        except Exception as e:
            logger.exception("tenant_provisioning_failed", societe_id=str(societe.id), db_name=db_name, error=str(e))
            raise AppException(
                message=(
                    f"La société '{societe.nom}' a été enregistrée mais le provisionnement de sa base de "
                    "données a échoué. Statut laissé à PROVISIONING pour reprise manuelle."
                ),
                code="TENANT_PROVISIONING_FAILED",
                status_code=500,
                details={"societe_id": str(societe.id), "db_name": db_name},
            ) from e

        tenant_db.statut = "ACTIVE"
        session.add(tenant_db)
        await session.commit()

        logger.info(
            "tenant_provisioned_successfully",
            societe_id=str(societe.id),
            db_name=db_name,
            nom=societe.nom,
        )
        return societe

    @staticmethod
    async def get_all_societes(session: AsyncSession) -> list[Societe]:
        stmt = select(Societe).order_by(Societe.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_societe_by_id(session: AsyncSession, societe_id: uuid.UUID) -> Societe:
        stmt = select(Societe).where(Societe.id == societe_id)
        result = await session.execute(stmt)
        societe = result.scalar_one_or_none()
        if not societe:
            raise EntityNotFoundException("Société", societe_id)
        return societe
