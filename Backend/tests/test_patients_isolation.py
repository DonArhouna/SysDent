"""
Tests d'isolation multi-tenant (contrainte structurante de SysDent).

Un cabinet ne doit jamais voir, ni même deviner l'existence, d'un dossier patient
appartenant à un autre cabinet. Ces tests créent deux bases tenant distinctes et
vérifient que les identifiants et les numéros de dossier ne se croisent pas.

Note sur l'outillage : `app.dependency_overrides` est un dictionnaire GLOBAL.
Deux clients ne peuvent donc pas garder leurs injections en place simultanément —
la dernière écrase la première. On réinstalle l'injection du cabinet concerné
juste avant chacun de ses appels (`Ctx.use()`), ce qui est correct puisque les
appels sont séquentiels.
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
from src.modules.tenants.models import Cabinet, Patient, Role, Utilisateur
from tests.conftest import _async_url, _sync_url


class Ctx:
    """Un cabinet : sa session base de données et son client HTTP."""

    def __init__(self, label: str, session: AsyncSession, user: Utilisateur):
        self.label = label
        self.session = session
        self.user = user
        self.tenant_id = str(uuid.uuid4())
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def use(self) -> AsyncClient:
        """Installe l'injection de session de CE cabinet et renvoie son client."""
        session = self.session
        user = self.user

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
    await session.commit()

    ctx = Ctx(label, session, user)
    token = create_access_token(
        user_id=str(user.id), tenant_id=ctx.tenant_id, role="ADMIN_CABINET", permissions=[]
    )
    ctx.client.headers.update({"Authorization": f"Bearer {token}"})
    return ctx


@pytest_asyncio.fixture
async def deux_cabinets():
    """Deux bases tenant jetables, chacune avec son administrateur."""
    noms = [f"sysdent_iso_a_{uuid.uuid4().hex[:8]}", f"sysdent_iso_b_{uuid.uuid4().hex[:8]}"]

    admin = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    for nom in noms:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{nom}"'))

    for nom in noms:
        await asyncio.to_thread(upgrade_tenant_to_head, _sync_url(nom))

    ctx_a = await _creer_ctx("cabinet-a", noms[0])
    ctx_b = await _creer_ctx("cabinet-b", noms[1])

    yield ctx_a, ctx_b

    app.dependency_overrides.clear()
    await ctx_a.aclose()
    await ctx_b.aclose()
    await admin.dispose()
    for nom in noms:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))


NOUVEAU_PATIENT = {
    "prenom": "Secret",
    "nom": "Confidentiel",
    "date_naissance": "1975-03-03",
    "sexe": "M",
    "telephone_1": "778888888",
}


@pytest.mark.asyncio
async def test_patient_cree_dans_un_cabinet_invisible_dans_lautre(deux_cabinets):
    ctx_a, ctx_b = deux_cabinets

    creation = await (await ctx_a.use()).post("/api/v1/patients", json=NOUVEAU_PATIENT)
    assert creation.status_code == 201, creation.text

    liste_b = await (await ctx_b.use()).get("/api/v1/patients")
    assert liste_b.status_code == 200
    assert liste_b.json()["meta"]["total_records"] == 0, "le cabinet B voit un patient du cabinet A"


@pytest.mark.asyncio
async def test_acces_direct_par_id_refuse_dans_lautre_cabinet(deux_cabinets):
    """
    Le cas le plus critique : deviner un UUID. Un praticien du cabinet B qui
    soumet l'ID d'un patient du cabinet A doit obtenir un 404, pas les données.
    """
    ctx_a, ctx_b = deux_cabinets

    creation = await (await ctx_a.use()).post("/api/v1/patients", json=NOUVEAU_PATIENT)
    patient_id = creation.json()["data"]["id"]

    lecture = await (await ctx_b.use()).get(f"/api/v1/patients/{patient_id}")
    assert lecture.status_code == 404, f"le cabinet B a pu lire le dossier: {lecture.text}"
    assert lecture.json()["error"]["code"] == "PATIENT_NOT_FOUND"

    dossier = await (await ctx_b.use()).get(f"/api/v1/patients/{patient_id}/dossier")
    assert dossier.status_code == 404


@pytest.mark.asyncio
async def test_modification_croisee_refusee(deux_cabinets):
    """Écrire dans le dossier d'un autre cabinet doit être impossible."""
    ctx_a, ctx_b = deux_cabinets

    creation = await (await ctx_a.use()).post("/api/v1/patients", json=NOUVEAU_PATIENT)
    patient_id = creation.json()["data"]["id"]

    reponse = await (await ctx_b.use()).patch(
        f"/api/v1/patients/{patient_id}", json={"nom": "Detournement"}
    )
    assert reponse.status_code == 404

    # Vérification côté base du propriétaire : la donnée n'a pas bougé.
    from sqlalchemy import select

    patient = (
        await ctx_a.session.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one()
    assert patient.nom == "Confidentiel", "le nom a été modifié depuis un autre cabinet"


@pytest.mark.asyncio
async def test_archivage_croise_refuse(deux_cabinets):
    """Archiver le dossier d'un autre cabinet doit échouer aussi."""
    ctx_a, ctx_b = deux_cabinets

    creation = await (await ctx_a.use()).post("/api/v1/patients", json=NOUVEAU_PATIENT)
    patient_id = creation.json()["data"]["id"]

    reponse = await (await ctx_b.use()).post(
        f"/api/v1/patients/{patient_id}/archiver", json={"motif": "Attaque"}
    )
    assert reponse.status_code == 404

    from sqlalchemy import select

    patient = (
        await ctx_a.session.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one()
    assert patient.archive is False, "le dossier a été archivé depuis un autre cabinet"


@pytest.mark.asyncio
async def test_numerotation_independante_par_cabinet(deux_cabinets):
    """
    Chaque cabinet a sa propre base : les compteurs sont donc indépendants.
    Deux cabinets peuvent tous deux avoir un PAT-2026-000001 sans collision,
    puisque le numéro n'a de sens qu'à l'intérieur d'un cabinet.
    """
    ctx_a, ctx_b = deux_cabinets

    creation_a = await (await ctx_a.use()).post("/api/v1/patients", json=NOUVEAU_PATIENT)
    creation_b = await (await ctx_b.use()).post(
        "/api/v1/patients",
        json={
            "prenom": "Autre",
            "nom": "Cabinet",
            "date_naissance": "1992-02-02",
            "sexe": "F",
            "telephone_1": "772222222",
        },
    )

    numero_a = creation_a.json()["data"]["numero_dossier"]
    numero_b = creation_b.json()["data"]["numero_dossier"]

    assert numero_a.endswith("-000001")
    assert numero_b.endswith("-000001"), "chaque cabinet doit démarrer son propre compteur"

    # Et les identifiants techniques ne doivent pas se confondre.
    assert creation_a.json()["data"]["id"] != creation_b.json()["data"]["id"]
