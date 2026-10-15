"""
Un compte PostgreSQL dédié par cabinet.

**Pourquoi.** Tous les cabinets se connectaient avec le compte d'administration
du serveur (`TENANT_DB_USER`, en pratique `postgres`, superutilisateur). Une
faille dans le code exécuté pour UN cabinet donnait alors accès aux bases de
TOUS les cabinets - et au droit de les supprimer.

Désormais, chaque cabinet a son propre compte :

- sans aucun privilège d'administration (`NOSUPERUSER NOCREATEDB NOCREATEROLE`) ;
- **propriétaire de sa base** et de ses tables (migrations et semis tournent
  sous ce compte) ;
- seul autorisé à s'y connecter : `CONNECT` est retiré à `PUBLIC`, donc le
  compte d'un autre cabinet est refusé à la connexion ;
- mot de passe aléatoire, stocké uniquement **chiffré** dans le registre master
  (`tenants_db.db_password`), jamais journalisé.

Le compte d'administration ne sert plus qu'à créer et supprimer bases et
comptes. Les identifiants sont des valeurs contrôlées (`[a-z0-9_]` pour les
noms, hexadécimal pour le mot de passe) : `CREATE ROLE` n'accepte pas de
paramètre lié, ils sont donc insérés tels quels, après vérification.
"""

import re
import secrets
from typing import Tuple

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import settings

logger = structlog.get_logger(__name__)

_IDENTIFIANT_SUR = re.compile(r"^[a-z0-9_]{1,63}$")


def _verifier(identifiant: str) -> str:
    if not _IDENTIFIANT_SUR.match(identifiant):
        raise ValueError(f"Identifiant PostgreSQL refusé : {identifiant!r}")
    return identifiant


def nom_role(db_name: str) -> str:
    """Nom du compte d'un cabinet, dérivé de sa base (63 caractères au plus)."""
    return _verifier(f"u_{db_name}"[:63])


def generer_identifiants(db_name: str) -> Tuple[str, str]:
    """(compte, mot de passe) d'un nouveau cabinet. Hexadécimal : sûr dans une URL et en SQL."""
    return nom_role(db_name), secrets.token_hex(24)


def url_tenant(db_name: str, user: str, password: str) -> str:
    return (
        f"postgresql+asyncpg://{user}:{password}"
        f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/{db_name}"
    )


def _url_admin(base: str) -> str:
    return url_tenant(base, settings.TENANT_DB_USER, settings.TENANT_DB_PASSWORD)


async def creer_base_dediee(db_name: str, role: str, mot_de_passe: str) -> None:
    """
    Crée le compte du cabinet, puis sa base, qui lui appartient et à lui seul.

    Idempotent : un compte déjà présent (reprise après échec) voit son mot de
    passe réaligné sur celui du registre, une base déjà présente est conservée.
    """
    _verifier(db_name)
    _verifier(role)
    if not re.fullmatch(r"[0-9a-f]{16,128}", mot_de_passe):
        raise ValueError("Mot de passe de cabinet inattendu : hexadécimal requis.")

    admin = _verifier(settings.TENANT_DB_USER)
    moteur = create_async_engine(_url_admin("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with moteur.connect() as conn:
            existe = await conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role})
            clauses = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            if existe.scalar_one_or_none():
                await conn.execute(text(f"ALTER ROLE {role} WITH {clauses} PASSWORD '{mot_de_passe}'"))
            else:
                await conn.execute(text(f"CREATE ROLE {role} WITH {clauses} PASSWORD '{mot_de_passe}'"))

            base = await conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name})
            if not base.scalar_one_or_none():
                await conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER {role}'))
            else:
                await conn.execute(text(f'ALTER DATABASE "{db_name}" OWNER TO {role}'))

            # Personne d'autre que le cabinet (et l'administrateur du serveur) ne
            # peut ouvrir cette base : sans ce REVOKE, `PUBLIC` garde CONNECT.
            await conn.execute(text(f'REVOKE ALL ON DATABASE "{db_name}" FROM PUBLIC'))
            await conn.execute(text(f'GRANT CONNECT, TEMPORARY ON DATABASE "{db_name}" TO {role}'))
    finally:
        await moteur.dispose()

    # Dans la base elle-même, toujours en administrateur :
    moteur = create_async_engine(_url_admin(db_name), isolation_level="AUTOCOMMIT")
    try:
        async with moteur.connect() as conn:
            # Le cabinet possède son schéma : il y crée ses tables (PostgreSQL < 15
            # laisse `public` à l'administrateur).
            await conn.execute(text(f"ALTER SCHEMA public OWNER TO {role}"))
            await conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            # Extension utilisée par les migrations (contrainte d'exclusion des
            # rendez-vous). L'installer ici évite d'exiger un superutilisateur
            # pendant les migrations, qui tournent sous le compte du cabinet.
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
            # Garde-fou : un objet créé plus tard par l'administrateur (outil de
            # maintenance, migration lancée avec le mauvais compte) reste
            # utilisable par le cabinet au lieu de casser ses requêtes.
            for objets in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                await conn.execute(
                    text(
                        f"ALTER DEFAULT PRIVILEGES FOR ROLE {admin} IN SCHEMA public "
                        f"GRANT ALL ON {objets} TO {role}"
                    )
                )
    finally:
        await moteur.dispose()

    logger.info("base_cabinet_dediee_creee", db_name=db_name, role=role)


async def supprimer_base_et_role(db_name: str, role: str) -> None:
    """Compensation : supprime la base puis le compte. Chaque étape est tentée."""
    _verifier(db_name)
    moteur = create_async_engine(_url_admin("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with moteur.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
            if role and _IDENTIFIANT_SUR.match(role) and role != settings.TENANT_DB_USER:
                await conn.execute(text(f"DROP ROLE IF EXISTS {role}"))
    finally:
        await moteur.dispose()
