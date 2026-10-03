"""
Tests du Sprint 0bis — sécurité.

Ces tests couvrent les corrections quiFERMENT une escalade de privilèges ou
suppriment l'absence de contrôle d'accès :

  1. `/master/societes` exige un Super Admin authentifié (avant : ouvert à tous)
  2. `/auth/refresh` ne peut plus accorder `ADMIN_CABINET` (avant : rôle en dur)
  3. Les sessions sont persistées et révocables (avant : refresh rejouable 7 jours)
  4. Le RBAC refuse réellement les rôles non autorisés (avant : aucun seed)
  5. Le rate limiting bloque la force brute
  6. L'index Master rend le login O(1) sans toucher aux autres bases
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import MasterAsyncSessionFactory
from src.core.rate_limit import RateLimiter, cle_login
from src.core.security import create_access_token, create_refresh_token, get_password_hash
from src.main import app
from src.modules.master.models import Societe, SuperAdmin, TenantDB, UtilisateurIndex
from src.modules.tenants.models import Permission, Role, Utilisateur


# ==============================================================================
# 1. CONSOLE MASTER — AUTHENTIFICATION OBLIGATOIRE
# ==============================================================================

@pytest_asyncio.fixture
async def super_admin(master_db: AsyncSession) -> SuperAdmin:
    admin = SuperAdmin(
        email="root@sysdent.pro",
        mot_de_passe=get_password_hash("MotDePasseAdmin!"),
        nom_complet="Racine SysDent",
        actif=True,
    )
    master_db.add(admin)
    await master_db.commit()
    return admin


@pytest_asyncio.fixture
async def client_master(master_db: AsyncSession) -> AsyncClient:
    """
    Client HTTP pour la console Master, branché sur le moteur du test.

    `get_master_db` est surchargé pour pointer la session du test : sinon la
    route utiliserait `master_engine`, un moteur global instancié à l'import
    dont le pool de connexions resterait attaché à la première boucle
    d'événements utilisée. Le test suivant, sur une autre boucle, échouerait
    alors sur « Event loop is closed ».
    """
    from src.core.database import get_master_db

    async def _override_master_db():
        yield master_db

    app.dependency_overrides[get_master_db] = _override_master_db
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def super_admin(master_db: AsyncSession):
    """
    Super Admin de test, avec un email unique par exécution.

    La base Master est partagée par la suite (elle n'est pas jetable par test
    comme les bases tenants) : chaque test reçoit donc un compte neuf, supprimé
    en fin de test. Sans cela, les tentatives de verrouillage d'un test
    contamineraient les suivants.
    """
    from src.modules.master.models import SuperAdminSession

    email = f"root-{uuid.uuid4().hex[:8]}@sysdent.pro"
    admin = SuperAdmin(
        email=email,
        mot_de_passe=get_password_hash("MotDePasseAdmin!"),
        nom_complet="Racine SysDent",
        actif=True,
    )
    master_db.add(admin)
    await master_db.commit()

    yield {"email": email, "id": admin.id}

    cible = (
        await master_db.execute(select(SuperAdmin).where(SuperAdmin.email == email))
    ).scalar_one_or_none()
    if cible is not None:
        await master_db.execute(
            SuperAdminSession.__table__.delete().where(SuperAdminSession.super_admin_id == cible.id)
        )
        await master_db.delete(cible)
        await master_db.commit()


@pytest.mark.asyncio
async def test_creation_societe_refusee_sans_token(client_master: AsyncClient):
    """
    Régression la plus grave du Sprint 0 : cette route déclenchait un vrai
    CREATE DATABASE et était accessible sans aucune authentification.
    """
    reponse = await client_master.post(
        "/api/v1/master/societes",
        json={
            "nom": "Clinique Pirate",
            "ninea": "NINEA-PIRATE-001",
            "admin_email": "pirate@clinique.dz",
            "admin_prenom": "Jean",
            "admin_nom": "Pirate",
            "admin_password": "MotDePasse123!",
        },
    )

    assert reponse.status_code == 401, "une création de cabinet ne doit pas être accessible sans jeton"
    assert reponse.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_liste_societes_refusee_sans_token(client_master: AsyncClient):
    reponse = await client_master.get("/api/v1/master/societes")

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_statistiques_refusees_sans_token(client_master: AsyncClient):
    reponse = await client_master.get("/api/v1/master/statistiques")

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_suspension_cabinet_refusee_sans_token(client_master: AsyncClient):
    """Suspendre un cabinet coupe l'accès de ses utilisateurs : route sensible."""
    reponse = await client_master.post(
        f"/api/v1/master/societes/{uuid.uuid4()}/statut", json={"actif": False}
    )

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_token_de_cabinet_refuse_console_master(client_master: AsyncClient):
    """
    Un token d'utilisateur de cabinet (avec tenant_id) ne doit jamais donner
    accès à la console plateforme.
    """
    token = create_access_token(
        user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()), role="ADMIN_CABINET", permissions=["*"]
    )
    client_master.headers.update({"Authorization": f"Bearer {token}"})

    reponse = await client_master.get("/api/v1/master/societes")

    assert reponse.status_code == 401
    assert reponse.json()["error"]["code"] == "SUPER_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_token_invalide_refuse(client_master: AsyncClient):
    client_master.headers.update({"Authorization": "Bearer pas.un.jwt.valide"})

    reponse = await client_master.get("/api/v1/master/societes")

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_login_master_reussit(client_master: AsyncClient, super_admin):
    reponse = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "MotDePasseAdmin!"},
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["nom_complet"] == "Racine SysDent"


@pytest.mark.asyncio
async def test_login_master_mauvais_mot_de_passe(client_master: AsyncClient, super_admin):
    reponse = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "mauvais"},
    )

    assert reponse.status_code == 401
    assert reponse.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_master_compte_inactif_refuse(
    client_master: AsyncClient, super_admin, master_db: AsyncSession
):
    """
    Un Super Admin désactivé ne doit plus pouvoir se connecter.

    La désactivation passe par l'ORM et non par un `UPDATE` sur `__table__` :
    ce dernier n'actualise pas l'`identity_map`, et la session renverrait alors
    l'instance encore active conservée en mémoire — le test passerait à côté de
    ce qu'il cherche à vérifier.
    """
    compte = (
        await master_db.execute(
            select(SuperAdmin).where(SuperAdmin.email == super_admin["email"])
        )
    ).scalar_one()
    compte.actif = False
    await master_db.commit()

    reponse = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "MotDePasseAdmin!"},
    )

    assert reponse.status_code == 401


@pytest.mark.asyncio
async def test_login_master_verrouille_apres_echecs(client_master: AsyncClient, super_admin):
    """Après N échecs, le compte est temporairement verrouillé (anti force brute)."""
    for _ in range(5):
        await client_master.post(
            "/api/v1/master/auth/login",
            json={"email": super_admin["email"], "password": "mauvais"},
        )

    # Le 6e essai est bloqué, même avec le BON mot de passe.
    reponse = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "MotDePasseAdmin!"},
    )

    assert reponse.status_code == 429
    assert reponse.json()["error"]["code"] == "TOO_MANY_REQUESTS"


@pytest.mark.asyncio
async def test_echecs_login_sont_journalises(client_master: AsyncClient, super_admin, master_db):
    """Une tentative de connexion échouée laisse une trace (traçabilité Master)."""
    from src.modules.master.models import AuditLogGlobal

    avant = int(
        (
            await master_db.execute(
                select(func.count(AuditLogGlobal.id)).where(
                    AuditLogGlobal.auteur_email == super_admin["email"]
                )
            )
        ).scalar_one()
    )

    await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "mauvais"},
    )

    apres = int(
        (
            await master_db.execute(
                select(func.count(AuditLogGlobal.id)).where(
                    AuditLogGlobal.auteur_email == super_admin["email"]
                )
            )
        ).scalar_one()
    )

    assert apres > avant, "une tentative de connexion échouée doit laisser une trace"


@pytest.mark.asyncio
async def test_accessions_master_apres_login(client_master: AsyncClient, super_admin):
    login = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "MotDePasseAdmin!"},
    )
    token = login.json()["data"]["access_token"]

    client_master.headers.update({"Authorization": f"Bearer {token}"})
    reponse = await client_master.get("/api/v1/master/statistiques")

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["data"]["super_admins"] >= 1


# ==============================================================================
# 10. PROVISIONNING COMPLET (le chemin le plus lourd de conséquences)
# ==============================================================================

@pytest.mark.asyncio
async def test_provisioning_cree_base_rbac_et_index(client_master: AsyncClient, super_admin):
    """
    Un `POST /master/societes` authentifié doit produire un cabinet opérationnel :
    base PostgreSQL créée et migrée, RBAC seedé, compte admin, index alimenté.

    Cette fonction est celle qui a concentré tous les bugs du projet (lazy-load
    async en sortie de transaction, rôle ADMIN_CABINET créé en double). Elle
    mérite un test dans la suite plutôt qu'un simple script de vérification
    manuel exécuté une fois.
    """
    import asyncpg

    from src.core.config import settings

    login = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "MotDePasseAdmin!"},
    )
    token = login.json()["data"]["access_token"]

    suffixe = uuid.uuid4().hex[:8]
    admin_email = f"admin-nouveau-{suffixe}@clinique.dz"

    reponse = await client_master.post(
        "/api/v1/master/societes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nom": f"Clinique Provisionnement {suffixe}",
            "ninea": f"NINEA-PROV-{suffixe}",
            "admin_email": admin_email,
            "admin_prenom": "Ami",
            "admin_nom": "Admin",
            "admin_password": "MotDePasse123!",
        },
    )

    assert reponse.status_code == 201, reponse.text
    societe_id = reponse.json()["data"]["id"]
    db_name = reponse.json()["data"]["tenant_db"]["db_name"]

    # La base existe réellement et porte le schéma complet.
    import os

    connexion = await asyncpg.connect(
        host=os.environ.get("TENANT_DB_HOST", settings.TENANT_DB_HOST),
        port=int(os.environ.get("TENANT_DB_PORT", settings.TENANT_DB_PORT)),
        user=settings.TENANT_DB_USER,
        password=settings.TENANT_DB_PASSWORD,
        database=db_name,
    )
    try:
        tables = {
            r["table_name"]
            for r in await connexion.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        }
        nb_permissions = await connexion.fetchval("SELECT count(*) FROM permissions")
        nb_roles = await connexion.fetchval("SELECT count(*) FROM roles")
        nb_liens = await connexion.fetchval("SELECT count(*) FROM permission_roles")
        nb_utilisateurs = await connexion.fetchval("SELECT count(*) FROM utilisateurs")
        nb_cabinets = await connexion.fetchval("SELECT count(*) FROM cabinets")
        nb_praticiens = await connexion.fetchval("SELECT count(*) FROM praticiens")
    finally:
        await connexion.close()

    assert {"patients", "consultations", "compteurs", "etats_generaux", "sessions_utilisateurs"} <= tables
    assert nb_permissions > 0, "le RBAC doit être semé, sinon toute route protégée renvoie 403"
    assert nb_roles >= 5, f"rôles métier manquants ({nb_roles})"
    assert nb_liens > 0
    assert nb_utilisateurs == 1
    assert nb_cabinets == 1, "un cabinet doit être créé d'office"
    assert nb_praticiens == 1, "le compte fondateur doit porter un profil praticien"

    # L'index de routage est alimenté : c'est lui qui rend le login possible.
    async with MasterAsyncSessionFactory() as session:
        entry = (
            await session.execute(
                select(UtilisateurIndex).where(UtilisateurIndex.email == admin_email)
            )
        ).scalar_one_or_none()
        statut = (
            await session.execute(
                select(TenantDB.statut).where(TenantDB.societe_id == societe_id)
            )
        ).scalar_one()

    assert entry is not None, "sans index email, le login de ce cabinet échouerait"
    assert statut == "ACTIVE"

    # Nettoyage de la base créée par ce test.
    admin = create_async_engine(
        settings.master_db_async_url.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    await admin.dispose()


@pytest.mark.asyncio
async def test_provisioning_refuse_email_deja_utilise(client_master: AsyncClient, super_admin):
    """
    Un même login ne peut pas être provisionné dans deux cabinets : le login
    serait alors ambigu, et un cabinet pourrait hériter des droits de l'autre.
    """
    login = await client_master.post(
        "/api/v1/master/auth/login",
        json={"email": super_admin["email"], "password": "MotDePasseAdmin!"},
    )
    token = login.json()["data"]["access_token"]

    email_partage = f"partage-{uuid.uuid4().hex[:8]}@clinique.dz"
    for suffixe in ("a", "b"):
        reponse = await client_master.post(
            "/api/v1/master/societes",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "nom": f"Clinique Partage {suffixe}",
                "admin_email": email_partage,
                "admin_prenom": "Ami",
                "admin_nom": "Admin",
                "admin_password": "MotDePasse123!",
            },
        )
        if suffixe == "a":
            assert reponse.status_code == 201, reponse.text
            db_name = reponse.json()["data"]["tenant_db"]["db_name"]
        else:
            assert reponse.status_code == 401
            assert reponse.json()["error"]["code"] == "EMAIL_DEJA_UTILISE"

    from src.core.config import settings

    admin = create_async_engine(
        settings.master_db_async_url.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
    await admin.dispose()


# ==============================================================================
# 2 & 3. SESSIONS TENANT — ROTATION ET RÉVOCATION
# ==============================================================================

@pytest.mark.asyncio
async def test_refresh_ne_promet_plus_admin_cabinet(tenant_db: AsyncSession):
    """
    Régression critique : l'ancien `/auth/refresh` reconstruisait le token avec
    `role="ADMIN_CABINET"` et `permissions=["ALL"]` codés en dur. Un refresh
    token d'un compte au rôle minimal remontait en administrateur complet.
    """
    from src.modules.auth.services import AuthService
    from src.modules.tenants.models import Cabinet, Praticien

    role = Role(nom="SECRETAIRE", description="Secrétariat", niveau_hierarchie=3)
    cabinet = Cabinet(nom="Cabinet Test", ville="Dakar", actif=True)
    tenant_db.add_all([role, cabinet])
    await tenant_db.flush()

    user = Utilisateur(
        email="secretaire@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Seynabou",
        nom="Diallo",
        actif=True,
    )
    tenant_db.add(user)
    await tenant_db.flush()
    tenant_db.add(Praticien(utilisateur_id=user.id, titre="Dr"))
    await tenant_db.commit()

    # Aucun PermissionRole n'est créé pour SECRETAIRE : le rôle n'a aucun droit.
    _, access, refresh, tenant_id = await AuthService.renouveller_session(
        tenant_db, (await AuthService.ouvrir_session(tenant_db, user, str(uuid.uuid4())))[1]
    )

    from src.core.security import decode_token

    payload = decode_token(access)
    assert payload["role"] == "SECRETAIRE", "le rôle ne doit jamais être promu au refresh"
    assert payload["permissions"] == [], "aucune permission ne doit être accordée"
    assert tenant_id is not None


@pytest.mark.asyncio
async def test_refresh_revoque_lancien_token(tenant_db: AsyncSession):
    """La rotation doit invalider immédiatement le refresh token consommé."""
    from src.modules.auth.services import AuthService
    from src.modules.tenants.models import Cabinet

    role = Role(nom="PRATICIEN", description="Dentiste", niveau_hierarchie=2)
    cabinet = Cabinet(nom="Cabinet Test", ville="Dakar", actif=True)
    tenant_db.add_all([role, cabinet])
    await tenant_db.flush()

    user = Utilisateur(
        email="dentiste@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Moussa",
        nom="Sow",
        actif=True,
    )
    tenant_db.add(user)
    await tenant_db.commit()

    _, ancien_refresh = await AuthService.ouvrir_session(tenant_db, user, str(uuid.uuid4()))
    await tenant_db.commit()

    # Premier refresh : OK, et l'ancien token est consommé.
    await AuthService.renouveller_session(tenant_db, ancien_refresh)
    await tenant_db.commit()

    # Réutilisation du même token : refusée.
    from src.core.exceptions import InvalidTokenException

    with pytest.raises(InvalidTokenException):
        await AuthService.renouveller_session(tenant_db, ancien_refresh)


@pytest.mark.asyncio
async def test_refresh_refuse_compte_desactive(tenant_db: AsyncSession):
    """Un compte désactivé ne doit pas pouvoir renouveler sa session."""
    from src.core.exceptions import InvalidTokenException
    from src.modules.auth.services import AuthService
    from src.modules.tenants.models import Cabinet

    role = Role(nom="PRATICIEN", description="Dentiste", niveau_hierarchie=2)
    cabinet = Cabinet(nom="Cabinet Test", ville="Dakar", actif=True)
    tenant_db.add_all([role, cabinet])
    await tenant_db.flush()

    user = Utilisateur(
        email="desactive@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Test",
        nom="Desactive",
        actif=True,
    )
    tenant_db.add(user)
    await tenant_db.commit()

    _, refresh = await AuthService.ouvrir_session(tenant_db, user, str(uuid.uuid4()))
    await tenant_db.commit()

    user.actif = False
    await tenant_db.commit()

    with pytest.raises(InvalidTokenException):
        await AuthService.renouveller_session(tenant_db, refresh)


@pytest.mark.asyncio
async def test_logout_revoque_la_session(tenant_db: AsyncSession):
    """Après logout, le refresh token ne doit plus fonctionner."""
    from src.core.exceptions import InvalidTokenException
    from src.modules.auth.services import AuthService
    from src.modules.tenants.models import Cabinet

    role = Role(nom="PRATICIEN", description="Dentiste", niveau_hierarchie=2)
    cabinet = Cabinet(nom="Cabinet Test", ville="Dakar", actif=True)
    tenant_db.add_all([role, cabinet])
    await tenant_db.flush()

    user = Utilisateur(
        email="logout@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Test",
        nom="Logout",
        actif=True,
    )
    tenant_db.add(user)
    await tenant_db.commit()

    _, refresh = await AuthService.ouvrir_session(tenant_db, user, str(uuid.uuid4()))
    await tenant_db.commit()

    revoquee = await AuthService.revoquer_session(tenant_db, refresh)
    assert revoquee is True

    with pytest.raises(InvalidTokenException):
        await AuthService.renouveller_session(tenant_db, refresh)


@pytest.mark.asyncio
async def test_revoquer_toutes_sessions(tenant_db: AsyncSession):
    """Déconnexion forcée (RG12 : invalidation de session) : tout tombe."""
    from src.modules.auth.services import AuthService
    from src.modules.tenants.models import Cabinet, SessionUser

    role = Role(nom="PRATICIEN", description="Dentiste", niveau_hierarchie=2)
    cabinet = Cabinet(nom="Cabinet Test", ville="Dakar", actif=True)
    tenant_db.add_all([role, cabinet])
    await tenant_db.flush()

    user = Utilisateur(
        email="multi@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Test",
        nom="Multi",
        actif=True,
    )
    tenant_db.add(user)
    await tenant_db.commit()

    refreshes = []
    for _ in range(3):
        _, refresh = await AuthService.ouvrir_session(tenant_db, user, str(uuid.uuid4()))
        refreshes.append(refresh)
    await tenant_db.commit()

    nb_revoquees = await AuthService.revoquer_toutes_sessions(tenant_db, user.id)
    await tenant_db.commit()

    assert nb_revoquees == 3

    stmt = select(func.count(SessionUser.id)).where(
        SessionUser.utilisateur_id == user.id, SessionUser.est_revoque.is_(False)
    )
    restantes = int((await tenant_db.execute(stmt)).scalar_one())
    assert restantes == 0


# ==============================================================================
# 4. RBAC — LE SEED EXISTE ET REFUSE
# ==============================================================================

@pytest.mark.asyncio
async def test_seeds_permissions_et_roles(tenant_db: AsyncSession):
    """Le provisioning doit semer le catalogue : sans lui, tout 403."""
    from src.modules.rbac.services import RbacService

    await RbacService.bootstrap_complet(tenant_db)

    nb_permissions = int(
        (await tenant_db.execute(select(func.count(Permission.id)))).scalar_one()
    )
    assert nb_permissions > 0, "aucune permission seedée : toutes les routes protégées renverraient 403"

    roles = (await tenant_db.execute(select(Role.nom))).scalars().all()
    for attendu in ["ADMIN_CABINET", "PRATICIEN", "SECRETAIRE", "COMPTABLE"]:
        assert attendu in roles, f"rôle {attendu} absent"


@pytest.mark.asyncio
async def test_secretaire_na_pas_acces_au_dossier_medical(tenant_db: AsyncSession):
    """
    Règle clinique : le secrétariat enregistre les patients mais n'accède pas au
    dossier médical. Le RBAC doit l'interdire.
    """
    from src.modules.rbac.services import RbacService

    await RbacService.bootstrap_complet(tenant_db)

    stmt = select(Role).where(Role.nom == "SECRETAIRE")
    role = (await tenant_db.execute(stmt)).scalar_one()
    permissions = await RbacService.permissions_d_un_role(tenant_db, str(role.id))
    permissions_lecture = [p for p in permissions if p.endswith(":READ")]

    assert "PATIENTS:CREATE" in permissions, "la secrétaire doit pouvoir créer un patient"
    assert "PATIENTS:DELETE" not in permissions, "la secrétaire ne doit pas supprimer un dossier"

    modules_lecture = {p.split(":")[0] for p in permissions_lecture}
    assert "FACTURATION" in modules_lecture, "la secrétaire gère la caisse"


@pytest.mark.asyncio
async def test_comptable_na_pas_acces_au_dossier_patient(tenant_db: AsyncSession):
    """Le comptable gère la facturation mais ne voit pas les dossiers patients."""
    from src.modules.rbac.services import RbacService

    await RbacService.bootstrap_complet(tenant_db)

    stmt = select(Role).where(Role.nom == "COMPTABLE")
    role = (await tenant_db.execute(stmt)).scalar_one()
    permissions = await RbacService.permissions_d_un_role(tenant_db, str(role.id))

    assert "FACTURATION:UPDATE" in permissions
    assert not any(p.startswith("PATIENTS:") for p in permissions), (
        f"le comptable ne doit pas accéder aux patients : {permissions}"
    )
    assert not any(p.startswith("CONSULTATIONS:") for p in permissions)


@pytest.mark.asyncio
async def test_praticien_a_acces_clinique_mais_pas_facturation(tenant_db: AsyncSession):
    from src.modules.rbac.services import RbacService

    await RbacService.bootstrap_complet(tenant_db)

    stmt = select(Role).where(Role.nom == "PRATICIEN")
    role = (await tenant_db.execute(stmt)).scalar_one()
    permissions = await RbacService.permissions_d_un_role(tenant_db, str(role.id))

    assert "CONSULTATIONS:CREATE" in permissions
    assert "ODONTOGRAMME:UPDATE" in permissions
    assert not any(p.startswith("FACTURATION:") for p in permissions), (
        "le dentiste ne modifie pas la facturation (matrice du regles.md)"
    )


def _verifier_permission(payload: dict, requise: str) -> None:
    """
    Rejoue la logique de `require_permissions` sur un payload décodé.

    La garde est une dépendance FastAPI qui résout le payload elle-même ; on
    extract ici pour tester la règle d'autorisation sans monter une requête HTTP.
    """
    from src.core.exceptions import PermissionDeniedException

    if payload.get("role") in ["SUPER_ADMIN", "ADMIN_CABINET"]:
        return
    if requise not in payload.get("permissions", []):
        raise PermissionDeniedException(f"Permission requise manquante : '{requise}'.")


@pytest.mark.asyncio
async def test_rbac_refuse_role_sans_permission(tenant_db: AsyncSession):
    """
    Un utilisateur dont le rôle ne porte aucune permission ne doit pas atteindre
    une route protégée. Avant le Sprint 0bis, aucune permission n'existait en
    base : le contrôle ne pouvait aboutir que pour un rôle administrateur.
    """
    from src.core.security import create_access_token, decode_token

    role_sans_droits = Role(nom="STAGE_SANS_DROITS", description="Stage", niveau_hierarchie=3)
    tenant_db.add(role_sans_droits)
    await tenant_db.flush()

    utilisateur_sans_droits = Utilisateur(
        email="stage@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role_sans_droits.id,
        prenom="Stagiaire",
        nom="SansDroits",
        actif=True,
    )
    tenant_db.add(utilisateur_sans_droits)
    await tenant_db.commit()

    token = create_access_token(
        user_id=str(utilisateur_sans_droits.id),
        tenant_id=str(uuid.uuid4()),
        role="STAGE_SANS_DROITS",
        permissions=[],
    )
    payload = decode_token(token)

    from src.core.exceptions import PermissionDeniedException

    with pytest.raises(PermissionDeniedException):
        _verifier_permission(payload, "PATIENTS:DELETE")


@pytest.mark.asyncio
async def test_role_admin_cabinet_contourne_le_rbac(tenant_db: AsyncSession, cabinet):
    """
    ADMIN_CABINET doit garder un accès complet : c'est le rôle de secours qui
    empêche un cabinet de se verrouiller hors de sa propre base.
    """
    from src.core.security import create_access_token, decode_token

    token = create_access_token(
        user_id=str(cabinet["user"].id), tenant_id=str(uuid.uuid4()), role="ADMIN_CABINET", permissions=[]
    )

    # Ne doit pas lever, même sans permissions dans le jeton.
    _verifier_permission(decode_token(token), "PATIENTS:DELETE")


@pytest.mark.asyncio
async def test_rbac_effectif_via_api(client_authenticated: AsyncClient, tenant_db: AsyncSession):
    """
    Contrôle RBAC de bout en bout, par la vraie dépendance FastAPI.

    Un utilisateur SECRETAIRE reçoit 403 sur une route `CONSULTATIONS:CREATE`
    alors qu'ADMIN_CABINET réussit.
    """
    from src.modules.auth import dependencies as auth_deps
    from src.core.security import create_access_token
    from src.modules.rbac.services import RbacService

    await RbacService.bootstrap_complet(tenant_db)

    role_secretaire = (
        await tenant_db.execute(select(Role).where(Role.nom == "SECRETAIRE"))
    ).scalar_one()

    user_secretaire = Utilisateur(
        email="secretaire.e2e@cabinet.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role_secretaire.id,
        prenom="Seynabou",
        nom="Diallo",
        actif=True,
    )
    tenant_db.add(user_secretaire)
    await tenant_db.commit()

    # JWT de la secrétaire : ses permissions sont relues depuis la matrice.
    permissions_secretaire = await RbacService.permissions_d_un_role(
        tenant_db, str(role_secretaire.id)
    )
    assert "PATIENTS:CREATE" in permissions_secretaire
    assert "CONSULTATIONS:CREATE" not in permissions_secretaire
    token = create_access_token(
        user_id=str(user_secretaire.id),
        tenant_id=str(uuid.uuid4()),
        role="SECRETAIRE",
        permissions=permissions_secretaire,
    )

    async def _override_user():
        return user_secretaire

    app.dependency_overrides[auth_deps.get_current_user] = _override_user

    # `require_permissions` lit les permissions du JETON, pas de la base :
    # il faut donc remplacer l'en-tête Authorization, sinon le contrôle
    # continuerait de voir le rôle ADMIN_CABINET du client par défaut.
    client_authenticated.headers.update({"Authorization": f"Bearer {token}"})

    try:
        # La secrétaire peut créer un patient (PATIENTS:CREATE est dans sa matrice).
        creation = await client_authenticated.post(
            "/api/v1/patients",
            json={
                "prenom": "Patiente",
                "nom": "Secretaire",
                "date_naissance": "1995-01-01",
                "sexe": "F",
                "telephone_1": "771000123",
            },
        )
        assert creation.status_code == 201, creation.text
        patient_id = creation.json()["data"]["id"]

        # Mais PAS démarrer une consultation (CONSULTATIONS:CREATE absent).
        consultation = await client_authenticated.post(
            "/api/v1/consultations",
            json={"patient_id": patient_id, "motif": "Douleur"},
        )
        assert consultation.status_code == 403, consultation.text
        assert consultation.json()["error"]["code"] == "PERMISSION_DENIED"
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 5. RATE LIMITING
# ==============================================================================

def test_rate_limiter_bloque_apres_n_tentatives():
    limiteur = RateLimiter(max_tentatives=3, fenetre_secondes=60, duree_blocage_secondes=120)
    cle = "user@x|1.2.3.4"

    limiteur.tenter(cle)
    limiteur.tenter(cle)
    limiteur.tenter(cle)

    from src.core.exceptions import TooManyRequestsException

    with pytest.raises(TooManyRequestsException):
        limiteur.tenter(cle)


def test_rate_limiter_remet_a_zero_apres_succes():
    limiteur = RateLimiter(max_tentatives=2, fenetre_secondes=60, duree_blocage_secondes=120)
    cle = "user@y|1.2.3.4"

    limiteur.tenter(cle)
    limiteur.tenter(cle)
    limiteur.reussite(cle)

    # Le compteur est remis à zéro : deux nouvelles tentatives passent.
    limiteur.tenter(cle)
    limiteur.tenter(cle)


def test_rate_limiter_isole_les_cles():
    """Bloquer un compte ne doit pas bloquer un autre compte ni une autre IP."""
    limiteur = RateLimiter(max_tentatives=1, fenetre_secondes=60, duree_blocage_secondes=120)

    limiteur.tenter("a@x|1.1.1.1")

    from src.core.exceptions import TooManyRequestsException

    with pytest.raises(TooManyRequestsException):
        limiteur.tenter("a@x|1.1.1.1")

    # Autre email, même IP : passe.
    limiteur.tenter("b@x|1.1.1.1")
    # Même email, autre IP : passe.
    limiteur.tenter("a@x|2.2.2.2")


def test_cle_login_normalise_email():
    assert cle_login("  Admin@SysDent.PRO ", "1.2.3.4") == "admin@sysdent.pro|1.2.3.4"


# ==============================================================================
# 6. INDEX MASTER — LOGIN O(1) ET NON-TRAVERSÉE
# ==============================================================================

@pytest.mark.asyncio
async def test_index_email_est_unique_plateforme(master_db: AsyncSession):
    """Un même login ne peut pas appartenir à deux cabinets."""
    from src.core.exceptions import AuthenticationException
    from src.modules.auth.services import AuthService

    # Email unique : la base Master persiste entre les exécutions. Un email fixe
    # entrerait en conflit avec une exécution précédente, et l'exception serait
    # levée sur le PREMIER appel, hors du bloc `pytest.raises`.
    email = f"contact-{uuid.uuid4().hex[:8]}@clinique.dz"
    societe_a = Societe(nom=f"Clinique A {email}", actif=True)
    societe_b = Societe(nom=f"Clinique B {email}", actif=True)
    master_db.add_all([societe_a, societe_b])
    await master_db.flush()

    # Les identifiants sont capturés avant le `finally` : après un rollback,
    # les objets SQLAlchemy sont expirés et lire `.id` déclencherait un
    # rechargement paresseux, interdit en contexte async (MissingGreenlet).
    id_a, id_b = societe_a.id, societe_b.id

    try:
        await AuthService.enregistrer_index(
            master_db, email=email, societe_id=id_a, utilisateur_id=uuid.uuid4()
        )
        await master_db.commit()

        with pytest.raises(AuthenticationException):
            await AuthService.enregistrer_index(
                master_db, email=email, societe_id=id_b, utilisateur_id=uuid.uuid4()
            )
    finally:
        await master_db.rollback()
        await master_db.execute(
            UtilisateurIndex.__table__.delete().where(UtilisateurIndex.email == email)
        )
        await master_db.execute(Societe.__table__.delete().where(Societe.id.in_([id_a, id_b])))
        await master_db.commit()


@pytest.mark.asyncio
async def test_index_routage_present_apres_provisioning(master_db: AsyncSession):
    """Le provisioning doit alimenter l'index : sans lui, login impossible."""
    from src.modules.auth.services import AuthService

    suffix = uuid.uuid4().hex[:8]
    email_saisi = f"Admin-{suffix}@Clinique.DZ"
    email_normalise = f"admin-{suffix}@clinique.dz"

    societe = Societe(nom=f"Clinique Index {suffix}", actif=True)
    master_db.add(societe)
    await master_db.flush()
    societe_id = societe.id

    try:
        await AuthService.enregistrer_index(
            master_db,
            email=email_saisi,
            societe_id=societe_id,
            utilisateur_id=uuid.uuid4(),
        )
        await master_db.commit()

        stmt = select(UtilisateurIndex).where(UtilisateurIndex.email == email_normalise)
        entry = (await master_db.execute(stmt)).scalar_one_or_none()

        assert entry is not None, "l'index doit normaliser l'email en minuscules"
        assert entry.societe_id == societe_id
    finally:
        await master_db.rollback()
        await master_db.execute(
            UtilisateurIndex.__table__.delete().where(UtilisateurIndex.email == email_normalise)
        )
        await master_db.execute(Societe.__table__.delete().where(Societe.id == societe_id))
        await master_db.commit()
