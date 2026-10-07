"""
Gestion des comptes et des rôles de la console PLATEFORME (Phase A.2 et A.5).

Toutes les routes exigent une permission `platform.users.*`. La suppression
définitive exige en plus la permission `platform.users.delete`, la double
confirmation explicite, un motif, et l'absence de « dernier Super Admin ».
"""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.core.exceptions import BusinessRuleViolationException
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import (
    get_current_platform_user,
    refuser_acces_client,
    require_platform_permissions,
)
from src.modules.platform.models import PermissionPlateforme, SessionPlateforme, UtilisateurPlateforme
from src.modules.platform.schemas import (
    Activation2FAResponse,
    CreationUtilisateurResponse,
    DesactivationRequest,
    DetailUtilisateurResponse,
    PermissionPlateformeResponse,
    ReinitialisationAccesRequest,
    RolePlateformeResponse,
    SuppressionRequest,
    UtilisateurPlateformeCreate,
    UtilisateurPlateformeResponse,
    UtilisateurPlateformeUpdate,
)
from src.modules.platform.services.auth import PlatformAuthService
from src.modules.platform.services.rbac import PlatformRbacService
from src.modules.platform.services.users import PlatformUserService

platform_users_router = APIRouter(prefix="/platform", tags=["Platform · Utilisateurs & Rôles"])


def _vers_reponse(user: UtilisateurPlateforme) -> UtilisateurPlateformeResponse:
    return UtilisateurPlateformeResponse(
        id=user.id,
        email=user.email,
        prenom=user.prenom,
        nom=user.nom,
        telephone=user.telephone,
        statut=user.statut.value,
        roles=[r.code for r in user.roles],
        deux_facteurs_actif=user.deux_facteurs_actif,
        dernier_login=user.dernier_login,
        tentatives_echouees=user.tentatives_echouees,
        verrouille_jusqua=user.verrouille_jusqua,
        motif_desactivation=user.motif_desactivation,
        cree_le=user.created_at,
        modifie_le=user.updated_at,
    )


# ==============================================================================
# RÔLES & PERMISSIONS (lecture)
# ==============================================================================


@platform_users_router.get(
    "/roles",
    response_model=APIResponse[List[RolePlateformeResponse]],
    summary="Lister les rôles de la console et leurs permissions",
    responses={401: {"description": "Non authentifié"}, 403: {"description": "Permission insuffisante"}},
)
async def lister_roles(
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.read")),
):
    """Catalogue des cinq rôles système et de leurs permissions effectives."""
    roles = await PlatformRbacService.lister_roles(db)
    return APIResponse(data=[RolePlateformeResponse(**r) for r in roles])


@platform_users_router.get(
    "/permissions",
    response_model=APIResponse[List[PermissionPlateformeResponse]],
    summary="Lister le catalogue des permissions `platform.*`",
)
async def lister_permissions(
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.read")),
):
    """Catalogue complet des permissions de la console, pour construire l'écran de matrice."""
    stmt = select(PermissionPlateforme).order_by(
        PermissionPlateforme.ressource, PermissionPlateforme.action
    )
    permissions = (await db.execute(stmt)).scalars().all()
    return APIResponse(
        data=[
            PermissionPlateformeResponse(
                code=p.code,
                ressource=p.ressource,
                action=p.action,
                description=p.description,
                sensible=p.sensible,
            )
            for p in permissions
        ]
    )


# ==============================================================================
# UTILISATEURS
# ==============================================================================


@platform_users_router.get(
    "/users",
    response_model=PaginatedResponse[UtilisateurPlateformeResponse],
    summary="Lister les comptes de la console",
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Permission insuffisante"},
    },
)
async def lister_utilisateurs(
    request: Request,
    q: Optional[str] = Query(None, description="Recherche sur e-mail, prénom ou nom"),
    statut: Optional[str] = Query(None, description="ACTIF | DESACTIF | VERROUILLE"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.read")),
):
    """Registre paginé des comptes de la console, filtrable par recherche et statut."""
    refuser_acces_client(request)
    params = PaginationParams(page=page, limit=limit)
    items = await PlatformUserService.lister(
        db, recherche=q, statut=statut, limit=params.limit, offset=params.offset
    )
    total = await PlatformUserService.compter(db, recherche=q, statut=statut)
    return paginate(items=[_vers_reponse(u) for u in items], total_records=total, params=params)


@platform_users_router.post(
    "/users",
    response_model=APIResponse[CreationUtilisateurResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte de la console",
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Permission insuffisante"},
        409: {"description": "Adresse e-mail déjà utilisée"},
        422: {"description": "Mot de passe non conforme à la politique (détail des règles)"},
    },
)
async def creer_utilisateur(
    data: UtilisateurPlateformeCreate,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.users.create")
    ),
):
    """
    Crée un compte et renvoie, s'il est demandé, le PREPARATIF d'activation 2FA.

    Le secret TOTP n'est renvoyé qu'ici : ni la base (chiffré) ni le journal ne
    le conservent en clair.
    """
    refuser_acces_client(request)
    resultat = await PlatformUserService.creer(
        db,
        email=data.email,
        prenom=data.prenom,
        nom=data.nom,
        mot_de_passe=data.mot_de_passe,
        roles=data.roles,
        telephone=data.telephone,
        activer_2fa=data.activer_2fa,
        auteur=auteur.email,
    )
    return APIResponse(
        message=(
            "Compte créé. Communiquez le secret d'activation à l'utilisateur : "
            "il ne sera plus jamais affiché."
            if resultat["activation_2fa"]
            else "Compte créé."
        ),
        data=CreationUtilisateurResponse(
            utilisateur=_vers_reponse(resultat["utilisateur"]),
            activation_2fa=(
                Activation2FAResponse(**resultat["activation_2fa"])
                if resultat["activation_2fa"]
                else None
            ),
        ),
    )


@platform_users_router.get(
    "/users/{utilisateur_id}",
    response_model=APIResponse[DetailUtilisateurResponse],
    summary="Détail d'un compte",
    responses={404: {"description": "Compte introuvable"}},
)
async def detail_utilisateur(
    utilisateur_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.read")),
):
    """Fiche d'un compte : identité, rôles, permissions effectives et sessions ouvertes."""
    from src.modules.platform.services.users import PlatformUserService

    user = await PlatformUserService._charger(db, utilisateur_id)
    permissions = await PlatformRbacService.permissions_utilisateur(db, user.id)
    stmt = select(SessionPlateforme).where(
        SessionPlateforme.utilisateur_id == user.id, SessionPlateforme.est_revoque.is_(False)
    )
    sessions = (await db.execute(stmt)).scalars().all()
    return APIResponse(
        data=DetailUtilisateurResponse(
            utilisateur=_vers_reponse(user),
            permissions=permissions,
            sessions_actives=len(sessions),
        )
    )


@platform_users_router.patch(
    "/users/{utilisateur_id}",
    response_model=APIResponse[UtilisateurPlateformeResponse],
    summary="Modifier un compte",
    responses={
        404: {"description": "Compte introuvable"},
        422: {"description": "Rôle inconnu ou retrait du rôle du dernier Super Admin refusé"},
    },
)
async def modifier_utilisateur(
    utilisateur_id: uuid.UUID,
    data: UtilisateurPlateformeUpdate,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.update")),
):
    """
    Met à jour l'identité ou les rôles d'un compte.

    Un changement de rôles **révoque les sessions ouvertes** : sans cela, un
    agent déclassé conserverait ses droits jusqu'à l'expiration de son jeton.
    """
    user = await PlatformUserService.mettre_a_jour(
        db,
        utilisateur_id,
        prenom=data.prenom,
        nom=data.nom,
        telephone=data.telephone,
        roles=data.roles,
        auteur=auteur.email,
        motif=data.motif,
    )
    return APIResponse(message="Compte modifié.", data=_vers_reponse(user))


@platform_users_router.post(
    "/users/{utilisateur_id}/desactivation",
    response_model=APIResponse[UtilisateurPlateformeResponse],
    summary="Désactiver un compte",
    responses={
        403: {"description": "Permission insuffisante"},
        422: {"description": "Refusé : c'est le dernier Super Admin actif"},
    },
)
async def desactiver_utilisateur(
    utilisateur_id: uuid.UUID,
    data: DesactivationRequest,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.users.deactivate")
    ),
):
    """
    Désactive un compte et coupe toutes ses sessions.

    **Garde-fou** : refusé si le compte porte le rôle Super Admin et qu'aucun
    autre Super Admin actif ne subsiste.
    """
    user = await PlatformUserService.desactiver(db, utilisateur_id, data.motif, auteur.email)
    return APIResponse(message="Compte désactivé.", data=_vers_reponse(user))


@platform_users_router.post(
    "/users/{utilisateur_id}/reactivation",
    response_model=APIResponse[UtilisateurPlateformeResponse],
    summary="Réactiver un compte",
)
async def reactiver_utilisateur(
    utilisateur_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.update")),
):
    """Réactive un compte désactivé. Le second facteur reste obligatoire."""
    user = await PlatformUserService.reactiver(db, utilisateur_id, auteur.email)
    return APIResponse(message="Compte réactivé.", data=_vers_reponse(user))


@platform_users_router.post(
    "/users/{utilisateur_id}/reinitialisation-acces",
    response_model=APIResponse[Activation2FAResponse],
    summary="Réinitialiser l'accès d'un compte",
    responses={422: {"description": "Refusé : c'est le dernier Super Admin actif"}},
)
async def reinitialiser_acces(
    utilisateur_id: uuid.UUID,
    data: ReinitialisationAccesRequest,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.reset")),
):
    """
    Remet à zéro l'authentification : nouveau secret 2FA, sessions révoquées.

    Action de support classique (téléphone perdu). Toujours tracée, toujours avec
    motif obligatoire.
    """
    from src.modules.platform.services.users import PlatformUserService

    user = await PlatformUserService._charger(db, utilisateur_id)
    if await PlatformUserService._est_dernier_super_admin(db, user, True):
        raise BusinessRuleViolationException(
            "Impossible de réinitialiser l'accès du dernier Super Admin actif.",
            code="DERNIER_SUPER_ADMIN",
        )
    preparation = await PlatformAuthService.reinitialiser_acces(db, user, data.motif, auteur.email)
    return APIResponse(
        message="Accès réinitialisé. Toutes les sessions ont été révoquées.",
        data=Activation2FAResponse(**preparation),
    )


@platform_users_router.delete(
    "/users/{utilisateur_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer DÉFINITIVEMENT un compte",
    responses={
        403: {"description": "Permission insuffisante"},
        422: {"description": "Motif absent, confirmation incorrecte, ou dernier Super Admin"},
    },
)
async def supprimer_utilisateur(
    utilisateur_id: uuid.UUID,
    data: SuppressionRequest,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.users.delete")),
):
    """
    Suppression définitive, protégée par TROIS verrous :

    1. la permission `platform.users.delete` (distincte de `deactivate`) ;
    2. une confirmation explicite — le corps doit contenir `SUPPRIMER` ;
    3. l'interdiction de supprimer le dernier Super Admin actif.

    Le journal d'audit, lui, survit à la suppression du compte : effacer un agent
    ne doit pas effacer ce qu'il a fait.
    """
    if data.confirmation != "SUPPRIMER":
        raise BusinessRuleViolationException(
            "Confirmation invalide : saisissez exactement SUPPRIMER pour confirmer la suppression.",
            code="CONFIRMATION_REQUISE",
        )
    await PlatformUserService.supprimer(db, utilisateur_id, auteur.email, data.motif)
    return None