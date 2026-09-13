from datetime import datetime, timezone
from typing import List, Tuple
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.database import tenant_db_manager
from src.core.exceptions import AuthenticationException
from src.core.security import decrypt_secret, verify_password
from src.modules.master.models import Societe, TenantDB
from src.modules.tenants.models import PermissionRole, Role, Utilisateur

logger = structlog.get_logger(__name__)


class AuthService:
    @staticmethod
    async def authenticate(
        email: str,
        password: str,
        master_db: AsyncSession,
    ) -> Tuple[Utilisateur, str, List[str]]:
        """
        Résout le cabinet rattaché à l'email puis valide le mot de passe dans sa base tenant.

        Il n'existe pas (encore) d'index email -> société en base Master : on parcourt les
        sociétés actives et on interroge chaque base tenant jusqu'à trouver l'utilisateur.
        Acceptable au volume actuel ; à remplacer par une table d'index dès que les migrations
        Alembic (Chantier 1) permettent d'ajouter ce nouveau schéma proprement.
        """
        stmt = (
            select(TenantDB)
            .join(Societe, Societe.id == TenantDB.societe_id)
            .where(TenantDB.statut == "ACTIVE", Societe.actif == True)
        )
        result = await master_db.execute(stmt)
        tenant_configs = result.scalars().all()

        for tenant_config in tenant_configs:
            tenant_id = str(tenant_config.societe_id)
            tenant_db_manager.get_or_create_engine(
                tenant_id=tenant_id,
                db_name=tenant_config.db_name,
                host=tenant_config.db_host,
                port=tenant_config.db_port,
                user=tenant_config.db_user,
                password=decrypt_secret(tenant_config.db_password),
            )
            session_factory = tenant_db_manager.get_session_factory(tenant_id)

            async with session_factory() as tenant_session:
                stmt_user = (
                    select(Utilisateur)
                    .options(
                        selectinload(Utilisateur.role)
                        .selectinload(Role.permission_roles)
                        .selectinload(PermissionRole.permission)
                    )
                    .where(Utilisateur.email == email.lower(), Utilisateur.actif == True)
                )
                user_result = await tenant_session.execute(stmt_user)
                user = user_result.scalar_one_or_none()

                if not user:
                    continue

                if not verify_password(password, user.mot_de_passe):
                    logger.warning("login_wrong_password", email=email, tenant_id=tenant_id)
                    raise AuthenticationException("Email ou mot de passe incorrect.", code="INVALID_CREDENTIALS")

                user.dernier_login = datetime.now(timezone.utc)
                await tenant_session.commit()

                permissions = sorted(
                    {
                        f"{pr.permission.module}:{pr.permission.action}"
                        for pr in user.role.permission_roles
                    }
                )
                return user, tenant_id, permissions

        raise AuthenticationException("Email ou mot de passe incorrect.", code="INVALID_CREDENTIALS")
