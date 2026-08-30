from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import structlog
from src.api.v1.router import api_v1_router
from src.core.config import settings
from src.core.database import master_engine, tenant_db_manager
from src.core.exception_handlers import register_exception_handlers
from src.core.logging import setup_logging
from src.core.middleware import setup_middlewares

# Initialiser le logging structuré
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestionnaire de cycle de vie de l'application FastAPI (Démarrage & Arrêt)."""
    logger.info(
        "app_starting_up",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    yield
    logger.info("app_shutting_down")
    # Fermeture des connexions DB
    await master_engine.dispose()
    await tenant_db_manager.close_all()
    logger.info("all_database_connections_closed")


# Initialisation de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API Backend Haute Performance & Sécurité pour la Gestion Multi-Cabinets Dentaires",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 1. Middlewares de sécurité et corrélation de requêtes
setup_middlewares(app)

# 2. CORS (Cross-Origin Resource Sharing)
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 3. Trusted Hosts
if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[str(host) for host in settings.ALLOWED_HOSTS],
    )

# 4. Enregistrement des Exception Handlers unifiés (RFC 7807)
register_exception_handlers(app)

# 5. Inclusion des Routes API
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Monitoring & Santé"])
async def health_check():
    """Vérification de l'état de fonctionnement du serveur."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
