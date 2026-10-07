import json
from typing import List, Literal, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "SysDent Pro API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Sécurité & Auth
    SECRET_KEY: str = "sysdent-dev-secret-key-super-secure-for-local-testing-purposes-only-32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Clé Fernet (32 octets url-safe base64) utilisée pour chiffrer les secrets stockés en base (ex: TenantDB.db_password).
    # CHANGER en production : Fernet.generate_key().decode()
    TENANT_DB_ENCRYPTION_KEY: str = "T8WR4tc3-0J8dU0YTg44LB-lsD_hfK4JtMCGf6eRkc0="

    # ─────────────────────────────────────────────────────────────────────────
    # PLATEFORME (backoffice éditeur) — decisions D1 a D5 de l'etat des lieux
    # ─────────────────────────────────────────────────────────────────────────
    # Base DEDICEE `sysdent_platform`, distincte de la base master ET des bases
    # tenants : un role SQL plateforme n'a aucun droit sur les bases clients, et
    # aucune donnee plateforme (secrets 2FA, journal immuable) n'est atteignable
    # depuis le chemin d'authentification de l'application cliente.
    PLATFORM_DB_HOST: str = "localhost"
    PLATFORM_DB_PORT: int = 5432
    PLATFORM_DB_USER: str = "postgres"
    PLATFORM_DB_PASSWORD: str = "postgres_password"
    PLATFORM_DB_NAME: str = "sysdent_platform"
    PLATFORM_DB_ECHO: bool = False
    PLATFORM_DB_POOL_SIZE: int = 5
    PLATFORM_DB_MAX_OVERFLOW: int = 10

    # Cle de signature DEDICEE aux jetons de la plateforme. Un jeton plateforme
    # signe avec cette cle, un jeton tenant avec SECRET_KEY : la signature seule
    # suffit a interdire le passage d'un monde a l'autre.
    # VIDE => derivee de SECRET_KEY (HKDF, info="sysdent-platform") en
    # developpement uniquement, avec avertissement. En production le refus de
    # demarrer est immediate : une cle dediee explicite est une exigence.
    PLATFORM_SECRET_KEY: str = ""
    # HS512 pour la plateforme : cout marginal, defense en profondeur face a une
    # divulgation de cle (le secret d'un compte editeur n'est pas reutilisable).
    PLATFORM_ALGORITHM: str = "HS512"
    # Audiences et scopes des trois familles de jetons. Un jeton n'est accepte que
    # par la famille qui l'a emis (cf. core/security.decode_token_scoped).
    PLATFORM_AUDIENCE: str = "sysdent-platform"
    TENANT_AUDIENCE: str = "sysdent-tenant"
    PLATFORM_SCOPE: str = "platform"
    SUPPORT_SCOPE: str = "support"
    TENANT_SCOPE: str = "tenant"

    # Durees : plus courtes que celles du client (D4). Un acces plateforme
    # contourne tout le RBAC d'un cabinet, la surface doit etre etroite.
    PLATFORM_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10
    PLATFORM_REFRESH_TOKEN_EXPIRE_HOURS: int = 8
    PLATFORM_SUPPORT_TOKEN_EXPIRE_MINUTES: int = 30
    # Elévation d'un acces support hors lecture seule (Phase D.2). Desactivee par
    # defaut : un acces en ecriture dans le dossier d'un cabinet doit etre une
    # decision explicite de l'exploitant, jamais un simple drapeau a poser.
    PLATFORM_SUPPORT_ELEVATION_ABILITEE: bool = False
    # Notification de l'administrateur du cabinet a chaque ouverture d'acces
    # (Phase D.3). Le journal d'audit du cabinet reste, lui, toujours alimente.
    PLATFORM_SUPPORT_NOTIFIER_ADMIN: bool = False

    # Job periodique d'agregation des statistiques de supervision (Phase E.1).
    # Aucun planificateur n'est embarque : le job est expose comme service et
    # appelle par cron. La valeur sert a afficher la frequence ATTENDUE dans
    # `GET /platform/sante` — declarer une cadence que rien n'applique serait
    # une fausse assurance.
    PLATFORM_JOB_FREQUENCE_AGGREGATION: str = "quotidienne (02:00 UTC)"

    # 2FA TOTP obligatoire pour tout compte plateforme (Phase A.4).
    PLATFORM_2FA_ISSUER: str = "SysDent Pro Plateforme"
    PLATFORM_2FA_TOTP_DIGITS: int = 6
    PLATFORM_2FA_TOTP_INTERVAL: int = 30

    # Politique de mot de passe stricte (Phase A.4).
    PLATFORM_PASSWORD_MIN_LENGTH: int = 12
    PLATFORM_MAX_FAILED_LOGINS: int = 5
    PLATFORM_LOCKOUT_MINUTES: int = 15
    # Liste blanche d'IP pour la console plateforme (Phase A.4).
    # Vide = aucune restriction. Format : liste separee par des virgules, CIDR accepte.
    PLATFORM_IP_WHITELIST: Union[List[str], str] = ""

    # Cle Fernet dediee : chiffre en base les secrets plateforme qui ne sont pas
    # des hachages (secret TOTP, jetons de verification / invitation en attente).
    # Distincte de TENANT_DB_ENCRYPTION_KEY pour qu'une fuite ne serve pas les deux.
    PLATFORM_SECRET_ENCRYPTION_KEY: str = ""

    # ─────────────────────────────────────────────────────────────────────────
    # ONBOARDING PUBLIC (Phase F)
    # ─────────────────────────────────────────────────────────────────────────
    ONBOARDING_ENABLED: bool = True
    ONBOARDING_ESSAI_DAYS: int = 14
    # Regle appliquee a l'expiration d'un essai : `suspend` (le cabinet perd l'acces
    # sans perdre ses donnees) ou `cancel` (l'essai bascule en `resilie`).
    ONBOARDING_ESSAI_EXPIRE_ACTION: Literal["suspend", "cancel"] = "suspend"
    ONBOARDING_VERIFICATION_TOKEN_MINUTES: int = 60
    # Anti-bot : `none` (desactive), `header` (secret partage attendu dans un
    # en-tete — integration Turnstile/hCaptcha cote proxy), `honeypot` (champ-piege
    # que seul un robot remplit).
    ONBOARDING_CAPTCHA_MODE: Literal["none", "header", "honeypot"] = "honeypot"
    ONBOARDING_CAPTCHA_HEADER: str = "X-Captcha-Token"
    ONBOARDING_CAPTCHA_SECRET: str = ""

    # Base de donnees Master (Centrale)
    MASTER_DB_HOST: str = "localhost"
    MASTER_DB_PORT: int = 5432
    MASTER_DB_USER: str = "postgres"
    MASTER_DB_PASSWORD: str = "postgres_password"
    MASTER_DB_NAME: str = "sysdent_master"
    MASTER_DB_ECHO: bool = False
    MASTER_DB_POOL_SIZE: int = 10
    MASTER_DB_MAX_OVERFLOW: int = 20

    # Configuration générique des bases de données Tenants
    TENANT_DB_HOST: str = "localhost"
    TENANT_DB_PORT: int = 5432
    TENANT_DB_USER: str = "postgres"
    TENANT_DB_PASSWORD: str = "postgres_password"
    TENANT_DB_POOL_SIZE: int = 5
    TENANT_DB_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # CORS & Domaines autorisés
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
    ALLOWED_HOSTS: Union[List[str], str] = ["*"]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", "PLATFORM_IP_WHITELIST", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [i.strip() for i in value.split(",") if i.strip()]
        return value

    @property
    def master_db_async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.MASTER_DB_USER}:{self.MASTER_DB_PASSWORD}"
            f"@{self.MASTER_DB_HOST}:{self.MASTER_DB_PORT}/{self.MASTER_DB_NAME}"
        )

    @property
    def master_db_sync_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.MASTER_DB_USER}:{self.MASTER_DB_PASSWORD}"
            f"@{self.MASTER_DB_HOST}:{self.MASTER_DB_PORT}/{self.MASTER_DB_NAME}"
        )

    @property
    def platform_db_async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.PLATFORM_DB_USER}:{self.PLATFORM_DB_PASSWORD}"
            f"@{self.PLATFORM_DB_HOST}:{self.PLATFORM_DB_PORT}/{self.PLATFORM_DB_NAME}"
        )

    @property
    def platform_db_sync_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.PLATFORM_DB_USER}:{self.PLATFORM_DB_PASSWORD}"
            f"@{self.PLATFORM_DB_HOST}:{self.PLATFORM_DB_PORT}/{self.PLATFORM_DB_NAME}"
        )

    @property
    def platform_server_url(self) -> str:
        """URL du serveur PostgreSQL plateforme, sans nom de base (creation de base)."""
        return (
            f"postgresql://{self.PLATFORM_DB_USER}:{self.PLATFORM_DB_PASSWORD}"
            f"@{self.PLATFORM_DB_HOST}:{self.PLATFORM_DB_PORT}"
        )

    @property
    def ip_whitelist_platform(self) -> List[str]:
        return self.PLATFORM_IP_WHITELIST or []

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()


def _deriver_cle_platform(secret_key: str) -> str:
    """
    Derive une cle de signature plateforme a partir de SECRET_KEY (HKDF-SHA256).

    Solution de repli pour le developpement uniquement : la cle reste DISTINCTE de
    SECRET_KEY (l'etancheite par signature est donc preservee) mais elle est
    reproductible, ce qui permet de demarrer sans configuration prealable. En
    production, `PLATFORM_SECRET_KEY` est obligatoire.
    """
    import hashlib
    import hmac

    return hmac.new(
        secret_key.encode("utf-8"),
        b"sysdent-platform",
        hashlib.sha256,
    ).hexdigest()


def resoudre_cle_platform() -> str:
    """Cle effective de signature des jetons plateforme."""
    if settings.PLATFORM_SECRET_KEY:
        return settings.PLATFORM_SECRET_KEY
    if settings.APP_ENV == "production":
        raise RuntimeError(
            "PLATFORM_SECRET_KEY est obligatoire en production : la cle de signature "
            "de la plateforme ne peut pas heriter de SECRET_KEY."
        )
    return _deriver_cle_platform(settings.SECRET_KEY)


def resoudre_fernet_platform():
    """Instance Fernet dediee au stockage des secrets plateforme en base."""
    from cryptography.fernet import Fernet

    if settings.PLATFORM_SECRET_ENCRYPTION_KEY:
        return Fernet(settings.PLATFORM_SECRET_ENCRYPTION_KEY.encode())
    # Repli dev : cle derivee de la cle de chiffrement des bases tenants. Distincte
    # en production, ou PLATFORM_SECRET_ENCRYPTION_KEY est obligatoire.
    import base64
    import hashlib

    if settings.APP_ENV == "production":
        raise RuntimeError("PLATFORM_SECRET_ENCRYPTION_KEY est obligatoire en production.")
    brut = hashlib.sha256(
        (settings.TENANT_DB_ENCRYPTION_KEY + "|sysdent-platform").encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(brut))
