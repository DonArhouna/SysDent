import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.common.base_model import TenantBase
# Importer les modèles Tenant pour qu'ils s'enregistrent dans TenantBase.metadata.
from src.modules.tenants import models as tenant_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = TenantBase.metadata

# Cet environnement est appliqué à N bases (une par cabinet) : il n'y a pas d'URL fixe.
# Ordre de résolution : config.attributes (appel programmatique depuis le provisioning)
# > -x tenant_db_url=... (CLI) > variable d'env ALEMBIC_TENANT_DB_URL (CLI / génération de baseline).
x_args = context.get_x_argument(as_dictionary=True)
db_url = (
    config.attributes.get("tenant_db_url")
    or x_args.get("tenant_db_url")
    or os.environ.get("ALEMBIC_TENANT_DB_URL")
)
if not db_url:
    raise RuntimeError(
        "URL de la base tenant manquante. Utiliser -x tenant_db_url=postgresql+psycopg2://... "
        "ou définir la variable d'environnement ALEMBIC_TENANT_DB_URL."
    )
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
