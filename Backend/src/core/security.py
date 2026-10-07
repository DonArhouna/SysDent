from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import jwt
from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
from .config import settings
from .exceptions import AuthenticationException

# Utilisation d'Argon2 et Bcrypt pour une sécurité de niveau bancaire/médical
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si un mot de passe en clair correspond au hash sécurisé."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Génère un hash robuste du mot de passe avec Argon2."""
    return pwd_context.hash(password)


def create_access_token(
    user_id: str,
    tenant_id: Optional[str],
    role: str,
    permissions: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
    custom_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Génère un JWT Access Token de courte durée."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "role": role,
        "permissions": permissions or [],
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "nbf": int(now.timestamp()),
    }

    if custom_claims:
        payload.update(custom_claims)

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    user_id: str,
    tenant_id: Optional[str],
    jti: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Génère un JWT Refresh Token de longue durée.

    Le `jti` est une clé de session unique, persistée en base. Il sert à deux
    choses : identifier la session à révoquer, et empêcher la réutilisation d'un
    refresh token déjà consommé (rotation). Sans `jti` dans le payload, un token
    volé resterait rejouable pendant toute sa durée de vie.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "jti": jti,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Décode et valide la signature et l'expiration d'un JWT signé avec la clé TENANT.

    Fonction volontairement inchangée dans son comportement : elle reste le point
    d'entrée de l'application cliente. Le contrôle d'audience est ajouté plus bas
    par `decode_token_scoped`, appelé par les dépendances.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("La session a expiré. Veuillez vous reconnecter.", code="TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID")


# ==============================================================================
# FAMILLES DE JETONS — ÉTANCHÉITÉ (décision D3)
# ==============================================================================
# Trois familles de jetons coexistent désormais :
#   - `tenant`   : signé avec SECRET_KEY, audience `sysdent-tenant`, par l'app cliente ;
#   - `platform` : signé avec PLATFORM_SECRET_KEY, audience `sysdent-platform` ;
#   - `support`  : signé avec PLATFORM_SECRET_KEY, audience `sysdent-tenant`,
#                  scope `support`, accepté UNIQUEMENT par les routes tenant et
#                  UNIQUEMENT en lecture (Phase D).
#
# L'étanchéité ne repose pas sur un seul mécanisme mais sur trois superposés :
#   1. la clé de signature (une fuite de l'une ne sert pas l'autre) ;
#   2. l'audience (`aud`) ;
#   3. le scope (`scope`) vérifié par la dépendance de chaque famille de routes.


def _decoder(cle: str, algorithme: str, audience: Optional[str]):
    """
    Fabrique un décodeur JWT verrouillé sur une clé, un algorithme et une audience.

    `audience` est exigée ET vérifiée quand elle est fournie. C'est volontaire :
    PyJWT refuse un jeton portant `aud` si l'audience attendue est absente du
    payload. Côté client on passe `audience=None` pour rester tolérant aux jetons
    émis avant l'introduction du claim ; côté plateforme l'exigence est stricte.

    Le premier paramètre positionnel de `jwt.decode` est le JETON, pas la clé :
    d'où l'appel par mot-clé `key=` ci-dessous.
    """
    return lambda token: jwt.decode(
        token,
        key=cle,
        algorithms=[algorithme],
        audience=audience,
        options={"require": ["exp", "sub", "type"]},
    )


def _erreur_appropriee(exc: Exception) -> AuthenticationException:
    if isinstance(exc, jwt.ExpiredSignatureError):
        return AuthenticationException(
            "La session a expiré. Veuillez vous reconnecter.", code="TOKEN_EXPIRED"
        )
    return AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID")


def decode_platform_token(token: str) -> Dict[str, Any]:
    """
    Décode un jeton PLATEFORME ou SUPPORT (clé dédiée).

    L'exigence est stricte là où elle est laxiste côté client :
    - signature vérifiée avec `PLATFORM_SECRET_KEY` : un jeton tenant est rejeté
      car il est signé avec une autre clé ;
    - `aud` et `scope` obligatoires, ce qui interdit aussi le rejeu d'un jeton
      support sur une route plateforme (scope différent).
    """
    from .config import resoudre_cle_platform

    try:
        return _decoder(
            resoudre_cle_platform(),
            settings.PLATFORM_ALGORITHM,
            audience=settings.PLATFORM_AUDIENCE,
        )(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("La session a expiré. Veuillez vous reconnecter.", code="TOKEN_EXPIRED")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID") from exc


def decode_support_token(token: str) -> Dict[str, Any]:
    """
    Décode un jeton d'accès SUPPORT depuis une route tenant.

    Utilisé par `get_token_payload` : un jeton support est le SEUL jeton signé
    avec la clé plateforme qu'une route tenant doit reconnaître, et seulement
    pour des opérations en lecture.
    """
    from .config import resoudre_cle_platform

    try:
        payload = _decoder(
            resoudre_cle_platform(),
            settings.PLATFORM_ALGORITHM,
            audience=settings.TENANT_AUDIENCE,
        )(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationException("Jeton d'accès expiré.", code="TOKEN_EXPIRED")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID") from exc

    if payload.get("scope") != settings.SUPPORT_SCOPE:
        raise AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID")
    return payload


def decode_token_scoped(token: str) -> Dict[str, Any]:
    """
    Décode un jeton pour une ROUTE TENANT : jeton tenant, ou jeton support.

    Ajoute la claim `family` au payload (`tenant` ou `support`) afin que les
    gardes de permission puissent interdire l'écriture à un jeton support sans
    avoir à re-décoder le jeton.

    Rétrocompatibilité : un jeton tenant émis AVANT cette mission ne porte ni
    `aud` ni `scope`. Il reste accepté (sinon toutes les sessions ouvertes
    seraient déconnectées au déploiement), mais il est rejeté s'il porte un
    `aud`/`scope` qui ne correspond pas.
    """
    try:
        payload = decode_token(token)
    except AuthenticationException as exc:
        if exc.code == "TOKEN_EXPIRED":
            raise
        payload = None

    if payload is not None:
        aud = payload.get("aud")
        scope = payload.get("scope")
        if aud is not None and aud != settings.TENANT_AUDIENCE:
            raise AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID")
        if scope is not None and scope != settings.TENANT_SCOPE:
            raise AuthenticationException("Jeton d'authentification invalide ou altéré.", code="TOKEN_INVALID")
        payload["family"] = settings.TENANT_SCOPE
        return payload

    support = decode_support_token(token)
    support["family"] = settings.SUPPORT_SCOPE
    return support


# ==============================================================================
# ÉMISSION — PLATEFORME
# ==============================================================================


def _payload_platform(
    user_id: str,
    token_type: str,
    expire: datetime,
    claims: Dict[str, Any],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "aud": settings.PLATFORM_AUDIENCE,
        "scope": settings.PLATFORM_SCOPE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.APP_NAME,
    }
    payload.update(claims)
    return payload


def _signer_platform(payload: Dict[str, Any]) -> str:
    from .config import resoudre_cle_platform

    return jwt.encode(payload, resoudre_cle_platform(), algorithm=settings.PLATFORM_ALGORITHM)


def create_platform_access_token(
    user_id: str,
    roles: List[str],
    permissions: List[str],
    expires_delta: Optional[timedelta] = None,
    custom_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Jeton d'accès PLATEFORME.

    Durée volontairement plus courte que celle du client (10 min contre 15) : un
    compte plateforme contourne le RBAC d'un cabinet entier, la fenêtre
    d'exposition doit être plus étroite.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.PLATFORM_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    claims: Dict[str, Any] = {"roles": roles, "permissions": permissions}
    if custom_claims:
        claims.update(custom_claims)
    return _signer_platform(_payload_platform(user_id, "access", expire, claims))


def create_platform_refresh_token(
    user_id: str,
    jti: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Refresh plateforme : 8 h, rotation obligatoire, révocable via `jti`."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.PLATFORM_REFRESH_TOKEN_EXPIRE_HOURS)
    )
    return _signer_platform(_payload_platform(user_id, "refresh", expire, {"jti": jti}))


def create_support_access_token(
    tenant_id: str,
    agent_id: str,
    agent_email: str,
    access_id: str,
    motif: str,
    ticket: Optional[str],
    lecture_seule: bool = True,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Jeton d'accès SUPPORT (Phase D) : 30 minutes, non renouvelable.

    - Audience `sysdent-tenant` : il est destiné aux routes du cabinet, pas à la
      console plateforme ; un jeton support ne peut donc pas ouvrir `/platform/*`.
    - `lecture_seule=True` par défaut : `require_permissions` refuse alors toute
      permission d'écriture, d'export ou de gestion des droits. Lever cette
      contrainte exige la permission `platform.support.elevation` ET un motif
      renforcé validé côté service.
    - `jti` = identifiant de la demande : chaque ligne d'accès support est
      révocable individuellement.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.PLATFORM_SUPPORT_TOKEN_EXPIRE_MINUTES)
    )
    now = int(datetime.now(timezone.utc).timestamp())
    payload: Dict[str, Any] = {
        "sub": str(agent_id),
        "type": "access",
        "aud": settings.TENANT_AUDIENCE,
        "scope": settings.SUPPORT_SCOPE,
        "tenant_id": str(tenant_id),
        "impersonated_by": str(agent_id),
        "impersonated_by_email": agent_email,
        "support_reason": motif,
        "support_ticket": ticket,
        "support_access_id": str(access_id),
        "lecture_seule": bool(lecture_seule),
        "role": "SUPPORT_LECTURE",
        "permissions": ["*:READ"],
        "iat": now,
        "nbf": now,
        "exp": int(expire.timestamp()),
        "iss": f"{settings.APP_NAME} Support",
    }
    return _signer_platform(payload)


_fernet = Fernet(settings.TENANT_DB_ENCRYPTION_KEY.encode())


def encrypt_secret(plain_value: str) -> str:
    """Chiffre une valeur sensible (ex: mot de passe de connexion tenant) avant stockage en base."""
    return _fernet.encrypt(plain_value.encode()).decode()


def decrypt_secret(encrypted_value: str) -> str:
    """Déchiffre une valeur précédemment chiffrée avec `encrypt_secret`."""
    try:
        return _fernet.decrypt(encrypted_value.encode()).decode()
    except InvalidToken as e:
        raise ValueError("Impossible de déchiffrer la valeur : clé TENANT_DB_ENCRYPTION_KEY invalide ou valeur corrompue.") from e
