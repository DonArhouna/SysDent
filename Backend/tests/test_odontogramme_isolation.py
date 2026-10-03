"""
Tests d'isolation multi-tenant pour l'Odontogramme.

Un odontogramme est la donnée la plus sensible du dossier dentaire : il décrit
l'intégrité buccale d'une personne. Un cabinet ne doit jamais y accéder, même
par un identifiant deviné.

Rappel outillage : `app.dependency_overrides` est global — on réinstalle
l'injection du cabinet concerné avant chacun de ses appels (`Ctx.use()`).
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.migrations import upgrade_tenant_to_head
from src.core.security import create_access_token, get_password_hash
from src.main import app
from src.modules.auth import dependencies as auth_deps
from src.modules.tenants.models import Cabinet, Praticien, Role, Utilisateur
from tests.conftest import _async_url, _sync_url


class Ctx:
    def __init__(self, label: str, session: AsyncSession, user: Utilisateur):
        self.label = label
        self.session = session
        self.user = user
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def use(self) -> AsyncClient:
        session, user = self.session, self.user

        async def _tenant_db():
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        async def _current_user():
            return user

        app.dependency_overrides[auth_deps.get_tenant_db] = _tenant_db
        app.dependency_overrides[auth_deps.get_current_user] = _current_user
        return self.client

    async def aclose(self):
        await self.client.aclose()
        await self.session.close()
        await self.session.bind.dispose()


async def _creer_ctx(label: str, db_name: str) -> Ctx:
    engine = create_async_engine(_async_url(db_name))
    session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)()

    role = Role(nom="ADMIN_CABINET", description="Admin", niveau_hierarchie=1)
    cabinet = Cabinet(nom=f"Cabinet {label}", ville="Dakar", actif=True)
    session.add_all([role, cabinet])
    await session.flush()

    user = Utilisateur(
        email=f"admin@{label}.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Admin",
        nom=label,
        actif=True,
    )
    session.add(user)
    await session.flush()
    session.add(
        Praticien(utilisateur_id=user.id, titre="Dr", specialite="Chirurgien-Dentiste")
    )
    await session.commit()

    ctx = Ctx(label, session, user)
    token = create_access_token(
        user_id=str(user.id), tenant_id=str(uuid.uuid4()), role="ADMIN_CABINET", permissions=[]
    )
    ctx.client.headers.update({"Authorization": f"Bearer {token}"})
    return ctx


@pytest_asyncio.fixture
async def deux_cabinets():
    noms = [f"sysdent_odo_a_{uuid.uuid4().hex[:8]}", f"sysdent_odo_b_{uuid.uuid4().hex[:8]}"]
    admin = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    for nom in noms:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{nom}"'))
    for nom in noms:
        await asyncio.to_thread(upgrade_tenant_to_head, _sync_url(nom))

    ctx_a = await _creer_ctx("odo-a", noms[0])
    ctx_b = await _creer_ctx("odo-b", noms[1])
    yield ctx_a, ctx_b

    app.dependency_overrides.clear()
    await ctx_a.aclose()
    await ctx_b.aclose()
    await admin.dispose()
    for nom in noms:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))


async def _patient_avec_odontogramme(ctx: Ctx) -> str:
    """Crée un patient et force la génération de son odontogramme dans CE cabinet."""
    client = await ctx.use()
    patient = await client.post(
        "/api/v1/patients",
        json={
            "prenom": "Patient",
            "nom": "Confidentiel",
            "date_naissance": "1980-07-07",
            "sexe": "F",
            "telephone_1": "771234567",
        },
    )
    assert patient.status_code == 201, patient.text
    patient_id = patient.json()["data"]["id"]

    await client.get(f"/api/v1/odontogramme/patients/{patient_id}")
    return patient_id


@pytest.mark.asyncio
async def test_odontogramme_invisible_dans_lautre_cabinet(deux_cabinets):
    ctx_a, ctx_b = deux_cabinets
    patient_id = await _patient_avec_odontogramme(ctx_a)

    # Le cabinet B ne voit ni le patient ni son odontogramme.
    liste = await (await ctx_b.use()).get("/api/v1/odontogramme/patients/" + patient_id)
    assert liste.status_code == 404, liste.text
    assert liste.json()["error"]["code"] == "PATIENT_NOT_FOUND"

    # Aucune donnée dentaire dans la réponse : ni dents, ni états, ni résumé.
    for marqueur in ("numero_fdi", "etat_actuel", "nb_dents", "SAINE"):
        assert marqueur not in liste.text, f"fuite de données dentaires via {marqueur}"


@pytest.mark.asyncio
async def test_modification_croisee_refusee(deux_cabinets):
    """Un cabinet ne doit pas pouvoir modifier l'odontogramme d'un autre patient."""
    ctx_a, ctx_b = deux_cabinets
    patient_id = await _patient_avec_odontogramme(ctx_a)

    client_b = await ctx_b.use()
    reponse = await client_b.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_AVANCEE"},
    )

    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "PATIENT_NOT_FOUND"

    # Vérification côté propriétaire : rien n'a bougé.
    from sqlalchemy import select

    from src.modules.tenants.models import Dent

    client_a = await ctx_a.use()
    lecture = await client_a.get(f"/api/v1/odontogramme/patients/{patient_id}/dent/26")
    assert lecture.json()["data"]["etat_actuel"] == "SAINE"

    dents = (await ctx_a.session.execute(select(Dent).where(Dent.numero_fdi == 26))).scalars().all()
    assert all(d.etat_actuel == "SAINE" for d in dents)


@pytest.mark.asyncio
async def test_historique_croise_refuse(deux_cabinets):
    """L'historique dentaire est la pièce la plus sensible : il ne doit pas fuir."""
    ctx_a, ctx_b = deux_cabinets
    patient_id = await _patient_avec_odontogramme(ctx_a)

    client_a = await ctx_a.use()
    await client_a.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_PROFONDE"},
    )

    client_b = await ctx_b.use()
    for chemin in (
        f"/api/v1/odontogramme/patients/{patient_id}/dent/26/historique",
        f"/api/v1/odontogramme/patients/{patient_id}/historique",
        f"/api/v1/odontogramme/patients/{patient_id}/charting",
    ):
        reponse = await client_b.get(chemin)
        assert reponse.status_code == 404, f"{chemin} -> {reponse.status_code}"


@pytest.mark.asyncio
async def test_creation_croisee_refusee(deux_cabinets):
    """
    Générer un odontogramme pour un patient d'un autre cabinet doit échouer :
    cela créerait 32 dents dans la base du cabinet B pour un patient du A.
    """
    ctx_a, ctx_b = deux_cabinets
    patient_id = await _patient_avec_odontogramme(ctx_a)

    reponse = await (await ctx_b.use()).post(
        f"/api/v1/odontogramme/patients/{patient_id}", json={"type": "ADULTE"}
    )

    assert reponse.status_code == 404

    # Aucune dent ne doit avoir été créée du côté du cabinet B.
    from sqlalchemy import func, select

    from src.modules.tenants.models import Odontogramme

    total = int(
        (
            await ctx_b.session.execute(select(func.count(Odontogramme.id)))
        ).scalar_one()
    )
    assert total == 0, "le cabinet B a créé un odontogramme pour un patient du cabinet A"


@pytest.mark.asyncio
async def test_nombre_de_dents_identique_par_cabinet(deux_cabinets):
    """Chaque cabinet gère ses propres odontogrammes : 32 dents chez chacun."""
    ctx_a, ctx_b = deux_cabinets
    patient_a = await _patient_avec_odontogramme(ctx_a)
    patient_b = await _patient_avec_odontogramme(ctx_b)

    a = await (await ctx_a.use()).get(f"/api/v1/odontogramme/patients/{patient_a}")
    b = await (await ctx_b.use()).get(f"/api/v1/odontogramme/patients/{patient_b}")

    assert a.json()["data"]["nb_dents"] == 32
    assert b.json()["data"]["nb_dents"] == 32
