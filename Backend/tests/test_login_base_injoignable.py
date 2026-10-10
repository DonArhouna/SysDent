"""Un login dont la base de cabinet est injoignable ne produit jamais un 500.

**Le cas réel.** Le 08/10, `POST /auth/login` a renvoyé
``asyncpg.exceptions.InvalidCatalogNameError: database "sysdent_tenant_..."
does not exist`` : la purge avait effacé la base du cabinet, et l'erreur
partait telle quelle au client, nom de base compris.

**Pourquoi le diagnostic précédent n'avait rien discriminé.** Il testait un
utilisateur **inexistant** : le 401 tombait avant toute résolution de base. Ce
test-ci fait échouer la base, pas l'utilisateur - c'est la seule façon de
distinguer les deux.

Aucune base n'est créée ni supprimée ici : la base est simulée.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
from sqlalchemy.exc import InterfaceError, OperationalError, ProgrammingError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.exceptions import (  # noqa: E402
    AppException,
    AuthenticationException,
    TenantConnectionException,
)
from src.modules.auth import services  # noqa: E402
from src.modules.auth.services import AuthService  # noqa: E402

#: Nom réel de la base qui a disparu le 08/10.
DB_NAME = "sysdent_tenant_clinique_cabinet_sn_5bd215"


class _SessionQuiEchoue:
    """Session tenant dont la base n'existe plus : la première exécution lève."""

    def __init__(self, erreur: BaseException) -> None:
        self._erreur = erreur

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *args, **kwargs):
        raise self._erreur


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        societe_id=uuid.uuid4(),
        db_name=DB_NAME,
        db_host="127.0.0.1",
        db_port=55435,
        db_user="postgres",
        db_password="chiffre",
    )


async def _login_sur_base_injoignable(monkeypatch, erreur: BaseException):
    """Lance un login dont la base tenant échoue. Renvoie (exception, config)."""
    config = _config()

    async def _resoudre(master_db, email):
        return config, None

    async def _moteur(**kwargs):
        return None

    async def _fabrique(tenant_id):
        return lambda: _SessionQuiEchoue(erreur)

    monkeypatch.setattr(AuthService, "_resoudre_tenant", _resoudre)
    monkeypatch.setattr(services.tenant_db_manager, "get_or_create_engine", _moteur)
    monkeypatch.setattr(services.tenant_db_manager, "get_session_factory", _fabrique)
    # Le mot de passe de la base est chiffré dans le registre : ici il n'a pas
    # à être réel, la base de toute façon n'existe pas.
    monkeypatch.setattr(services, "decrypt_secret", lambda valeur: "clair")

    with pytest.raises(BaseException) as recolte:
        await AuthService.authenticate(
            email="praticien@cabinet.sn", password="motdepasse", master_db=None
        )
    return recolte.value, config


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "erreur",
    [
        # Le 08/10, à l'identique.
        asyncpg.exceptions.InvalidCatalogNameError(f'database "{DB_NAME}" does not exist'),
        asyncpg.exceptions.ConnectionDoesNotExistError("connection does not exist"),
        asyncpg.exceptions.PostgresConnectionError("connection refused"),
        asyncpg.exceptions.ClientCannotConnectError("no more connections allowed"),
        asyncpg.exceptions.AdminShutdownError("server shut down"),
        asyncpg.exceptions.TooManyConnectionsError("too many connections"),
        OperationalError("connection", None, ConnectionRefusedError(111)),
        InterfaceError("interface", None, OSError(104)),
    ],
)
async def test_un_login_sur_base_injoignable_ne_produit_pas_un_500(monkeypatch, erreur) -> None:
    """
    **Chaque erreur de la liste fermée donne le même résultat contrôlé.**

    Ni l'identifiant du cabinet, ni le nom de sa base, ni le message de
    PostgreSQL ne doivent atteindre le client : le nom de la base, c'est
    exactement ce qui fuitait dans le 500.
    """
    soulevee, config = await _login_sur_base_injoignable(monkeypatch, erreur)

    assert isinstance(soulevee, TenantConnectionException), (
        f"{type(erreur).__name__} doit devenir une réponse contrôlée, "
        f"pas un {type(soulevee).__name__}"
    )
    assert soulevee.status_code == 503
    assert soulevee.code == "SERVICE_INDISPONIBLE"

    # Aucune fuite d'information, ni dans le message ni dans les détails.
    textes = [soulevee.message, str(soulevee.details)]
    assert str(config.societe_id) not in textes
    assert DB_NAME not in textes
    assert "does not exist" not in textes
    assert soulevee.details == {}


@pytest.mark.asyncio
async def test_le_nom_de_la_base_ne_sort_jamais(monkeypatch) -> None:
    """
    La vérification la plus directe : le nom de la base disparue, cherché mot
    pour mot dans tout ce qui part vers le client.
    """
    erreur = asyncpg.exceptions.InvalidCatalogNameError(f'database "{DB_NAME}" does not exist')
    soulevee, _ = await _login_sur_base_injoignable(monkeypatch, erreur)
    # Le nom apparaît dans la cause, jamais dans la réponse.
    assert DB_NAME in str(soulevee.__cause__)
    assert DB_NAME not in repr(AppException.__doc__ or "")
    for fragment in (soulevee.message, str(soulevee.details), soulevee.code):
        assert DB_NAME not in fragment


@pytest.mark.asyncio
async def test_une_erreur_de_donnee_n_est_pas_deguisee_en_503(monkeypatch) -> None:
    """
    La liste est fermée : une erreur qui vient de la donnée n'est pas une panne.

    Si un `except Exception` prenait la place, une violation de contrainte
    deviendrait « service indisponible » et le vrai bug deviendrait invisible.
    """
    soulevee, _ = await _login_sur_base_injoignable(monkeypatch, ValueError("bug d'application"))
    assert isinstance(soulevee, ValueError)
    assert not isinstance(soulevee, AppException)


@pytest.mark.asyncio
async def test_un_email_inconnu_reste_un_refus_de_mot_de_passe(monkeypatch) -> None:
    """
    La base répond, mais l'utilisateur n'y est pas : c'est un 401, pas un 503.

    C'est le cas que le diagnostic précédent testait - il ne discriminait rien
    puisqu'il tombait ici quel que soit l'état de la base.
    """

    class _SessionVide:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *args, **kwargs):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    config = _config()

    async def _resoudre(master_db, email):
        return config, None

    async def _moteur(**kwargs):
        return None

    async def _fabrique_vide(tenant_id):
        return _SessionVide

    monkeypatch.setattr(AuthService, "_resoudre_tenant", _resoudre)
    monkeypatch.setattr(services.tenant_db_manager, "get_or_create_engine", _moteur)
    monkeypatch.setattr(services.tenant_db_manager, "get_session_factory", _fabrique_vide)
    monkeypatch.setattr(services, "decrypt_secret", lambda valeur: "clair")

    with pytest.raises(AuthenticationException) as recolte:
        await AuthService.authenticate(
            email="inconnu@cabinet.sn", password="motdepasse", master_db=None
        )
    assert recolte.value.status_code == 401
    assert recolte.value.code == "INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# 6. Schema perime : la base repond, mais plus comme le code l'attend
# ---------------------------------------------------------------------------
#:
#: Le 10/10, la base d'un cabinet restauree etait en retard de deux migrations.
#: La connexion reussissait, puis la premiere requete levait
#: `UndefinedColumnError: column utilisateurs.cabinet_id does not exist` - un 500
#: dont le client apprenait le schema interne du cabinet.
#:
#: SQLAlchemy encapsule cette erreur dans `ProgrammingError`. Ce n'est pas un 500
#: de plus a ajouter au traitement : c'est un 500 de trop, qui doit rejoindre
#: les autres.


def _erreur_sqlalchemy(classe_asyncpg: type, message: str) -> ProgrammingError:
    """Reproduit l'encapsulation reelle : SQLAlchemy garde l'erreur asyncpg dans `.orig`."""
    origine = classe_asyncpg(message)
    return ProgrammingError("SELECT ...", {}, origine)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "erreur",
    [
        _erreur_sqlalchemy(
            asyncpg.exceptions.UndefinedColumnError,
            "column utilisateurs.cabinet_id does not exist",
        ),
        _erreur_sqlalchemy(
            asyncpg.exceptions.UndefinedTableError,
            'relation "file_attente" does not exist',
        ),
    ],
)
async def test_un_schema_perime_ne_produit_pas_un_500(monkeypatch, erreur) -> None:
    """
    **La base est la, le code ne l'est plus.** Reponse controlee, generique,
    sans nom de colonne ni nom de table dans la reponse.
    """
    soulevee, _ = await _login_sur_base_injoignable(monkeypatch, erreur)

    assert isinstance(soulevee, TenantConnectionException), (
        f"{type(erreur.orig).__name__} doit devenir une reponse controlee, "
        f"pas un {type(soulevee).__name__}"
    )
    assert soulevee.status_code == 503
    assert soulevee.code == "SERVICE_INDISPONIBLE"
    assert soulevee.details == {}
    for fragment in (soulevee.message, str(soulevee.details), soulevee.code):
        assert "cabinet_id" not in fragment
        assert "file_attente" not in fragment


@pytest.mark.asyncio
async def test_une_erreur_sql_de_code_n_est_pas_deguisee(monkeypatch) -> None:
    """
    La liste reste fermee, en profondeur cette fois : `ProgrammingError` est
    aussi levee par une requete mal ecrite. Un SQL casse par le code n'est pas
    une base injoignable - il doit remonter tel quel, sinon le vrai bug devient
    un « service indisponible » et disparait des journaux exploitables.
    """
    erreur = _erreur_sqlalchemy(
        asyncpg.exceptions.SyntaxOrAccessError, 'syntax error at or near "SELCT"'
    )
    soulevee, _ = await _login_sur_base_injoignable(monkeypatch, erreur)

    assert not isinstance(soulevee, AppException), (
        "une erreur SQL de code ne doit pas devenir une reponse controlee"
    )
    assert isinstance(soulevee, ProgrammingError)


@pytest.mark.asyncio
async def test_un_schema_perime_est_journalise_avec_le_cabinet(monkeypatch) -> None:
    """
    Le journal doit identifier le cabinet et nommer la divergence, sans jamais
    laisser fuiter d'identifiants de connexion.
    """
    import structlog
    from structlog.testing import capture_logs

    erreur = _erreur_sqlalchemy(
        asyncpg.exceptions.UndefinedColumnError,
        "column utilisateurs.cabinet_id does not exist",
    )
    config = SimpleNamespace(
        societe_id=uuid.uuid4(),
        db_name=DB_NAME,
        db_host="127.0.0.1",
        db_port=55435,
        db_user="postgres",
        db_password="NE_DOIT_PAS_APPARAITRE",
    )

    async def _resoudre(master_db, email):
        return config, None

    async def _moteur(**kwargs):
        return None

    async def _fabrique(tenant_id):
        return lambda: _SessionQuiEchoue(erreur)

    monkeypatch.setattr(AuthService, "_resoudre_tenant", _resoudre)
    monkeypatch.setattr(services.tenant_db_manager, "get_or_create_engine", _moteur)
    monkeypatch.setattr(services.tenant_db_manager, "get_session_factory", _fabrique)
    monkeypatch.setattr(services, "decrypt_secret", lambda valeur: "NE_DOIT_PAS_APPARAITRE")

    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(0))
    with capture_logs() as journaux:
        with pytest.raises(TenantConnectionException):
            await AuthService.authenticate(
                email="praticien@cabinet.sn", password="x", master_db=None
            )

    evenements = [e for e in journaux if "base_tenant_injoignable" in str(e.get("event", ""))]
    assert len(evenements) == 1, f"un seul journal attendu, obtenu {journaux}"
    entree = evenements[0]
    assert entree["tenant_id"] == str(config.societe_id)
    assert entree["db_name"] == DB_NAME
    assert entree["erreur"] == "UndefinedColumnError"
    assert "NE_DOIT_PAS_APPARAITRE" not in str(entree)
