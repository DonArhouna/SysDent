"""
Fixtures de test du module Patients.

Ces tests s'exécutent contre une VRAIE base PostgreSQL jetable, pas contre SQLite :
le module utilise du JSONB, des UUID natifs et des `INSERT ... ON CONFLICT`, que
SQLite ne sait pas reproduire. Un faux positif sur SQLite donnerait une fausse
confiance sur la numérotation et l'atomicité des compteurs.

La base est créée et détruite automatiquement à partir de `TEST_MASTER_DB_URL`
(ou des variables TENANT_DB_* du .env si absente).
"""

import asyncio
import gc
import hashlib
import hmac
import os
import re
import sys
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timezone
from typing import AsyncGenerator
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
import structlog
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.database import tenant_db_manager
from src.core.migrations import upgrade_tenant_to_head
from src.core.security import get_password_hash
from src.main import app
# `tests/__init__.py` existe : le dossier des tests est un paquet, et un
# import nu ne resout donc pas. La racine du depot doit etre sur le chemin,
# ce que fait pytest via la racine de `testpaths`.
try:  # pragma: no cover - depend de la maniere dont pytest est invoque
    from tests import base_de_test
except ImportError:  # pragma: no cover
    import base_de_test


structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))


def _server_url() -> str:
    """URL du serveur PostgreSQL de test (sans nom de base)."""
    base = os.environ.get("TEST_MASTER_DB_URL")
    if base:
        return base
    return (
        f"postgresql://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
        f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}"
    )


def _creds() -> str:
    """Partie `user:password@host:port` de l'URL, sans le nom de base."""
    base = _server_url()
    _, _, reste = base.partition("://")
    return reste.rstrip("/").rsplit("/", 1)[0]


def _async_url(db_name: str) -> str:
    """URL asyncpg pour SQLAlchemy async."""
    return f"postgresql+asyncpg://{_creds()}/{db_name}"


def _sync_url(db_name: str) -> str:
    """URL des migrations. Alembic est synchrone, mais le moteur est
    asynchrone : `src/core/alembic_async.py` fait tourner les migrations dans son
    thread interne. Le pilote reste donc `asyncpg`, celui de la pile applicative."""
    return f"postgresql+asyncpg://{_creds()}/{db_name}"


@pytest_asyncio.fixture
async def master_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Session isolée sur la base Master.

    Contrairement aux bases tenants, la base Master n'est pas jetable par test :
    elle accueille les Super Admin, la table d'index email -> société et le
    journal global, tous persistants par nature. Les tests s'isolent donc par
    identifiants uniques.

    On crée un moteur dédié plutôt que d'utiliser `master_engine` : ce moteur
    global est instancié à l'import du module et ses connexions restent
    attachées à la première boucle d'événements qui les a utilisées. La
    réutiliser entre tests (qui tournent chacun sur leur propre boucle) produit
    « Event loop is closed » dès que pytest-asyncio ferme la boucle précédente.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.core.config import settings

    engine = create_async_engine(settings.master_db_async_url)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


#: Registre des bases creees **par cette session de tests**. Une base qui y
#: figure est de la peine a jetter : aucun doute possible. Le motif de nom, lui,
#: n'est qu'un indice.
BASES_CREEES_PAR_LA_SESSION: set[str] = set()


def _enregistrer(nom: str) -> None:
    BASES_CREEES_PAR_LA_SESSION.add(nom)


async def _creer_base(db_name: str) -> None:
    """Crée une base jetable sur l'instance de maintenance `postgres`."""
    admin_engine = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        _enregistrer(db_name)
    finally:
        await admin_engine.dispose()


async def _supprimer_base(db_name: str) -> None:
    admin_engine = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    finally:
        await admin_engine.dispose()


#: Prefixe -> forme du suffixe, **calibre sur les noms reellement produits**.
#:
#: Une longueur fixe unique aurait ete fausse : `nom_jetable` fait
#: `uuid4().hex[:12]`, l'isolation de patients fait 8 caracteres, le partage de
#: tenant 6, et les cabinets de recette `lettre_hex8_hex8`. Quatre formes, pas
#: une. Un motif trop permissif (`se terminait par de l'hexa`) laissait passer
#: des noms tapes a la main ; un motif trop strict laissait 80 bases sur place.
#:
#: Chaque forme est **fixe** : c'est ce qui rend la regle verifiable plutot que
#: devinable.
#: **Liste de protection absolue.** Verifiee en premier, jamais contournable, meme
#: si le motif de nom devait un jour considerer `postgres` comme jetable.
#:
#: `sysdent_platform` est la plateforme, `sysdent_master` son registre de controle,
#: `sysdent_modele_tenant` le modele clone a chaque test, `sysdent_tenant_ref` le
#: tenant de reference. Les perdre, c'est perdre le travail.
BASES_PROTEGEES = frozenset(
    {
        "postgres",
        "template0",
        "template1",
        "sysdent_master",
        "sysdent_modele_tenant",
        "sysdent_platform",
        "sysdent_tenant_ref",
    }
)

#: Variable d'environnement exigee pour que la purge s'execute. Sans elle, la
#: garde ne fait rien et le dit : une purge qui s'execute sur le mauvais serveur
#: est irrattrapable, une purge qui ne s'execute pas se relance.
VARS_PURGE = "SYSDENT_TESTS_PURGE"


MOTIFS_JETABLES: dict[str, re.Pattern[str]] = {
    # `nom_jetable()` : uuid4().hex[:12]
    "sysdent_test_": re.compile(r"^[0-9a-f]{12}$"),
    "sysdent_platform_enrolement_": re.compile(r"^[0-9a-f]{12}$"),
    # Isolation : 8 caracteres.
    "sysdent_iso_a_": re.compile(r"^[0-9a-f]{8}$"),
    "sysdent_iso_b_": re.compile(r"^[0-9a-f]{8}$"),
    # Cabinet : `lettre_hex8_hex8` (verif b/c/d/e) et `onboarding_hex8_hex8`.
    "sysdent_tenant_cabinet_verif_": re.compile(r"^[a-z]_[0-9a-f]{8}_[0-9a-f]{6}$"),
    "sysdent_tenant_cabinet_onboarding_": re.compile(r"^[0-9a-f]{8}_[0-9a-f]{6}$"),
    # Recette et essai : 6 caracteres.
    "sysdent_tenant_cabinet_recette_": re.compile(r"^[0-9a-f]{6}$"),
    "sysdent_tenant_clinique_essai_": re.compile(r"^[0-9a-f]{6}$"),
    # Partage de tenant : `a` ou `b` puis 6 caracteres.
    "sysdent_tenant_clinique_partage_": re.compile(r"^[ab]_[0-9a-f]{6}$"),
    "sysdent_tenant_clinique_cabinet_sn_": re.compile(r"^[0-9a-f]{6}$"),
    # Les cabinets modifies gardent leur slug lisible **avant** du fragment.
    # `d_mo_dakar_69a2de` et `demo_dakar_050843` sont des bases de demonstration
    # REELLEMENT utilisees : hors motif, elles ne sont protegees que par le
    # registre. C est deliberement plus prudent que l inverse.
    "sysdent_tenant_clinique_diagnostic_": re.compile(r"^dakar_[0-9a-f]{8}$"),
}


def _motif_jetable(nom: str) -> bool:
    """Le nom ressemble-t-il a une base de test ? Preuve **faible**."""
    for prefixe, motif in MOTIFS_JETABLES.items():
        if nom.startswith(prefixe) and motif.match(nom[len(prefixe) :]):
            return True
    return False


def classer_base(nom: str, avant_session: frozenset[str], tenants_reels: frozenset[str]) -> str:
    """
    Renvoie la categorie d'une base. L'ordre des tests **est** la securite.

    ``protege``  jamais supprimee, quelle que soit la suite du nom ;
    ``session``  creee par cette session : certitude, pas indice ;
    ``indice``   ressemble a une base de test, a verifier ;
    ``conserve`` on ne sait pas : on ne touche pas.

    La derniere branche est la plus importante : **une base qu'on ne reconnait
    pas est une base qu'on garde.** Une garde destructive doit etablir par
    l'absence de doute, jamais par l'absence de preuve.
    """
    if nom in BASES_PROTEGEES:
        return "protege"
    if nom in tenants_reels:
        # Reference par le registre des tenants, et presente avant la session :
        # c'est un tenant reel, pas un residu.
        return "protege"
    if nom in BASES_CREEES_PAR_LA_SESSION:
        return "session"
    if nom in avant_session:
        # Presente avant la session et inconnue du registre : laissee en place.
        # Elle peut venir d'un usage manuel ; on ne devine pas.
        return "conserve"
    if _motif_jetable(nom):
        return "indice"
    return "conserve"


# ---------------------------------------------------------------------------
# Instance de tests : la garde ne s'y execute que si on la lui designe
# ---------------------------------------------------------------------------
#:
#: Une purge ne se juge pas a ce qu'elle supprime, mais a ce qu'elle **peut**
#: supprimer. Celle du 08/10 se contentait du nom : elle a efface la base de
#: demonstration du proprietaire, `sysdent_tenant_clinique_cabinet_sn_5bd215`,
#: dont la forme est exactement celle d'un residu de test. Le provisionnement
#: nomme en effet ses cabinets `sysdent_tenant_<slug>_<hex6>` - le meme motif que
#: `nom_jetable()`. Depuis, le login du client tombe en 500 sur cette base
#: introuvable.
#:
#: La reponse n'est donc pas un motif de nom plus fin : aucun motif ne distingue
#: une base de cabinet d'un residu. C'est l'**instance** qui doit etre distinguee.

#: Variable d'environnement designant l'instance de tests.
VARS_URL_TESTS = "TEST_DATABASE_URL"

#: Base-temoin : sa presence sur une instance signifie qu'on l'a volontairement
#: dediee aux tests. Aucune instance reelle n'en porte une.
MARQUEUR_INSTANCE_DE_TESTS = "sysdent_instance_de_tests"

#: Prefixe de toute base provisionnee pour un cabinet (`sanitize_db_name`).
PREFIXE_TENANT = "sysdent_tenant_"


def url_de_tests() -> str | None:
    """`TEST_DATABASE_URL`, ou `None` si elle n'est pas renseignee."""
    url = os.environ.get(VARS_URL_TESTS, "").strip()
    return url or None


def resume_url(url: str) -> str:
    """`hote:port/nom` : les identifiants ne sortent jamais, meme dans un journal."""
    donnees = urlsplit(url)
    hote = donnees.hostname or "?"
    port = f":{donnees.port}" if donnees.port else ""
    return f"{hote}{port}/{donnees.path.lstrip('/') or '?'}"


def _cible(url: str) -> tuple[str, int]:
    """`(hote, port)` d'une URL, avec le port PostgreSQL par defaut."""
    donnees = urlsplit(url)
    return (donnees.hostname or "", donnees.port or 5432)


def cible_distincte(url_tests: str, hote_ref: str, port_ref: int) -> bool:
    """L'instance de tests est-elle une **autre** que celle des tenants ?"""
    return _cible(url_tests) != (hote_ref, port_ref)


def instance_explicitement_marquee(noms: Iterable[str]) -> bool:
    """L'instance porte-t-elle la base-temoin qui la dedie aux tests ?"""
    return MARQUEUR_INSTANCE_DE_TESTS in set(noms)


def base_supprimable(nom: str, *, tenants_reels: frozenset[str], session: set[str]) -> bool:
    """Une base peut-elle etre supprimee ? Le doute se resout **contre** la
    suppression : c'est le cas `5bd215` qui a coute sa base au proprietaire.
    """
    if nom in BASES_PROTEGEES:
        return False
    if nom in tenants_reels:
        # Portee au registre `tenants_db` : c'est un cabinet reel, quoi dise son
        # nom. Le motif de nom n'est qu'un indice, le registre est la preuve.
        return False
    if nom in session:
        # Creee par cette session : certitude, pas indice.
        return True
    if nom.startswith(PREFIXE_TENANT):
        # Une base de cabinet non creee par nous n'est jamais supprimee, motif ou
        # non : on ne distingue pas un cabinet d'un residu de test par le nom.
        return False
    return _motif_jetable(nom)


def bases_a_supprimer(
    noms: Iterable[str],
    *,
    tenants_reels: frozenset[str],
    session: set[str],
    url_tests: str | None,
    hote_ref: str,
    port_ref: int,
) -> list[str]:
    """Les bases que la garde a le droit de supprimer, et les seules.

    Trois verrous, tous **necessaires** : une URL de tests, une instance autre
    que celle des tenants, et la base-temoin sur cette instance. Un seul verrou
    manquant et la liste est vide, quoi que dise le nom des bases.
    """
    if not url_tests:
        return []
    if not cible_distincte(url_tests, hote_ref, port_ref):
        return []
    if not instance_explicitement_marquee(noms):
        return []
    return [n for n in noms if base_supprimable(n, tenants_reels=tenants_reels, session=session)]


@pytest.fixture(scope="session", autouse=True)
def _garder_la_purge():
    """
    Supprime, en fin de session, les bases laissees derriere par les tests.

    **Pourquoi une garde globale plutot qu'un `finally` par test.** Les tests
    creent des bases par plusieurs chemins - `nom_jetable`, creation de tenant par
    l'API, clones d'isolation - et chacun avait sa propre suppression, ou pas du
    tout. 89 bases s'etaient accumulees, et la duree de la suite cresait avec
    (13 min, puis 18, puis 21).

    **La garde est un `try/finally` sur la session, pas sur le monde.** Si la
    session est interrompue, la purge n'a pas lieu et les bases restent : mieux
    vaut des residus qu'une suppression sur un serveur qui n'est pas celui des
    tests.

    **Les trois verrous.** La garde reste inerte tant que les trois ne sont pas
    reunis : `TEST_DATABASE_URL` designe une instance, cette instance n'est pas
    celle des tenants, et elle porte la base-temoin
    `sysdent_instance_de_tests`. Ensuite encore, elle ne supprime ni une base
    portee au registre `tenants_db`, ni aucune `sysdent_tenant_*` non creee par
    la session. Sans cela, une purge n'est pas un nettoyage : c'est ce qui a
    coute sa base de demonstration au proprietaire le 08/10.
    """
    url_tests = url_de_tests()

    def _verrou() -> str | None:
        """Raison pour laquelle la garde reste inerte, ou `None` si un est ouverte."""
        if not url_tests:
            return f"{VARS_URL_TESTS} n'est pas renseignee : aucune instance de tests designee"
        if not cible_distincte(url_tests, settings.TENANT_DB_HOST, settings.TENANT_DB_PORT):
            return (
                f"{resume_url(url_tests)} vise l'instance des tenants "
                f"({settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}), pas une instance dediee"
            )
        return None

    async def _inventaire_tests() -> list[str]:
        """Noms presents sur l'instance de tests. Lecture seule."""
        moteur = create_async_engine(url_tests or "", isolation_level="AUTOCOMMIT")
        try:
            async with moteur.connect() as conn:
                lignes = await conn.execute(
                    text("SELECT datname FROM pg_database WHERE datistemplate = false")
                )
                return [r[0] for r in lignes.fetchall()]
        finally:
            await moteur.dispose()

    async def _registre() -> frozenset[str]:
        """Registre `tenants_db`, lu sur la base Master de reference. Lecture seule.

        La lecture echoue-t-elle, toute la purge est abandonnee : une garde qui
        ignore quels tenants sont reels n'a aucun droit de supprimer. La lecture
        se faisait auparavant sur la base `postgres`, qui ne contient pas la
        table : elle levait `UndefinedTableError` et la protection par registre
        n'a donc **jamais** fonctionne.
        """
        moteur = create_async_engine(settings.master_db_async_url, isolation_level="AUTOCOMMIT")
        try:
            async with moteur.connect() as conn:
                lignes = await conn.execute(text("SELECT db_name FROM tenants_db"))
                return frozenset(r[0] for r in lignes.fetchall())
        finally:
            await moteur.dispose()

    async def _nettoyer() -> tuple[list[str], list[str], frozenset[str], bool]:
        noms = await _inventaire_tests()
        marque = instance_explicitement_marquee(noms)
        if not marque:
            # Pas de base-temoin : rien n'a ete dit de cette instance, donc rien
            # n'en sort.
            return [], noms, frozenset(), False
        # Deux lectures avant toute decision : l'instance, puis le registre.
        tenants = await _registre()
        cibles = bases_a_supprimer(
            noms,
            tenants_reels=tenants,
            session=BASES_CREEES_PAR_LA_SESSION,
            url_tests=url_tests,
            hote_ref=settings.TENANT_DB_HOST,
            port_ref=settings.TENANT_DB_PORT,
        )
        moteur = create_async_engine(url_tests or "", isolation_level="AUTOCOMMIT")
        try:
            async with moteur.connect() as conn:
                for nom in cibles:
                    await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))
        finally:
            await moteur.dispose()
        return cibles, noms, tenants, marque

    verrou = _verrou()
    if verrou:
        print(
            f"\n  [garde] purge inoffensive : {verrou}.\n"
            f"  [garde] Une purge ne s'execute que sur une instance dediee aux tests, "
            f"portant la base-temoin '{MARQUEUR_INSTANCE_DE_TESTS}'. "
            f"Les bases de test resteront en place."
        )
        # Un fixture generateur doit toujours `yield` : c'est l'unique instant ou
        # la garde pouvait agir, et il est ferme.
        yield
        return

    yield

    if os.environ.get(VARS_PURGE) != "1":
        print(
            f"\n  [garde] purge non executee : {VARS_PURGE}=1 est requis. "
            f"Les bases de test resteront apres cette session."
        )
        return
    try:
        supprimees, noms, tenants, marque = asyncio.run(_nettoyer())
    except Exception as e:  # noqa: BLE001
        # Une purge qui leve ferait echouer une suite pourtant verte, et l'erreur
        #aurait etre sans rapport avec le test qui l'a provoquee. Elle doit
        # rester visible, pas bloquante.
        print(
            f"\n  [garde] purge impossible sur {resume_url(url_tests or '')} : {e}\n"
            f"  [garde] rien n'a ete supprime."
        )
        return
    if not marque:
        print(
            f"\n  [garde] purge abandonnee : {resume_url(url_tests or '')} ne porte pas "
            f"la base-temoin '{MARQUEUR_INSTANCE_DE_TESTS}'. Rien n'a ete supprime."
        )
        return
    conserves = len(noms) - len(supprimees)
    proteges = sum(1 for n in noms if n in tenants or n in BASES_PROTEGEES)
    print(
        f"\n  [garde] instance de tests {resume_url(url_tests or '')}\n"
        f"  [garde] {len(supprimees)} base(s) supprimee(s) sur {len(noms)}, "
        f"{conserves} conservee(s), dont {proteges} portee(s) au registre ou protegee(s)."
    )


# ---------------------------------------------------------------------------
# Hachage de mot de passe : cout de production, reserve a la production
# ---------------------------------------------------------------------------
#
# **Mesure, pas supposition.** Argon2 (64 Mio de memoire, 3 passes) coute 440 ms
# pour hacher et 574 ms pour verifier sur ce poste. La suite cree un compte par
# test et en verifie un ou deux : sur 320 tests, cela represente environ
# 8 minutes et demies de la seule fonction de hachage.
#
# **Pourquoi c'est legitime de le reduire.** La fonction de derivation n'est pas
# ce que ces tests verifient : ils verifient que le mot de passe juste ne
# fonctionne pas, que le mauvais echoue, que le changement de mot de passe prend
# effet. Un KDF rapide mais ** reel** — sale, non reversible, et qui rejette
# effectivement un mauvais mot de passe — verifie exactement cela. Retirer le
# cout ne retire aucune assertion.
#
# **Ce qui n'est pas touche** : `src/core/security.py` garde ses parametres de
# production. Seul le nom lie dans chaque module est remplace, et uniquement
# pendant la session de test. Aucun code livre n'est modifie.

_ITERATIONS_TEST = 1_000


def _hache_test(mot_de_passe: str) -> str:
    sel = os.urandom(16)
    derive = hashlib.pbkdf2_hmac(
        "sha256", mot_de_passe.encode(), sel, _ITERATIONS_TEST
    )
    return f"pbkdf2_sha256${_ITERATIONS_TEST}${sel.hex()}${derive.hex()}"


def _verifie_test(mot_de_passe: str, hache: str) -> bool:
    try:
        _, iterations, sel_hex, attendu_hex = hache.split("$")
        derive = hashlib.pbkdf2_hmac(
            "sha256",
            mot_de_passe.encode(),
            bytes.fromhex(sel_hex),
            int(iterations),
        )
    except (ValueError, AttributeError):
        return False
    # `compare_digest` : la comparaison doit.constant-time comme en production.
    return hmac.compare_digest(derive.hex(), attendu_hex)


def _appliquer_hachage_rapide() -> None:
    """Remplace le hachage dans tous les modules qui l'ont lie par son nom.

    Les fonctions sont importees par nom (`from src.core.security import
    get_password_hash`) : redefinir l'attribut du seul module `security` ne
    changerait rien pour les appelants, et les tests qui importent **dans** leur
    corps relisent l'attribut du module `security`. On parcourt donc tous les
    modules deja charges, y compris `security` lui-meme.

    Execute a l'import du `conftest`, et non dans une fixture : une fixture de
    session peutDemarrer apres qu'un module de test ait deja capture la
    fonction d'origine, et l'echec serait silencieux — exactement le genre de
    correction qui a l'air d'avoir marche.
    """
    from src.core import security

    remplacements = {
        "get_password_hash": _hache_test,
        "verify_password": _verifie_test,
    }
    # **Les originaux sont captures avant toute substitution.** Comparer chaque
    # module a `security` pendant la boucle donnerait un résultat faux : dès la
    # premiere substitution, l'attribut de `security` ne serait plus l'original,
    # et plus aucun module ne « correspondrait ». Le remplacement silencieux
    # n'aurait levé aucune erreur — seule la mesure l'aurait montre.
    originaux = {nom: getattr(security, nom) for nom in remplacements}
    for module in list(sys.modules.values()):
        if module is None:
            continue
        for nom, original in originaux.items():
            if getattr(module, nom, None) is original:
                setattr(module, nom, remplacements[nom])


_appliquer_hachage_rapide()


# ---------------------------------------------------------------------------
# Modele de base : migre UNE fois par session, clone par test
# ---------------------------------------------------------------------------
#
# **Pourquoi.** Chaque test creait sa base, appliquait les 17 migrations Alembic
# (demarrage d'Alembic + import de toute l'application + 17 lots de DDL), puis
# supprimait la base. Sur 320 tests cela representait la quasi-totalite du temps
# de la suite : plus de 40 minutes, dont 17 % jamais atteints puisque le delai
# etait depasse avant la fin.
#
# **Ce qui change.** Le schema est construit une seule fois, puis chaque test
# obtient sa base par `CREATE DATABASE ... TEMPLATE ...`, une copie au niveau des
# fichiers que PostgreSQL fait en quelques dizaines de millisecondes.
#
# **Ce qui ne change pas, et c'est l'essentiel :** chaque test conserve sa
# **propre base physique**, creee depuis un modele vide et sans connexion
# ouverte. L'isolation entre tests et entre tenants reste structurelle ; elle est
# simplement obtenue plus vite.


async def _construire_modele(nom: str, migration, url_sync) -> None:
    """Cree une base vide, la migre a jour, puis libere toute connexion.

    La liberation des connexions est obligatoire : `CREATE DATABASE ... TEMPLATE`
    echoue si le modele a ne serait-ce qu'une seule connexion ouverte.
    """
    admin = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{nom}"'))
        # Alembic est synchrone : execute hors de la boucle asyncio.
        await asyncio.to_thread(migration, url_sync(nom))
    finally:
        await admin.dispose()


@pytest_asyncio.fixture(scope="session")
def _modele_tenant() -> str:
    """Base vide au schema tenant a jour, creee une fois par session."""
    asyncio.run(base_de_test.construire_modele())
    return base_de_test.MODELE_TENANT


@pytest_asyncio.fixture
async def tenant_db(_modele_tenant: str) -> AsyncGenerator[AsyncSession, None]:
    """
    Base tenant jetable : **un clone du modele migre**, supprimee apres le test.

    Un tenant par test : aucun etat ne fuite d'un test a l'autre.

    Tolérance a une reconnexion : sous Windows, la pile reseau d'asyncpg peut
    abandonner une connexion en cours (WinError 995 / ConnectionResetError) lors
    des ouvertures et fermetures rapides de sockets - la suite cree et supprime
    plus d'une centaine de bases. Une reprise unique est appliquee : elle
    concerne l'outillage de test, pas le comportement du produit, qui est
    valide separement par les scripts de verification bout-en-bout.
    """
    derniere_erreur = None

    for tentative in range(2):
        db_name = f"sysdent_test_{uuid.uuid4().hex[:12]}"
        os.environ["TEST_TENANT_DB_NAME"] = db_name
        try:
            await base_de_test.cloner(db_name)
            break
        except (OSError, ConnectionError) as exc:
            derniere_erreur = exc
            await _supprimer_base(db_name)
            if tentative == 0:
                continue
            raise
    else:  # pragma: no cover - defensif
        raise AssertionError(f"Impossible de creer la base de test : {derniere_erreur}")

    engine = create_async_engine(_async_url(db_name))
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
        await _supprimer_base(db_name)


@pytest_asyncio.fixture(autouse=True)
async def _purge_moteurs_globaux_et_tenants():
    """
    Purge les moteurs de connexion avant et après chaque test, puis force la
    collecte des objets qui leur appartiennent.

    Trois moteurs sont concernés :

    1. `master_engine` (global, `core/database.py:18`) et `platform_engine`
       (global) sont créés à l'IMPORT du module, donc sur la boucle du premier
       test. Or chaque test a sa propre boucle, et `get_tenant_db` passe par
       `get_master_db` — c'est-à-dire que **toute** requête authentifiée touche
       le moteur master. Au deuxième test, ce moteur est lié à une boucle
       morte.
    2. `tenant_db_manager` met en cache jusqu'à 50 `AsyncEngine`, un par base de
       test. La suite crée plus de 150 bases : le cache déborde et l'éviction
       appelle `dispose()` sur un engine d'une boucle déjà fermée.

    `dispose()` ne suffit pas sous Windows : le `Protocol` asyncpg n'est pas
    finalisé au retour de la coroutine. Sa collecte survient pendant le test
    SUIVANT, et son callback appelle `call_soon` sur la boucle morte —
    l'erreur « Event loop is closed » atterrit alors au milieu d'une requête
    sans rapport. C'est ce qui faisait échouer `POST /praticiens` dans
    `test_cabinets.py` : le test passait seul, échouait en suite.

    D'où le `gc.collect()` : les objets sont libérés pendant que la boucle
    courante est encore ouverte, la cible du callback est donc une boucle
    vivante et l'appel devient inoffensif. Deux passes, la seconde après un
    tour de boucle, car `dispose()` recrée parfois des cycles.

    `autouse` car le déclenchement ne dépend pas du test concerné.
    """
    from src.core.database import master_engine
    from src.core.platform_database import platform_engine

    async def purger() -> None:
        await tenant_db_manager.close_all()
        await master_engine.dispose()
        await platform_engine.dispose()
        gc.collect()
        await asyncio.sleep(0)
        gc.collect()

    await purger()
    yield
    await purger()


@pytest_asyncio.fixture
async def cabinet(tenant_db: AsyncSession) -> dict:
    """
    Jeu de données de référence : rôle ADMIN_CABINET + utilisateur, comme le crée
    le provisioning réel (`MasterTenantService._bootstrap_tenant_schema_and_admin`).
    """
    from src.modules.tenants.models import Cabinet, Role, Utilisateur

    role = Role(nom="ADMIN_CABINET", description="Administrateur du cabinet", niveau_hierarchie=1)
    cabinet = Cabinet(nom="Clinique Test Dakar", ville="Dakar", actif=True)
    tenant_db.add_all([role, cabinet])
    await tenant_db.flush()

    user = Utilisateur(
        email="admin@clinique-test.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Admin",
        nom="Test",
        actif=True,
    )
    tenant_db.add(user)
    await tenant_db.flush()

    # Le compte porte un profil praticien comme le ferait l'onboarding. Ce n'est
    # plus une condition pour consulter — depuis le découplage, l'auteur d'une
    # consultation est le compte, et le profil n'est qu'une attribution
    # réglementaire facultative. On le crée quand même parce que la plupart des
    # tests l'exercent, et parce que l'ordonnance l'exige toujours.
    from src.modules.tenants.models import Praticien

    praticien = Praticien(
        utilisateur_id=user.id,
        titre="Dr",
        specialite="Chirurgien-Dentiste",
        numero_ordre="ORD-TEST-001",
    )
    tenant_db.add(praticien)
    await tenant_db.commit()

    return {
        "role": role,
        "user": user,
        "cabinet": cabinet,
        "praticien": praticien,
        "tenant_id": str(uuid.uuid4()),
    }


@pytest_asyncio.fixture
async def session_caisse(client_authenticated: AsyncClient, cabinet) -> dict:
    """
    Ouvre une session de caisse pour le site du test et renvoie son numéro.

    Depuis la clôture de caisse, un encaissement refuse de se faire hors session
    ouverte : c'est délibéré, sinon le rapport journalier est faux et rien ne le
    signale. Les tests qui encaissent doivent donc passer par cette fixture —
    c'est le comportement réel du produit, pas un contournement de test.
    """
    reponse = await client_authenticated.post(
        "/api/v1/caisse/sessions",
        json={"cabinet_id": str(cabinet["cabinet"].id), "ouverture_especes": "0"},
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]


@pytest_asyncio.fixture
async def client_authenticated(tenant_db, cabinet) -> AsyncGenerator[AsyncClient, None]:
    """
    Client HTTP authentifié en tant qu'ADMIN_CABINET, avec la dépendance
    `get_tenant_db` redirigée vers la base jetable du test.

    On ne passe pas par `POST /auth/login` : ce endpoint résout le tenant en
    parcourant les bases déclarées dans la table Master, ce qui n'a pas de sens
    ici. On valide le JWT par la vraie fonction `create_access_token` et on
    surcouche uniquement l'injection de session — le reste de la chaîne
    (RBAC, audit, schémas) est réellement exercé.
    """
    from src.core.security import create_access_token
    from src.modules.auth import dependencies as auth_deps
    from src.modules.tenants.models import Utilisateur

    token = create_access_token(
        user_id=str(cabinet["user"].id),
        tenant_id=cabinet["tenant_id"],
        role="ADMIN_CABINET",
        permissions=[],
    )

    # Copie DÉTACHÉE de l'utilisateur, et non l'objet vivant du session.
    # Un `rollback` (provoqué par toute requête en erreur) expire les objets du
    # session ; relire `auteur.id` ensuite depuis une coroutine lève alors
    # `MissingGreenlet`. En production chaque requête charge un utilisateur
    # neuf : la copie détachée reproduit ce comportement et supprime une classe
    # entière d'échecs trompeurs. Le code applicatif ne lit que `id` et `email`.
    utilisateur = Utilisateur(
        id=cabinet["user"].id,
        email=cabinet["user"].email,
        prenom=cabinet["user"].prenom,
        nom=cabinet["user"].nom,
        role_id=cabinet["user"].role_id,
        actif=True,
    )

    async def _override_get_tenant_db():
        try:
            yield tenant_db
            await tenant_db.commit()
        except Exception:
            await tenant_db.rollback()
            raise

    async def _override_get_current_user():
        return utilisateur

    app.dependency_overrides[auth_deps.get_tenant_db] = _override_get_tenant_db
    app.dependency_overrides[auth_deps.get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac

    app.dependency_overrides.clear()
    await tenant_db.rollback()


@pytest_asyncio.fixture
async def patient_factory(client_authenticated: AsyncClient, tenant_db: AsyncSession):
    """Crée un patient via l'API et renvoie (réponse JSON, id UUID)."""

    def _factory(**overrides):
        payload = {
            "prenom": "Aminata",
            "nom": "Diop",
            "date_naissance": "1990-05-12",
            "sexe": "F",
            "telephone_1": "771234567",
            "ville": "Dakar",
        }
        payload.update(overrides)
        return client_authenticated.post("/api/v1/patients", json=payload)

    return _factory


@pytest_asyncio.fixture
async def nomenclature(client_authenticated: AsyncClient):
    """
    Nomenclature minimale pour les tests Consultations : un acte global et un acte
    unitaire (qui exige un numéro de dent). Les tarifs sont en FCFA.
    """
    await client_authenticated.post(
        "/api/v1/nomenclature/actes",
        json={
            "code": "CONS",
            "libelle": "Consultation dentaire",
            "categorie": "SOINS",
            "tarif_base": "15000.00",
            "duree_estimee_min": 20,
            "unitaire": False,
        },
    )
    await client_authenticated.post(
        "/api/v1/nomenclature/actes",
        json={
            "code": "DETART",
            "libelle": "Détartrage monodentaire",
            "categorie": "SOINS",
            "tarif_base": "7500.00",
            "duree_estimee_min": 15,
            "unitaire": True,
        },
    )
    liste = await client_authenticated.get("/api/v1/nomenclature/actes", params={"limit": 100})
    actes = {a["code"]: a for a in liste.json()["items"]}
    return actes


@pytest_asyncio.fixture
async def consultation_factory(client_authenticated: AsyncClient, patient_factory, nomenclature):
    """Crée un patient puis démarre une consultation dessus. Renvoie la réponse JSON."""

    async def _factory(*, patient_kwargs: dict | None = None, consultation_kwargs: dict | None = None):
        creation_patient = await patient_factory(**(patient_kwargs or {}))
        assert creation_patient.status_code == 201, creation_patient.text
        patient_id = creation_patient.json()["data"]["id"]

        payload = {
            "patient_id": patient_id,
            "motif": "Douleur dentaire",
            "type_motif": "DOULEUR",
        }
        payload.update(consultation_kwargs or {})

        reponse = await client_authenticated.post("/api/v1/consultations", json=payload)
        assert reponse.status_code == 201, reponse.text
        return reponse.json()["data"]

    return _factory


PATIENT_VALIDE = {
    "prenom": "Aminata",
    "nom": "Diop",
    "date_naissance": "1990-05-12",
    "sexe": "F",
    "telephone_1": "771234567",
    "ville": "Dakar",
}




# ==============================================================================
# CONSOLE PLATEFORME (Phases A → F)
# ==============================================================================
#
# Ces tests s'exécutent contre une vraie base PostgreSQL : la console repose sur
# des déclencheurs (`journal_audit_plateforme` refuse UPDATE / DELETE /
# TRUNCATE), des énumérations natives et du JSONB. SQLite ne pourrait ni
# reproduire ces déclencheurs ni valider l'immuabilité du journal — le test
# passerait alors sur une garantie que la production n'a pas.


def _url_base_plateforme(nom: str) -> str:
    """URL de la base plateforme de test (asyncpg).

    Les identifiants viennent de `PLATFORM_DB_*` et non de `TENANT_DB_*` : les
    deux univers sont des bases distinctes, même si elles partagent ici le même
    serveur. Utiliser les mauvais identifiants produirait une URL qui « marche »
    par hasard et masque une migration appliquée sur la mauvaise base.
    """
    return (
        f"postgresql+asyncpg://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
        f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{nom}"
    )


@pytest_asyncio.fixture(scope="function")
async def platform_base() -> AsyncGenerator[str, None]:
    """
    Nom d'une base plateforme jetable, créée et supprimée pour chaque test.

    Le MOTEUR est reconstruit à chaque fixture qui le réclame : pytest asyncio
    n'attache pas les fixtures à un moteur unique, et un moteur `session`
    réutiliserait une boucle d'événements déjà fermée. D'où la séparation :
    `platform_base` porte le cycle de vie (une base par test), `platform_engine_test`
    construit un moteur neuf par fixture sur cette base.
    """
    nom = f"sysdent_platform_test_{uuid.uuid4().hex[:10]}"
    await _creer_base(nom)
    try:
        yield nom
    finally:
        await _supprimer_base(nom)


@pytest_asyncio.fixture
async def platform_engine_test(platform_base):
    """
    Moteur plateforme jetable, migrations appliquées.

    Le moteur global (`platform_engine`) pointe sur la base de développement : y
    écrire contredirait les assertions d'immuabilité et laisserait derrière lui
    des cabinets de test. Un moteur dédié est donc construit ici, avec le même
    schéma que la production (migrations jusqu'à `head`).
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from alembic import command
    from alembic.config import Config

    config = Config("alembic_platform.ini")
    config.set_main_option("sqlalchemy.url", _url_base_plateforme(platform_base))
    # Alembic est synchrone : l'appeler depuis une coroutine déjà placée dans
    # une boucle asyncio deadlock. On l'exécute dans un thread à part.
    await asyncio.get_running_loop().run_in_executor(None, command.upgrade, config, "head")

    # `NullPool` : aucune connexion n'est conservée entre deux fixtures. Un pool
    # persistant garderait des sockets attachés à une boucle d'événements déjà
    # fermée, et le test suivant échouerait sur « Event loop is closed » — un
    # échec dû au harnais, pas au code testé.
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(_url_base_plateforme(platform_base), poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_plateforme(platform_engine_test) -> AsyncGenerator[AsyncSession, None]:
    """Session longue durée sur la base plateforme de test.

    Une SEULE session est partagée par la fixture HTTP et les assertions directes.
    Sans cela, pytest instancie `platform_engine_test` séparément pour chaque
    fixture : deux moteurs, et surtout deux sessions qui ne voient pas les mêmes
    données non commitées — un rôle créé dans une session resterait invisible
    depuis l'autre.
    """
    async with platform_engine_test() as session:
        yield session


@pytest_asyncio.fixture
async def _purge_moteur_plateforme_global():
    """
    Ferme le moteur plateforme GLOBAL avant et après chaque test plateforme.

    Le moteur global a été créé (et a ouvert des connexions) lors de l'import de
    `src.core.platform_database`, donc sur la boucle d'événements du PREMIER test.
    Au deuxième test, cette boucle est fermée : toute réutilisation lève « Event
    loop is closed ». Le symptôme apparaît sur un test qui n'a rien à voir avec
    le moteur global — d'où la difficulty à le rattacher à sa cause.

    Le meme raisonnement vaut pour le moteur MASTER : `/platform/sante`
    l'utilise pour contrôler l'etat des bases clients, et il est lui aussi cree
    a l'import.

    On ne les annule pas globalement : `src/core/*_database.py` les recree a
    chaque usage, et une fixture qui les remplacerait par `None` casserait le
    CLI. On ferme simplement les connexions ouvertes sur l'ancienne boucle.
    """
    from src.core.database import master_engine
    from src.core.platform_database import platform_engine

    await platform_engine.dispose()
    await master_engine.dispose()
    yield
    await platform_engine.dispose()
    await master_engine.dispose()


@pytest_asyncio.fixture
async def client_platform(
    session_plateforme, _purge_moteur_plateforme_global
) -> AsyncGenerator[AsyncClient, None]:
    """
    Client HTTP dont la base plateforme est la base de TEST.

    La substitution se fait par `dependency_overrides`, exactement comme le
    ferait une injection de dépendance en production : aucune variable globale
    n'est touchée, donc les tests peuvent tourner en parallèle sans se voir.
    """
    from src.core.platform_database import get_platform_db

    async def _session_de_test():
        yield session_plateforme

    app.dependency_overrides[get_platform_db] = _session_de_test
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_platform_db, None)


@pytest_asyncio.fixture
async def catalogue_bootstrap(session_plateforme) -> None:
    """RBAC et catalogue de plans amorcés, comme le fait `init_platform.py`."""
    from src.modules.platform.services.plans import bootstrap_catalogue
    from src.modules.platform.services.rbac import PlatformRbacService

    await PlatformRbacService.bootstrap_complet(session_plateforme)
    await bootstrap_catalogue(session_plateforme)
    await session_plateforme.commit()


@pytest_asyncio.fixture
async def super_admin(client_platform, session_plateforme, catalogue_bootstrap):
    """Compte Super Admin actif, 2FA configuree, et son jeton d'acces."""
    from src.modules.platform.models import UtilisateurPlateforme
    from src.modules.platform.security import (
        chiffrer_secret_2fa,
        generer_secret_totp,
    )
    from src.modules.platform.services.users import PlatformUserService

    session = session_plateforme
    await PlatformUserService.creer(
        session,
        email="superadmin.test@sysdent.pro",
        prenom="Super",
        nom="Admin",
        mot_de_passe="MotDePassePlateforme-2026!Ok",
        roles=["SUPER_ADMIN_PLATEFORME"],
        auteur="fixture",
        activer_2fa=False,
    )
    await session.commit()

    # Le secret TOTP est généré ici : `activer_2fa=False` laisse le compte sans
    # secret, et un compte plateforme sans 2FA ne peut pas se connecter — ce qui
    # est exactement ce qu'exige la Phase A.
    #
    # Le compte est ensuite mis dans l'état **enrôlé** : `deux_facteurs_actif`
    # vrai (le login décide sur l'état actif, plus sur l'existence d'un secret)
    # et `codes_secours_a_regenerer` vrai, parce que ce compte de test n'a
    # aucun code de secours — exactement le cas que l'indicateur décrit, et la
    # contrainte `ck_2fa_active_exige_secours` l'exige à l'écriture.
    compte = (
        await session.execute(
            select(UtilisateurPlateforme).where(
                UtilisateurPlateforme.email == "superadmin.test@sysdent.pro"
            )
        )
    ).scalar_one()
    secret = generer_secret_totp()
    compte.secret_2fa_chiffre = chiffrer_secret_2fa(secret)
    compte.deux_facteurs_actif = True
    compte.deux_facteurs_confirme_at = datetime.now(timezone.utc)
    compte.codes_secours_a_regenerer = True
    await session.commit()
    compte_id = compte.id

    jeton = await _connecter(client_platform, "superadmin.test@sysdent.pro", secret)
    return {
        "id": uuid.UUID(str(compte_id)),
        "email": "superadmin.test@sysdent.pro",
        "secret_2fa": secret,
        "access_token": jeton,
        "headers": {"Authorization": f"Bearer {jeton}"},
    }


async def _connecter(client: AsyncClient, email: str, secret_2fa: str) -> str:
    """Connexion plateforme complète : mot de passe puis TOTP."""
    from src.modules.platform.security import codes_totp

    r = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": email, "mot_de_passe": "MotDePassePlateforme-2026!Ok"},
    )
    assert r.status_code == 200, r.text
    challenge = r.json()["data"]["jeton_challenge"]

    code, _ = codes_totp(secret_2fa)
    r = await client.post(
        "/api/v1/platform/auth/2fa",
        json={"jeton_challenge": challenge, "code": code},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]
