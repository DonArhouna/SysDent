"""
Rôles et permissions À L'INTÉRIEUR d'un cabinet, pilotés depuis la console.

**La seule écriture de la console dans une base cliente** en dehors du
provisionnement. Elle rompt volontairement l'étanchéité console/cabinets, et
c'est pourquoi elle est encadrée :

- droit dédié `platform.tenants.rbac`, sensible, accordé au seul Super Admin ;
- motif obligatoire ;
- trace **dans les deux journaux** : celui de la console (qui a agi) et celui du
  cabinet (ce qui a changé chez lui) - l'administrateur du cabinet doit pouvoir
  voir qu'un changement ne vient pas de son équipe ;
- mêmes garde-fous que l'application cliente : `RbacService` est réutilisé tel
  quel, et seules les permissions du catalogue peuvent être accordées.

`ADMIN_CABINET` et `SUPER_ADMIN` ne passent pas par les permissions (ils les
court-circuitent, cf. `ROLES_SANS_CONTROLE_PERMISSIONS`) : les modifier ne
changerait rien, et retirer à `ADMIN_CABINET` est refusé par le service. Ils
sont donc protégés ici dans les deux sens.

Les permissions vivent dans le jeton de l'utilisateur : un changement s'applique
à sa prochaine connexion ou au renouvellement de sa session.
"""

import uuid
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.permissions import (
    CATALOGUE_PERMISSIONS,
    ROLES_SANS_CONTROLE_PERMISSIONS,
    format_permission,
)
from src.core.database import tenant_db_manager
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.platform.services.journal import JournalService

logger = structlog.get_logger(__name__)


class RbacCabinetService:
    @staticmethod
    async def _session(tenant_id: uuid.UUID):
        """Session sur la base du cabinet ; le nom de base vient du registre master."""
        try:
            fabrique = await tenant_db_manager.get_session_factory(str(tenant_id))
        except Exception as exc:  # registre absent, base introuvable
            raise EntityNotFoundException("Base du cabinet", str(tenant_id)) from exc
        return fabrique()

    @staticmethod
    async def lire(tenant_id: uuid.UUID) -> Dict[str, Any]:
        """Matrice du cabinet : ses rôles, leurs permissions, et le catalogue accordable."""
        from src.modules.rbac.services import RbacService
        from src.modules.tenants.models import Permission

        async with await RbacCabinetService._session(tenant_id) as session:
            roles = await RbacService.lister_roles(session)
            lignes = (
                await session.execute(select(Permission).order_by(Permission.module, Permission.action))
            ).scalars().all()

        connues = {(l.module, l.action): l.description for l in lignes}
        catalogue = [
            {
                "code": format_permission(module, action),
                "module": module,
                "action": action,
                "description": connues.get((module, action)),
                # Au catalogue du code mais absente de la base de ce cabinet :
                # semée par une version plus récente. Non accordable tant que
                # la base n'est pas réalignée.
                "disponible": (module, action) in connues,
            }
            for module, action in CATALOGUE_PERMISSIONS
        ]
        for role in roles:
            role["modifiable"] = role["nom"] not in ROLES_SANS_CONTROLE_PERMISSIONS
        return {"roles": roles, "catalogue": catalogue}

    @staticmethod
    async def modifier(
        platform_db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: str,
        permission: str,
        accorder: bool,
        motif: str,
        auteur_email: str,
        auteur_id: Optional[uuid.UUID] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> List[str]:
        """
        Accorde ou retire `permission` (« MODULE:ACTION ») au rôle, et renvoie
        les permissions du rôle après modification.

        Ordre : le journal de la console est écrit (non validé), puis la base du
        cabinet est modifiée et validée, puis la console valide. Un échec côté
        cabinet annule donc aussi l'entrée de la console : on ne journalise pas
        un changement qui n'a pas eu lieu.
        """
        from src.modules.audit.services import AuditService
        from src.modules.rbac.services import RbacService
        from src.modules.tenants.models import Role

        module, _, action = permission.partition(":")
        if (module, action) not in CATALOGUE_PERMISSIONS:
            raise BusinessRuleViolationException(
                f"Permission inconnue du catalogue : {permission}.", code="PERMISSION_INCONNUE"
            )

        async with await RbacCabinetService._session(tenant_id) as session:
            role = (await session.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
            if role is None:
                raise EntityNotFoundException("Rôle", role_id)
            if role.nom in ROLES_SANS_CONTROLE_PERMISSIONS:
                raise BusinessRuleViolationException(
                    f"Le rôle {role.nom} a tous les droits par construction : ses permissions "
                    "ne se modifient pas.",
                    code="ROLE_PROTEGE",
                )

            avant = await RbacService.permissions_d_un_role(session, role_id)
            if (permission in avant) == accorder:
                return avant  # déjà dans l'état demandé : rien à journaliser

            await JournalService.journaliser(
                platform_db,
                action="PLATFORM_CABINET_RBAC_MODIFIE",
                type_cible="TENANT",
                cible_id=str(tenant_id),
                tenant_id=tenant_id,
                acteur_email=auteur_email,
                acteur_id=auteur_id,
                avant={"role": role.nom, "permission": permission, "accordee": not accorder},
                apres={"role": role.nom, "permission": permission, "accordee": accorder},
                motif=motif,
                ip_address=ip,
                user_agent=user_agent,
            )

            if accorder:
                await RbacService.accorder_permission(session, role_id, module, action)
            else:
                await RbacService.retirer_permission(session, role_id, module, action)

            await AuditService.log_action(
                session,
                action="RBAC_MODIFIE_PAR_PLATEFORME",
                resource_type="ROLE",
                resource_id=role_id,
                # Pas d'utilisateur du cabinet : l'auteur est un compte éditeur,
                # préfixé pour ne jamais se confondre avec un membre de l'équipe.
                user_email=f"console:{auteur_email}",
                changes={
                    "role": role.nom,
                    "permission": permission,
                    "operation": "accordee" if accorder else "retiree",
                    "motif": motif,
                },
                ip_address=ip,
                user_agent=user_agent,
            )
            apres = await RbacService.permissions_d_un_role(session, role_id)
            await session.commit()

        await platform_db.commit()
        logger.info(
            "cabinet_rbac_modifie",
            tenant_id=str(tenant_id),
            role=role.nom,
            permission=permission,
            accordee=accorder,
            auteur=auteur_email,
        )
        return apres
