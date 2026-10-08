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


class UnknownQueryParamMiddleware(BaseHTTPMiddleware):
    """
    Refuse les paramètres de requête qu'aucune route ne déclare.

    **Pourquoi.** FastAPI ignore silencieusement un paramètre qu'il ne connaît
    pas. C'est la cause directe d'un bug déjà rencontré : le tableau de bord
    envoyait `?page=1&limit=5` sur une route attendant `limite`, la pagination
    était ignorée, et **rien ne le signalait** — le juste affichait 100
    rendez-vous au lieu de 5, sans le moindre message.

    Un paramètre ignoré en silence est la pire sorte de défaut : il ne se voit
    pas à l'exécution, pas au type-check, et pas dans le test de l'écran qui
    suppose que le filtre a fonctionné. On préfère une erreur franche.

    **Périmètre étroit, volontairement.** Seules les requêtes dont le chemin
    *et* la méthode correspondent à une route enregistrée sont contrôlées. Les
    paramètres sont lus dans la signature du endpoint, donc la liste autorisée
    est toujours celle du code : aucun risque de dérive entre les deux.

    **Quand la table est construite.** À la première requête, pas à
    l'enregistrement du middleware : celui-ci est posé avant l'inclusion des
    routes (ordre de `main.py`), et une table bâtie à cet instant serait vide.
    La construire paresseusement est donc ce qui la rend correcte.

    Les paramètres de chemin (`{id}`) sont retirés de la comparaison — ils ne
    sont pas des paramètres de requête.
    """

    #: Préfixe sous lequel les routers sont montés (`/api/v1`).
    PREFIXE: str = "/api/v1"

    #: Cache chemin+méthode → {paramètres de requête acceptés}.
    _autorises: dict[str, frozenset[str]] | None = None

    @staticmethod
    def _aplatir(routes, profondeur: int = 0):
        """Parcourt les routes **et** les routeurs inclus, quel que soit leur niveau.

        Cette version de FastAPI ne fusionne pas les routeurs inclus dans
        `app.routes` : l'arbre est un enchaînement de nœuds `_IncludedRouter`, du
        routeur v1 jusqu'aux modules. Ne pas descendre dedans donne une table
        vide — et donc un contrôle qui ne s'exécute jamais, en silence. C'est
        exactement le piège rencontré dans `tests/inventaire_listes.py`.

        On suit `original_router.routes` : ce nœud **n'expose pas d'attribut
        `routes` du tout** (y accéder lève `AttributeError`), et `original_router`
        est le seul accès au contenu.

        La profondeur est bornée : un graphe malformé ne doit pas boucler.
        """
        if profondeur > 20:  # pragma: no cover - garde-fou
            return
        from fastapi.routing import APIRoute

        for route in routes:
            if isinstance(route, APIRoute):
                yield route
                continue
            origine = getattr(route, "original_router", None)
            if origine is not None:
                yield from UnknownQueryParamMiddleware._aplatir(
                    getattr(origine, "routes", []), profondeur + 1
                )

    @classmethod
    def _construire(cls, app: FastAPI) -> dict[str, frozenset[str]]:
        import inspect

        from fastapi.routing import APIRoute

        if cls._autorises is not None:
            return cls._autorises
        autorises: dict[str, frozenset[str]] = {}
        for route in cls._aplatir(app.routes):
            signature = inspect.signature(route.endpoint)
            noms = {
                nom
                for nom, param in signature.parameters.items()
                if param.default is not inspect.Parameter.empty
                and param.annotation is not inspect.Parameter.empty
            }
            for methode in route.methods or set():
                # Deux clés par route : le chemin **monté** (celui que reçoit la
                # requête) et le chemin relatif au router (celui qu'expose
                # `route.path`). Ne garder que le premier ne matchait jamais, et
                # le second ne correspond pas à l'URL : le contrôle était donc
                # simplement inerte.
                chemin = route.path or "/"
                autorises[f"{methode} {cls.PREFIXE}{chemin}"] = frozenset(noms)
                autorises[f"{methode} {chemin}"] = frozenset(noms)
        cls._autorises = autorises
        return autorises

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from fastapi.responses import JSONResponse

        autorises = self._construire(request.app)
        cle = f"{request.method} {request.url.path}"
        attendus = autorises.get(cle)
        if attendus is not None:
            recus = set(request.query_params.keys())
            # Un paramètre répété (`?statut=A&statut=B`) est légitime : c'est la
            # façon dont FastAPI déclare une liste. On ne le compte donc pas.
            inconnus = sorted(recus - attendus)
            if inconnus:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "PARAMETRE_INCONNU",
                            "message": (
                                f"Paramètre(s) non reconnu(s) : {', '.join(inconnus)}. "
                                f"Paramètres acceptés : {', '.join(sorted(attendus))}."
                            ),
                            "details": {"inconnus": inconnus},
                        }
                    },
                )
        return await call_next(request)


def setup_middlewares(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestCorrelationMiddleware)
    # Enregistré en dernier : `add_middleware` empile, et c'est le dernier
    # ajouté qui s'exécute en premier — donc celui qui contrôle les paramètres
    # avant que la route ne les interprète.
    app.add_middleware(UnknownQueryParamMiddleware)
