"""
Routes de consultation et d'ajustement des rôles (console d'administration du cabinet).

L'accès est régi par `ADMIN:READ` (lecture) et `ADMIN:UPDATE` (écriture), selon la
matrice de `src/common/permissions.py`.
"""

from typing import List
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from src.core.exceptions import BusinessRuleViolationException
from src.modules.auth.dependencies import (
    get_actor,
    get_current_user,
    get_tenant_db,
    require_permissions,
)
from src.modules.rbac.schemas import PermissionGrant, RoleCreate, RoleResponse
from src.modules.rbac.services import RbacService
from src.modules.tenants.models import Permission, Role, Utilisateur

router = APIRouter(prefix="/rbac", tags=["RBAC & Rôles"])


@router.get("/roles", response_model=APIResponse[List[RoleResponse]])
async def list_roles(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_actor),
    _: bool = Depends(require_permissions("ADMIN:READ")),
):
    """
    Liste les rôles du cabinet avec leurs permissions effectives.

    Route de diagnostic la plus utile du produit pour le support : « le compte
    du praticien a le bon rôle ? » se répond ici, sans toucher à une donnée
    patient. Elle accepte donc un jeton support (lecture seule).
    """
    roles = await RbacService.lister_roles(db)
    return APIResponse(data=roles)


@router.post("/roles", response_model=APIResponse[RoleResponse], status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ADMIN:UPDATE")),
):
    """
    Crée un rôle métier.

    Le rôle naît SANS permission : l'administrateur accorde ensuite les droits
    une par une. Créer un rôle déjà armchairé de ADMIN_CABINET serait une
    escalade de privilèges en une seule requête.
    """
    nom_normalise = data.nom.strip().upper()
    existant = (await db.execute(select(Role).where(Role.nom == nom_normalise))).scalar_one_or_none()
    if existant is not None:
        raise BusinessRuleViolationException(
            f"Le rôle '{nom_normalise}' existe déjà.", code="ROLE_DEJA_EXISTANT"
        )

    role = Role(
        nom=nom_normalise,
        description=data.description,
        niveau_hierarchie=data.niveau_hierarchie,
    )
    db.add(role)
    await db.commit()

    return APIResponse(
        message="Rôle créé. Accordez-lui les permissions nécessaires.",
        data=RoleResponse(
            id=str(role.id),
            nom=role.nom,
            description=role.description,
            niveau_hierarchie=role.niveau_hierarchie,
            permissions=[],
            nb_utilisateurs=0,
        ),
    )


@router.post("/roles/{role_id}/permissions", response_model=APIResponse[RoleResponse])
async def grant_permission(
    role_id: uuid.UUID,
    data: PermissionGrant,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ADMIN:UPDATE")),
):
    """Accorde une permission à un rôle (format MODULE:ACTION)."""
    await RbacService.accorder_permission(db, str(role_id), data.module, data.action)
    await db.commit()

    roles = await RbacService.lister_roles(db)
    cible = next((r for r in roles if r["id"] == str(role_id)), None)
    return APIResponse(
        message=f"Permission {data.module}:{data.action} accordée.",
        data=RoleResponse(**cible) if cible else None,
    )


@router.delete("/roles/{role_id}/permissions", response_model=APIResponse[RoleResponse])
async def revoke_permission(
    role_id: uuid.UUID,
    permission: str = Query(..., description="Permission au format MODULE:ACTION"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ADMIN:UPDATE")),
):
    """
    Retire une permission d'un rôle.

    L'opération est refusée sur ADMIN_CABINET : c'est le rôle de secours qui
    garantit qu'un cabinet ne peut pas se verrouiller hors de sa base.
    """
    grant = PermissionGrant.parse(permission)
    retiree = await RbacService.retirer_permission(db, str(role_id), grant.module, grant.action)
    await db.commit()

    if not retiree:
        raise BusinessRuleViolationException(
            f"Le rôle ne possède pas la permission '{permission}'.", code="PERMISSION_NON_ACCORDEE"
        )

    roles = await RbacService.lister_roles(db)
    cible = next((r for r in roles if r["id"] == str(role_id)), None)
    return APIResponse(
        message=f"Permission {permission} retirée.",
        data=RoleResponse(**cible) if cible else None,
    )


@router.get("/permissions", response_model=APIResponse[List[dict]])
async def list_permissions(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_actor),
    _: bool = Depends(require_permissions("ADMIN:READ")),
):
    """Catalogue des permissions disponibles, pour construire l'écran d'attribution."""
    stmt = select(Permission).order_by(Permission.module, Permission.action)
    permissions = (await db.execute(stmt)).scalars().all()
    return APIResponse(
        data=[
            {
                "module": p.module,
                "action": p.action,
                "description": p.description,
                "cle": f"{p.module}:{p.action}",
            }
            for p in permissions
        ]
    )
