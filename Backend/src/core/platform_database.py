"""
Accès à la base DÉDIÉE de la plateforme (`sysdent_platform`).

Ce module est le pendant exact de `src/core/database.py` (base master) et
`TenantDatabaseManager` (bases clients) pour le troisième univers : le backoffice
éditeur. Trois moteurs, trois métadonnées, trois contextes Alembic — aucune
session n'est partagée, donc aucune requête ne peut croiser deux mondes par
accident.

Pourquoi une base séparée et pas un schéma dans `sysdent_master` : c'est la
décision D1 de `docs/backoffice/00_ETAT_DES_LIEUX.md`. Le motif tient en une
phrase : la base master est sur le chemin d'authentification de l'application
cliente ; y placer les secrets 2FA et le journal immuable de l'éditeur rendrait
toute fuite de ce chemin —au plus banal— une fuite de la plateforme.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

# Moteur plateforme. `create_async_engine` n'ouvre AUCUNE connexion à l'import :
# une base plateforme absente n'empêche donc pas l'application cliente de
# démarrer (les routes `/platform/*` lèveront 503, pas 500).
platform_engine: AsyncEngine = create_async_engine(
    settings.platform_db_async_url,
    echo=settings.PLATFORM_DB_ECHO,
    pool_size=settings.PLATFORM_DB_POOL_SIZE,
    max_overflow=settings.PLATFORM_DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

PlatformSessionFactory = async_sessionmaker(
    bind=platform_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_platform_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance FastAPI fournissant une session sur la base plateforme.

    Commit automatique en sortie, rollback sur exception : le même contrat que
    `get_master_db`, pour que les services aient les mêmes habitudes.
    """
    async with PlatformSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_platform_engine() -> None:
    """Ferme le pool plateforme (appelé au lifespan de l'application)."""
    await platform_engine.dispose()