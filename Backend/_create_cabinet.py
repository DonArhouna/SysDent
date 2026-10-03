"""
Crée une société (cabinet) + son compte administrateur.

Usage :
    .\\.venv\\Scripts\\python.exe .\\_create_cabinet.py <email> <mot_de_passe> [nom]

Pourquoi ce script existe
-------------------------
Le frontend n'expose que `/login` et `/dashboard` : il n'y a pas d'écran de
provisionnement. Sans société en base, le login renvoie 401 quel que soit le
mot de passe — il n'y a personne à qui se connecter. Ce script passe par la
console Master, exactement comme le ferait un administrateur SysDent, et
n'écrit rien directement dans les tables métier.

Exemples :
    .\\_create_cabinet.py admin@cabinet.sn MotDePasse123!
    .\\_create_cabinet.pyadmin@cabinet.sn MotDePasse123! "Clinique齿科"
"""

import asyncio
import sys
import uuid

sys.path.insert(0, ".")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.core.database import MasterAsyncSessionFactory, master_engine, tenant_db_manager
from src.core.rate_limit import login_master_limiter
from src.core.security import get_password_hash
from src.main import app
from src.modules.master.models import SuperAdmin, TenantDB

# 21 societies issues des scripts de verification polluent le master : leurs
# bases tenant ont disparu (conteneur jetable supprime). On cree donc un super
# admin a usage unique si aucun n'existe deja.
SUPER_EMAIL = "root@sysdent.pro"
SUPER_PASSWORD = "MotDePasseRoot!"


async def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    email = sys.argv[1].strip().lower()
    mot_de_passe = sys.argv[2]
    nom = sys.argv[3] if len(sys.argv) > 3 else "Clinique Demo"

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    # ---------------------------------------- super admin (console Master)
    async with MasterAsyncSessionFactory() as s:
        existant = (
            await s.execute(select(SuperAdmin).where(SuperAdmin.email == SUPER_EMAIL))
        ).scalar_one_or_none()
        if existant is None:
            s.add(
                SuperAdmin(
                    email=SUPER_EMAIL,
                    mot_de_passe=get_password_hash(SUPER_PASSWORD),
                    nom_complet="Administrateur SysDent",
                    actif=True,
                )
            )
            await s.commit()
            print(f"Super Admin cree : {SUPER_EMAIL} / {SUPER_PASSWORD}")

    login_master_limiter.reinitialiser()
    r = await client.post(
        "/api/v1/master/auth/login",
        json={"email": SUPER_EMAIL, "password": SUPER_PASSWORD},
    )
    if r.status_code != 200:
        print(f"Echec login master : HTTP {r.status_code}")
        print(r.text[:300])
        return 1
    token = r.json()["data"]["access_token"]

    # --------------------------------------------------- provisionnement
    suffixe = uuid.uuid4().hex[:8]
    r = await client.post(
        "/api/v1/master/societes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nom": nom,
            "ninea": f"NINEA-{suffixe.upper()}",
            "admin_email": email,
            "admin_prenom": "Administrateur",
            "admin_nom": nom.split()[0],
            "admin_password": mot_de_passe,
        },
    )
    if r.status_code != 201:
        # Un email déjà pris n'est pas une erreur de script : la société existe
        # déjà. On le dit clairement plutôt que d'afficher un échec.
        code = r.json().get("error", {}).get("code")
        if code == "EMAIL_DEJA_UTILISE":
            print(f"Societe deja existante pour {email} — verification du login...")
            return await _verifier(client, email, mot_de_passe)
        print(f"Echec provisionnement : HTTP {r.status_code}")
        print(r.text[:500])
        return 1

    societe_id = r.json()["data"]["id"]

    async with MasterAsyncSessionFactory() as s:
        cfg = (
            await s.execute(select(TenantDB).where(TenantDB.societe_id == societe_id))
        ).scalar_one()
    print(f"Societe creee : {nom}")
    print(f"  base tenant : {cfg.db_name}")

    return await _verifier(client, email, mot_de_passe)


async def _verifier(client, email, mot_de_passe) -> int:
    """Login reel + lecture du profil, pour ne pas annoncer un compte casse."""
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": mot_de_passe})
    if r.status_code != 200:
        print(f"\nEchec verification login : HTTP {r.status_code}")
        print(r.text[:300])
        return 1

    token = r.json()["data"]["access_token"]
    print("\nLogin verifie (HTTP 200), token obtenu.")

    # `/auth/login` ne renvoie que les jetons : le profil et le role viennent
    # d'un second appel. C'est aussi ce que fait le frontend.
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 200:
        profil = r.json()["data"]
        print(f"  profil : {profil.get('email')} ({profil.get('prenom', '')} {profil.get('nom', '')})")
        print(f"  role   : {profil.get('role')}")

    print(f"\n  Connexion : http://localhost:5173/login")
    print(f"  {email}")
    print(f"  {mot_de_passe}")
    return 0


if __name__ == "__main__":
    try:
        code_sortie = asyncio.run(main())
    finally:
        # Les moteurs SQLAlchemy tiennent des sockets ; sans ça le script
        # laisse le port 55435 dans l'état TIME_WAIT et les avertissements
        # « Event loop is closed » à la fin.
        asyncio.run(tenant_db_manager.close_all())
        asyncio.run(master_engine.dispose())
    sys.exit(code_sortie)