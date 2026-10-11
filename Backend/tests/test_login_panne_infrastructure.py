"""Un login ne doit jamais produire un 500 pour une panne d'infrastructure.

**Ce que ce fichier corrige, et pourquoi le test existant ne l'avait pas vu.**

`test_login_base_injoignable.py` verifie qu'un schema perime donne un 503. Il le
fait sur une **erreur fabriquee** a la main :

    ProgrammingError("SELECT ...", {}, UndefinedColumnError(...))

Cette forme n'est pas celle que SQLAlchemy produit. Mesure sur une base reelle,
colonne `utilisateurs.cabinet_id` reellement supprimee, la chaine est :

    niveau 0  sqlalchemy.exc.ProgrammingError
      .orig -> niveau 1  sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError
                    sqlstate=42703
                .orig -> niveau 2  asyncpg.exceptions.UndefinedColumnError
                                sqlstate=42703

`_est_divergence_de_schema` n'examinait que le niveau 1. L'erreur asyncpg, elle,
est au niveau 2. Le tri rendait donc « pas une divergence » et laissait remonter
un 500 - exactement la panne qu'il pretendait empecher.

Une simulation ne prouve que ce que son auteur a cru ecrire. D'ou les deux
volumes de ce fichier :

- la reproduction **reelle**, sur une base `jetable_*` de l'instance de tests ;
- les formes de panne que l'on peut fabriquer sans base, completees par la
  forme reelle observee pour la connexion.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.exceptions import AppException, TenantConnectionException  # noqa: E402
from src.modules.auth import services  # noqa: E402
from src.modules.auth.services import AuthService  # noqa: E402

#: Une base jetable est jetable : son nom commence par ce prefixe, et la garde de
#: purge reconnait ce prefixe. Aucun nom de base reelle n'est employe ici.
PREFIXE_JETABLE = "jetable_"


def _config(nom_base: str) -> SimpleNamespace:
    import os
    from urllib.parse import urlsplit

    p = urlsplit(os.environ["TEST_DATABASE_URL"].strip())
    return SimpleNamespace(
        societe_id=uuid.uuid4(),
        db_name=nom_base,
        db_host=p.hostname or "127.0.0.1",
        db_port=p.port or 5432,
        db_user=p.username or "utilisateur",
        db_password="chiffre",
    )


async def _login(monkeypatch, erreur: BaseException, nom_base: str = "jetable_factice"):
    """Login dont la base tenant leve `erreur` a la premiere requete."""
    config = _config(nom_base)

    async def _resoudre(master_db, email):
        return config, None

    async def _moteur(**kwargs):
        return None

    async def _fabrique(tenant_id):
        class _SessionQuiEchoue:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, *args, **kwargs):
                raise erreur

        return lambda: _SessionQuiEchoue()

    monkeypatch.setattr(AuthService, "_resoudre_tenant", _resoudre)
    monkeypatch.setattr(services.tenant_db_manager, "get_or_create_engine", _moteur)
    monkeypatch.setattr(services.tenant_db_manager, "get_session_factory", _fabrique)
    monkeypatch.setattr(services, "decrypt_secret", lambda valeur: "clair")

    with pytest.raises(BaseException) as recolte:
        await AuthService.authenticate(
            email="praticien@cabinet.sn", password="motdepasse", master_db=None
        )
    return recolte.value, config


# ---------------------------------------------------------------------------
# 1. La forme reelle de l'encapsulation SQLAlchemy
# ---------------------------------------------------------------------------


def _double_enveloppement() -> ProgrammingError:
    """Reproduit la forme mesuree : deux `ProgrammingError` avant asyncpg."""
    asyncpg_erreur = asyncpg.exceptions.UndefinedColumnError(
        "column utilisateurs.cabinet_id does not exist"
    )
    adaptateur = ProgrammingError("SELECT ...", {}, asyncpg_erreur)
    return ProgrammingError("SELECT ...", {}, adaptateur)


@pytest.mark.asyncio
async def test_la_forme_reelle_d_un_schema_perime_donne_un_503(monkeypatch) -> None:
    """
    **Le test qui manquait.** La forme ci-dessus est celle de SQLAlchemy sur
    asyncpg ; les tests existants en synthetisent une autre.
    """
    soulevee, config = await _login(monkeypatch, _double_enveloppement())

    assert isinstance(soulevee, TenantConnectionException), (
        f"forme reelle non reconnue : {type(soulevee).__name__}"
    )
    assert soulevee.status_code == 503
    assert soulevee.code == "SERVICE_INDISPONIBLE"
    assert soulevee.details == {}
    assert "cabinet_id" not in soulevee.message


@pytest.mark.asyncio
async def test_la_forme_reelle_par_sqlstate_est_reconnue(monkeypatch) -> None:
    """
    Le pilote publie `sqlstate=42703` des le premier niveau. Un code d'erreur
    PostgreSQL est une preuve plus solide qu'un nom de classe : on s'en sert
    aussi, pour ne pas dependre de la seule hierarchie d'exceptions.
    """
    origine = asyncpg.exceptions.UndefinedColumnError(
        "column utilisateurs.cabinet_id does not exist"
    )
    origine.sqlstate = "42703"
    adaptateur = ProgrammingError("SELECT ...", {}, origine)
    soulevee, _ = await _login(monkeypatch, ProgrammingError("SELECT ...", {}, adaptateur))

    assert isinstance(soulevee, TenantConnectionException), (
        f"sqlstate 42703 non reconnu : {type(soulevee).__name__}"
    )
    assert soulevee.status_code == 503


@pytest.mark.asyncio
async def test_une_erreur_sql_de_code_reste_non_deguisee(monkeypatch) -> None:
    """
    Descendre plus bas dans la chaine ne doit rien attraper de plus.

    Une faute de frappe dans une requete est un bug du code : la remonter
    intacte, sinon elle disparait derriere un « service indisponible ».
    """
    origine = asyncpg.exceptions.SyntaxOrAccessError('syntax error at or near "SELCT"')
    adaptateur = ProgrammingError("SELECT ...", {}, origine)
    soulevee, _ = await _login(monkeypatch, ProgrammingError("SELECT ...", {}, adaptateur))

    assert not isinstance(soulevee, AppException), (
        "une erreur SQL de code ne doit pas devenir une reponse controlee"
    )
    assert isinstance(soulevee, ProgrammingError)


# ---------------------------------------------------------------------------
# 2. Serveur injoignable : la forme reelle ne passe par aucun encapsulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "erreur",
    [
        # Mesure sur un port mort, une seule adresse.
        ConnectionRefusedError(111, "Connection refused"),
        # Mesure sur le 500 du 11/10 : `localhost` resout en deux adresses,
        # asyncpg agrege leurs echecs et leve le plus petit ancetre commun.
        OSError(
            "Multiple exceptions: [Errno 10061] Connect call failed ('::1', 55435, 0, 0), "
            "[Errno 10061] Connect call failed ('127.0.0.1', 55435)"
        ),
    ],
)
async def test_un_serveur_injoignable_ne_produit_pas_de_500(monkeypatch, erreur) -> None:
    """
    SQLAlchemy **n'encapsule pas** un echec de connexion d'ouverture : l'erreur
    remonte nue. La liste fermee du 10/10 ne contenait que des formes
    PostgreSQL ; un `ConnectionRefusedError` brut la traversait entierement.
    """
    soulevee, config = await _login(monkeypatch, erreur)

    assert isinstance(soulevee, TenantConnectionException), (
        f"{type(erreur).__name__} doit devenir une reponse controlee, "
        f"pas un {type(soulevee).__name__}"
    )
    assert soulevee.status_code == 503
    assert soulevee.details == {}
    # Ni identifiant de cabinet, ni hote, ni port dans ce qui part au client.
    for fragment in (soulevee.message, str(soulevee.details), soulevee.code):
        assert str(config.societe_id) not in fragment
        assert str(config.db_port) not in fragment


# ---------------------------------------------------------------------------
# 4. Le registre lui-meme injoignable : le 500 du 11/10
# ---------------------------------------------------------------------------
#:
#: Ce n'est pas la base d'un cabinet qui manque, c'est le **registre**. Le
#: conteneur PostgreSQL de developpement s'etait arrete, et le login repondait :
#:
#:     HTTP 500  details.exception = "Multiple exceptions: [Errno 10061]
#:                  Connect call failed ('::1', 55435, 0, 0), ..."
#:
#: Le client apprenait ainsi l'hote et le port du serveur. La panne est
#: d'infrastructure, pas de code : elle doit valoir 503, sans detail.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "erreur",
    [
        ConnectionRefusedError(111, "Connection refused"),
        OSError(
            "Multiple exceptions: [Errno 10061] Connect call failed ('::1', 55435, 0, 0), "
            "[Errno 10061] Connect call failed ('127.0.0.1', 55435)"
        ),
    ],
)
async def test_un_registre_injoignable_ne_produit_pas_de_500(erreur) -> None:
    """La session master convertit un echec de connexion en 503 generique."""
    from src.core.database import get_master_db
    from src.core.exceptions import MasterDatabaseUnavailableException

    dependance = get_master_db()
    await dependance.__anext__()  # la session est paresseuse : rien n'est ouvert

    with pytest.raises(MasterDatabaseUnavailableException) as recolte:
        await dependance.athrow(erreur)

    assert recolte.value.status_code == 503
    assert recolte.value.code == "SERVICE_INDISPONIBLE"
    assert recolte.value.details == {}
    # Ni l'hote, ni le port, ni le message systeme ne doivent partir au client.
    texte = recolte.value.message + str(recolte.value.details)
    assert "55435" not in texte
    assert "Errno" not in texte
    assert "Connect call failed" not in texte


@pytest.mark.asyncio
async def test_un_bug_de_code_n_est_pas_deguis_en_panne_de_registre() -> None:
    """
    La liste reste fermee : un bug d'application doit remonter tel quel, sinon
    il disparait derriere un « service indisponible » que personne n'investigue.
    """
    from src.core.database import get_master_db
    from src.core.exceptions import MasterDatabaseUnavailableException

    dependance = get_master_db()
    await dependance.__anext__()

    with pytest.raises(ValueError):
        await dependance.athrow(ValueError("bug d'application"))

    assert ValueError is not MasterDatabaseUnavailableException


# ---------------------------------------------------------------------------
# 3. Reproduction reelle : une colonne vraiment absente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reproduction_reelle_colonne_absente(monkeypatch) -> None:
    """
    Le meme scenario sur une base **reelle** : migrations jouees, utilisateur
    insere, puis une seule colonne supprimee.

    Cette section est celle que les tests simules ne pouvaient pas remplacer.
    Elle est sautee, jamais ignoree en silence, si l'instance de tests n'est pas
    lancee : le reste du fichier, lui, tourne toujours.
    """
    from tests.base_de_test import construire_modele
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from urllib.parse import urlsplit

    import os

    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL absent : instance de tests non designee")

    nom = f"{PREFIXE_JETABLE}drift_{uuid.uuid4().hex[:6]}"

    async def _moteur(nom_base: str):
        p = urlsplit(url)
        return create_async_engine(
            f"postgresql+asyncpg://{p.username}:{p.password}@{p.hostname}:{p.port}/{nom_base}",
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )

    try:
        await construire_modele(nom)
    except Exception as exc:  # noqa: BLE001 - l'absence d'instance doit etre dite
        pytest.skip(f"instance de tests injoignable ({type(exc).__name__})")

    base = await _moteur(nom)
    try:
        role_id = uuid.uuid4()
        email = "derive.tests@exemple.com"
        async with base.connect() as conn:
            await conn.execute(
                text(
                    "INSERT INTO roles (id, nom, niveau_hierarchie, created_at, updated_at)"
                    " VALUES (:i, 'ADMIN_TEST', 1, now(), now())"
                ),
                {"i": role_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO utilisateurs (id, email, prenom, nom, mot_de_passe,"
                    " role_id, actif, deux_facteurs, created_at, updated_at)"
                    " VALUES (:i, :e, 'Test', 'Derive', :p, :r, true, false, now(), now())"
                ),
                {"i": uuid.uuid4(), "e": email, "p": "hachage-factice", "r": role_id},
            )
            # Une seule colonne retiree : c'est ce que laisse une migration manquee.
            await conn.execute(text("ALTER TABLE utilisateurs DROP COLUMN cabinet_id"))
    finally:
        await base.dispose()

    config = _config(nom)

    def _cible(nom_base: str) -> str:
        p = urlsplit(url)
        return (
            f"postgresql+asyncpg://{p.username}:{p.password}@{p.hostname}:{p.port}/{nom_base}"
        )

    async def _resoudre(master_db, email_arg):
        return config, None

    async def _moteur_vide(**kwargs):
        return None

    # La session doit pointer sur la base dont la colonne a ete supprimee :
    # c'est elle qui produit l'erreur, reellement. `get_session_factory` est
    # **await** par `authenticate` : la fonction de remplacement doit donc etre
    # asynchrone, sous peine de tester autre chose que le defaut qu'on vise.
    async def _session_reelle(tenant_id):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        fabrique = create_async_engine(_cible(nom), poolclass=NullPool)
        return async_sessionmaker(
            bind=fabrique, class_=AsyncSession, expire_on_commit=False
        )

    monkeypatch.setattr(AuthService, "_resoudre_tenant", _resoudre)
    monkeypatch.setattr(services.tenant_db_manager, "get_or_create_engine", _moteur_vide)
    monkeypatch.setattr(
        services.tenant_db_manager, "get_session_factory", _session_reelle
    )
    monkeypatch.setattr(services, "decrypt_secret", lambda valeur: "clair")

    with pytest.raises(TenantConnectionException) as recolte:
        await AuthService.authenticate(
            email=email, password="MotDePasseFictif_123", master_db=None
        )

    assert recolte.value.status_code == 503
    assert recolte.value.details == {}
    for fragment in (recolte.value.message, str(recolte.value.details)):
        assert "cabinet_id" not in fragment
        assert nom not in fragment