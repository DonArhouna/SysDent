"""
Tests du module Patients — dossier médical, état général, antécédents, alertes.

Couvre les cas d'usage UC1, UC2, UC3, UC5, UC6, UC7, UC12 du CDC et les règles
RG02 (vérification de l'état général) et RG12 (traçabilité médico-légale).
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.models import AuditLogTenant, EtatGeneral, Patient


# ==============================================================================
# RECHERCHE (UC2)
# ==============================================================================

@pytest.mark.asyncio
async def test_recherche_par_nom(client_authenticated, patient_factory):
    await patient_factory(nom="Diop", prenom="Aminata")
    await patient_factory(nom="Fall", prenom="Moussa", telephone_1="771000001")

    reponse = await client_authenticated.get("/api/v1/patients", params={"nom": "Diop"})

    assert reponse.status_code == 200
    meta = reponse.json()["meta"]
    assert meta["total_records"] == 1
    assert reponse.json()["items"][0]["nom"] == "Diop"


@pytest.mark.asyncio
async def test_recherche_par_telephone(client_authenticated, patient_factory):
    await patient_factory(nom="Sagna", prenom="Fatou", telephone_1="779876543")

    reponse = await client_authenticated.get("/api/v1/patients", params={"telephone": "77987"})

    assert reponse.json()["meta"]["total_records"] == 1
    assert reponse.json()["items"][0]["nom"] == "Sagna"


@pytest.mark.asyncio
async def test_recherche_libre_par_numero_dossier(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Ndiaye", prenom="Ibrahima", telephone_1="775550001")
    numero = creation.json()["data"]["numero_dossier"]

    reponse = await client_authenticated.get("/api/v1/patients", params={"q": numero})

    assert reponse.json()["meta"]["total_records"] == 1


@pytest.mark.asyncio
async def test_recherche_ignore_les_archives_par_defaut(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Archive", prenom="Test", telephone_1="771111111")
    await client_authenticated.post(
        f"/api/v1/patients/{creation.json()['data']['id']}/archiver",
        json={"motif": "Test automatisé"},
    )

    par_defaut = await client_authenticated.get("/api/v1/patients")
    assert par_defaut.json()["meta"]["total_records"] == 0

    avec_archives = await client_authenticated.get(
        "/api/v1/patients", params={"include_archives": True}
    )
    assert avec_archives.json()["meta"]["total_records"] == 1


@pytest.mark.asyncio
async def test_pagination_meta_coherente(client_authenticated, patient_factory):
    for i in range(5):
        await patient_factory(nom=f"Pag{i:02d}", prenom="Test", telephone_1=f"77000000{i}")

    page1 = await client_authenticated.get("/api/v1/patients", params={"page": 1, "limit": 2})
    meta1 = page1.json()["meta"]

    assert len(page1.json()["items"]) == 2
    assert meta1["total_records"] == 5
    assert meta1["total_pages"] == 3
    assert meta1["has_next"] is True
    assert meta1["has_previous"] is False

    page3 = await client_authenticated.get("/api/v1/patients", params={"page": 3, "limit": 2})
    assert len(page3.json()["items"]) == 1
    assert page3.json()["meta"]["has_next"] is False
    assert page3.json()["meta"]["has_previous"] is True


# ==============================================================================
# ARCHIVAGE (UC12)
# ==============================================================================

@pytest.mark.asyncio
async def test_archivage_est_reversible(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Reactivable", prenom="Test", telephone_1="772222222")
    patient_id = creation.json()["data"]["id"]

    archive = await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/archiver", json={"motif": "Erreur de saisie"}
    )
    assert archive.status_code == 200
    assert archive.json()["data"]["archive"] is True
    assert archive.json()["data"]["actif"] is False

    reactif = await client_authenticated.post(f"/api/v1/patients/{patient_id}/reactiver")
    assert reactif.status_code == 200
    assert reactif.json()["data"]["archive"] is False
    assert reactif.json()["data"]["actif"] is True


@pytest.mark.asyncio
async def test_modification_refusee_sur_dossier_archive(client_authenticated, patient_factory):
    """Un dossier archivé ne doit plus être modifiable sans réactivation."""
    creation = await patient_factory(nom="Gele", prenom="Test", telephone_1="773333333")
    patient_id = creation.json()["data"]["id"]
    await client_authenticated.post(f"/api/v1/patients/{patient_id}/archiver", json={})

    reponse = await client_authenticated.patch(
        f"/api/v1/patients/{patient_id}", json={"nom": "DoitEchouer"}
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


# ==============================================================================
# ÉTAT GÉNÉRAL (UC6, RG02)
# ==============================================================================

@pytest.mark.asyncio
async def test_etat_general_existe_des_la_creation(client_authenticated, patient_factory, tenant_db):
    """
    RG02 : l'état général doit exister dès l'ouverture du dossier pour servir de
    point de comparaison à chaque consultation.
    """
    await patient_factory()

    stmt = select(func.count(EtatGeneral.id))
    total = int((await tenant_db.execute(stmt)).scalar_one())
    assert total == 1, "l'état général doit être matérialisé à la création du dossier"


@pytest.mark.asyncio
async def test_enregistrement_etat_general(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Grossesse", prenom="Test", telephone_1="774444444")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.put(
        f"/api/v1/patients/{patient_id}/etat-general",
        json={
            "grossesse": True,
            "grossesse_terme": "32 SA",
            "diabete": True,
            "diabete_type": "GESTATIONNEL",  # majuscules : le service normalise en minuscules
            "allergies": [
                {"substance": "Pénicilline", "reaction": "Urticaire", "severite": "grave"}
            ],
        },
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["grossesse"] is True
    assert data["grossesse_terme"] == "32 SA"
    assert data["diabete_type"] == "gestationnel"  # normalisé en minuscules
    assert data["allergies"][0]["substance"] == "Pénicilline"


@pytest.mark.asyncio
async def test_type_diabete_invalide_refuse(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Diabete", prenom="Test", telephone_1="775555555")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.put(
        f"/api/v1/patients/{patient_id}/etat-general",
        json={"diabete": True, "diabete_type": "diabete_spatial"},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_grossesse_terme_sans_grossesse_refuse(client_authenticated, patient_factory):
    """terme renseigné sans grossesse = incohérence, doit être rejetée."""
    creation = await patient_factory(nom="Incoherent", prenom="Test", telephone_1="776666666")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.put(
        f"/api/v1/patients/{patient_id}/etat-general",
        json={"grossesse": False, "grossesse_terme": "8 mois"},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_patch_etat_general_partiel(client_authenticated, patient_factory):
    """Un PATCH ne doit toucher que les champs transmis (vérification à la consultation)."""
    creation = await patient_factory(nom="Partiel", prenom="Test", telephone_1="777777777")
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.put(
        f"/api/v1/patients/{patient_id}/etat-general", json={"hta": True, "tabac": True}
    )
    reponse = await client_authenticated.patch(
        f"/api/v1/patients/{patient_id}/etat-general", json={"hta": False}
    )

    assert reponse.status_code == 200
    assert reponse.json()["data"]["hta"] is False
    assert reponse.json()["data"]["tabac"] is True, "un champ non transmis ne doit pas être écrasé"


# ==============================================================================
# ANTÉCÉDENTS (UC7)
# ==============================================================================

@pytest.mark.asyncio
async def test_ajout_antecedent_normalise_le_type(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Antecedent", prenom="Test", telephone_1="778888888")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/antecedents",
        json={
            "type_antecedent": "chirurgical",
            "description": "Appendicectomie en 2015",
            "date_survenue": "2015-06-10",
            "en_cours": False,
        },
    )

    assert reponse.status_code == 201, reponse.text
    assert reponse.json()["data"]["type_antecedent"] == "CHIRURGICAL"
    assert reponse.json()["data"]["date_survenue"] == "2015-06-10"


@pytest.mark.asyncio
async def test_antecedents_en_cours_listes_en_premier(client_authenticated, patient_factory):
    """UX clinique : ce qui est actif doit remonter avant l'historique."""
    creation = await patient_factory(nom="Tri", prenom="Test", telephone_1="779999999")
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/antecedents",
        json={"type_antecedent": "DENTAIRE", "description": "Traitement ancien", "en_cours": False},
    )
    await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/antecedents",
        json={"type_antecedent": "HTA", "description": "Hypertension traitée", "en_cours": True},
    )

    reponse = await client_authenticated.get(f"/api/v1/patients/{patient_id}/antecedents")
    items = reponse.json()["data"]

    assert len(items) == 2
    assert items[0]["en_cours"] is True


@pytest.mark.asyncio
async def test_cloture_antecedent(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Cloture", prenom="Test", telephone_1="770001111")
    patient_id = creation.json()["data"]["id"]

    creation_antecedent = await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/antecedents",
        json={"type_antecedent": "RESPIRATOIRE", "description": "Asthme", "en_cours": True},
    )
    antecedent_id = creation_antecedent.json()["data"]["id"]

    reponse = await client_authenticated.patch(
        f"/api/v1/patients/antecedents/{antecedent_id}",
        json={"en_cours": False, "notes": "Sous contrôle, désensibilisé"},
    )

    assert reponse.status_code == 200
    assert reponse.json()["data"]["en_cours"] is False


# ==============================================================================
# ALERTES CLINIQUES (RG03, RG04)
# ==============================================================================

@pytest.mark.asyncio
async def test_alertes_grossesse_et_allergie_grave(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Alertes", prenom="Test", telephone_1="770002222")
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.put(
        f"/api/v1/patients/{patient_id}/etat-general",
        json={
            "grossesse": True,
            "grossesse_terme": "36 SA",
            "allergies": [{"substance": "Latex", "severite": "grave"}],
        },
    )

    reponse = await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")
    alertes = reponse.json()["data"]["alertes"]
    codes = {a["code"] for a in alertes}

    assert "GROSSESSE" in codes
    assert "ALLERGIE" in codes
    grossesse = next(a for a in alertes if a["code"] == "GROSSESSE")
    assert grossesse["niveau"] == "GRAVE"
    assert "36 SA" in grossesse["message"]


@pytest.mark.asyncio
async def test_alerte_antecedent_cardiaque_actif(client_authenticated, patient_factory):
    """Un antécédent cardiovasculaire actif doit alerter même sans saisie d'état général."""
    creation = await patient_factory(nom="Cardio", prenom="Test", telephone_1="770003333")
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/antecedents",
        json={
            "type_antecedent": "CARDIO",
            "description": "Infarctus du myocarde en 2020",
            "en_cours": True,
        },
    )

    reponse = await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")
    alertes = reponse.json()["data"]["alertes"]

    assert any(a["code"] == "ANTECEDENT_CARDIAQUE" for a in alertes)
    assert any(a["niveau"] == "GRAVE" for a in alertes)


@pytest.mark.asyncio
async def test_aucune_alerte_pour_patient_sain(client_authenticated, patient_factory):
    creation = await patient_factory(nom="Sain", prenom="Test", telephone_1="770004444")
    patient_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")

    assert reponse.status_code == 200
    assert reponse.json()["data"]["alertes"] == []


@pytest.mark.asyncio
async def test_antecedent_cloture_fait_disparaitre_l_alerte(client_authenticated, patient_factory):
    """Fermer un antécédent doit retirer l'alerte correspondante (bruit clinique)."""
    creation = await patient_factory(nom="ClotureAlerte", prenom="Test", telephone_1="770005555")
    patient_id = creation.json()["data"]["id"]

    antecedent = await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/antecedents",
        json={"type_antecedent": "CARDIO", "description": "Hypertension", "en_cours": True},
    )
    avant = await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")
    assert any(a["code"] == "ANTECEDENT_CARDIAQUE" for a in avant.json()["data"]["alertes"])

    await client_authenticated.patch(
        f"/api/v1/patients/antecedents/{antecedent.json()['data']['id']}",
        json={"en_cours": False},
    )
    apres = await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")
    assert not any(a["code"] == "ANTECEDENT_CARDIAQUE" for a in apres.json()["data"]["alertes"])


# ==============================================================================
# TRAÇABILITÉ MÉDICO-LÉGALE (RG12)
# ==============================================================================

@pytest.mark.asyncio
async def test_creation_patient_est_tracee(client_authenticated, patient_factory, tenant_db):
    creation = await patient_factory()
    patient_id = creation.json()["data"]["id"]

    stmt = select(AuditLogTenant).where(
        AuditLogTenant.resource_id == patient_id, AuditLogTenant.action == "PATIENT_CREATE"
    )
    entree = (await tenant_db.execute(stmt)).scalar_one_or_none()

    assert entree is not None, "la création d'un dossier doit être journalisée (RG12)"
    assert entree.resource_type == "Patient"
    assert entree.changes is not None
    assert "numero_dossier" in entree.changes


@pytest.mark.asyncio
async def test_consultation_dossier_est_tracee(client_authenticated, patient_factory, tenant_db):
    """
    Ouvrir un dossier médical doit laisser une trace : qui a consulté quel dossier,
    et quand. C'est l'exigence médico-légale centrale de SysDent.
    """
    creation = await patient_factory()
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")

    stmt = select(func.count(AuditLogTenant.id)).where(
        AuditLogTenant.resource_id == patient_id, AuditLogTenant.action == "PATIENT_VIEW"
    )
    assert int((await tenant_db.execute(stmt)).scalar_one()) == 1


@pytest.mark.asyncio
async def test_modification_trace_avant_apres(client_authenticated, patient_factory, tenant_db):
    creation = await patient_factory(nom="Avant", prenom="Test", telephone_1="770006666")
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.patch(f"/api/v1/patients/{patient_id}", json={"nom": "Apres"})

    stmt = select(AuditLogTenant).where(
        AuditLogTenant.resource_id == patient_id, AuditLogTenant.action == "PATIENT_UPDATE"
    )
    entree = (await tenant_db.execute(stmt)).scalar_one_or_none()

    assert entree is not None
    assert entree.changes["nom"]["ancien"] == "Avant"
    assert entree.changes["nom"]["nouveau"] == "Apres"


@pytest.mark.asyncio
async def test_archivage_trace_le_motif(client_authenticated, patient_factory, tenant_db):
    creation = await patient_factory(nom="ArchiveTrace", prenom="Test", telephone_1="770007777")
    patient_id = creation.json()["data"]["id"]

    await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/archiver", json={"motif": "Demande du patient"}
    )

    stmt = select(AuditLogTenant).where(
        AuditLogTenant.resource_id == patient_id, AuditLogTenant.action == "PATIENT_ARCHIVE"
    )
    entree = (await tenant_db.execute(stmt)).scalar_one_or_none()

    assert entree is not None
    assert entree.changes["motif"] == "Demande du patient"


# ==============================================================================
# ISOLATION MULTI-TENANT
# ==============================================================================

@pytest.mark.asyncio
async def test_patient_inexistant_renvoie_404_rfc7807(client_authenticated):
    reponse = await client_authenticated.get(f"/api/v1/patients/{uuid.uuid4()}")

    assert reponse.status_code == 404
    corps = reponse.json()
    assert corps["success"] is False
    assert corps["error"]["code"] == "PATIENT_NOT_FOUND"
    assert "request_id" in corps["error"]


@pytest.mark.asyncio
async def test_uuid_invalide_renvoie_422(client_authenticated):
    reponse = await client_authenticated.get("/api/v1/patients/pas-un-uuid")

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_creation_complete_en_un_appel(client_authenticated, patient_factory):
    """
    Le CDC permet de créer identité + état général + antécédents en une fois (étapes 1 à 3).

    Ce test a détecté un vrai bug : `creer_patient` ignorait le champ
    `etat_general` de la requête et ne créait que l'état général vide.
    """
    reponse = await patient_factory(
        etat_general={"diabete": True, "diabete_type": "type2"},
        antecedents=[
            {"type_antecedent": "HTA", "description": "Hypertension légère", "en_cours": True}
        ],
    )

    assert reponse.status_code == 201, reponse.text
    patient_id = reponse.json()["data"]["id"]

    dossier = await client_authenticated.get(f"/api/v1/patients/{patient_id}/dossier")
    data = dossier.json()["data"]

    assert data["etat_general"]["diabete"] is True
    assert len(data["antecedents"]) == 1
    assert any(a["code"] == "DIABETE" for a in data["alertes"])
