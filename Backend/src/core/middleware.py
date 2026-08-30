import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware qui injecte un Request ID (Corrélation ID) et mesure la latence HTTP.
    Transmet le contexte à structlog pour l'ensemble du cycle de vie de la requête.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Récupérer ou générer le Request-ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Lier le request_id aux logs du thread/coroutine en cours
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = str(process_time_ms)
            
            # Ne pas polluer avec les logs de santé / healthcheck fréquents
            if not request.url.path.endswith("/health"):
                logger.info(
                    "http_request_completed",
                    status_code=response.status_code,
                    duration_ms=process_time_ms,
                )
            return response
        except Exception as exc:
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "http_request_failed",
                error=str(exc),
                duration_ms=process_time_ms,
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware qui injecte les headers de sécurité standards recommandés pour la santé."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def setup_middlewares(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestCorrelationMiddleware)
