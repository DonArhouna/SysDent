"""
Rôles et permissions d'un cabinet, depuis la console.

Lecture : `platform.tenants.read`. Écriture : `platform.tenants.rbac`, droit
sensible du seul Super Admin. Voir `services/rbac_cabinet.py` pour les règles.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.schemas import APIResponse
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import (
    client_ip,
    exiger_ip_autorisee,
    refuser_acces_client,
    require_platform_permissions,
)
from src.modules.platform.models import UtilisateurPlateforme
from src.modules.platform.schemas import (
    ActionAccesAdminRequest,
    ActionAccesAdminResponse,
    AdminCabinetResponse,
    ChangementEmailAdminRequest,
    MatriceCabinetResponse,
    ModificationPermissionCabinet,
    PermissionsRoleCabinetResponse,
)
from src.modules.platform.services.acces_cabinet import AccesCabinetService, changer_email_admin
from src.modules.platform.services.rbac_cabinet import RbacCabinetService

platform_rbac_cabinet_router = APIRouter(
    prefix="/platform/tenants", tags=["Platform · Tenants (cycle de vie)"]
)


@platform_rbac_cabinet_router.get(
    "/{tenant_id}/rbac",
    response_model=APIResponse[MatriceCabinetResponse],
    summary="Rôles et permissions d'un cabinet",
)
async def lire_matrice(
    tenant_id: uuid.UUID,
    request: Request,
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.read")),
):
    """Rôles du cabinet avec leurs permissions, et le catalogue des permissions accordables."""
    refuser_acces_client(request)
    return APIResponse(data=MatriceCabinetResponse(**await RbacCabinetService.lire(tenant_id)))


async def _modifier(
    tenant_id: uuid.UUID,
    role_id: str,
    data: ModificationPermissionCabinet,
    accorder: bool,
    request: Request,
    db: AsyncSession,
    auteur: UtilisateurPlateforme,
) -> APIResponse[PermissionsRoleCabinetResponse]:
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)
    permissions = await RbacCabinetService.modifier(
        db,
        tenant_id,
        role_id,
        data.permission,
        accorder=accorder,
        motif=data.motif,
        auteur_email=auteur.email,
        auteur_id=auteur.id,
        ip=ip or client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return APIResponse(
        message="Permission accordée." if accorder else "Permission retirée.",
        data=PermissionsRoleCabinetResponse(role_id=role_id, permissions=permissions),
    )


@platform_rbac_cabinet_router.post(
    "/{tenant_id}/rbac/roles/{role_id}/permissions",
    response_model=APIResponse[PermissionsRoleCabinetResponse],
    summary="Accorder une permission à un rôle du cabinet",
    responses={422: {"description": "Rôle protégé ou permission hors catalogue"}},
)
async def accorder(
    tenant_id: uuid.UUID,
    role_id: str,
    data: ModificationPermissionCabinet,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.rbac")),
):
    """Trace dans le journal de la console ET dans celui du cabinet. Motif obligatoire."""
    return await _modifier(tenant_id, role_id, data, True, request, db, auteur)


@platform_rbac_cabinet_router.post(
    "/{tenant_id}/rbac/roles/{role_id}/permissions/retrait",
    response_model=APIResponse[PermissionsRoleCabinetResponse],
    summary="Retirer une permission à un rôle du cabinet",
    responses={422: {"description": "Rôle protégé ou permission hors catalogue"}},
)
async def retirer(
    tenant_id: uuid.UUID,
    role_id: str,
    data: ModificationPermissionCabinet,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.rbac")),
):
    """Trace dans le journal de la console ET dans celui du cabinet. Motif obligatoire."""
    return await _modifier(tenant_id, role_id, data, False, request, db, auteur)


# ── Accès des administrateurs du cabinet ──────────────────────────────────────


@platform_rbac_cabinet_router.get(
    "/{tenant_id}/administrateurs",
    response_model=APIResponse[List[AdminCabinetResponse]],
    summary="Administrateurs d'un cabinet",
)
async def lister_administrateurs(
    tenant_id: uuid.UUID,
    request: Request,
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.read")),
):
    """Comptes administrateurs du cabinet : état d'activation, de la 2FA, dernière connexion."""
    refuser_acces_client(request)
    return APIResponse(
        data=[AdminCabinetResponse(**a) for a in await AccesCabinetService.lister_admins(tenant_id)]
    )


@platform_rbac_cabinet_router.post(
    "/{tenant_id}/administrateurs/{utilisateur_id}/acces",
    response_model=APIResponse[ActionAccesAdminResponse],
    summary="Réinitialiser l'accès d'un administrateur du cabinet",
    responses={422: {"description": "Compte hors périmètre, ou e-mail non envoyé"}},
)
async def reinitialiser_acces_admin(
    tenant_id: uuid.UUID,
    utilisateur_id: uuid.UUID,
    data: ActionAccesAdminRequest,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.reset_access")),
):
    """
    `lien` (recommandé), `temporaire` (rendu une fois, changement imposé) ou
    `deux_facteurs` (téléphone perdu). Sessions coupées, motif journalisé dans
    la console et dans le cabinet. Aucun mot de passe choisi par un agent.
    """
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)
    resultat = await AccesCabinetService.agir(
        db,
        tenant_id,
        utilisateur_id,
        data.action,
        data.motif,
        auteur_email=auteur.email,
        auteur_id=auteur.id,
        ip=ip or client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return APIResponse(
        message=resultat["message"].capitalize() + ".",
        data=ActionAccesAdminResponse(
            compte=AdminCabinetResponse(**resultat["compte"]),
            mot_de_passe_temporaire=resultat["mot_de_passe_temporaire"],
        ),
    )


@platform_rbac_cabinet_router.post(
    "/{tenant_id}/administrateurs/{utilisateur_id}/email",
    response_model=APIResponse[AdminCabinetResponse],
    summary="Changer l'e-mail de connexion d'un administrateur du cabinet",
    responses={422: {"description": "Adresse déjà utilisée, identique, ou compte hors périmètre"}},
)
async def changer_email_administrateur(
    tenant_id: uuid.UUID,
    utilisateur_id: uuid.UUID,
    data: ChangementEmailAdminRequest,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.reset_access")),
):
    """
    Change l'adresse de connexion (base du cabinet + index master, ensemble) et
    envoie un lien d'activation à la nouvelle adresse. Sessions coupées.
    """
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)
    vue = await changer_email_admin(
        db, tenant_id, utilisateur_id, str(data.nouvel_email), data.motif,
        auteur_email=auteur.email, auteur_id=auteur.id, ip=ip or client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return APIResponse(
        message="Adresse de connexion modifiée. Un lien d'activation a été envoyé à la nouvelle adresse.",
        data=AdminCabinetResponse(**vue),
    )
