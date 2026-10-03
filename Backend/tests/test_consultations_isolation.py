"""
Tests d'isolation multi-tenant pour le module Consultations.

Complète `test_patients_isolation.py` : une consultation contient des données
cliniques (diagnostic, CIM-10) et des montants. Le cloisonnement doit être aussi
strict que pour les dossiers patients.

Rappel outillage : `app.dependency_overrides` est global — on réinstalle
l'injection du cabinet concerné avant chacun de ses appels.
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
        Praticien(utilisateur_id=user.id, titre="Dr", specialite="Chirurgien-Dentiste", numero_ordre=f"ORD-{label}")
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
    noms = [f"sysdent_cons_a_{uuid.uuid4().hex[:8]}", f"sysdent_cons_b_{uuid.uuid4().hex[:8]}"]
    admin = create_async_engine(_async_url("postgres"), isolation_level="AUTOCOMMIT")
    for nom in noms:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{nom}"'))
    for nom in noms:
        await asyncio.to_thread(upgrade_tenant_to_head, _sync_url(nom))

    ctx_a = await _creer_ctx("cons-a", noms[0])
    ctx_b = await _creer_ctx("cons-b", noms[1])
    yield ctx_a, ctx_b

    app.dependency_overrides.clear()
    await ctx_a.aclose()
    await ctx_b.aclose()
    await admin.dispose()
    for nom in noms:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))


async def _preparer(ctx: Ctx) -> str:
    """Crée un patient + une consultation terminée avec diagnostic, dans CE cabinet."""
    client = await ctx.use()
    await client.post(
        "/api/v1/nomenclature/actes",
        json={"code": "CONS", "libelle": "Consultation", "categorie": "SOINS", "tarif_base": "15000.00"},
    )
    acte = (await client.get("/api/v1/nomenclature/actes")).json()["items"][0]

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
    patient_id = patient.json()["data"]["id"]

    consultation = await client.post(
        "/api/v1/consultations",
        json={"patient_id": patient_id, "motif": "Douleur", "type_motif": "DOULEUR"},
    )
    consultation_id = consultation.json()["data"]["id"]
    await client.post(
        f"/api/v1/consultations/{consultation_id}/actes", json={"acte_id": acte["id"]}
    )
    await client.post(
        f"/api/v1/consultations/{consultation_id}/terminer",
        json={
            "diagnostic_principal": "Diagnostic confidentiel 26",
            "codes_cim10": ["K02.1"],
        },
    )
    return consultation_id


@pytest.mark.asyncio
async def test_consultation_invisible_dans_lautre_cabinet(deux_cabinets):
    ctx_a, ctx_b = deux_cabinets
    consultation_id = await _preparer(ctx_a)

    liste_b = await (await ctx_b.use()).get("/api/v1/consultations")

    assert liste_b.status_code == 200
    assert liste_b.json()["meta"]["total_records"] == 0


@pytest.mark.asyncio
async def test_acces_direct_par_id_refuse(deux_cabinets):
    ctx_a, ctx_b = deux_cabinets
    consultation_id = await _preparer(ctx_a)

    lecture = await (await ctx_b.use()).get(f"/api/v1/consultations/{consultation_id}")
    assert lecture.status_code == 404
    assert "Diagnostic confidentiel" not in lecture.text, "fuite de donnée clinique"

    detail = await (await ctx_b.use()).get(f"/api/v1/consultations/{consultation_id}/detail")
    assert detail.status_code == 404
    assert "K02.1" not in detail.text

    actes = await (await ctx_b.use()).get(f"/api/v1/consultations/{consultation_id}/actes")
    assert actes.status_code == 404

    total = await (await ctx_b.use()).get(f"/api/v1/consultations/{consultation_id}/total")
    assert total.status_code == 404


@pytest.mark.asyncio
async def test_modification_croisee_refusee(deux_cabinets):
    """Écrire dans la consultation d'un autre cabinet doit être impossible."""
    from sqlalchemy import select

    from src.modules.tenants.models import Consultation

    ctx_a, ctx_b = deux_cabinets
    consultation_id = await _preparer(ctx_a)

    reponse = await (await ctx_b.use()).patch(
        f"/api/v1/consultations/{consultation_id}", json={"plan_traitement": "Détournement"}
    )
    assert reponse.status_code == 404

    await (await ctx_b.use()).post(
        f"/api/v1/consultations/{consultation_id}/annuler", json={"motif_annulation": "Attaque"}
    )

    consultation = (
        await ctx_a.session.execute(select(Consultation).where(Consultation.id == consultation_id))
    ).scalar_one()
    assert consultation.statut == "TERMINEE"
    assert consultation.plan_traitement != "Détournement"


@pytest.mark.asyncio
async def test_ajout_acte_croise_refuse(deux_cabinets):
    """Le montant facturable d'un autre cabinet ne doit pas être modifiable."""
    ctx_a, ctx_b = deux_cabinets
    consultation_id = await _preparer(ctx_a)

    # Le cabinet B crée sa propre nomenclature et tente de l'ajouter sur la
    # consultation du cabinet A.
    client_b = await ctx_b.use()
    await client_b.post(
        "/api/v1/nomenclature/actes",
        json={"code": "CONS", "libelle": "Consultation", "categorie": "SOINS", "tarif_base": "999999.00"},
    )
    acte_b = (await client_b.get("/api/v1/nomenclature/actes")).json()["items"][0]

    reponse = await client_b.post(
        f"/api/v1/consultations/{consultation_id}/actes", json={"acte_id": acte_b["id"]}
    )
    assert reponse.status_code == 404

    total = await (await ctx_b.use()).get(f"/api/v1/consultations/{consultation_id}/total")
    assert total.status_code == 404


@pytest.mark.asyncio
async def test_totaux_facturables_independants(deux_cabinets):
    """Chaque cabinet compte ses propres actes : aucun recoupement possible."""
    ctx_a, ctx_b = deux_cabinets
    consultation_a = await _preparer(ctx_a)

    client_b = await ctx_b.use()
    await client_b.post(
        "/api/v1/nomenclature/actes",
        json={"code": "CONS", "libelle": "Consultation", "categorie": "SOINS", "tarif_base": "15000.00"},
    )
    acte_b = (await client_b.get("/api/v1/nomenclature/actes")).json()["items"][0]
    patient_b = await client_b.post(
        "/api/v1/patients",
        json={
            "prenom": "Autre",
            "nom": "Patient",
            "date_naissance": "1991-02-02",
            "sexe": "M",
            "telephone_1": "779876543",
        },
    )
    consultation_b = await client_b.post(
        "/api/v1/consultations",
        json={
            "patient_id": patient_b.json()["data"]["id"],
            "motif": "Contrôle",
            "type_motif": "CONTROLE",
        },
    )
    consultation_b_id = consultation_b.json()["data"]["id"]
    await client_b.post(f"/api/v1/consultations/{consultation_b_id}/actes", json={"acte_id": acte_b["id"]})

    total_a = await (await ctx_a.use()).get(f"/api/v1/consultations/{consultation_a}/total")
    total_b = await (await ctx_b.use()).get(f"/api/v1/consultations/{consultation_b_id}/total")

    assert total_a.json()["data"]["total_actes"] == "15000.00"
    assert total_b.json()["data"]["total_actes"] == "15000.00"
