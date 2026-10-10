"""
Dépendances FastAPI de la console PLATEFORME.

Elles forment la barrière d'accès unique : aucune route `/platform/*` ne se
déclare sans passer par `get_current_platform_user`, et aucune ne modifie quoi
que ce soit sans passer par `require_platform_permissions`.

Trois contrôles, dans cet ordre :

1. **Adresse IP** (liste blanche configurable) — vérifiée AVANT tout accès base,
   pour qu'une IP non autorisée ne consomme même pas une connexion PostgreSQL.
2. **Signature + audience** — `decode_platform_token` rejette un jeton tenant
   (clé différente) et un jeton support (scope différent).
3. **Statut du compte + permissions** — relus en base à chaque requête, donc un
   compte désactivé perd l'accès immédiatement, sans attendre l'expiration du
   jeton.
"""

import uuid
from typing import Callable, List, Optional

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import AuthenticationException, PermissionDeniedException
from src.core.platform_database import get_platform_db
from src.core.security import decode_platform_token
from src.modules.platform.models import (
    StatutUtilisateurPlateforme,
    UtilisateurPlateforme,
)
from src.modules.platform.security import ip_autorisee


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def exiger_ip_autorisee(request: Request) -> str:
    ip = client_ip(request)
    autorisee, raison = ip_autorisee(ip)
    if not autorisee:
        # 403 et non 401 : le jeton peut être parfaitement valide, c'est la
        # machine qui n'est pas autorisée. Un 401 renverrait l'agent vers un
        # « mot de passe incorrect » alors que son mot de passe est bon.
        raise PermissionDeniedException(
            f"Accès refusé depuis cette adresse ({raison}). "
            "Contactez votre administrateur si vous pensez qu'il s'agit d'une erreur."
        )
    return ip


async def get_platform_token_payload(request: Request) -> dict:
    """Extrait et décode le jeton plateforme (Bearer en priorité, cookie en repli)."""
    token = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("platform_access_token")

    if not token:
        raise AuthenticationException("Authentification requise.", code="AUTHENTICATION_REQUIRED")

    payload = decode_platform_token(token)
    if payload.get("type") != "access":
        raise AuthenticationException(
            "Type de jeton invalide : un jeton d'accès est requis.", code="TOKEN_INVALID"
        )
    return payload


async def get_current_platform_user(
    request: Request,
    payload: dict = Depends(get_platform_token_payload),
    db: AsyncSession = Depends(get_platform_db),
) -> UtilisateurPlateforme:
    """
    Compte plateforme authentifié, actif, avec ses rôles et permissions.

    Les permissions sont RELUES en base, pas prises du JWT : un rôle retiré ou un
    compte désactivé perd l'accès à la requête suivante, pas à l'expiration du
    jeton.
    """
    exiger_ip_autorisee(request)

    sub = payload.get("sub")
    if not sub:
        raise AuthenticationException("Jeton invalide.", code="TOKEN_INVALID")

    stmt = (
        select(UtilisateurPlateforme)
        .options(selectinload(UtilisateurPlateforme.roles))
        .where(UtilisateurPlateforme.id == sub)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise AuthenticationException("Compte introuvable.", code="AUTHENTICATION_REQUIRED")

    if user.statut.value != "ACTIF":
        raise AuthenticationException(
            "Ce compte n'est pas actif.", code="COMPTE_NON_ACTIF"
        )

    return user


async def get_current_platform_user_enrolement(
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
) -> UtilisateurPlateforme:
    """
    Resout l'utilisateur d'un **jeton d'enrolement** — et rien d'autre.

    Le jeton n'ouvre que la preparation et l'activation du second facteur. Il est
    rejete partout ailleurs, y compris sur `/platform/auth/me` : sans cela, un
    jeton emis a un compte sans 2FA deviendrait une session a ce compte, et la 2FA
    serait purement decorative.

    La restriction est portee par la **colonne `usage`** du jeton : c'est elle qui
    distingue un jeton d'enrolement d'un challenge et d'une session. Une erreur
    ici serait un trou, d'ou les tests.
    """
    from datetime import datetime, timezone

    from src.modules.platform.models import JetonUsageUnique, UsageJeton
    from src.modules.platform.security import hacher_jeton

    token = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AuthenticationException("Authentification requise.", code="AUTHENTICATION_REQUIRED")

    ligne = (
        await db.execute(
            select(JetonUsageUnique).where(
                JetonUsageUnique.hash_jeton == hacher_jeton(token),
                # **La restriction de portée.** C'est cette clause qui empêche un
                # jeton d'enrolement de valoir session.
                JetonUsageUnique.usage == UsageJeton.ENROLEMENT_2FA,
                JetonUsageUnique.utilise.is_(False),
                JetonUsageUnique.expire_le > datetime.now(timezone.utc),
            )
        )
    ).scalar_one_or_none()
    if ligne is None:
        raise AuthenticationException("Jeton invalide ou expire.", code="JETON_INVALIDE")

    try:
        cible = uuid.UUID(ligne.cible_id)
    except (ValueError, AttributeError):
        raise AuthenticationException("Jeton invalide ou expire.", code="JETON_INVALIDE")

    user = (
        await db.execute(
            select(UtilisateurPlateforme)
            .options(selectinload(UtilisateurPlateforme.roles))
            .where(UtilisateurPlateforme.id == cible)
        )
    ).scalar_one_or_none()
    if user is None or user.statut is not StatutUtilisateurPlateforme.ACTIF:
        raise AuthenticationException("Jeton invalide ou expire.", code="JETON_INVALIDE")
    return user


def permissions_effectives(user: UtilisateurPlateforme) -> List[str]:
    """Permissions de l'utilisateur, déduites de ses rôles et relues de la base."""
    from src.modules.platform.permissions import format_permission

    codes: List[str] = []
    for role in user.roles:
        for permission in role.permissions:
            codes.append(format_permission(permission.ressource, permission.action))
    return sorted(set(codes))


def require_platform_permissions(*required: str) -> Callable:
    """
    Exige toutes les permissions listées, au format `platform.<ressource>.<action>`.

    Aucun rôle n'a de court-circuit : même le Super Admin doit posséder le droit
    dans la matrice. Un droit implicite est un droit qu'on ne peut retirer à
    personne, et la fuite d'un compte éditeur n'est pas rattrapable.
    """

    async def _garde(user: UtilisateurPlateforme = Depends(get_current_platform_user)) -> UtilisateurPlateforme:
        # Retourne l'utilisateur, pas `True` : les routes qui doivent signer le
        # journal d'audit ont besoin de savoir QUI agit, pas seulement QUE la
        # permission est détenue. Typé en `UtilisateurPlateforme`, la garde reste
        # utilisable comme `_: UtilisateurPlateforme = Depends(...)`.
        if not required:
            return user
        effectif = permissions_effectives(user)
        manquantes = [perm for perm in required if perm not in effectif]
        if manquantes:
            raise PermissionDeniedException(
                "Permission insuffisante pour cette opération.",
                details={"requises": list(required), "manquantes": manquantes},
            )
        return user

    return _garde


def exiger_role(*codes_roles: str) -> Callable:
    """Exige au moins un des rôles indiqués. Utilisé pour les garde-fous globaux."""

    async def _garde(user: UtilisateurPlateforme = Depends(get_current_platform_user)) -> bool:
        codes = {role.code for role in user.roles}
        if not (codes & set(codes_roles)):
            raise PermissionDeniedException(
                "Rôle requis pour cette opération.",
                details={"roles_requis": list(codes_roles)},
            )
        return True

    return _garde


def est_super_admin(user: UtilisateurPlateforme) -> bool:
    from src.modules.platform.permissions import ROLE_SUPER_ADMIN

    return any(role.code == ROLE_SUPER_ADMIN for role in user.roles)


def refuser_acces_client(request: Request) -> None:
    """
    Interdit tout jeton non-plateforme sur une route `/platform/*`.

    Appelée par un routeur de la console avant ses dépendances propres : même si
    une dépendance de permission était oubliée, le jeton d'un cabinet ne peut pas
    ouvrir la console. Défense en profondeur, pas substitution.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return
    if not authorization.lower().startswith("bearer "):
        return
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_platform_token(token)
    except AuthenticationException:
        return
    if payload.get("scope") != "platform":
        raise PermissionDeniedException(
            "Accès réservé à la console d'administration de la plateforme.",
            code="PLATFORM_REQUIRED",
        )


# ---------------------------------------------------------------------------
# Dependances "soft" : acceptent deux types de jeton sur une meme route
# ---------------------------------------------------------------------------
#
# Indispensable pour `preparer_2fa`, qui doit accepter aussi bien une session
# qu'un jeton d'enrolement. Une dependance qui **leve** court-circuite la chaine
# : FastAPI ne tente jamais la dependance suivante, donc une route a deux types
# de jeton est impossible a ecrire sans ces variantes.
#
# L'ordre des definitions compte : la valeur par defaut d'un parametre
# `Depends(...)` est evaluee a l'import du module.


async def get_platform_token_payload_soft(request: Request) -> Optional[dict]:
    """`get_platform_token_payload` qui rend `None` plutot que de lever."""
    try:
        return await get_platform_token_payload(request)
    except AuthenticationException:
        return None


async def get_current_platform_user_soft(
    request: Request,
    payload: Optional[dict] = Depends(get_platform_token_payload_soft),
    db: AsyncSession = Depends(get_platform_db),
) -> Optional[UtilisateurPlateforme]:
    """
    `get_current_platform_user`, mais `None` si le jeton n'est pas une session.

    **Contrat des dependances « soft ».** Elles n'existent que pour une route qui
    accepte **deux** types de jeton : sans cela, une dependance stricte refuserait
    la requete entiere alors qu'un jeton de l'autre type est parfaitement valide.

    Trois regles, non negociables :

    1. **Le captage est type, pas large.** Seul `AuthenticationException` est
       transforme en `None`. Un `except Exception` élargi avalerait un defaut de
       notre code - une colonne renommee, une conversion qui echoue - et le
       transformerait en « aucun jeton », donc en 401. Une panne de notre cote
       deviendrait un refus d'authentification : impossible a diagnostiquer, et
       impossible a distinguer d'un vrai echec de connexion.
    2. **Ce n'est pas une porte de securite.** La dependance **stricte** reste
       celle utilisee partout ailleurs, et elle seule refuse.
    3. **Le comportement par defaut est le refus.** Si aucun des deux types de
       jeton ne resout de porteur, la route doit lever une erreur
       d'authentification explicite. Passer `None` au service le ferait echouer
       sur un attribut, en 500 - une reponse qui accuse la route d'etre cassee
       alors que la seule erreur est l'absence d'identite. Voir `preparer_2fa`.
    """
    if payload is None:
        return None
    try:
        return await get_current_platform_user(request, payload, db)
    except AuthenticationException:
        return None


async def get_current_platform_user_enrolement_soft(
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
) -> Optional[UtilisateurPlateforme]:
    """
    `get_current_platform_user_enrolement`, mais `None` au lieu d'echouer.

    **Ne doit jamais se substituer a la version stricte** sur une route qui doit
    refuser un mauvais jeton : la version stricte est la seule a lever, et donc
    la seule a garantir le refus.
    """
    try:
        return await get_current_platform_user_enrolement(request, db)
    except AuthenticationException:
        return None

