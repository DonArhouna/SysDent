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
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Génère un JWT Refresh Token de longue durée avec signature unique."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Décode et valide la signature et l'expiration d'un JWT."""
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
