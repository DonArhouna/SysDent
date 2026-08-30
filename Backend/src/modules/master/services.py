import re
import uuid
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from src.core.config import settings
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.core.security import get_password_hash
from src.modules.master.models import AuditLogGlobal, Societe, TenantDB
from src.modules.master.schemas import SocieteCreate, SocieteUpdate
from src.modules.tenants.models import Role, Utilisateur

logger = structlog.get_logger(__name__)


def sanitize_db_name(name: str) -> str:
    """Génère un nom de base PostgreSQL valide et sécurisé."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower().strip())
    return f"sysdent_tenant_{clean[:30]}_{uuid.uuid4().hex[:6]}"


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
            db_password=settings.TENANT_DB_PASSWORD,
            statut="ACTIVE",
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
