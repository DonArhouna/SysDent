import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.core.alembic_async import run_migrations_async, normaliser_url_vers_asyncpg
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
        "URL de la base tenant manquante. Utiliser -x tenant_db_url=postgresql+asyncpg://... "
        "ou définir la variable d'environnement ALEMBIC_TENANT_DB_URL."
    )
# Le chemin d'exécution est asynchrone (`run_migrations_async` ouvre un moteur
# `asyncpg`). Une URL `psycopg2` doit donc être convertie ici, sinon c'est elle
# qui est sélectionnée et la DLL native est chargée — ce que la stratégie de
# contrôle d'application de certains postes bloque, avec un `ImportError` qui ne
# parle ni de l'URL, ni du pilote, ni de la DLL.
db_url = normaliser_url_vers_asyncpg(db_url)
# `%%` : l'URL passe par ConfigParser, où `%` est un caractère d'interpolation.
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))


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
    # Mode asynchrone via `asyncpg` : meme raison que le contexte plateforme.
    run_migrations_async(db_url, target_metadata)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
