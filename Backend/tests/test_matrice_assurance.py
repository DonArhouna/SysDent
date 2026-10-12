"""Matrice assurance validee : ecriture des organismes et des droits de patient.

La matrice a change, et les deux gestes separes ne peuvent pas l'etre par
hasard. Ces tests existent parce que l'ecart **est** survenu : un
`ASSURANCE:WRITE` unique couvrait a la fois la creation d'un organisme payeur -
un referentiel du cabinet - et la declaration du droit d'un patient.

Un test par couple (role, geste), avec le statut HTTP attendu. Un jeton qui ne
porte **que** le droit cite : un jeton sans droit n'est jamais passe, et ne
prouverait rien.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.modules.tenants.models import DroitPriseEnCharge, OrganismeAssurance

BASE = "/api/v1/tarification"
ANCIEN = "ASSURANCE:WRITE"
NOUVEAU = "ASSURANCE:WRITE_PATIENT"


@asynccontextmanager
async def _avec_permissions(client: AsyncClient, cabinet: dict, permissions: list[str]):
    """
    Emprunte le client avec exactement les permissions citees, puis le rend.

    `client_authenticated` est un objet unique partage par tous les fixtures du
    fichier. Sans restauration, le premier test qui passe en secretaire laisse
    les suivants en secretaire, et les 403 attendus deviennent des 200.
    """
    from src.common.permissions import format_permission

    precedent = client.headers.get("Authorization")
    jeton = create_access_token(
        user_id=str(cabinet["user"].id),
        tenant_id=cabinet["tenant_id"],
        role="PERMISSONS_PRECISES",
        permissions=permissions,
    )
    client.headers.update({"Authorization": f"Bearer {jeton}"})
    try:
        yield client
    finally:
        client.headers.update({"Authorization": precedent})


@pytest.fixture
def cabinet_admin(client_authenticated: AsyncClient, cabinet: dict):
    return cabinet


async def _organisme(client: AsyncClient) -> dict:
    reponse = await client.post(
        f"{BASE}/organismes",
        json={
            "code": f"org-{uuid.uuid4().hex[:8]}",
            "nom": "Organisme fictif",
            "type_organisme": "MUTUELLE",
        },
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]


# ==============================================================================
# 1. Ecriture d'un organisme : TARIFS:WRITE
# ==============================================================================


@pytest.mark.asyncio
async def test_un_administrateur_peut_ecrire_un_organisme(
    client_authenticated: AsyncClient, cabinet_admin: dict
) -> None:
    async with _avec_permissions(
        client_authenticated, cabinet_admin, ["TARIFS:WRITE"]
    ) as client:
        creation = await client.post(
            f"{BASE}/organismes",
            json={"code": "adm-org", "nom": "Assurance fictive", "type_organisme": "ASSURANCE"},
        )
        assert creation.status_code == 201, creation.text

        organisme_id = creation.json()["data"]["id"]
        modification = await client.patch(
            f"{BASE}/organismes/{organisme_id}", json={"nom": "Renommee"}
        )
        assert modification.status_code == 200, modification.text

        desactivation = await client.patch(
            f"{BASE}/organismes/{organisme_id}", json={"actif": False}
        )
        assert desactivation.status_code == 200, desactivation.text
        assert desactivation.json()["data"]["actif"] is False


@pytest.mark.asyncio
async def test_un_secretaire_ne_peut_pas_ecrire_un_organisme(
    client_authenticated: AsyncClient, cabinet_admin: dict
) -> None:
    """Le geste que le secretariat faisait, et qu'il ne doit plus pouvoir faire."""
    async with _avec_permissions(
        client_authenticated,
        cabinet_admin,
        ["ASSURANCE:READ", NOUVEAU],
    ) as client:
        creation = await client.post(
            f"{BASE}/organismes",
            json={"code": "sec-org", "nom": "Mutuelle du secretariat", "type_organisme": "MUTUELLE"},
        )
        assert creation.status_code == 403, creation.text
        assert creation.json()["error"]["code"] == "PERMISSION_DENIED", creation.text

        # Meme un droit supplementaire de lecture ne change rien.
        async with _avec_permissions(
            client_authenticated, cabinet_admin, ["ASSURANCE:READ", NOUVEAU, "TARIFS:READ"]
        ) as autre:
            refus = await autre.post(
                f"{BASE}/organismes",
                json={"code": "sec-org2", "nom": "Autre", "type_organisme": "MUTUELLE"},
            )
            assert refus.status_code == 403, refus.text


@pytest.mark.asyncio
async def test_un_practicien_ne_peut_pas_ecrire_un_organisme(
    client_authenticated: AsyncClient, cabinet_admin: dict
) -> None:
    async with _avec_permissions(client_authenticated, cabinet_admin, ["ASSURANCE:READ"]) as client:
        reponse = await client.post(
            f"{BASE}/organismes",
            json={"code": "pra-org", "nom": "Mutuelle", "type_organisme": "MUTUELLE"},
        )
        assert reponse.status_code == 403, reponse.text


# ==============================================================================
# 2. Ecriture des droits d'un patient : ASSURANCE:WRITE_PATIENT
# ==============================================================================


@pytest.mark.asyncio
async def test_un_secretaire_peut_ecrire_un_droit_de_patient(
    client_authenticated: AsyncClient, cabinet_admin: dict, patient_factory
) -> None:
    """Le geste qu'il conserve : la carte de mutuelle saisie a l'accueil."""
    patient_id = (await patient_factory()).json()["data"]["id"]
    # L'organisme est cree **avant** d'emprunter le client : creer un organisme
    # demande TARIFS:WRITE, que le secretariat n'a pas par construction.
    organisme = await _organisme(client_authenticated)

    async with _avec_permissions(
        client_authenticated, cabinet_admin, ["ASSURANCE:READ", NOUVEAU]
    ) as client:
        reponse = await client.post(
            f"{BASE}/patients/{patient_id}/droits",
            json={
                "organisme_id": organisme["id"],
                "numero_police": "2024-001234",
                "taux_prise_en_charge": "70.00",
                "priorite": 1,
            },
        )
        assert reponse.status_code == 201, reponse.text
        droit_id = reponse.json()["data"]["id"]

        modification = await client.patch(
            f"{BASE}/droits/{droit_id}", json={"taux_prise_en_charge": "80.00"}
        )
        assert modification.status_code == 200, modification.text
        assert modification.json()["data"]["taux_prise_en_charge"] == "80.00"


@pytest.mark.asyncio
async def test_un_practicien_ne_peut_pas_ecrire_un_droit_de_patient(
    client_authenticated: AsyncClient, cabinet_admin: dict, patient_factory
) -> None:
    """Il **lit** - savoir qui couvre quoi avant de soin - mais ne declare pas."""
    patient_id = (await patient_factory()).json()["data"]["id"]
    organisme = await _organisme(client_authenticated)
    async with _avec_permissions(client_authenticated, cabinet_admin, ["ASSURANCE:READ"]) as client:
        lecture = await client.get(f"{BASE}/patients/{patient_id}/droits")
        assert lecture.status_code == 200, lecture.text

        refus = await client.post(
            f"{BASE}/patients/{patient_id}/droits",
            json={
                "organisme_id": organisme["id"],
                "taux_prise_en_charge": "70.00",
                "priorite": 1,
            },
        )
        assert refus.status_code == 403, refus.text


@pytest.mark.asyncio
async def test_tarifs_write_ne_donne_pas_le_droit_sur_un_droit_de_patient(
    client_authenticated: AsyncClient, cabinet_admin: dict, patient_factory
) -> None:
    """
    Les deux droits sont distincts, et dans les deux sens.

    `TARIFS:WRITE` permet d'ecrire un organisme ; il ne doit rien dire d'un
    droit de patient. L'inverse non plus. Sans ce test, le jour ou quelqu'un
    regroupe les deux gestes sous un seul droit, rien ne le signalerait.
    """
    patient_id = (await patient_factory()).json()["data"]["id"]
    async with _avec_permissions(client_authenticated, cabinet_admin, ["TARIFS:WRITE"]) as client:
        organisme = await _organisme(client)
        refus = await client.post(
            f"{BASE}/patients/{patient_id}/droits",
            json={
                "organisme_id": organisme["id"],
                "taux_prise_en_charge": "70.00",
                "priorite": 1,
            },
        )
        assert refus.status_code == 403, refus.text


# ==============================================================================
# 3. L'ancien droit n'existe plus
# ==============================================================================


@pytest.mark.asyncio
async def test_l_ancien_droit_assurance_write_ne_passe_plus(
    client_authenticated: AsyncClient, cabinet_admin: dict, patient_factory
) -> None:
    """
    Un jeton portant l'ancien droit est refuse partout.

    Le droit a ete retire du catalogue : une session delivree avant la
    matrice validee le transporte encore, et elle ne doit pas continuer a
    ecrire. C'est le comportement voulu d'un droit retire, pas une regression.
    """
    patient_id = (await patient_factory()).json()["data"]["id"]
    async with _avec_permissions(client_authenticated, cabinet_admin, [ANCIEN]) as client:
        creation_organisme = await client.post(
            f"{BASE}/organismes",
            json={"code": "ancien", "nom": "Ancien droit", "type_organisme": "MUTUELLE"},
        )
        assert creation_organisme.status_code == 403, creation_organisme.text

        assert (
            await client.post(
                f"{BASE}/patients/{patient_id}/droits",
                json={
                    "organisme_id": str(uuid.uuid4()),
                    "taux_prise_en_charge": "70.00",
                    "priorite": 1,
                },
            )
        ).status_code == 403


def test_l_ancien_droit_a_quitte_le_catalogue() -> None:
    from src.common.permissions import CATALOGUE_PERMISSIONS, format_permission

    codes = {format_permission(m, a) for m, a in CATALOGUE_PERMISSIONS}
    assert ANCIEN not in codes, "l'ancien droit est encore au catalogue"
    assert NOUVEAU in codes, "le nouveau droit manque au catalogue"


def test_la_matrice_attribue_les_deux_droits_au_bon_profil() -> None:
    from src.common.permissions import format_permission, permissions_for_role

    def droits(role: str) -> set[str]:
        return {format_permission(m, a) for m, a in permissions_for_role(role)}

    assert "TARIFS:WRITE" in droits("ADMIN_CABINET")
    assert NOUVEAU in droits("ADMIN_CABINET")

    assert NOUVEAU in droits("SECRETAIRE"), "le secretariat doit conserver la saisie"
    assert "TARIFS:WRITE" not in droits("SECRETAIRE"), "il ne doit pas creer d'organisme"

    for role in ("PRATICIEN", "ASSISTANT", "COMPTABLE", "GESTIONNAIRE_STOCK"):
        assert NOUVEAU not in droits(role), f"{role} ne doit pas ecrire de droit"
        assert "TARIFS:WRITE" not in droits(role), f"{role} ne doit pas ecrire d'organisme"


@pytest.mark.asyncio
async def test_le_secretariat_declenche_bien_son_droit_en_base(
    client_authenticated: AsyncClient,
    cabinet_admin: dict,
    patient_factory,
    tenant_db: AsyncSession,
) -> None:
    """
    Le geste aboutit en base, pas seulement en HTTP.

    Un 201 suivi d'un INSERT confirme la chaine entiere. C'est la seule maniere
    de distinguer « le serveur a accepte » de « le serveur a accepte et ecrit ».
    """
    from sqlalchemy import select

    patient_id = (await patient_factory()).json()["data"]["id"]
    organisme = await _organisme(client_authenticated)
    async with _avec_permissions(
        client_authenticated, cabinet_admin, ["ASSURANCE:READ", NOUVEAU]
    ) as client:
        reponse = await client.post(
            f"{BASE}/patients/{patient_id}/droits",
            json={
                "organisme_id": organisme["id"],
                "numero_police": "POL-1",
                "taux_prise_en_charge": "65.50",
                "priorite": 2,
            },
        )
        assert reponse.status_code == 201, reponse.text
        droit_id = uuid.UUID(reponse.json()["data"]["id"])

    ecrits = (
        await tenant_db.execute(select(DroitPriseEnCharge).where(DroitPriseEnCharge.id == droit_id))
    ).scalars().all()
    assert len(ecrits) == 1, ecrits
    assert ecrits[0].taux_prise_en_charge == Decimal("65.50")
    assert ecrits[0].numero_police == "POL-1"
    assert ecrits[0].priorite == 2

    await tenant_db.execute(
        DroitPriseEnCharge.__table__.delete().where(DroitPriseEnCharge.id == droit_id)
    )
    await tenant_db.execute(
        OrganismeAssurance.__table__.delete().where(OrganismeAssurance.id == uuid.UUID(organisme["id"]))
    )
    await tenant_db.commit()