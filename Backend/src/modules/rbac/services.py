"""
Service RBAC : catalogue des permissions et matrice des rôles.

Les permissions d'un rôle sont stockées en base (table `permission_roles`) et non
calculées à la volée. Le catalogue de `src/common/permissions.py` sert de source
de vérité pour le seed initial et permet au Super Admin d'accorder une
permission à un rôle sans redéployer.

Conséquence importante : un rôle créé sans permission n'a aucun accès (les rôles
ADMIN_CABINET et SUPER_ADMIN sont les seules exceptions, court-circuités dans
`require_permissions`). Avant ce module, aucune permission n'était seedée : la
table était vide et tout rôle non-administrateur se heurtait à un 403 sur la
seule route `/audit` protégée.
"""

from typing import Dict, List, Optional
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.common.permissions import (
    CATALOGUE_PERMISSIONS,
    DESCRIPTIONS_ROLES,
    MATRICE_ROLES,
    NIVEAUX_HIERARCHIE,
    format_permission,
    permissions_for_role,
)
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.tenants.models import Permission, PermissionRole, Role

logger = structlog.get_logger(__name__)


class RbacService:
    @staticmethod
    async def semer_permissions(db: AsyncSession) -> int:
        """
        Insère le catalogue de permissions (idempotent).

        Idempotent : une permission déjà présente n'est pas dupliquée, ce qui
        permet de relancer le seed sur une base existante après une mise à jour
        du catalogue.
        """
        existantes = {
            (p.module, p.action) for p in (await db.execute(select(Permission))).scalars().all()
        }
        nouvelles = [p for p in CATALOGUE_PERMISSIONS if p not in existantes]

        for module, action in nouvelles:
            db.add(
                Permission(
                    module=module,
                    action=action,
                    description=f"Permission {action} sur le module {module}",
                )
            )
        await db.flush()

        if nouvelles:
            logger.info("rbac_permissions_semees", nombre=len(nouvelles))
        return len(nouvelles)

    @staticmethod
    async def semer_roles(db: AsyncSession) -> List[str]:
        """
        Crée les rôles métier du cabinet s'ils n'existent pas (idempotent).

        N'accorde AUCUNE permission : les liens rôle-permission sont créés par
        `appliquer_matrice_roles`. Les deux étapes sont séparées pour qu'un
        Super Admin puisse ajuster une matrice avant de l'appliquer.
        """
        crees: List[str] = []
        existants = {r.nom for r in (await db.execute(select(Role))).scalars().all()}

        for nom, description in DESCRIPTIONS_ROLES.items():
            if nom in existants:
                continue
            db.add(
                Role(
                    nom=nom,
                    description=description,
                    niveau_hierarchie=NIVEAUX_HIERARCHIE.get(nom, 3),
                )
            )
            crees.append(nom)

        await db.flush()
        if crees:
            logger.info("rbac_roles_crees", roles=crees)
        return crees

    @staticmethod
    async def appliquer_matrice_roles(db: AsyncSession, remplacer: bool = True) -> int:
        """
        Aligne les permissions de chaque rôle sur la matrice de référence.

        `remplacer=True` (défaut) : la matrice fait autorité. Les écarts introduits
        à la main sont écrasés, ce qui garantit qu'un rôle PRATICIEN n'accède pas
        à la facturation par accident.

        `remplacer=False` : seules les permissions manquantes sont ajoutées, ce qui
        permet de conserver un ajustement local sans le réécrire entièrement.
        """
        permissions = {
            (p.module, p.action): p for p in (await db.execute(select(Permission))).scalars().all()
        }
        roles = {r.nom: r for r in (await db.execute(select(Role))).scalars().all()}

        total = 0
        for nom_role, matrice in MATRICE_ROLES.items():
            role = roles.get(nom_role)
            if role is None:
                logger.warning("rbac_role_absent_ignore", role=nom_role)
                continue

            if remplacer:
                await db.execute(
                    delete(PermissionRole).where(PermissionRole.role_id == role.id)
                )
                await db.flush()

            existantes = {
                (pr.permission.module, pr.permission.action)
                for pr in (
                    await db.execute(
                        select(PermissionRole)
                        .options(selectinload(PermissionRole.permission))
                        .where(PermissionRole.role_id == role.id)
                    )
                ).scalars().all()
            }

            for module, action in matrice:
                if not remplacer and (module, action) in existantes:
                    continue
                permission = permissions.get((module, action))
                if permission is None:
                    logger.warning("rbac_permission_absente", module=module, action=action)
                    continue
                db.add(
                    PermissionRole(
                        role_id=role.id,
                        permission_id=permission.id,
                        scope="CABINET_LOCAL",
                    )
                )
                total += 1

        await db.flush()
        logger.info("rbac_matrice_appliquee", liens=total)
        return total

    @staticmethod
    async def bootstrap_complet(db: AsyncSession) -> Dict[str, int]:
        """
        Seed complet appelé au provisioning d'un cabinet : permissions, rôles, matrice.

        Ordre imposé : les permissions doivent exister avant les liens rôle-permission.
        """
        await RbacService.semer_permissions(db)
        await RbacService.semer_roles(db)
        liens = await RbacService.appliquer_matrice_roles(db)
        return {"permissions": len(CATALOGUE_PERMISSIONS), "roles": len(MATRICE_ROLES), "liens": liens}

    @staticmethod
    async def permissions_d_un_role(db: AsyncSession, role_id: str) -> List[str]:
        stmt = (
            select(Permission)
            .join(PermissionRole, PermissionRole.permission_id == Permission.id)
            .where(PermissionRole.role_id == role_id)
            .order_by(Permission.module, Permission.action)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [format_permission(r.module, r.action) for r in rows]

    @staticmethod
    async def lister_roles(db: AsyncSession) -> List[Dict]:
        """Rôles du cabinet avec leurs permissions, pour l'écran d'administration."""
        stmt = (
            select(Role)
            .options(selectinload(Role.permission_roles).selectinload(PermissionRole.permission))
            .order_by(Role.niveau_hierarchie, Role.nom)
        )
        roles = (await db.execute(stmt)).scalars().all()

        resultat: List[Dict] = []
        for role in roles:
            permissions = sorted(
                f"{pr.permission.module}:{pr.permission.action}"
                for pr in role.permission_roles
                if pr.permission is not None
            )
            resultat.append(
                {
                    "id": str(role.id),
                    "nom": role.nom,
                    "description": role.description,
                    "niveau_hierarchie": role.niveau_hierarchie,
                    "permissions": permissions,
                    "nb_utilisateurs": len(role.utilisateurs or []),
                }
            )
        return resultat

    @staticmethod
    async def accorder_permission(
        db: AsyncSession, role_id: str, module: str, action: str
    ) -> PermissionRole:
        """Accorde une permission à un rôle (usage console d'administration)."""
        role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
        if role is None:
            raise EntityNotFoundException("Rôle", role_id)

        permission = (
            await db.execute(
                select(Permission).where(Permission.module == module, Permission.action == action)
            )
        ).scalar_one_or_none()
        if permission is None:
            raise EntityNotFoundException("Permission", f"{module}:{action}")

        existant = (
            await db.execute(
                select(PermissionRole).where(
                    PermissionRole.role_id == role.id,
                    PermissionRole.permission_id == permission.id,
                )
            )
        ).scalar_one_or_none()
        if existant is not None:
            return existant

        lien = PermissionRole(role_id=role.id, permission_id=permission.id, scope="CABINET_LOCAL")
        db.add(lien)
        await db.flush()
        logger.info("rbac_permission_accordee", role=role.nom, permission=f"{module}:{action}")
        return lien

    @staticmethod
    async def retirer_permission(
        db: AsyncSession, role_id: str, module: str, action: str
    ) -> bool:
        """Retire une permission d'un rôle. Refusé sur ADMIN_CABINET."""
        role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
        if role is None:
            raise EntityNotFoundException("Rôle", role_id)

        if role.nom == "ADMIN_CABINET":
            raise BusinessRuleViolationException(
                "Les droits de l'administrateur de cabinet ne sont pas modifiables : "
                "c'est le rôle de secours d'un cabinet.",
                code="ROLE_PROTEGE",
            )

        permission = (
            await db.execute(
                select(Permission).where(Permission.module == module, Permission.action == action)
            )
        ).scalar_one_or_none()
        if permission is None:
            raise EntityNotFoundException("Permission", f"{module}:{action}")

        resultat = await db.execute(
            delete(PermissionRole).where(
                PermissionRole.role_id == role.id,
                PermissionRole.permission_id == permission.id,
            )
        )
        await db.flush()
        return int(resultat.rowcount or 0) > 0
