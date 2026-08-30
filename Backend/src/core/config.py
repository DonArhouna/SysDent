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

    # Base de données Master (Centrale)
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

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
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
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
