import asyncio
import os
import sys

# Assurer que le dossier Backend est dans le sys.path (permet d'exécuter depuis n'importe où)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from sqlalchemy import select
from src.common.base_model import Base
from src.core.database import MasterAsyncSessionFactory, master_engine
from src.core.security import get_password_hash
# Importer explicitement les modèles Master pour les enregistrer dans SQLAlchemy Base.metadata
from src.modules.master.models import AuditLogGlobal, Societe, SuperAdmin, TenantDB


async def init_database() -> None:
    """Crée toutes les tables de la base de données Master et insère le Super Admin par défaut."""
    print("🚀 Initialisation de la base Master PostgreSQL...")

    # 1. Création des tables Master
    async with master_engine.begin() as conn:
        print("📦 Création des tables : societes, tenants_db, super_admins, audit_logs_global...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables Master créées avec succès !")

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
