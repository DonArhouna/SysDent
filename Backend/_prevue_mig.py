import os, sys
sys.path.insert(0, ".")
from alembic import command
from alembic.config import Config

RACINE = os.path.abspath(".")
def cfg(script, ini):
    c = Config(os.path.join(RACINE, ini))
    c.set_main_option("script_location", os.path.join(RACINE, script))
    return c

URL = os.environ["PREUVE_URL"]
os.environ["ALEMBIC_PLATFORM_DB_URL"] = URL

c = cfg("alembic_platform", "alembic_platform.ini")
c.set_main_option("sqlalchemy.url", URL)
print("  revision courante :", command.current(c, verbose=False) or "(head)")
command.upgrade(c, "head")
print("  upgrade  -> OK")
command.downgrade(c, "-1")
print("  downgrade-> OK")
command.upgrade(c, "head")
print("  upgrade  -> OK (aller-retour complet)")
