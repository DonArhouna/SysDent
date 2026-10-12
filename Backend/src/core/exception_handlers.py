from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from .config import settings
from .exceptions import AppException
from .schema_perime import (
    CODE_SCHEMA_EN_RETARD,
    MESSAGE_SCHEMA_EN_RETARD,
    element_manquant,
    est_divergence_de_schema,
    tenant_courant,
)

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

    @app.exception_handler(DBAPIError)
    async def dbapi_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
        """
        Erreur renvoyée par le pilote de base : 503 si le cabinet est en retard
        de migrations, 500 sinon.

        **Pourquoi un gestionnaire dédié.** Le login traitait deja ce cas, mais
        seul : les routes de tarification lisaient la base de la meme facon et
        renvoyaient 500. Le client voyait alors une panne de l'application, et
        l'interface ne pouvait rien dire de plus. Un triage qui ne s'applique
        qu'a une route est un triage incomplet.

        **Le 503 ne doit rien laisser fuir.** Ni nom de table, ni identifiant de
        cabinet : le nom de la table manquante dit au client que la base est
        presente mais en retard, et le nom lui revele son schema. Ces deux
        elements vont au journal du serveur, avec le cabinet, la ou un
        administrateur peut agir.

        **Le reste n'est pas masqué.** Seules les divergences de schema
        recognisedes deviennent un 503. Toute autre erreur du pilote garde le
        500 d'avant, journalise avec sa trace : une faute de frappe dans une
        requete ne doit pas devenir invisible sous un libelle de maintenance.
        """
        request_id = getattr(request.state, "request_id", "unknown")

        if not est_divergence_de_schema(exc):
            return await unhandled_exception_handler(request, exc)

        manquant = element_manquant(exc)
        logger.error(
            "schema_tenant_en_retard",
            tenant_id=tenant_courant(),
            element_manquant=manquant,
            erreur=type(exc).__name__,
            sqlstate=getattr(exc, "sqlstate", None) or getattr(
                getattr(exc, "orig", None), "sqlstate", None
            ),
            request_id=request_id,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": CODE_SCHEMA_EN_RETARD,
                    "message": MESSAGE_SCHEMA_EN_RETARD,
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
