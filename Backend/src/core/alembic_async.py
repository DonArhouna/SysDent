"""Exécution des migrations Alembic en mode **asynchrone**, via `asyncpg`.

**Pourquoi.** La pile applicative parle PostgreSQL par `asyncpg`. Les migrations,
elles, passaient par `postgresql+psycopg2`, et ce choix portait deux consequences
invisibles :

- `asyncpg` et `psycopg2` n'ont ni le même pilote ni la même gestion de types ;
  une migration écrite pour l'un est appliquée par l'autre sans que rien ne le
  dise ;
- le pilote `psycopg2` charge une DLL native. Sur un poste où une politique de
  contrôle d'application bloque cette DLL, **toute la suite de tests echoue a la
  collection**, sans qu'aucun test n'ait ete ecrit faux.

Ce module retire psycopg2 du chemin d'execution : Alembic ouvre un moteur
`asyncpg` et fait tourner les migrations synchrones dans son thread interne, via
`run_sync` - le mecanisme officiel d'Alembic pour le mode asynchrone.

**Pourquoi `asyncio.run` ici.** Le point d'entree public
(`src.core.migrations.upgrade_*`) est **synchrone**, et ses appelants
l'executent deja dans un thread dedie via `asyncio.to_thread` : il n'y a donc
aucune boucle en cours dans ce thread, et `asyncio.run` y est legal. Ecrire un
`asyncio.run` imbrique depuis du code deja async serait une erreur ; ici ce n'est
pas le cas, et c'est verifiable dans les appelants.

Si un jour un appelant veut migrer depuis sa propre boucle, il doit utiliser
`run_migrations_async_engine` avec son moteur existant plutot que celui-ci.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


def run_migrations_async(
    url: str,
    target_metadata: Any,
    *,
    compare_type: bool = False,
) -> None:
    """Applique les migrations en cours sur l'URL donnée. Synchrone pour l'appelant."""
    from alembic import context

    connectable = create_async_engine(url, poolclass=NullPool)

    def _appliquer(synchrone) -> None:
        context.configure(
            connection=synchrone,
            target_metadata=target_metadata,
            compare_type=compare_type,
        )
        with context.begin_transaction():
            context.run_migrations()

    async def _executer() -> None:
        try:
            async with connectable.connect() as connexion:
                await connexion.run_sync(_appliquer)
        finally:
            # `dispose` doit attendre la fermeture de la boucle : apres
            # `asyncio.run`, le moteur ne serait plus utilisable.
            await connectable.dispose()

    asyncio.run(_executer())


def normaliser_url_vers_asyncpg(url: str) -> str:
    """
    Ramene une URL vers `postgresql+asyncpg://`.

    Un `.env` ou une commande peut encore fournir `postgresql+psycopg2://` :
    refuser cette URL serait casser une installation qui fonctionne, et
    l'accepter telle quelle echouerait a l'import du pilote. La convertir est le
    comportement utile.
    """
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


async def run_migrations_async_engine(moteur, target_metadata: Any, *, compare_type: bool = False) -> None:
    """
    Applique les migrations depuis une boucle **deja ouverte**.

    Pour un appelant async qui possede deja son moteur. Utiliser celle-ci plutot
    que `run_migrations_async`, qui fermerait la boucle de l'appelant.
    """
    from alembic import context

    def _appliquer(synchrone) -> None:
        context.configure(
            connection=synchrone,
            target_metadata=target_metadata,
            compare_type=compare_type,
        )
        with context.begin_transaction():
            context.run_migrations()

    async with moteur.connect() as connexion:
        await connexion.run_sync(_appliquer)


__all__ = [
    "run_migrations_async",
    "run_migrations_async_engine",
    "normaliser_url_vers_asyncpg",
]