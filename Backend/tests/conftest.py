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
import os
import uuid
from datetime import date
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import structlog
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.database import tenant_db_manager
from src.core.migrations import upgrade_tenant_to_head
from src.core.security import get_password_hash
from src.main import app

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
    """URL psycopg2 pour Alembic (qui est synchrone)."""
    return f"postgresql+psycopg2://{_creds()}/{db_name}"


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


async def _creer_base(db_name: str) -> None:
    """Crée une base jetable sur l'instance de maintenance `postgres`."""
    admin_engine = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await admin_engine.dispose()


async def _supprimer_base(db_name: str) -> None:
    admin_engine = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    finally:
        await admin_engine.dispose()


@pytest_asyncio.fixture
async def tenant_db(tmp_path) -> AsyncGenerator[AsyncSession, None]:
    """
    Crée une base tenant jetable, applique les migrations Alembic, fournit une
    session, puis supprime la base. Un tenant par test : aucun état ne fuite
    d'un test à l'autre.

    Tolérance à une reconnexion : sous Windows, la pile réseau d'asyncpg peut
    abandonner une connexion en cours (WinError 995 / ConnectionResetError) lors
    des ouvertures et fermetures rapides de sockets — la suite crée et supprime
    plus d'une centaine de bases. Une reprise unique est appliquée : elle
    concerne l'outillage de test, pas le comportement du produit, qui est
    validé séparément par le script de vérification bout-en-bout.
    """
    derniere_erreur = None

    for tentative in range(2):
        db_name = f"sysdent_test_{uuid.uuid4().hex[:12]}"
        os.environ["TEST_TENANT_DB_NAME"] = db_name
        try:
            await _creer_base(db_name)
            # Alembic est synchrone : exécuté hors du loop asyncio.
            await asyncio.to_thread(upgrade_tenant_to_head, _sync_url(db_name))
            break
        except (OSError, ConnectionError) as exc:
            derniere_erreur = exc
            await _supprimer_base(db_name)
            if tentative == 0:
                continue
            raise
    else:  # pragma: no cover - défensif
        raise AssertionError(f"Impossible de créer la base de test : {derniere_erreur}")

    engine = create_async_engine(_async_url(db_name))
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
        await _supprimer_base(db_name)


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

    # Le compte doit porter un profil praticien : sans lui, le service Consultations
    # refuse toute consultation (la traçabilité médico-légale exige un auteur
    # clinique identifié). On crée donc le praticien comme le ferait l'onboarding.
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
