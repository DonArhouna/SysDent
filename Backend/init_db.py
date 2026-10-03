import asyncio
import os
import sys

# Assurer que le dossier Backend est dans le sys.path (permet d'exécuter depuis n'importe où)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from sqlalchemy import select
from src.core.database import MasterAsyncSessionFactory, master_engine
from src.core.migrations import upgrade_master_to_head
from src.core.security import get_password_hash
from src.modules.master.models import SuperAdmin

SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "admin@sysdent.pro")


def _mot_de_passe_super_admin() -> str:
    """
    Récupère le mot de passe du Super Admin depuis l'environnement.

    En développement uniquement, on tolère une valeur de secours afin que
    `python init_db.py` reste exécutable sans configuration. En production
    (APP_ENV=production), l'absence de variable est une erreur : un compte
    Super Admin à mot de passe deviant sur une installation réelle est pire que
    pas de compte du tout.
    """
    from src.core.config import settings

    mot_de_passe = os.environ.get("SUPER_ADMIN_PASSWORD")
    if mot_de_passe:
        return mot_de_passe

    if settings.APP_ENV == "production":
        raise SystemExit(
            "SUPER_ADMIN_PASSWORD est obligatoire en production. "
            "Exemple : $env:SUPER_ADMIN_PASSWORD='un-mot-de-passe-solide'"
        )

    return "Admin123!"


async def init_database() -> None:
    """
    Applique les migrations Alembic de la base Master et insère le Super Admin par défaut.

    Le mot de passe du Super Admin n'est plus codé en dur : il doit être fourni
    par `SUPER_ADMIN_PASSWORD`. Un mot de passe par défaut dans le dépôt serait
    un mot de passe par défaut sur toutes les installations, alors que ce compte
    peut provisionner n'importe quel cabinet.
    """
    print("🚀 Initialisation de la base Master PostgreSQL...")

    # 1. Schéma Master versionné via Alembic (voir Backend/alembic/). Alembic étant synchrone,
    # on l'exécute dans un thread pour ne pas bloquer l'event loop asyncio de ce script.
    print("📦 Application des migrations Alembic (societes, tenants_db, super_admins, audit_logs_global)...")
    await asyncio.to_thread(upgrade_master_to_head)
    print("✅ Schéma Master à jour !")

    # 2. Création d'un Super Admin par défaut si inexistant
    mot_de_passe = _mot_de_passe_super_admin()
    async with MasterAsyncSessionFactory() as session:
        stmt = select(SuperAdmin).where(SuperAdmin.email == SUPER_ADMIN_EMAIL)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            print(f"👤 Création du compte Super Administrateur ({SUPER_ADMIN_EMAIL})...")
            super_admin = SuperAdmin(
                email=SUPER_ADMIN_EMAIL,
                mot_de_passe=get_password_hash(mot_de_passe),
                nom_complet="Super Administrateur SysDent",
                actif=True,
            )
            session.add(super_admin)
            await session.commit()
            print("✅ Compte Super Admin créé avec succès :")
            print(f"   - Email        : {SUPER_ADMIN_EMAIL}")
            print("   - Mot de passe : (celui défini dans SUPER_ADMIN_PASSWORD)")
        else:
            print(f"ℹ️ Le compte Super Admin ({SUPER_ADMIN_EMAIL}) existe déjà.")

    # 3. Fermeture propre du pool de connexions
    await master_engine.dispose()
    print("🎉 Initialisation terminée !")


if __name__ == "__main__":
    asyncio.run(init_database())
