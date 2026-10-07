"""
Tests du module Facturation & Caisse (D2C).

Couvre :
  - l'émission depuis une consultation (RG07 : montant recalculé, jamais reçu) ;
  - l'émission libre et le calcul des lignes ;
  - les encaissements partiels et totaux (statut dérivé du montant payé) ;
  - les garde-fous : trop-perçu, facture annulée, annulation avec encaissement ;
  - l'échelonnement (RG08 : échéances générées côté serveur) ;
  - le cycle de vie des devis et la conversion (RG14 : une seule fois) ;
  - le journal de caisse et la traçabilité (RG12) ;
  - le RBAC : `FACTURATION:*` est exigé hors ADMIN_CABINET.
"""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.modules.tenants.models import (
    AuditLogTenant,
    Devis,
    Echeance,
    Facture,
    Paiement,
)


# ==============================================================================
# OUTILS
# ==============================================================================

async def _consultation_terminee_avec_actes(client_authenticated, consultation_factory, nomenclature):
    """
    Crée une consultation TERMINÉE avec deux actes :
      CONS    15 000 FCFA (acte global)
      DETART  7 500 FCFA (acte unitaire, dent 26)
    Total facturable attendu : 22 500 FCFA.
    """
    consultation = await consultation_factory()
    cid = consultation["id"]

    for code in ("CONS", "DETART"):
        entree = nomenclature[code]
        payload = {"acte_id": entree["id"]}
        if entree.get("unitaire"):
            payload["dent_numero"] = 26
        reponse = await client_authenticated.post(f"/api/v1/consultations/{cid}/actes", json=payload)
        assert reponse.status_code == 201, reponse.text

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{cid}/terminer",
        json={"diagnostic_principal": "Carie dentaire 26 (K02.1)"},
    )
    assert reponse.status_code == 200, reponse.text
    return cid, Decimal("22500.00")


async def _facture_depuis_consultation(client_authenticated, consultation_factory, nomenclature):
    cid, total = await _consultation_terminee_avec_actes(
        client_authenticated, consultation_factory, nomenclature
    )
    reponse = await client_authenticated.post(f"/api/v1/factures/consultation/{cid}", json={})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"], total


async def _facture_libre(client_authenticated, patient_factory, montant="100000.00"):
    creation = await patient_factory(nom="Ndiaye", prenom="Fatou", telephone_1="778889991")
    assert creation.status_code == 201, creation.text
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.post(
        "/api/v1/factures",
        json={
            "patient_id": patient_id,
            "lignes": [
                {"designation": "Couronne céramique", "quantite": 1, "prix_unitaire": montant},
            ],
        },
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]


# ==============================================================================
# ÉMISSION DEPUIS UNE CONSULTATION (RG07)
# ==============================================================================

@pytest.mark.asyncio
async def test_facture_depuis_consultation_importe_les_actes(
    client_authenticated, consultation_factory, nomenclature, tenant_db
):
    facture, total = await _facture_depuis_consultation(
        client_authenticated, consultation_factory, nomenclature
    )

    assert facture["numero"].startswith("FAC-")
    assert Decimal(facture["montant_total"]) == total == Decimal("22500.00")
    # RG07 : le reste à payer recopie le total tant que rien n'est encaissé.
    assert Decimal(facture["montant_restant"]) == total
    assert Decimal(facture["montant_paye"]) == Decimal("0.00")
    assert facture["statut"] == "EMISE"
    assert facture["consultation_id"] is not None

    assert len(facture["lignes"]) == 2
    designations = {l["designation"] for l in facture["lignes"]}
    assert "Consultation dentaire" in designations
    assert "Détartrage monodentaire" in designations
    # Le total des lignes doit valoir le total de la facture (aucun écart de centime).
    somme_lignes = sum(Decimal(l["montant"]) for l in facture["lignes"])
    assert somme_lignes == Decimal(facture["montant_total"])

    # Traçabilité (RG12)
    entree = (
        await tenant_db.execute(
            select(AuditLogTenant).where(
                AuditLogTenant.resource_id == facture["id"],
                AuditLogTenant.action == "FACTURE_EMISSION",
            )
        )
    ).scalar_one_or_none()
    assert entree is not None, "l'émission d'une facture doit être journalisée"


@pytest.mark.asyncio
async def test_consultation_non_terminee_refusee(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/factures/consultation/{consultation['id']}", json={}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONSULTATION_NON_TERMINEE"


@pytest.mark.asyncio
async def test_consultation_deja_facturee_refusee(
    client_authenticated, consultation_factory, nomenclature
):
    cid, _ = await _consultation_terminee_avec_actes(
        client_authenticated, consultation_factory, nomenclature
    )
    premiere = await client_authenticated.post(f"/api/v1/factures/consultation/{cid}", json={})
    assert premiere.status_code == 201

    seconde = await client_authenticated.post(f"/api/v1/factures/consultation/{cid}", json={})

    assert seconde.status_code == 422
    assert seconde.json()["error"]["code"] == "CONSULTATION_DEJA_FACTUREE"


@pytest.mark.asyncio
async def test_consultation_sans_actes_refusee(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()
    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/terminer",
        json={"diagnostic_principal": "Contrôle"},
    )
    assert reponse.status_code == 200, reponse.text

    refus = await client_authenticated.post(
        f"/api/v1/factures/consultation/{consultation['id']}", json={}
    )

    assert refus.status_code == 422
    assert refus.json()["error"]["code"] == "CONSULTATION_SANS_ACTES"


# ==============================================================================
# ÉMISSION LIBRE
# ==============================================================================

@pytest.mark.asyncio
async def test_facture_libre_calcule_ses_totaux(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Sow", prenom="Ibrahima", telephone_1="770001112")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.post(
        "/api/v1/factures",
        json={
            "patient_id": patient_id,
            "lignes": [
                {"designation": "Gouttière", "quantite": 2, "prix_unitaire": "30000.00"},
                {"designation": "Radiographie", "quantite": 1, "prix_unitaire": "10000.00"},
            ],
        },
    )

    assert reponse.status_code == 201, reponse.text
    facture = reponse.json()["data"]
    # Le total est CALCULÉ : 2 × 30 000 + 1 × 10 000.
    assert Decimal(facture["montant_total"]) == Decimal("70000.00")
    assert Decimal(facture["montant_restant"]) == Decimal("70000.00")
    assert facture["statut"] == "EMISE"
    assert all(Decimal(l["montant"]) == Decimal(l["quantite"]) * Decimal(l["prix_unitaire"])
               for l in facture["lignes"])


@pytest.mark.asyncio
async def test_facture_libre_refusee_sans_lignes(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Ba", prenom="Ousmane", telephone_1="770001113")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.post(
        "/api/v1/factures", json={"patient_id": patient_id, "lignes": []}
    )

    assert reponse.status_code == 422  # validation Pydantic : min_length=1


# ==============================================================================
# ENCAISSEMENTS
# ==============================================================================

@pytest.mark.asyncio
async def test_encaissement_partiel_passe_en_partiellement_payee(
    client_authenticated, patient_factory, session_caisse
):
    facture = await _facture_libre(client_authenticated, patient_factory)

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "40000.00", "mode": "MOBILE_MONEY", "reference": "WV-789"},
    )

    assert reponse.status_code == 201, reponse.text
    paiement = reponse.json()["data"]
    assert paiement["recu_numero"].startswith("RECU-")
    assert Decimal(paiement["montant"]) == Decimal("40000.00")

    detail = (await client_authenticated.get(f"/api/v1/factures/{facture['id']}")).json()["data"]
    assert detail["statut"] == "PARTIELLEMENT_PAYEE"
    assert Decimal(detail["montant_paye"]) == Decimal("40000.00")
    assert Decimal(detail["montant_restant"]) == Decimal("60000.00")


@pytest.mark.asyncio
async def test_soldage_complet_passe_en_payee(
    client_authenticated, patient_factory, session_caisse
):
    facture = await _facture_libre(client_authenticated, patient_factory)
    await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "30000.00", "mode": "ESPECES"},
    )
    seconde = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "70000.00", "mode": "ESPECES"},
    )
    assert seconde.status_code == 201, seconde.text

    detail = (await client_authenticated.get(f"/api/v1/factures/{facture['id']}")).json()["data"]
    assert detail["statut"] == "PAYEE"
    assert Decimal(detail["montant_restant"]) == Decimal("0.00")
    assert len(detail["paiements"]) == 2


@pytest.mark.asyncio
async def test_trop_percu_refuse(client_authenticated, patient_factory):
    facture = await _facture_libre(client_authenticated, patient_factory)

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "150000.00", "mode": "ESPECES"},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "PAIEMENT_TROP_ELEVE"


@pytest.mark.asyncio
async def test_encaissement_impossible_sur_facture_annulee(client_authenticated, patient_factory):
    facture = await _facture_libre(client_authenticated, patient_factory)
    annulation = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/annuler", params={"motif": "Erreur de saisie"}
    )
    assert annulation.status_code == 200, annulation.text

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "1000.00", "mode": "ESPECES"},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "FACTURE_ANNULEE"


@pytest.mark.asyncio
async def test_annulation_interdite_avec_encaissement(
    client_authenticated, patient_factory, session_caisse
):
    facture = await _facture_libre(client_authenticated, patient_factory)
    await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "10000.00", "mode": "ESPECES"},
    )

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/annuler", params={"motif": "Annulation testée"}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "FACTURE_AVEC_PAIEMENTS"


@pytest.mark.asyncio
async def test_annulation_sans_encaissement_est_trabee(
    client_authenticated, patient_factory, tenant_db
):
    facture = await _facture_libre(client_authenticated, patient_factory)

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/annuler", params={"motif": "Doublon saisi par erreur"}
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["data"]["statut"] == "ANNULEE"

    entree = (
        await tenant_db.execute(
            select(AuditLogTenant).where(
                AuditLogTenant.resource_id == facture["id"],
                AuditLogTenant.action == "FACTURE_ANNULATION",
            )
        )
    ).scalar_one_or_none()
    assert entree is not None
    assert "Doublon" in entree.changes["motif"]


@pytest.mark.asyncio
async def test_paiements_enregistrent_leur_tracabilite(
    client_authenticated, patient_factory, tenant_db, session_caisse
):
    facture = await _facture_libre(client_authenticated, patient_factory)
    encaissement = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "5000.00", "mode": "CHEQUE", "reference": "CHQ-001"},
    )
    paiement_id = encaissement.json()["data"]["id"]

    entree = (
        await tenant_db.execute(
            select(AuditLogTenant).where(
                AuditLogTenant.resource_id == paiement_id,
                AuditLogTenant.action == "PAIEMENT_ENCAISSE",
            )
        )
    ).scalar_one_or_none()
    assert entree is not None, "un encaissement doit être journalisé"
    assert entree.changes["mode"] == "CHEQUE"
    assert entree.changes["recu_numero"].startswith("RECU-")


# ==============================================================================
# ÉCHELONNEMENT (RG08)
# ==============================================================================

@pytest.mark.asyncio
async def test_plan_echelonnement_genere_les_echeances(
    client_authenticated, patient_factory, tenant_db
):
    facture = await _facture_libre(client_authenticated, patient_factory)

    reponse = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/echelonnement",
        json={"nombre_echeances": 3, "date_debut": "2026-10-15", "frequence": "MENSUEL"},
    )

    assert reponse.status_code == 201, reponse.text
    plan = reponse.json()["data"]
    assert plan["nombre_echeances"] == 3
    assert len(plan["echeances"]) == 3

    # La somme des échéances vaut exactement le reste à payer (RG08).
    somme = sum(Decimal(e["montant_prevu"]) for e in plan["echeances"])
    assert somme == Decimal("100000.00")
    assert all(e["statut"] == "A_PAYER" for e in plan["echeances"])

    # Dates mensuelles glissantes.
    dates = [e["date_prevue"] for e in plan["echeances"]]
    assert dates == ["2026-10-15", "2026-11-15", "2026-12-15"]

    # Persistance
    persiste = (
        await tenant_db.execute(select(Echeance).where(Echeance.plan_id == plan["id"]))
    ).scalars().all()
    assert len(persiste) == 3


@pytest.mark.asyncio
async def test_deuxieme_plan_refuse(client_authenticated, patient_factory):
    facture = await _facture_libre(client_authenticated, patient_factory)
    premier = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/echelonnement",
        json={"nombre_echeances": 2, "date_debut": "2026-10-15"},
    )
    assert premier.status_code == 201

    second = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/echelonnement",
        json={"nombre_echeances": 4, "date_debut": "2026-11-01"},
    )

    assert second.status_code == 422
    assert second.json()["error"]["code"] == "PLAN_DEJA_EXISTANT"


@pytest.mark.asyncio
async def test_paiement_dune_echeance_exact(
    client_authenticated, patient_factory, session_caisse
):
    facture = await _facture_libre(client_authenticated, patient_factory)
    plan = (
        await client_authenticated.post(
            f"/api/v1/factures/{facture['id']}/echelonnement",
            json={"nombre_echeances": 2, "date_debut": "2026-10-15"},
        )
    ).json()["data"]
    premiere = plan["echeances"][0]
    montant_attendu = str(Decimal(premiere["montant_prevu"]))

    # Montant faux d'abord : la caisse ne fait pas d'allocation approximative.
    refus = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "10000.00", "mode": "ESPECES", "echeance_id": premiere["id"]},
    )
    assert refus.status_code == 422
    assert refus.json()["error"]["code"] == "ECHEANCE_MONTANT_INCOHERENT"

    # Montant exact ensuite.
    encaissement = await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": montant_attendu, "mode": "MOBILE_MONEY", "echeance_id": premiere["id"]},
    )
    assert encaissement.status_code == 201, encaissement.text

    detail = (await client_authenticated.get(f"/api/v1/factures/{facture['id']}")).json()["data"]
    assert detail["statut"] == "PARTIELLEMENT_PAYEE"
    plan_lu = (
        await client_authenticated.get(f"/api/v1/factures/{facture['id']}/echelonnement")
    ).json()["data"]
    statuts = {e["numero"]: e["statut"] for e in plan_lu["echeances"]}
    assert statuts[1] == "PAYEE"
    assert statuts[2] == "A_PAYER"


# ==============================================================================
# JOURNAL DE CAISSE
# ==============================================================================

@pytest.mark.asyncio
async def test_journal_caisse_liste_les_encaissements(
    client_authenticated, patient_factory, session_caisse
):
    facture = await _facture_libre(client_authenticated, patient_factory)
    await client_authenticated.post(
        f"/api/v1/factures/{facture['id']}/paiements",
        json={"montant": "25000.00", "mode": "ESPECES"},
    )

    reponse = await client_authenticated.get("/api/v1/factures/journal-caisse")

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["meta"]["total_records"] >= 1
    entree = corps["items"][0]
    assert entree["recu_numero"].startswith("RECU-")
    assert entree["facture_numero"] == facture["numero"]
    assert entree["patient"] == "Fatou Ndiaye"
    assert entree["mode"] == "ESPECES"


# ==============================================================================
# DEVIS (RG14)
# ==============================================================================

async def _devis_client(client_authenticated, patient_factory, montant="80000.00"):
    creation = await patient_factory(nom="Diallo", prenom="Mariama", telephone_1="776665554")
    patient_id = creation.json()["data"]["id"]
    reponse = await client_authenticated.post(
        "/api/v1/devis",
        json={
            "patient_id": patient_id,
            "lignes": [{"designation": "Implant", "quantite": 1, "prix_unitaire": montant}],
        },
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]


@pytest.mark.asyncio
async def test_devis_cycle_de_vie_complet(client_authenticated, patient_factory, tenant_db):
    devis = await _devis_client(client_authenticated, patient_factory)
    assert devis["statut"] == "BROUILLON"
    assert devis["numero"].startswith("DEV-")

    envoye = await client_authenticated.post(
        f"/api/v1/devis/{devis['id']}/statut", json={"statut": "ENVOYE"}
    )
    assert envoye.status_code == 200, envoye.text

    # ACCEPTE sans signature : refusé.
    sans_signature = await client_authenticated.post(
        f"/api/v1/devis/{devis['id']}/statut", json={"statut": "ACCEPTE"}
    )
    assert sans_signature.status_code == 422
    assert sans_signature.json()["error"]["code"] == "SIGNATURE_PATIENT_REQUISE"

    accepte = await client_authenticated.post(
        f"/api/v1/devis/{devis['id']}/statut",
        json={"statut": "ACCEPTE", "signature_patient": True},
    )
    assert accepte.status_code == 200, accepte.text
    assert accepte.json()["data"]["signature_patient"] is True

    # Conversion (RG14)
    conversion = await client_authenticated.post(f"/api/v1/devis/{devis['id']}/convertir")
    assert conversion.status_code == 201, conversion.text
    facture = conversion.json()["data"]
    assert Decimal(facture["montant_total"]) == Decimal("80000.00")
    assert len(facture["lignes"]) == 1

    # Seconde conversion : refusée (le même soin ne se facture pas deux fois).
    seconde = await client_authenticated.post(f"/api/v1/devis/{devis['id']}/convertir")
    assert seconde.status_code == 422
    assert seconde.json()["error"]["code"] == "DEVIS_DEJA_CONVERTI"

    # Lien permanent devis -> facture.
    en_base = (
        await tenant_db.execute(select(Devis).where(Devis.id == devis["id"]))
    ).scalar_one()
    assert str(en_base.facture_id) == facture["id"]


@pytest.mark.asyncio
async def test_devis_refuse_ne_convertit_pas(client_authenticated, patient_factory):
    devis = await _devis_client(client_authenticated, patient_factory)
    await client_authenticated.post(f"/api/v1/devis/{devis['id']}/statut", json={"statut": "ENVOYE"})
    refuse = await client_authenticated.post(
        f"/api/v1/devis/{devis['id']}/statut", json={"statut": "REFUSE"}
    )
    assert refuse.status_code == 200

    conversion = await client_authenticated.post(f"/api/v1/devis/{devis['id']}/convertir")

    assert conversion.status_code == 422
    assert conversion.json()["error"]["code"] == "DEVIS_NON_ACCEPTE"


@pytest.mark.asyncio
async def test_transition_devis_interdite(client_authenticated, patient_factory):
    devis = await _devis_client(client_authenticated, patient_factory)

    # BROUILLON ne va pas directement à REFUSE (cycle fermé).
    reponse = await client_authenticated.post(
        f"/api/v1/devis/{devis['id']}/statut", json={"statut": "REFUSE"}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "DEVIS_TRANSITION_INVALIDE"


# ==============================================================================
# RBAC
# ==============================================================================

@pytest.mark.asyncio
async def test_facturation_exige_permission(tenant_db, cabinet):
    """Hors ADMIN_CABINET, une requête sans `FACTURATION:READ` dans le JWT doit être refusée."""
    from src.core.security import create_access_token
    from src.main import app
    from src.modules.auth import dependencies as auth_deps
    from src.modules.tenants.models import Utilisateur

    token = create_access_token(
        user_id=str(cabinet["user"].id),
        tenant_id=cabinet["tenant_id"],
        role="SECRETAIRE",
        permissions=[],  # aucun droit accordé : même la lecture est refusée
    )
    utilisateur = Utilisateur(
        id=cabinet["user"].id,
        email=cabinet["user"].email,
        prenom=cabinet["user"].prenom,
        nom=cabinet["user"].nom,
        role_id=cabinet["user"].role_id,
        actif=True,
    )

    async def _override_db():
        try:
            yield tenant_db
            await tenant_db.commit()
        except Exception:
            await tenant_db.rollback()
            raise

    async def _override_user():
        return utilisateur

    app.dependency_overrides[auth_deps.get_tenant_db] = _override_db
    app.dependency_overrides[auth_deps.get_current_user] = _override_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.headers.update({"Authorization": f"Bearer {token}"})
            reponse = await ac.get("/api/v1/factures")
    finally:
        app.dependency_overrides.clear()

    assert reponse.status_code == 403
    assert reponse.json()["error"]["code"] == "PERMISSION_DENIED"
