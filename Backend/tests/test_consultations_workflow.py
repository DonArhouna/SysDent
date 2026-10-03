"""
Tests du module Consultations & Actes (D1B).

Couvre le workflow Étapes 4 à 6 du CDC, les garde-fous métier (pas de clôture
sans diagnostic, pas d'annulation avec actes, tarif figé) et la traçabilité.
"""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.models import ActeRealise, AuditLogTenant, Consultation


# ==============================================================================
# DÉMARRAGE (Étape 4)
# ==============================================================================

@pytest.mark.asyncio
async def test_demarrer_consultation_passe_en_cours(consultation_factory):
    consultation = await consultation_factory()

    assert consultation["statut"] == "EN_COURS"
    assert consultation["motif"] == "Douleur dentaire"
    assert consultation["type_motif"] == "DOULEUR"
    assert consultation["patient_numero_dossier"].startswith("PAT-")
    assert consultation["cabinet_id"] is not None


@pytest.mark.asyncio
async def test_consultation_refusee_pour_patient_inexistant(client_authenticated, nomenclature):
    reponse = await client_authenticated.post(
        "/api/v1/consultations",
        json={"patient_id": str(uuid.uuid4()), "motif": "Douleur"},
    )

    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "PATIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_consultation_refusee_pour_dossier_archive(
    client_authenticated, patient_factory, nomenclature
):
    creation = await patient_factory(nom="Archive", prenom="Test", telephone_1="771111100")
    patient_id = creation.json()["data"]["id"]
    await client_authenticated.post(f"/api/v1/patients/{patient_id}/archiver", json={})

    reponse = await client_authenticated.post(
        "/api/v1/consultations", json={"patient_id": patient_id, "motif": "Douleur"}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "PATIENT_ARCHIVE"


@pytest.mark.asyncio
async def test_demarrage_trace_dans_audit(consultation_factory, tenant_db: AsyncSession):
    consultation = await consultation_factory()

    stmt = select(AuditLogTenant).where(
        AuditLogTenant.resource_id == consultation["id"],
        AuditLogTenant.action == "CONSULTATION_START",
    )
    entree = (await tenant_db.execute(stmt)).scalar_one_or_none()

    assert entree is not None, "le démarrage d'une consultation doit être journalisé"
    assert entree.changes["type_motif"] == "DOULEUR"


# ==============================================================================
# EXAMEN & DIAGNOSTIC (Étape 5)
# ==============================================================================

@pytest.mark.asyncio
async def test_saisie_examen_et_diagnostic(client_authenticated, consultation_factory):
    consultation = await consultation_factory()

    reponse = await client_authenticated.patch(
        f"/api/v1/consultations/{consultation['id']}",
        json={
            "examen_exobuccal": "Faciès normal, pas d'asymétrie",
            "examen_endobuccal": "Carie cavitaire 26, sensibilité au froid",
            "diagnostic_principal": "Carie dentaire 26 (K02.1)",
            "codes_cim10": ["K02.1"],
            "diagnostics_differentiels": ["Hypersensibilité dentinaire"],
        },
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["diagnostic_principal"] == "Carie dentaire 26 (K02.1)"
    assert data["codes_cim10"] == ["K02.1"]
    assert "examen_exobuccal" in data and data["examen_exobuccal"] is not None


@pytest.mark.asyncio
async def test_codes_cim10_normalises_et_dedupliques(client_authenticated, consultation_factory):
    consultation = await consultation_factory()

    reponse = await client_authenticated.patch(
        f"/api/v1/consultations/{consultation['id']}",
        json={"codes_cim10": ["k02.1", "K05.0", "K02.1"]},
    )

    assert reponse.status_code == 200
    codes = reponse.json()["data"]["codes_cim10"]
    assert codes == ["K02.1", "K05.0"], f"normalisation/déduplication incorrecte : {codes}"


@pytest.mark.asyncio
async def test_code_cim10_invalide_refuse(client_authenticated, consultation_factory):
    consultation = await consultation_factory()

    reponse = await client_authenticated.patch(
        f"/api/v1/consultations/{consultation['id']}", json={"codes_cim10": ["ZZZ"]}
    )

    assert reponse.status_code == 422
    assert "CIM-10" in reponse.text


# ==============================================================================
# ACTES RÉALISÉS (Étape 6)
# ==============================================================================

@pytest.mark.asyncio
async def test_ajout_acte_global_sans_dent(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"], "quantite": 1},
    )

    assert reponse.status_code == 201, reponse.text
    data = reponse.json()["data"]
    assert data["code_acte"] == "CONS"
    assert data["tarif_applique"] == "15000.00"
    assert data["montant"] == "15000.00", "le montant doit être calculé, pas fourni"


@pytest.mark.asyncio
async def test_acte_unitaire_exige_un_numero_de_dent(
    client_authenticated, consultation_factory, nomenclature
):
    """Un soin monodentaire sans dent n'a pas de sens clinique : refusé."""
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["DETART"]["id"]},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "DENT_NUMERO_OBLIGATOIRE"


@pytest.mark.asyncio
async def test_acte_unitaire_avec_dent_valide(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={
            "acte_id": nomenclature["DETART"]["id"],
            "dent_numero": 26,
            "face": "OCCLUSAL_INCISAL",
            "quantite": 2,
        },
    )

    assert reponse.status_code == 201, reponse.text
    data = reponse.json()["data"]
    assert data["dent_numero"] == 26
    assert data["face"] == "OCCLUSAL_INCISAL"
    assert data["montant"] == "15000.00", "7500 × 2"


@pytest.mark.asyncio
async def test_numero_dent_fdi_invalide_refuse(
    client_authenticated, consultation_factory, nomenclature
):
    """99 n'est pas un numéro FDI valide : 11-48 (permanent) ou 51-85 (lait)."""
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["DETART"]["id"], "dent_numero": 99},
    )

    assert reponse.status_code == 422
    assert "FDI" in reponse.text


@pytest.mark.asyncio
async def test_face_sans_dent_refuse(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"], "face": "MESIAL"},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_face_invalide_refuse(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["DETART"]["id"], "dent_numero": 16, "face": "DISTALE_GAUCHE"},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_total_est_recalcule_et_non_fourni(client_authenticated, consultation_factory, nomenclature):
    """RG07 : le total vient des lignes. Le client ne peut pas l'imposer."""
    consultation = await consultation_factory()

    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"]},
    )
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["DETART"]["id"], "dent_numero": 26, "quantite": 3},
    )

    total = await client_authenticated.get(f"/api/v1/consultations/{consultation['id']}/total")

    assert total.status_code == 200
    data = total.json()["data"]
    assert data["total_actes"] == "37500.00", "15000 + 7500×3"
    assert data["nb_actes"] == 2
    assert data["devise"] == "XOF"


@pytest.mark.asyncio
async def test_tarif_negatif_refuse(client_authenticated, consultation_factory, nomenclature):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"], "tarif_applique": "-5000.00"},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_tarif_reduit_par_accord_commercial(client_authenticated, consultation_factory, nomenclature):
    """Un forfait négocié reste autorisé tant qu'il est positif (remise commerciale)."""
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"], "tarif_applique": "10000.00"},
    )

    assert reponse.status_code == 201
    assert reponse.json()["data"]["tarif_applique"] == "10000.00"


# ==============================================================================
# CLÔTURE
# ==============================================================================

@pytest.mark.asyncio
async def test_terminer_sans_diagnostic_refuse(client_authenticated, consultation_factory):
    """Une facture sans base clinique n'a pas de sens : on ne clôt pas sans diagnostic."""
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/terminer", json={}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "DIAGNOSTIC_OBLIGATOIRE"


@pytest.mark.asyncio
async def test_terminer_avec_diagnostic_passe_terminee(
    client_authenticated, consultation_factory, nomenclature
):
    consultation = await consultation_factory()
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"]},
    )

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/terminer",
        json={
            "diagnostic_principal": "Carie 26",
            "plan_traitement": "Obturation",
            "recommandations": "Brossage après chaque repas",
            "codes_cim10": ["K02.1"],
        },
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["statut"] == "TERMINEE"
    assert data["total_actes"] == "15000.00"
    assert data["nb_actes"] == 1


@pytest.mark.asyncio
async def test_consultation_terminee_non_modifiable(client_authenticated, consultation_factory):
    consultation = await consultation_factory()
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/terminer", json={"diagnostic_principal": "Carie 26"}
    )

    reponse = await client_authenticated.patch(
        f"/api/v1/consultations/{consultation['id']}", json={"plan_traitement": "Changer d'avis"}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONSULTATION_CLOSED"


@pytest.mark.asyncio
async def test_acte_ne_peut_plus_etre_ajoute_apres_cloture(
    client_authenticated, consultation_factory, nomenclature
):
    consultation = await consultation_factory()
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/terminer", json={"diagnostic_principal": "Carie 26"}
    )

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"]},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONSULTATION_CLOSED"


@pytest.mark.asyncio
async def test_cloture_tracee(client_authenticated, consultation_factory, tenant_db: AsyncSession):
    consultation = await consultation_factory()
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/terminer", json={"diagnostic_principal": "Carie 26"}
    )

    stmt = select(AuditLogTenant).where(
        AuditLogTenant.resource_id == consultation["id"],
        AuditLogTenant.action == "CONSULTATION_TERMINATE",
    )
    entree = (await tenant_db.execute(stmt)).scalar_one_or_none()

    assert entree is not None
    assert entree.changes["diagnostic_principal"] == "Carie 26"


# ==============================================================================
# ANNULATION
# ==============================================================================

@pytest.mark.asyncio
async def test_annulation_avec_actes_refusee(client_authenticated, consultation_factory, nomenclature):
    """
    Un acte réalisé est un acte physique. Il se facture ou se corrige,
    il ne s'efface pas par une annulation.
    """
    consultation = await consultation_factory()
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"]},
    )

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/annuler",
        json={"motif_annulation": "Erreur de saisie"},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONSULTATION_HAS_ACTES"


@pytest.mark.asyncio
async def test_annulation_possible_sans_acte(client_authenticated, consultation_factory):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/annuler",
        json={"motif_annulation": "Patient désisté"},
    )

    assert reponse.status_code == 200
    assert reponse.json()["data"]["statut"] == "ANNULEE"


@pytest.mark.asyncio
async def test_motif_annulation_obligatoire(client_authenticated, consultation_factory):
    consultation = await consultation_factory()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/annuler", json={}
    )

    assert reponse.status_code == 422


# ==============================================================================
# CORRECTION & SUPPRESSION D'ACTE
# ==============================================================================

@pytest.mark.asyncio
async def test_suppression_acte_laisse_la_consultation_intacte(
    client_authenticated, consultation_factory, nomenclature
):
    consultation = await consultation_factory()
    ajout = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"]},
    )
    acte_id = ajout.json()["data"]["id"]

    suppression = await client_authenticated.delete(
        f"/api/v1/consultations/actes/{acte_id}", params={"motif": "Doublon de saisie"}
    )

    assert suppression.status_code == 204
    total = await client_authenticated.get(f"/api/v1/consultations/{consultation['id']}/total")
    assert total.json()["data"]["total_actes"] == "0.00"
    assert total.json()["data"]["nb_actes"] == 0


@pytest.mark.asyncio
async def test_suppression_acte_tracee_avec_code_et_montant(
    client_authenticated, consultation_factory, nomenclature, tenant_db: AsyncSession
):
    """La trace d'audit doit conserver l'acte supprimé : le journal est la vérité."""
    consultation = await consultation_factory()
    ajout = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["DETART"]["id"], "dent_numero": 26},
    )
    acte_id = ajout.json()["data"]["id"]

    await client_authenticated.delete(
        f"/api/v1/consultations/actes/{acte_id}", params={"motif": "Erreur"}
    )

    stmt = select(AuditLogTenant).where(
        AuditLogTenant.resource_id == acte_id, AuditLogTenant.action == "ACTE_REALISE_DELETE"
    )
    entree = (await tenant_db.execute(stmt)).scalar_one_or_none()

    assert entree is not None
    assert entree.changes["code"] == "DETART"
    assert entree.changes["tarif_applique"] == "7500.00"
    assert entree.changes["motif_suppression"] == "Erreur"


@pytest.mark.asyncio
async def test_modification_quantite_recalcule_le_total(
    client_authenticated, consultation_factory, nomenclature
):
    consultation = await consultation_factory()
    ajout = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["DETART"]["id"], "dent_numero": 26, "quantite": 1},
    )
    acte_id = ajout.json()["data"]["id"]

    modification = await client_authenticated.patch(
        f"/api/v1/consultations/actes/{acte_id}", json={"quantite": 4}
    )

    assert modification.status_code == 200
    assert modification.json()["data"]["montant"] == "30000.00"

    total = await client_authenticated.get(f"/api/v1/consultations/{consultation['id']}/total")
    assert total.json()["data"]["total_actes"] == "30000.00"


# ==============================================================================
# RECHERCHE & LISTE
# ==============================================================================

@pytest.mark.asyncio
async def test_filtrage_par_patient(client_authenticated, consultation_factory, patient_factory):
    consultation = await consultation_factory()

    autre = await patient_factory(nom="Autre", prenom="Patient", telephone_1="775555500")
    autre_id = autre.json()["data"]["id"]

    liste = await client_authenticated.get(
        "/api/v1/consultations", params={"patient_id": consultation["patient_id"]}
    )
    assert liste.json()["meta"]["total_records"] == 1

    vide = await client_authenticated.get("/api/v1/consultations", params={"patient_id": autre_id})
    assert vide.json()["meta"]["total_records"] == 0


@pytest.mark.asyncio
async def test_filtrage_par_statut(client_authenticated, consultation_factory):
    await consultation_factory()

    en_cours = await client_authenticated.get(
        "/api/v1/consultations", params={"statut": "EN_COURS"}
    )
    assert en_cours.json()["meta"]["total_records"] == 1

    terminees = await client_authenticated.get(
        "/api/v1/consultations", params={"statut": "TERMINEE"}
    )
    assert terminees.json()["meta"]["total_records"] == 0


@pytest.mark.asyncio
async def test_detail_remonte_le_total_et_les_alertes(
    client_authenticated, consultation_factory, nomenclature, patient_factory
):
    """RG02 : le détail rappelle l'état des alertes cliniques du patient."""
    consultation = await consultation_factory(
        patient_kwargs={"nom": "Allergique", "prenom": "Test", "telephone_1": "776666600"},
    )
    # On enregistre l'allergie avant de lire le détail de la consultation.
    await client_authenticated.put(
        f"/api/v1/patients/{consultation['patient_id']}/etat-general",
        json={"allergies": [{"substance": "Latex", "severite": "grave"}]},
    )
    await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": nomenclature["CONS"]["id"]},
    )

    detail = await client_authenticated.get(f"/api/v1/consultations/{consultation['id']}/detail")

    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["total_actes"] == "15000.00"
    assert any(a["code"] == "ALLERGIE" for a in data["alertes"])


@pytest.mark.asyncio
async def test_consultation_inexistante_renvoie_404(client_authenticated, nomenclature):
    reponse = await client_authenticated.get(f"/api/v1/consultations/{uuid.uuid4()}")

    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "CONSULTATION_NOT_FOUND"


# ==============================================================================
# NOMENCLATURE
# ==============================================================================

@pytest.mark.asyncio
async def test_nomenclature_refuse_code_double(client_authenticated, nomenclature):
    reponse = await client_authenticated.post(
        "/api/v1/nomenclature/actes",
        json={
            "code": "CONS",
            "libelle": "Doublon",
            "categorie": "SOINS",
            "tarif_base": "1000.00",
        },
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "ACTE_CODE_EXISTANT"


@pytest.mark.asyncio
async def test_code_acte_normalise_en_majuscules(client_authenticated):
    reponse = await client_authenticated.post(
        "/api/v1/nomenclature/actes",
        json={"code": "ext01", "libelle": "Extraction simple", "categorie": "chirurgie", "tarif_base": "25000.00"},
    )

    assert reponse.status_code == 201
    data = reponse.json()["data"]
    assert data["code"] == "EXT01"
    assert data["categorie"] == "CHIRURGIE"


@pytest.mark.asyncio
async def test_recherche_nomenclature(client_authenticated, nomenclature):
    reponse = await client_authenticated.get("/api/v1/nomenclature/actes", params={"q": "détart"})

    assert reponse.status_code == 200
    items = reponse.json()["items"]
    assert len(items) >= 1
    assert any(i["code"] == "DETART" for i in items)


@pytest.mark.asyncio
async def test_acte_inactif_refuse_a_la_saisie(
    client_authenticated, consultation_factory, nomenclature, tenant_db: AsyncSession
):
    """Un acte retiré de la nomenclature ne peut plus être facturé."""
    from src.modules.tenants.models import ActeNomenclature

    consultation = await consultation_factory()

    acte_id = uuid.UUID(nomenclature["CONS"]["id"])
    acte = (
        await tenant_db.execute(select(ActeNomenclature).where(ActeNomenclature.id == acte_id))
    ).scalar_one()
    acte.actif = False
    await tenant_db.commit()

    reponse = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": str(acte_id)},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "ACTE_INACTIF"
