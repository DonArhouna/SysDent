"""
Clôture de caisse.

Ce que ces tests verrouillent, et qui n'existait pas avant :

- **un encaissement exige une session ouverte** — sans elle, le rapport journalier
  est faux et rien à l'écran ne le signale ;
- **une seule session ouverte par site** — deux caissiers dans le même tiroir
  produiraient un rapport faux, invérifiable ;
- **les totaux sont figés à la clôture** — un paiement ultérieur ne réécrit pas
  une journée close, sinon le chiffre du mois bouge sans que personne s'en
  aperçoive ;
- **l'écart d'espèces est calculé et conservé**, avec son motif s'il y en a un.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.models import Paiement, SessionCaisse


async def _patient_id(patient_factory) -> str:
    """`patient_factory` renvoie une réponse HTTP, pas un objet patient."""
    reponse = await patient_factory()
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]["id"]


async def _facture(client: AsyncClient, patient_id: str, montant: float) -> str:
    reponse = await client.post(
        "/api/v1/factures",
        json={
            "patient_id": patient_id,
            "lignes": [
                {"designation": "Acte de test clôture", "quantite": 1, "prix_unitaire": montant}
            ],
        },
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]["id"]


async def _encaisser(client: AsyncClient, patient_id: str, montant: float, mode: str) -> None:
    facture = await _facture(client, patient_id, montant)
    reponse = await client.post(
        f"/api/v1/factures/{facture}/paiements",
        json={"montant": montant, "mode": mode},
    )
    assert reponse.status_code == 201, reponse.text


# ==============================================================================
# Session obligatoire
# ==============================================================================


@pytest.mark.asyncio
async def test_encaissement_refuse_sans_session_ouverte(
    client_authenticated, patient_factory
):
    """Sans session, l'argent n'entre nulle part : le refus est explicite."""
    patient_id = await _patient_id(patient_factory)
    facture = await _facture(client_authenticated, patient_id, 10000)

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture}/paiements",
        json={"montant": 10000, "mode": "ESPECES"},
    )

    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["error"]["code"] == "AUCUNE_SESSION_CAISSE"


@pytest.mark.asyncio
async def test_une_seule_session_ouverte_par_site(client_authenticated, cabinet):
    site = str(cabinet["cabinet"].id)
    premiere = await client_authenticated.post(
        "/api/v1/caisse/sessions", json={"cabinet_id": site, "ouverture_especes": "0"}
    )
    assert premiere.status_code == 201, premiere.text

    seconde = await client_authenticated.post(
        "/api/v1/caisse/sessions", json={"cabinet_id": site, "ouverture_especes": "0"}
    )
    assert seconde.status_code == 422, seconde.text
    assert seconde.json()["error"]["code"] == "SESSION_DEJA_OUVERTE"


@pytest.mark.asyncio
async def test_session_courante_vide_puis_ouverte(client_authenticated, cabinet):
    site = str(cabinet["cabinet"].id)
    vide = await client_authenticated.get(
        "/api/v1/caisse/session-courante", params={"cabinet_id": site}
    )
    assert vide.status_code == 200
    assert vide.json()["data"] is None

    await client_authenticated.post(
        "/api/v1/caisse/sessions",
        json={"cabinet_id": site, "ouverture_especes": "2500"},
    )
    ouverte = await client_authenticated.get(
        "/api/v1/caisse/session-courante", params={"cabinet_id": site}
    )
    donnees = ouverte.json()["data"]
    assert donnees["numero"].startswith("Z-")
    assert Decimal(str(donnees["ouverture_especes"])) == Decimal("2500.00")


# ==============================================================================
# Clôture
# ==============================================================================


@pytest.mark.asyncio
async def test_cloture_fige_les_totaux_par_mode(
    client_authenticated, patient_factory, cabinet
):
    """Totaux par mode et écart d'espèces : le cœur de la clôture."""
    patient_id = await _patient_id(patient_factory)

    # Le dépôt est choisi ici, et non laissé à une fixture : l'écart d'espèces
    # est précisément « compté moins (dépôt + encaissements espèces) », il faut
    # donc maîtriser le dépôt pour que l'attestation ait un sens.
    ouverture = await client_authenticated.post(
        "/api/v1/caisse/sessions",
        json={"cabinet_id": str(cabinet["cabinet"].id), "ouverture_especes": "5000"},
    )
    assert ouverture.status_code == 201, ouverture.text
    session = ouverture.json()["data"]

    await _encaisser(client_authenticated, patient_id, 15000, "ESPECES")
    await _encaisser(client_authenticated, patient_id, 8000, "MOBILE_MONEY")

    # 5000 de dépôt + 15000 encaissés en espèces = 20000 attendus au tiroir.
    reponse = await client_authenticated.post(
        f"/api/v1/caisse/sessions/{session['id']}/cloture",
        json={"especes_comptees": "19500", "motif_ecart": "Rendu de monnaie égaré"},
    )
    assert reponse.status_code == 200, reponse.text
    cloturee = reponse.json()["data"]

    assert cloturee["statut"] == "CLOSE"
    assert Decimal(str(cloturee["especes_attendues"])) == Decimal("20000.00")
    assert Decimal(str(cloturee["ecart_especes"])) == Decimal("-500.00")
    assert Decimal(str(cloturee["total_especes"])) == Decimal("15000.00")
    assert Decimal(str(cloturee["total_mobile_money"])) == Decimal("8000.00")
    assert Decimal(str(cloturee["total_encaisse"])) == Decimal("23000.00")
    assert cloturee["nb_paiements"] == 2
    assert cloturee["motif_ecart"] == "Rendu de monnaie égaré"
    # La clôture est signée : on sait qui a constaté.
    assert cloturee["close_par"]


@pytest.mark.asyncio
async def test_recloture_refusee_et_encaissement_bloque(
    client_authenticated, patient_factory, session_caisse
):
    """Une journée close ne se rouvre pas, et l'argent ne rentre plus dedans."""
    patient_id = await _patient_id(patient_factory)
    await _encaisser(client_authenticated, patient_id, 5000, "ESPECES")

    premiere = await client_authenticated.post(
        f"/api/v1/caisse/sessions/{session_caisse['id']}/cloture",
        json={"especes_comptees": "5000"},
    )
    assert premiere.status_code == 200, premiere.text

    recloture = await client_authenticated.post(
        f"/api/v1/caisse/sessions/{session_caisse['id']}/cloture",
        json={"especes_comptees": "5000"},
    )
    assert recloture.status_code == 422, recloture.text
    assert recloture.json()["error"]["code"] == "SESSION_DEJA_CLOSE"

    bloque = await client_authenticated.post(
        f"/api/v1/factures/{await _facture(client_authenticated, patient_id, 7000)}/paiements",
        json={"montant": 7000, "mode": "ESPECES"},
    )
    assert bloque.status_code == 422, bloque.text
    assert bloque.json()["error"]["code"] == "AUCUNE_SESSION_CAISSE"


@pytest.mark.asyncio
async def test_comptage_negatif_refuse(client_authenticated, session_caisse):
    reponse = await client_authenticated.post(
        f"/api/v1/caisse/sessions/{session_caisse['id']}/cloture",
        json={"especes_comptees": "-1"},
    )
    assert reponse.status_code == 422, reponse.text


# ==============================================================================
# Rattachement et traçabilité
# ==============================================================================


@pytest.mark.asyncio
async def test_paiement_rattache_a_la_session(
    client_authenticated, patient_factory, session_caisse, tenant_db: AsyncSession
):
    """Le rattachement au tiroir est ce qui distingue une caisse de reçus empilés."""
    patient_id = await _patient_id(patient_factory)
    facture = await _facture(client_authenticated, patient_id, 4000)
    await client_authenticated.post(
        f"/api/v1/factures/{facture}/paiements",
        json={"montant": 4000, "mode": "ESPECES"},
    )

    paiement = (
        (
            await tenant_db.execute(
                select(Paiement).where(Paiement.facture_id == uuid.UUID(facture))
            )
        )
        .unique()
        .scalar_one()
    )
    assert paiement.session_caisse_id == uuid.UUID(session_caisse["id"])
    # L'email du caissier est figé au moment de l'encaissement : un compte
    # supprimé plus tard n'emporte pas la preuve.
    assert paiement.enregistre_par_email


@pytest.mark.asyncio
async def test_totaux_ne_bougent_pas_apres_cloture(
    client_authenticated, patient_factory, cabinet, session_caisse
):
    """
    Le rapport reste ce qui a été constaté.

    On relit la session après la clôture et après d'autres opérations : les
    totaux figés ne bougent pas, même si l'on encaisse ailleurs.
    """
    patient_id = await _patient_id(patient_factory)
    await _encaisser(client_authenticated, patient_id, 6000, "ESPECES")
    await client_authenticated.post(
        f"/api/v1/caisse/sessions/{session_caisse['id']}/cloture",
        json={"especes_comptees": "6000"},
    )

    # Nouvelle session, nouveau money : la première ne doit pas en bouger.
    site = str(cabinet["cabinet"].id)
    await client_authenticated.post(
        "/api/v1/caisse/sessions", json={"cabinet_id": site, "ouverture_especes": "0"}
    )
    await _encaisser(client_authenticated, patient_id, 9000, "ESPECES")

    relu = await client_authenticated.get(
        "/api/v1/caisse/sessions", params={"cabinet_id": site}
    )
    premiere = next(
        s for s in relu.json()["data"] if s["id"] == session_caisse["id"]
    )
    assert Decimal(str(premiere["total_especes"])) == Decimal("6000.00")
    assert premiere["nb_paiements"] == 1


@pytest.mark.asyncio
async def test_encaissement_assurance_compte_dans_la_cloture(
    client_authenticated, patient_factory, session_caisse
):
    """
    Régression : l'assurance était dans le catalogue mais pas dans les totaux.

    Le rapport de journée annonçait un chiffre inférieur au réel, sans aucun
    signal. Ce test échoue si un mode du catalogue perd sa colonne de total.
    """
    patient_id = await _patient_id(patient_factory)
    await _encaisser(client_authenticated, patient_id, 3000, "ESPECES")
    await _encaisser(client_authenticated, patient_id, 12000, "ASSURANCE")

    reponse = await client_authenticated.post(
        f"/api/v1/caisse/sessions/{session_caisse['id']}/cloture",
        json={"especes_comptees": "3000"},
    )
    assert reponse.status_code == 200, reponse.text
    cloturee = reponse.json()["data"]

    assert Decimal(str(cloturee["total_assurance"])) == Decimal("12000.00")
    # L'assurance entre dans le total encaissé : c'est de l'argent encaissé.
    assert Decimal(str(cloturee["total_encaisse"])) == Decimal("15000.00")
    # ... mais pas dans le tiroir : les espèces attendues restent au dépôt.
    assert Decimal(str(cloturee["especes_attendues"])) == Decimal("3000.00")


@pytest.mark.asyncio
async def test_session_inexistante_refusee(client_authenticated):
    fantome = uuid.uuid4()
    reponse = await client_authenticated.post(
        f"/api/v1/caisse/sessions/{fantome}/cloture", json={"especes_comptees": "0"}
    )
    assert reponse.status_code == 404, reponse.text


# ==============================================================================
# Garde-fou : aucun mode du catalogue ne doit manquer de total
# ==============================================================================


@pytest.mark.asyncio
async def test_tout_mode_de_paiement_a_un_total_de_cloture():
    """
    Un mode sans colonne de total produirait un rapport faux, en silence.

    C'est exactement le défaut trouvé en construisant ce module : `ASSURANCE`
    était dans le catalogue mais absent des colonnes. Ce test échouera dès
    qu'un mode sera ajouté sans que la clôture ne le couvre.
    """
    from src.modules.caisse.services import CaisseService
    from src.modules.tenants.models import ModePaiementEnum

    modes = {m.value for m in ModePaiementEnum}
    couverts = {m.value for m in CaisseService.COLONNES_TOTAL}
    assert modes == couverts, f"modes sans total de clôture : {modes - couverts}"
