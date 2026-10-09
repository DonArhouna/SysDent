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
from src.modules.platform.services.journal import JournalService
from src.modules.platform.dependencies import (
    client_ip,
    exiger_ip_autorisee,
    get_current_platform_user,
    get_current_platform_user_enrolement,
    get_current_platform_user_enrolement_soft,
    get_current_platform_user_soft,
    refuser_acces_client,
)
from src.modules.platform.models import UtilisateurPlateforme
from src.modules.platform.schemas import (
    Activer2FARequest,
    Activation2FAResponse,
    Enrolement2FAResponse,
    Challenge2FARequest,
    ChangementMotDePasseRequest,
    LoginPlateformeResponse,
    PlatformLoginRequest,
    PlatformProfilResponse,
    PlatformRefreshRequest,
    PlatformTokenResponse,
    RegenererCodesSecoursRequest,
    RegenererCodesSecoursResponse,
)
from src.modules.platform.services.auth import PlatformAuthService
from src.modules.platform.services.rbac import PlatformRbacService

platform_auth_router = APIRouter(prefix="/platform/auth", tags=["Platform · Authentification"])


def _jeton_de_l_entete(request: Request) -> str:
    """Jeton porteur de l'enrolement, lu comme le fait la dependance."""
    authorization = request.headers.get("Authorization") or ""
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return ""


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
    response_model=APIResponse[LoginPlateformeResponse],
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

    **La décision porte sur l'état actif du second facteur** :

    - 2FA inactive → un **jeton d'enrôlement**, jamais une session ni un défi.
      Le chemin du défi refuse un compte non actif : l'enrôlement ne se fait
      que par `/2fa/preparation` puis `/2fa/activation`, la seule voie qui
      émette les codes de secours ;
    - 2FA active → un **défi** à saisir dans l'application d'authentification.

    Dans les deux cas, aucun jeton de session n'est émis à cette étape : la
    session ne s'ouvre qu'après le second facteur.
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
    # **Le schema doit decrire la reponse reelle.** `APIResponse[dict]`
    # acceptait n'importe quoi : un champ renomme cote service auraitcontinue de
    # fonctionner, et le front l'aurait decouvert a l'execution - un 422, ou pire
    # un `undefined` silencieusement lu comme absent. En typant, le contrat
    # devient visible dans l'OpenAPI et se verifie des deux cotes.
    #
    # Le filtre de FastAPI ne perd rien ici : le service renvoie exactement les
    # champs declares par `LoginPlateformeResponse`. Si un jour il en renvoyait un
    # de plus, la reponse le perdrait **silencieusement** - d'ou le test de contrat.
    return APIResponse(
        message="Mot de passe correct. Saisissez le code de votre application d'authentification.",
        data=LoginPlateformeResponse(**resultat),
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
    """
    Valide le code TOTP (ou un code de secours) et ouvre la session.

    **Seulement pour un compte déjà enrôlé** : un compte dont la 2FA n'est pas
    active reçoit un jeton d'enrôlement au login, jamais un défi ; et si un défi
    lui parvient quand même, ce chemin refuse avec le message d'un code
    invalide — il n'active jamais le second facteur.
    """
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
            # Indicateur de la bannière : la 2FA est active mais les codes de
            # secours doivent être régénérés (compte préexistant sans codes).
            codes_secours_a_regenerer=user.codes_secours_a_regenerer,
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
    db: AsyncSession = Depends(get_platform_db),
    # Un jeton d'enrolement ouvre la preparation. Une session l'ouvre aussi :
    # un Super Admin doit pouvoir (re)generer un secret pour un collegue.
    # L'ordre compte : le jeton d'enrolement est essaye d'abord, parce qu'il
    # n'ouvre rien d'autre.
    user_enrolement: Optional[UtilisateurPlateforme] = Depends(
        get_current_platform_user_enrolement_soft
    ),
    user: Optional[UtilisateurPlateforme] = Depends(get_current_platform_user_soft),
):
    """
    Génère un secret TOTP pour le compte connecté.

    Le secret n'est renvoyé QU'ICI. Il est stocké chiffré (Fernet) et ne
    redevient jamais lisible : perdre son téléphone impose de passer par une
    réinitialisation tracée par un Super Admin.
    """
    # L'un OU l'autre ouvre la preparation. Sans cela, un jeton d'enrolement
    # resolvait bien `user_enrolement` mais n'etait pas utilise : le service
    # recevait `user=None` et levait un AttributeError -> 500 sur le premier
    # ecran de l'enrolement, celui que tout operateur voit en premier.
    porteur = user_enrolement or user
    if porteur is None:
        # **Echec ferme.** Aucune des deux dependances n'a resolu de porteur : le
        # jeton presente est invalide, expire, ou d'un autre usage. Passer `None`
        # au service levait un AttributeError -> 500, qui dit a l'appelant que la
        # route est cassee alors que la seule erreur est l'absence d'identite.
        # Les deux types de jeton sont refuses ici, sans dire lequel : dire lequel
        # reviendrait a confirmer qu'un jeton existe.
        raise AuthenticationException(
            "Authentification requise.", code="AUTHENTICATION_REQUIRED"
        )
    preparation = await PlatformAuthService.preparer_second_facteur(db, porteur)
    await db.commit()
    return APIResponse(data=Activation2FAResponse(**preparation))


@platform_auth_router.post(
    "/2fa/codes-secours/regenerer",
    response_model=APIResponse[RegenererCodesSecoursResponse],
    summary="Régénérer les codes de secours",
    responses={
        401: {"description": "TOTP invalide, ou compte sans second facteur actif"},
        429: {"description": "Trop de tentatives (limitation de débit)"},
    },
)
async def regenerer_codes_secours(
    data: RegenererCodesSecoursRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_platform_db),
    user: UtilisateurPlateforme = Depends(get_current_platform_user),
):
    """
    Remplace les codes de secours d'un compte déjà enrôlé par dix nouveaux.

    **Seule voie de recours après la perte des codes.** Garde-fous identiques au
    login : limitation de débit sur (e-mail, IP), message générique en cas
    d'échec, et une session ouverte ne suffit pas — un **TOTP valide sur le
    secret actif** et un **motif** sont exigés. Les anciens codes sont invalidés
    dans la même transaction, les dix nouveaux ne sont renvoyés qu'ici, et le
    journal ne contient que leur nombre.
    """
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)

    # Même limiteur et même granularité que le login : (e-mail, IP). Une
    # session ouverte ne doit pas permettre d'essayer des codes en boucle.
    cle = f"platform_codes_secours|{cle_login(user.email, ip)}"
    login_platform_limiter.tenter(cle)

    codes = await PlatformAuthService.regenerer_codes_secours(
        db,
        user,
        code=data.code,
        motif=data.motif,
        client_ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    login_platform_limiter.reussite(cle)
    await db.commit()
    return APIResponse(
        message="Codes de secours régénérés. Les précédents ne sont plus valables.",
        data=RegenererCodesSecoursResponse(codes_secours=codes),
    )


@platform_auth_router.post(
    "/2fa/activation",
    response_model=APIResponse[Enrolement2FAResponse],
    summary="Activer le second facteur et ouvrir la session",
    responses={
        401: {"description": "Jeton d'enrolement invalide, expire ou deja utilise"},
        422: {"description": "Code de verification invalide"},
    },
)
async def activer_2fa(
    data: Activer2FARequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_platform_db),
    user: UtilisateurPlateforme = Depends(get_current_platform_user_enrolement),
):
    """
    Troisieme etape : le code TOTP confirme l'activation, la session s'ouvre.

    C'est la **seule** voie qui emet une session pour un compte dont la 2FA
    vient d'etre activee. Le jeton d'enrolement est consomme ici et ne vaut plus
    rien : il ne reutilise pas le jeton de session, il disparait.

    Le code est verifie **sur le secret en attente** — celui que le compte vient
    de scanner — et le secret est ensuite promu secret actif. Un code de secours
    ne peut pas activer : il ouvre une session, il n'enrole pas.

    Les codes de secours sont renvoyes **une seule fois**. Ni la base ni le
    journal ne les conservent en clair.
    """
    refuser_acces_client(request)
    ip = exiger_ip_autorisee(request)

    jeton = _jeton_de_l_entete(request)
    # Limitation de débit comme au login : le code TOTP est devinable en
    # force brute si rien ne limite les essais. La clé suit le jeton
    # d'enrolement, éphémère et à usage unique — pas l'e-mail, pour ne pas
    # croiser le compteur du login proprement dit.
    cle = f"platform_activation|{cle_login(jeton[:16], ip)}"
    login_platform_limiter.tenter(cle)

    codes = await PlatformAuthService.activer_second_facteur(db, user, data.code)
    login_platform_limiter.reussite(cle)
    await PlatformAuthService._marquer_enrolement_consomme(db, jeton)

    await JournalService.journaliser(
        db,
        action="PLATFORM_2FA_ACTIVEE",
        type_cible="AUTH",
        acteur_email=user.email,
        acteur_id=user.id,
        apres={"codes_secours_emus": len(codes)},
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    tokens = await PlatformAuthService._ouvrir_session(
        db, user, client_ip=client_ip(request), user_agent=request.headers.get("user-agent")
    )
    await db.commit()
    _deposer_cookie(response, tokens["access_token"])
    return APIResponse(
        message="Second facteur activé.",
        data=Enrolement2FAResponse(**tokens, codes_secours=codes),
    )


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