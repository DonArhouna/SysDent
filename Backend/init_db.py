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


async def init_database() -> None:
    """Applique les migrations Alembic de la base Master et insère le Super Admin par défaut."""
    print("🚀 Initialisation de la base Master PostgreSQL...")

    # 1. Schéma Master versionné via Alembic (voir Backend/alembic/). Alembic étant synchrone,
    # on l'exécute dans un thread pour ne pas bloquer l'event loop asyncio de ce script.
    print("📦 Application des migrations Alembic (societes, tenants_db, super_admins, audit_logs_global)...")
    await asyncio.to_thread(upgrade_master_to_head)
    print("✅ Schéma Master à jour !")

    # 2. Création d'un Super Admin par défaut si inexistant
    async with MasterAsyncSessionFactory() as session:
        stmt = select(SuperAdmin).where(SuperAdmin.email == "admin@sysdent.pro")
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            print("👤 Création du compte Super Administrateur (admin@sysdent.pro)...")
            super_admin = SuperAdmin(
                email="admin@sysdent.pro",
                mot_de_passe=get_password_hash("Admin123!"),
                nom_complet="Super Administrateur SysDent",
                actif=True,
            )
            session.add(super_admin)
            await session.commit()
            print("✅ Compte Super Admin créé avec succès :")
            print("   - Email        : admin@sysdent.pro")
            print("   - Mot de passe : Admin123!")
        else:
            print("ℹ️ Le compte Super Admin (admin@sysdent.pro) existe déjà.")

    # 3. Fermeture propre du pool de connexions
    await master_engine.dispose()
    print("🎉 Initialisation terminée !")


if __name__ == "__main__":
    asyncio.run(init_database())
