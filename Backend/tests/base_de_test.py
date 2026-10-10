"""Outil de base de test : un modèle migré, cloné à la demande.

Séparé de `conftest.py` pour être importable par les tests d'isolation, qui
créent eux-mêmes **deux** bases (deux cabinets) et donc ne peuvent pas passer par
la fixture `tenant_db`.

Le constat qui a motivé ce module : les 17 migrations Alembic étaient rejouées
pour chaque base créée, et trois fichiers d'isolation en créaient deux par test.
Their setup coûtait 6 à 8,6 secondes, contre moins d'une seconde pour un clone.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import settings
from src.core.migrations import upgrade_tenant_to_head

#: Nom du modèle vide au schéma à jour. Renseigné au premier usage puis réutilisé
#: : le construire coûte le démarrage d'Alembic et 17 lots de DDL.
#:
#: Il porte le suffixe `_test` **exprès** : l'instance de développement possède
#: déjà une base `sysdent_modele_tenant`. Deux bases du même nom sur deux
#: instances, et une connexion qui dérape d'une ligne suffirait à supprimer la
#: mauvaise. Un nom distinct rend l'erreur visible au lieu de la rendre
#: irrattrapable.
MODELE_TENANT = "sysdent_modele_tenant_test"

_modele_prete: bool = False


def _creds() -> str:
    """Identifiants de l'instance de tests, **jamais ceux du développement**.

    Avant, ce module lisait `settings.TENANT_DB_*` : il créait et détruisait donc
    des bases sur l'instance qui porte les cabinets. Il lit désormais la même
    variable que `conftest.py`, dont la garde de démarrage a vérifié qu'elle
    désigne une instance marquée comme instance de tests.
    """
    base = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not base:
        raise RuntimeError(
            "TEST_DATABASE_URL absente : la garde de demarrage des tests devrait "
            "avoir arrete la session avant ce point."
        )
    _, _, reste = base.partition("://")
    return reste.rstrip("/").rsplit("/", 1)[0]


def _async_url(db_name: str) -> str:
    return f"postgresql+asyncpg://{_creds()}/{db_name}"


def _sync_url(db_name: str) -> str:
    return f"postgresql+asyncpg://{_creds()}/{db_name}"


async def _admin():
    return create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")


async def construire_modele(
    nom: str = MODELE_TENANT,
    migration: Callable[[str], None] = upgrade_tenant_to_head,
    url_sync: Callable[[str], str] = _sync_url,
) -> str:
    """Crée une base vide et la migre à jour. Les connexions sont libérées.

    La libération est obligatoire : `CREATE DATABASE … TEMPLATE` échoue si le
    modèle a ne serait-ce qu'une seule connexion ouverte.
    """
    global _modele_prete
    engine = await _admin()
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{nom}"'))
        # Alembic est synchrone : hors de la boucle asyncio.
        await asyncio.to_thread(migration, url_sync(nom))
    finally:
        await engine.dispose()
    _modele_prete = True
    return nom


async def cloner(nom: str, modele: str = MODELE_TENANT) -> str:
    """Copie le modèle migré dans une base neuve, et renvoie son nom."""
    if not _modele_prete:
        await asyncio.to_thread(construire_modele_sync, modele)
    engine = await _admin()
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{nom}" TEMPLATE "{modele}"'))
    finally:
        await engine.dispose()
    return nom


def construire_modele_sync(modele: str) -> None:
    """Variante synchrone pour être appelée depuis un `asyncio.to_thread`."""
    asyncio.run(construire_modele(modele))


def nom_jetable(prefixe: str = "sysdent_test") -> str:
    return f"{prefixe}_{uuid.uuid4().hex[:12]}"


def definir_environnement(db_name: str) -> None:
    """Les fixtures historiques lisent le nom de base via l'environnement."""
    os.environ["TEST_TENANT_DB_NAME"] = db_name