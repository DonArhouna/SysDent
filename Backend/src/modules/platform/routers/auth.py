"""
Routes d'authentification de la console PLATEFORME (Phase A.3).

Préfixe `/platform/auth`, groupe OpenAPI « Platform ».

Toutes les routes d'`/platform/*` passent par `refuser_acces_client`, qui refuse
un jeton de portée non plateforme. C'est une défense en profondeur : même si une
dépendance de permission était oubliée plus bas, un jeton de cabinet ne peut pas
ouvrir la console.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.schemas import APIResponse
from src.core.config import settings
from src.core.exceptions import AuthenticationException
from src.core.platform_database import get_platform_db
from src.core.rate_limit import cle_login, login_platform_limiter
from src.modules.platform.dependencies import (
    client_ip,
    exiger_ip_autorisee,
    get_current_platform_user,
    refuser_acces_client,
)
from src.modules.platform.models import UtilisateurPlateforme
from src.modules.platform.schemas import (
    Activation2FAResponse,
    Challenge2FARequest,
    ChangementMotDePasseRequest,
    Confirmer2FARequest,
    PlatformLoginRequest,
    PlatformProfilResponse,
    PlatformRefreshRequest,
    PlatformTokenResponse,
)
from src.modules.platform.services.auth import PlatformAuthService
from src.modules.platform.services.rbac import PlatformRbacService

platform_auth_router = APIRouter(prefix="/platform/auth", tags=["Platform · Authentification"])


def _deposer_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="platform_access_token",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.PLATFORM_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/api/v1/platform",
    )


@platform_auth_router.post(
    "/login",
    response_model=APIResponse[dict],
    summary="Première étape : e-mail + mot de passe",
    responses={
        401: {"description": "Identifiants invalides (message volontairement indistinct)"},
        403: {"description": "Adresse IP hors de la liste blanche"},
        429: {"description": "Trop de tentatives (limitation de débit)"},
    },
)
async def login(
    data: PlatformLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_platform_db),
):
    """
    Vérifie l'e-mail et le mot de passe d'un compte de la console.

    Retourne systématiquement un **défi 2FA** : un compte dont le second
    facteur n'est pas actif ne reçoit PAS de jeton de session, seulement une
    erreur explicite (`DEUX_FACTEURS_NON_ACTIVE`). Le second facteur n'est donc
    pas une option, il est une condition d'accès.
    """
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)

    cle = f"platform|{cle_login(data.email, ip)}"
    login_platform_limiter.tenter(cle)

    try:
        resultat = await PlatformAuthService.authentifier(
            db,
            email=data.email,
            mot_de_passe=data.mot_de_passe,
            client_ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        raise
    login_platform_limiter.reussite(cle)
    return APIResponse(
        message="Mot de passe correct. Saisissez le code de votre application d'authentification.",
        data=resultat,
    )


@platform_auth_router.post(
    "/2fa",
    response_model=APIResponse[PlatformTokenResponse],
    summary="Deuxième étape : code TOTP",
    responses={
        401: {"description": "Défi invalide, expiré ou code incorrect (message indistinct)"},
        429: {"description": "Trop de tentatives"},
    },
)
async def confirmer_2fa(
    data: Challenge2FARequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_platform_db),
):
    """Valide le code TOTP et ouvre la session (jeton d'accès 10 min, refresh 8 h)."""
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)

    cle = f"platform_2fa|{cle_login(data.jeton_challenge[:16], ip)}"
    login_platform_limiter.tenter(cle)

    tokens = await PlatformAuthService.confirmer_second_facteur(
        db,
        jeton_challenge=data.jeton_challenge,
        code=data.code,
        client_ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    login_platform_limiter.reussite(cle)
    _deposer_cookie(response, tokens["access_token"])

    return APIResponse(message="Authentification réussie.", data=PlatformTokenResponse(**tokens))


@platform_auth_router.post(
    "/refresh",
    response_model=APIResponse[PlatformTokenResponse],
    summary="Renouveler la session",
    responses={401: {"description": "Refresh token inconnu, révoqué ou expiré"}},
)
async def refresh(
    data: PlatformRefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_platform_db),
):
    """
    Rotation du refresh token.

    L'ancien jeton est révoqué au profit d'un nouveau : un refresh token volé
    n'est rejouable qu'une fois, et le rôle est RELU en base à chaque appel.
    """
    exiger_ip_autorisee(request)
    tokens = await PlatformAuthService.renouveller(
        db, data.refresh_token, client_ip=client_ip(request)
    )
    _deposer_cookie(response, tokens["access_token"])
    return APIResponse(message="Session renouvelée.", data=PlatformTokenResponse(**tokens))


@platform_auth_router.post("/logout", response_model=APIResponse[None], summary="Fermer la session")
async def logout(
    data: PlatformRefreshRequest,
    response: Response,
    db: AsyncSession = Depends(get_platform_db),
):
    """Révoque la session en base (le jeton de refresh devient inutilisable)."""
    await PlatformAuthService.revoquer(db, data.refresh_token)
    response.delete_cookie("platform_access_token", path="/api/v1/platform")
    return APIResponse(message="Déconnexion réussie.", data=None)


@platform_auth_router.get(
    "/me",
    response_model=APIResponse[PlatformProfilResponse],
    summary="Profil, rôles et permissions effectives",
    responses={401: {"description": "Non authentifié ou jeton expiré"}},
)
async def me(user: UtilisateurPlateforme = Depends(get_current_platform_user),
             db: AsyncSession = Depends(get_platform_db)):
    """
    Profil de l'agent connecté.

    `permissions` est la liste effective (`platform.<ressource>.<action>`) : c'est
    elle que l'interface doit utiliser pour afficher ou masquer un écran, plutôt
    qu'une liste de rôles réinterprétée côté client.
    """
    roles = await PlatformRbacService.roles_utilisateur(db, user.id)
    permissions = await PlatformRbacService.permissions_utilisateur(db, user.id)
    return APIResponse(
        data=PlatformProfilResponse(
            id=user.id,
            email=user.email,
            prenom=user.prenom,
            nom=user.nom,
            telephone=user.telephone,
            statut=user.statut.value,
            roles=roles,
            permissions=permissions,
            deux_facteurs_actif=user.deux_facteurs_actif,
            dernier_login=user.dernier_login,
            cree_le=user.created_at,
        )
    )


@platform_auth_router.get(
    "/2fa/preparation",
    response_model=APIResponse[Activation2FAResponse],
    summary="Générer un secret TOTP",
)
async def preparer_2fa(
    request: Request,
    user: UtilisateurPlateforme = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_platform_db),
):
    """
    Génère un secret TOTP pour le compte connecté.

    Le secret n'est renvoyé QU'ICI. Il est stocké chiffré (Fernet) et ne
    redevient jamais lisible : perdre son téléphone impose de passer par une
    réinitialisation tracée par un Super Admin.
    """
    preparation = await PlatformAuthService.preparer_second_facteur(db, user)
    await db.commit()
    return APIResponse(data=Activation2FAResponse(**preparation))


@platform_auth_router.post(
    "/2fa/confirmation",
    response_model=APIResponse[None],
    summary="Confirmer le secret TOTP",
    responses={401: {"description": "Code incorrect"}},
)
async def confirmer_activation_2fa(
    data: Confirmer2FARequest,
    user: UtilisateurPlateforme = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_platform_db),
):
    """Active le second facteur à partir d'un code valide. Le compte est verrouillé tant que ce n'est pas fait."""
    await PlatformAuthService.activer_second_facteur(db, user, data.code)
    await db.commit()
    return APIResponse(message="Second facteur activé.", data=None)


@platform_auth_router.post("/mot-de-passe", response_model=APIResponse[None], summary="Changer son mot de passe")
async def changer_mot_de_passe(
    data: ChangementMotDePasseRequest,
    user: UtilisateurPlateforme = Depends(get_current_platform_user),
    db: AsyncSession = Depends(get_platform_db),
):
    """Change le mot de passe du compte connecté, après validation de l'ancien."""
    await PlatformAuthService.changer_mot_de_passe(
        db, user, nouveau=data.nouveau, ancien=data.ancien
    )
    await db.commit()
    return APIResponse(message="Mot de passe modifié.", data=None)