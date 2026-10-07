import uuid
from collections import OrderedDict
from typing import AsyncGenerator, Dict, Optional
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from .config import settings
from .exceptions import TenantConnectionException

logger = structlog.get_logger(__name__)

# Engine Master pour la gestion centrale
master_engine: AsyncEngine = create_async_engine(
    settings.master_db_async_url,
    echo=settings.MASTER_DB_ECHO,
    pool_size=settings.MASTER_DB_POOL_SIZE,
    max_overflow=settings.MASTER_DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

MasterAsyncSessionFactory = async_sessionmaker(
    bind=master_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class TenantDatabaseManager:
    """
    Gestionnaire dynamique de pools de connexions pour les bases Tenants.
    Utilise un cache LRU pour éviter la surconsommation de sockets PostgreSQL.
    """

    def __init__(self, max_cached_engines: int = 50):
        self._engines: OrderedDict[str, AsyncEngine] = OrderedDict()
        self._session_factories: Dict[str, async_sessionmaker[AsyncSession]] = {}
        self._max_cached_engines = max_cached_engines

    def _build_tenant_url(
        self,
        db_name: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> str:
        h = host or settings.TENANT_DB_HOST
        p = port or settings.TENANT_DB_PORT
        u = user or settings.TENANT_DB_USER
        pwd = password or settings.TENANT_DB_PASSWORD
        return f"postgresql+asyncpg://{u}:{pwd}@{h}:{p}/{db_name}"

    async def get_or_create_engine(
        self,
        tenant_id: str,
        db_name: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> AsyncEngine:
        if tenant_id in self._engines:
            self._engines.move_to_end(tenant_id)
            return self._engines[tenant_id]

        url = self._build_tenant_url(db_name, host, port, user, password)
        logger.info("creating_tenant_engine", tenant_id=tenant_id, db_name=db_name)

        try:
            engine = create_async_engine(
                url,
                echo=settings.DEBUG and False,
                pool_size=settings.TENANT_DB_POOL_SIZE,
                max_overflow=settings.TENANT_DB_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
            self._engines[tenant_id] = engine
            self._session_factories[tenant_id] = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            # Éviction LRU si dépassement de capacité.
            # `dispose()` est indispensable : sans lui, chaque éviction abandonnait
            # un pool de connexions PostgreSQL ouvert. Le moteur était retiré du
            # cache mais ses sockets restaient actives jusqu'à la fermeture du
            # process — une fuite qui finit par épuiser le max_connections du
            # serveur au bout de quelques centaines de cabinets.
            if len(self._engines) > self._max_cached_engines:
                oldest_tenant, oldest_engine = self._engines.popitem(last=False)
                self._session_factories.pop(oldest_tenant, None)
                logger.info("evicting_old_tenant_engine", tenant_id=oldest_tenant)
                await oldest_engine.dispose()

            return engine
        except Exception as e:
            logger.exception("tenant_engine_creation_failed", tenant_id=tenant_id, error=str(e))
            raise TenantConnectionException(tenant_id=tenant_id, original_error=str(e))

    async def get_session_factory(self, tenant_id: str) -> async_sessionmaker[AsyncSession]:
        """
        Session factory d'un cabinet, en créant le moteur si besoin.

        Le nom de la base est lu dans `tenants_db` (base master), et NON deviné
        par convention. L'ancien repli `f"sysdent_tenant_{tenant_id}"" ne
        fonctionnait que parce que les anciennes bases ont ete creees avec cette
        convention : le provisionnement actuel (`sanitize_db_name`) genere un nom
        lisible (`sysdent_tenant_cabinet_dupont_1a2b3c`). Un cabinet cree par la
        console etait donc inaccessible a tout appelant qui n'avait pas encore
        passe par `get_tenant_db` — erreur « base does not exist » au lieu d'une
        session. Deviner un nom de base est de toute façon une faute : le
        véritable nom est une donnee, pas une convention.
        """
        if tenant_id not in self._session_factories:
            from src.core.security import decrypt_secret
            from src.modules.master.models import TenantDB

            from src.core.database import MasterAsyncSessionFactory

            async with MasterAsyncSessionFactory() as master:
                config = (
                    await master.execute(
                        select(TenantDB).where(TenantDB.societe_id == uuid.UUID(tenant_id))
                    )
                ).scalar_one_or_none()
            if config is None:
                raise TenantConnectionException(tenant_id=tenant_id, original_error="Dossier de base introuvable.")
            await self.get_or_create_engine(
                tenant_id=tenant_id,
                db_name=config.db_name,
                host=config.db_host,
                port=config.db_port,
                user=config.db_user,
                password=decrypt_secret(config.db_password),
            )
        return self._session_factories[tenant_id]

    async def close_all(self) -> None:
        """Ferme proprement tous les pools lors de l'arrêt de l'application."""
        logger.info("closing_all_tenant_engines", count=len(self._engines))
        for tenant_id, engine in list(self._engines.items()):
            await engine.dispose()
        self._engines.clear()
        self._session_factories.clear()


tenant_db_manager = TenantDatabaseManager()


async def get_master_db() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI pour obtenir une session de la base Master."""
    async with MasterAsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
