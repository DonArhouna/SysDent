from typing import AsyncGenerator, Callable, List, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.database import MasterAsyncSessionFactory, get_master_db, tenant_db_manager
from src.core.exceptions import AuthenticationException, PermissionDeniedException, TenantNotFoundException
from src.core.security import decode_token, decrypt_secret
from src.modules.master.models import Societe, TenantDB
from src.modules.tenants.models import PermissionRole, Role, Utilisateur

security_scheme = HTTPBearer(auto_error=False)


async def get_token_payload(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """Extrait le token JWT soit du header Authorization: Bearer, soit des cookies HttpOnly."""
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise AuthenticationException("Jeton d'accès manquant. Veuillez vous connecter.")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationException("Type de jeton invalide. Access token requis.")
    return payload


async def get_current_tenant_id(
    payload: dict = Depends(get_token_payload),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
) -> str:
    """Détermine le tenant_id à partir du JWT ou du header."""
    tenant_id = payload.get("tenant_id") or x_tenant_id
    if not tenant_id:
        raise TenantNotFoundException("Aucun cabinet associé à cette session.")
    return str(tenant_id)


async def get_tenant_db(
    tenant_id: str = Depends(get_current_tenant_id),
    master_db: AsyncSession = Depends(get_master_db),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance FastAPI fournissant une session DB asynchrone pointant vers le bon Tenant.
    Recherche d'abord la configuration de la DB dans Master (ou cache) et fournit la session.
    """
    stmt = (
        select(TenantDB)
        .where(TenantDB.societe_id == tenant_id, TenantDB.statut == "ACTIVE")
    )
    result = await master_db.execute(stmt)
    tenant_db_config = result.scalar_one_or_none()

    if not tenant_db_config:
        # Fallback pour le dev ou convention standard
        db_name = f"sysdent_tenant_{tenant_id}"
        session_factory = tenant_db_manager.get_session_factory(tenant_id)
    else:
        tenant_db_manager.get_or_create_engine(
            tenant_id=str(tenant_db_config.societe_id),
            db_name=tenant_db_config.db_name,
            host=tenant_db_config.db_host,
            port=tenant_db_config.db_port,
            user=tenant_db_config.db_user,
            password=decrypt_secret(tenant_db_config.db_password),
        )
        session_factory = tenant_db_manager.get_session_factory(str(tenant_db_config.societe_id))

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    tenant_db: AsyncSession = Depends(get_tenant_db),
) -> Utilisateur:
    """Récupère l'utilisateur connecté depuis la base du Tenant avec son Rôle et ses Permissions."""
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationException("Identifiant utilisateur absent du jeton.")

    stmt = (
        select(Utilisateur)
        .options(
            selectinload(Utilisateur.role).selectinload(Role.permission_roles).selectinload(PermissionRole.permission)
        )
        .where(Utilisateur.id == user_id, Utilisateur.actif == True)
    )
    result = await tenant_db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationException("Utilisateur introuvable ou compte désactivé.")
    return user


def require_permissions(*required_permissions: str) -> Callable:
    """Garde de sécurité RBAC vérifiant si l'utilisateur possède toutes les permissions requises."""
    async def permission_checker(payload: dict = Depends(get_token_payload)) -> bool:
        user_permissions = payload.get("permissions", [])
        role = payload.get("role")

        # Les administrateurs de cabinet ont tous les droits par défaut
        if role in ["SUPER_ADMIN", "ADMIN_CABINET"]:
            return True

        for perm in required_permissions:
            if perm not in user_permissions:
                raise PermissionDeniedException(
                    f"Permission requise manquante : '{perm}'."
                )
        return True

    return permission_checker
