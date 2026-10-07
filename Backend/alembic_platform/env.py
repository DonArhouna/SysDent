import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.common.base_model import PlatformBase

# Importer les modèles plateforme pour qu'ils s'enregistrent dans
# PlatformBase.metadata. On n'importe NI `master.models` NI `tenants.models` :
# les trois univers de données ont trois registres de métadonnées distincts, et
# un import de travers ferait créer les tables d'un univers dans la base d'un autre.
from src.modules.platform import models as platform_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = PlatformBase.metadata

# L'URL vient de settings (donc du .env), comme pour les deux autres contextes.
# ALEMBIC_PLATFORM_DB_URL permet de la surcharger ponctuellement (CI, copie de test).
db_url = os.environ.get("ALEMBIC_PLATFORM_DB_URL")
if not db_url:
    from src.core.config import settings

    db_url = settings.platform_db_sync_url

# Une URL fournie PAR LE SPOUVENIR (`-x sqlalchemy.url=`) prime sur le .env.
# Sans cette ligne, la suite de tests — qui crée une base jetable et demande
# explicitement d'y appliquer les migrations — verrait ses migrations appliquées
# sur la base de développement, et les tests s'executeraient ensuite contre une
# base vide.
#
# Alembic sérialise ses options dans `ConfigParser`, qui interpole `%` : une URL
# contenant un mot de passe avec `%` doit être échappée, sinon la lecture échoue
# silencieusement et le contexte retombe sur l'URL du .env.
url_fournie = config.get_main_option("sqlalchemy.url", None)
if url_fournie:
    db_url = url_fournie.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace("%", "%%")

config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()