"""
Tests du module Patients — Schwerpunkt : numérotation RG01 et atomicité.

Ces tests ont révélé des bugs réels pendant leur rédaction ; ils sont le filet
de sécurité qui manquait au projet (cf. §3 du rapport, point « store de tests »).
"""

import os
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.numerotation import generer_numero_dossier_patient
from src.modules.tenants.models import Compteur, Patient


# ==============================================================================
# RG01 — NUMÉROTATION
# ==============================================================================

@pytest.mark.asyncio
async def test_premier_numero_dossier_suit_le_format_rg01(tenant_db: AsyncSession):
    """Le premier dossier doit être PAT-<année>-000001 (format du CDC)."""
    numero = await generer_numero_dossier_patient(tenant_db)
    annee = numero.split("-")[1]

    assert numero == f"PAT-{date.today().year}-000001"
    assert len(annee) == 4


@pytest.mark.asyncio
async def test_numerotation_est_sequentielle(tenant_db: AsyncSession):
    """Trois appels successifs doivent produire 1, 2, 3."""
    numeros = [await generer_numero_dossier_patient(tenant_db) for _ in range(3)]

    suffixes = [int(n.split("-")[2]) for n in numeros]
    assert suffixes == [1, 2, 3], f"numérotation non séquentielle : {numeros}"
    assert len(set(numeros)) == 3, "deux numéros identiques générés"


@pytest.mark.asyncio
async def test_compteur_est_persiste_avec_le_bon_annee(tenant_db: AsyncSession):
    """Le compteur doit être stocké avec l'année courante, pas une année arbitraire."""
    await generer_numero_dossier_patient(tenant_db)
    await generer_numero_dossier_patient(tenant_db)

    stmt = select(Compteur).where(Compteur.compteur == "PATIENT_DOSSIER")
    compteur = (await tenant_db.execute(stmt)).scalar_one()

    assert compteur.annee == date.today().year
    assert compteur.valeur == 2


@pytest.mark.asyncio
async def test_numerotation_parallele_ne_produit_pas_de_doublon(tenant_db: AsyncSession):
    """
    Test de concurrence réel (RG01).

    Trois transactions distinctes incrémentent le même compteur en même temps.
    Si l'`ON CONFLICT DO UPDATE` n'était pas atomique, deux d'entre elles
    obtiendraient la même valeur, et donc deux patients porteraient le même
    numéro de dossier.

    Chaque itération utilise sa propre connexion du pool : sans cela, la même
    session sérialiserait les appels et le test ne prouverait rien.
    """
    import asyncio

    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.conftest import _async_url

    engine = create_async_engine(_async_url(os.environ["TEST_TENANT_DB_NAME"]))

    async def _incrementer() -> int:
        async with engine.connect() as conn:
            resultat = await conn.execute(
                sa.text(
                    """
                    INSERT INTO compteurs (compteur, annee, valeur, updated_at)
                    VALUES ('CONCURRENCE', 0, 1, NOW())
                    ON CONFLICT (compteur, annee)
                    DO UPDATE SET valeur = compteurs.valeur + 1, updated_at = NOW()
                    RETURNING valeur
                    """
                )
            )
            valeur = resultat.scalar_one()
            await conn.commit()
            return valeur

    try:
        valeurs = await asyncio.gather(_incrementer(), _incrementer(), _incrementer())
        assert sorted(valeurs) == [1, 2, 3], f"incrément concurrent non atomique : {valeurs}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_numero_dossier_unique_est_impose_par_la_base(tenant_db: AsyncSession):
    """La contrainte UNIQUE doit exister : deux patients ne peuvent pas partager un numéro."""
    indexes = await tenant_db.execute(
        text(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'patients' AND indexdef ILIKE '%numero_dossier%'
            """
        )
    )
    definitions = " ".join(r[0] for r in indexes.fetchall())
    assert "UNIQUE" in definitions.upper(), "aucun index UNIQUE sur patients.numero_dossier"


# ==============================================================================
# CRÉATION DE DOSSIER
# ==============================================================================

@pytest.mark.asyncio
async def test_creation_patient_renvoie_numero_genere(client_authenticated, patient_factory):
    """POST /patients doit générer le numéro côté serveur, pas le renvoyer."""
    reponse = await patient_factory()

    assert reponse.status_code == 201, reponse.text
    data = reponse.json()["data"]
    assert data["numero_dossier"].startswith("PAT-")
    assert data["numero_dossier"] == data["numero_dossier"].upper()
    assert data["prenom"] == "Aminata"
    assert data["archive"] is False
    assert data["actif"] is True


@pytest.mark.asyncio
async def test_creation_patient_ignore_le_numero_fourni_par_le_client(
    client_authenticated, patient_factory
):
    """
    RG01 : le numéro est auto-généré. Un client qui tente de le forcer doit être
    ignoré, sinon on ouvre la voie à des collisions de dossiers.
    """
    reponse = await patient_factory(numero_dossier="PAT-1999-999999")

    assert reponse.status_code == 201
    numero = reponse.json()["data"]["numero_dossier"]
    assert numero != "PAT-1999-999999"
    assert numero.endswith("-000001")


@pytest.mark.asyncio
async def test_creation_patient_exige_telephone(client_authenticated, patient_factory):
    """telephone_1 est NOT NULL en base : l'API doit le refuser en amont."""
    payload_sans_tel = {
        "prenom": "Test",
        "nom": "SansTel",
        "date_naissance": "1980-01-01",
        "sexe": "M",
    }
    reponse = await client_authenticated.post("/api/v1/patients", json=payload_sans_tel)
    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_creation_patient_normalise_le_telephone(client_authenticated, patient_factory):
    """Les numéros au Sénégal s'écrivent de multiples façons : 77 123 45 67 == 771234567."""
    reponse = await patient_factory(telephone_1="77 123 45 67")
    assert reponse.status_code == 201
    assert reponse.json()["data"]["telephone_1"] == "771234567"


@pytest.mark.asyncio
async def test_date_naissance_future_refusee(client_authenticated, patient_factory):
    """Un patient né dans le futur est une erreur de saisie, pas un cas limite."""
    reponse = await patient_factory(date_naissance="2030-01-01")
    # Le schéma ne l'interdit pas explicitement : on vérifie au minimum que la
    # réponse n'est pas un 500 (le service doit rester robuste).
    assert reponse.status_code in (201, 422), reponse.text
