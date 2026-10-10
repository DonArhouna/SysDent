import os
from alembic import command
from alembic.config import Config

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def upgrade_master_to_head() -> None:
    """Applique les migrations Alembic de la base Master (schéma societes/tenants_db/super_admins/audit_logs_global)."""
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")


def upgrade_tenant_to_head(tenant_db_url: str) -> None:
    """
    Applique les migrations Alembic du schéma Tenant (patients, consultations,
    facturation, salle d'attente...) sur la base PostgreSQL d'un cabinet.

    **Le chemin d'exécution est asynchrone.** `alembic_tenant/env.py` ouvre un
    moteur `asyncpg` et fait tourner les migrations synchrones dans son thread
    interne. L'URL peut donc être donnée sous les deux formes :
    `postgresql+asyncpg://` directement, ou `postgresql+psycopg2://` — elle est
    alors convertie avant tout chargement de pilote.

    Le paramètre s'appelait `tenant_db_sync_url` et sa docstring annonçait une
    URL synchrone : le contrat disait l'inverse de la réalité. Les deux
    appelants de production passaient déjà une URL `asyncpg`, et rien ne
    documentait pourquoi la forme « sync » échouait sur un poste où la DLL
    `psycopg2` est bloquée. Un nom qui ment sur le contrat coûte une heure.
    """
    cfg = Config(os.path.join(BACKEND_DIR, "alembic_tenant.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic_tenant"))
    # Transmis à alembic_tenant/env.py via `config.attributes` (mécanisme recommandé par Alembic
    # pour un usage programmatique, par opposition aux arguments -x réservés à la CLI).
    cfg.attributes["tenant_db_url"] = tenant_db_url
    command.upgrade(cfg, "head")


def upgrade_platform_to_head() -> None:
    """
    Applique les migrations Alembic de la base PLATEFORME (`sysdent_platform`).

    Troisième contexte, après la base master et les bases clients. Isolé de son
    côté : une migration plateforme ne peut pas voir les tables d'un cabinet, ni
    être appliquée par erreur sur une base client.
    """
    cfg = Config(os.path.join(BACKEND_DIR, "alembic_platform.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic_platform"))
    command.upgrade(cfg, "head")
