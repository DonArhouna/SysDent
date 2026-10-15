import uuid
from collections import OrderedDict
from typing import AsyncGenerator, Dict, Optional
import asyncpg
import structlog
from sqlalchemy import select
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from .config import settings
from .exceptions import MasterDatabaseUnavailableException, TenantConnectionException

logger = structlog.get_logger(__name__)

#: Échecs qui signifient « le registre est injoignable ». Liste fermée, pour la
#: même raison que celle du login : un `except Exception` déguiserait un bug en
#: panne d'infrastructure, et le bug deviendrait invisible.
#:
#: L'ouverture de connexion n'étant pas encapsulée par SQLAlchemy, l'erreur
#: remonte nue : `ConnectionRefusedError` sur une adresse, `OSError` quand
#: l'hôte résout en plusieurs et qu'asyncpg agrège leurs échecs. Les deux ont
#: été mesurés, le 11/10, avant d'être nommés ici.
REGISTRE_INJOIGNABLE = (
    ConnectionError,
    OSError,
    OperationalError,
    InterfaceError,
    asyncpg.exceptions.InvalidCatalogNameError,
    asyncpg.exceptions.PostgresConnectionError,
    asyncpg.exceptions.ClientCannotConnectError,
    asyncpg.exceptions.AdminShutdownError,
    asyncpg.exceptions.TooManyConnectionsError,
    asyncpg.exceptions.ConnectionDoesNotExistError,
)

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

    async def oublier(self, tenant_id: str) -> None:
        """
        Ferme et retire du cache le moteur d'un cabinet.

        Utile quand ses identifiants changent ou que sa base disparaît
        (compensation d'un provisionnement) : un moteur en cache garderait des
        connexions ouvertes avec les anciens identifiants.
        """
        engine = self._engines.pop(tenant_id, None)
        self._session_factories.pop(tenant_id, None)
        if engine is not None:
            await engine.dispose()

    async def close_all(self) -> None:
        """Ferme proprement tous les pools lors de l'arrêt de l'application."""
        logger.info("closing_all_tenant_engines", count=len(self._engines))
        for tenant_id, engine in list(self._engines.items()):
            await engine.dispose()
        self._engines.clear()
        self._session_factories.clear()


tenant_db_manager = TenantDatabaseManager()


async def get_master_db() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI pour obtenir une session de la base Master.

    **Une panne du registre est une panne d'infrastructure, pas un bug.** Le 11/10,
    le conteneur PostgreSQL de développement s'était arrêté ; le login renvoyait
    alors un 500 dont la réponse exposait `Connect call failed ('::1', 55435, 0, 0)`.
    Le client apprenait l'hôte et le port du serveur.

    L'échec d'ouverture de connexion n'est pas encapsulé par SQLAlchemy : il
    remonte **nu**, en `ConnectionRefusedError`, ou en `OSError` quand l'hôte
    résout en plusieurs adresses et qu'asyncpg agrège leurs échecs. Les deux
    formes sont converties ici en 503 générique, sans détail.

    La session est paresseuse : la connexion s'établit à la première requête,
    donc **après** le `yield`. L'erreur remonte alors par la dépendance ; c'est
    ici qu'elle est rattrapée, et nulle part ailleurs.
    """
    async with MasterAsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except REGISTRE_INJOIGNABLE as exc:
            await session.rollback()
            logger.error(
                "registre_injoignable",
                erreur=type(exc).__name__,
                detail=" ".join(str(exc).split())[:200],
            )
            raise MasterDatabaseUnavailableException() from exc
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
