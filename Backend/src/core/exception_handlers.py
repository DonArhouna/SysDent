from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from .config import settings
from .exceptions import AppException

logger = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        
        logger.warning(
            "app_exception_raised",
            code=exc.code,
            status_code=exc.status_code,
            message=exc.message,
            request_id=request_id,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Reformater les erreurs de validation Pydantic pour une meilleure lisibilité
        formatted_errors = []
        for error in exc.errors():
            loc = " -> ".join([str(x) for x in error.get("loc", []) if x != "body"])
            formatted_errors.append({
                "field": loc or "body",
                "message": error.get("msg"),
                "type": error.get("type"),
            })

        logger.info(
            "request_validation_failed",
            errors=formatted_errors,
            request_id=request_id,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Les données envoyées dans la requête sont invalides.",
                    "details": {"errors": formatted_errors},
                    "request_id": request_id,
                },
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def model_validation_exception_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        """
        Erreur de validation levée par un modèle construit DANS un handler.

        `RequestValidationError` ne couvre que la phase de lecture de la requête.
        Un service qui reconstruit un schéma métier — un `PATCH` fusionné avec
        l'état courant, par exemple — peut échouer plus tard, et l'erreur
        remontait alors en 500 « erreur interne ». C'est une faute de l'appelant,
        pas du serveur : la réponse doit être un 422 avec le champ fautif, sinon
        l'interface affiche « une erreur inattendue » au lieu d'indiquer quoi
        corriger.
        """
        request_id = getattr(request.state, "request_id", "unknown")

        formatted_errors = [
            {
                "field": " -> ".join(str(x) for x in error.get("loc", ())) or "body",
                "message": error.get("msg"),
                "type": error.get("type"),
            }
            for error in exc.errors()
        ]

        logger.info(
            "model_validation_failed",
            errors=formatted_errors,
            request_id=request_id,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Les données envoyées dans la requête sont invalides.",
                    "details": {"errors": formatted_errors},
                    "request_id": request_id,
                },
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "details": {},
                    "request_id": request_id,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")

        logger.exception(
            "unhandled_server_exception",
            error=str(exc),
            request_id=request_id,
            path=request.url.path,
        )

        # En production, ne JAMAIS renvoyer la stacktrace brute au client
        message = "Une erreur interne inattendue s'est produite. Veuillez contacter le support."
        details = {}
        if settings.DEBUG:
            details = {"exception": str(exc), "type": type(exc).__name__}

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": message,
                    "details": details,
                    "request_id": request_id,
                },
            },
        )
