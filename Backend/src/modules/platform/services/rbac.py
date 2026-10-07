"""
RBAC de la console plateforme : amorçage du catalogue et de la matrice.

Même contrat que `src/modules/rbac/services.py` côté cabinet (idempotent, séparé
en trois étapes : permissions → rôles → liens), mais avec deux différences
volontaires :

- les rôles sont **liés** au catalogue par la matrice, jamais créés « armés » ;
- `SUPER_ADMIN_PLATEFORME` n'a **aucun** droit implicite. Côté client,
  `ADMIN_CABINET` court-circuite `require_permissions` par conception ; ici ce
  court-circuit est refusé, parce qu'un compte éditeur qui peut tout est un
  compte dont on ne peut pas réduire les droits.
"""

from typing import Dict, List

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.platform.models import (
    PermissionPlateforme,
    RolePlateforme,
    UtilisateurPlateforme,
    role_permissions,
    utilisateur_roles,
)
from src.modules.platform.permissions import (
    CATALOGUE_PERMISSIONS,
    DESCRIPTIONS_PERMISSIONS,
    DESCRIPTIONS_ROLES,
    MATRICE_ROLES,
    NIVEAUX_HIERARCHIE,
    PERMISSIONS_SENSIBLES,
    format_permission,
)

logger = structlog.get_logger(__name__)


class PlatformRbacService:
    @staticmethod
    async def semer_permissions(db: AsyncSession) -> int:
        """Insère le catalogue `platform.*` de façon idempotente."""
        existantes = {
            (p.ressource, p.action)
            for p in (await db.execute(select(PermissionPlateforme))).scalars().all()
        }
        nouvelles = [p for p in CATALOGUE_PERMISSIONS if p not in existantes]

        for ressource, action in nouvelles:
            code = format_permission(ressource, action)
            db.add(
                PermissionPlateforme(
                    ressource=ressource,
                    action=action,
                    code=code,
                    description=DESCRIPTIONS_PERMISSIONS.get(
                        (ressource, action), f"Permission {action} sur {ressource}"
                    ),
                    # Une permission qui touche un droit, un secret ou une
                    # suppression définitive est marquée sensible.
                    sensible=code in PERMISSIONS_SENSIBLES,
                )
            )
        await db.flush()
        if nouvelles:
            logger.info("plateforme_permissions_semees", nombre=len(nouvelles))
        return len(nouvelles)

    @staticmethod
    async def semer_roles(db: AsyncSession) -> List[str]:
        """Crée les cinq rôles système s'ils n'existent pas encore (idempotent)."""
        existants = {r.code for r in (await db.execute(select(RolePlateforme))).scalars().all()}
        crees: List[str] = []
        for code, libelle in DESCRIPTIONS_ROLES.items():
            if code in existants:
                continue
            db.add(
                RolePlateforme(
                    code=code,
                    libelle=libelle,
                    description=libelle,
                    niveau_hierarchie=NIVEAUX_HIERARCHIE.get(code, 10),
                    systeme=True,
                )
            )
            crees.append(code)
        await db.flush()
        if crees:
            logger.info("plateforme_roles_crees", roles=crees)
        return crees

    @staticmethod
    async def appliquer_matrice(db: AsyncSession, remplacer: bool = True) -> int:
        """
        Aligne les permissions de chaque rôle sur la matrice de référence.

        `remplacer=True` : la matrice fait autorité, les écarts manuels sont
        écrasés. Un rôle SUPPORT qui se serait vu accorder `platform.tenants.delete`
        par erreur redevient conforme au réalignement suivant.
        """
        permissions = {
            (p.ressource, p.action): p
            for p in (await db.execute(select(PermissionPlateforme))).scalars().all()
        }
        roles = {r.code: r for r in (await db.execute(select(RolePlateforme))).scalars().all()}

        total = 0
        for code_role, matrice in MATRICE_ROLES.items():
            role = roles.get(code_role)
            if role is None:
                logger.warning("plateforme_role_absent_ignore", role=code_role)
                continue

            if remplacer:
                await db.execute(delete(role_permissions).where(role_permissions.c.role_id == role.id))
                await db.flush()
                existantes: set = set()
            else:
                stmt_existantes = (
                    select(PermissionPlateforme.ressource, PermissionPlateforme.action)
                    .join(
                        role_permissions,
                        role_permissions.c.permission_id == PermissionPlateforme.id,
                    )
                    .where(role_permissions.c.role_id == role.id)
                )
                existantes = {
                    (r, a) for r, a in (await db.execute(stmt_existantes)).all()
                }

            for ressource, action in matrice:
                if not remplacer and (ressource, action) in existantes:
                    continue
                permission = permissions.get((ressource, action))
                if permission is None:
                    logger.warning(
                        "plateforme_permission_absente", ressource=ressource, action=action
                    )
                    continue
                await db.execute(
                    role_permissions.insert().values(role_id=role.id, permission_id=permission.id)
                )
                total += 1

        await db.flush()
        logger.info("plateforme_matrice_appliquee", liens=total)
        return total

    @staticmethod
    async def bootstrap_complet(db: AsyncSession) -> Dict[str, int]:
        """Ordre imposé : les permissions avant les liens rôle-permission."""
        await PlatformRbacService.semer_permissions(db)
        await PlatformRbacService.semer_roles(db)
        liens = await PlatformRbacService.appliquer_matrice(db)
        return {
            "permissions": len(CATALOGUE_PERMISSIONS),
            "roles": len(MATRICE_ROLES),
            "liens": liens,
        }

    @staticmethod
    async def lister_roles(db: AsyncSession) -> List[Dict[str, object]]:
        stmt = (
            select(RolePlateforme)
            .options(selectinload(RolePlateforme.permissions))
            .order_by(RolePlateforme.niveau_hierarchie, RolePlateforme.code)
        )
        roles = (await db.execute(stmt)).scalars().all()

        # Comptage des utilisateurs par rôle en UNE requête groupée. Un
        # `selectinload(RolePlateforme.utilisateurs)` chargerait tous les comptes
        # de la console (et leurs hachages) pour n'en garder que le compte ; le
        # COUNT groupé ne transporte que des entiers.
        stmt_comptage = (
            select(utilisateur_roles.c.role_id, func.count(UtilisateurPlateforme.id))
            .select_from(
                utilisateur_roles.join(
                    UtilisateurPlateforme,
                    UtilisateurPlateforme.id == utilisateur_roles.c.utilisateur_id,
                )
            )
            .group_by(utilisateur_roles.c.role_id)
        )
        comptages = {str(r): n for r, n in (await db.execute(stmt_comptage)).all()}

        return [
            {
                "id": str(role.id),
                "code": role.code,
                "libelle": role.libelle,
                "description": role.description,
                "niveau_hierarchie": role.niveau_hierarchie,
                "systeme": role.systeme,
                "permissions": sorted(p.code for p in role.permissions),
                "nb_utilisateurs": comptages.get(str(role.id), 0),
            }
            for role in roles
        ]

    @staticmethod
    async def permissions_utilisateur(db: AsyncSession, utilisateur_id) -> List[str]:
        """Permissions effectives d'un compte, déduites de ses rôles."""
        stmt = (
            select(PermissionPlateforme.code)
            .join(role_permissions, role_permissions.c.permission_id == PermissionPlateforme.id)
            .join(utilisateur_roles, utilisateur_roles.c.role_id == role_permissions.c.role_id)
            .where(utilisateur_roles.c.utilisateur_id == utilisateur_id)
            .distinct()
        )
        lignes = (await db.execute(stmt)).scalars().all()
        return sorted(lignes)

    @staticmethod
    async def roles_utilisateur(db: AsyncSession, utilisateur_id) -> List[str]:
        stmt = (
            select(RolePlateforme.code)
            .join(utilisateur_roles, utilisateur_roles.c.role_id == RolePlateforme.id)
            .where(utilisateur_roles.c.utilisateur_id == utilisateur_id)
        )
        return sorted((await db.execute(stmt)).scalars().all())