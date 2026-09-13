import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.common.base_model import Base
from src.core.config import settings
# Importer les modèles Master pour qu'ils s'enregistrent dans Base.metadata.
from src.modules.master import models as master_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# L'URL vient de settings (donc de .env) et non du .ini, pour rester sur une seule source de vérité.
# ALEMBIC_MASTER_DB_URL permet de la surcharger ponctuellement (ex: génération de baseline sur une DB vierge).
db_url = os.environ.get("ALEMBIC_MASTER_DB_URL", settings.master_db_sync_url)
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
