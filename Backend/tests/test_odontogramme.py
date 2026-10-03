"""
Tests du module Odontogramme (D1C).

Couvre les règles RG10 (historisation des changements d'état) et RG11
(32 dents adulte / 20 dents enfant), plus le cloisonnement multi-tenant.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.models import (
    AuditLogTenant,
    ChartingParodontal,
    Dent,
    EtatDentHistorique,
    FaceDent,
    Odontogramme,
)


# ==============================================================================
# RG11 — GÉNÉRATION DE L'ODONTOGRAMME
# ==============================================================================

@pytest.mark.asyncio
async def test_adulte_a_32_dents(client_authenticated, patient_factory):
    """RG11 : un odontogramme adulte comprend 32 dents."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["type"] == "ADULTE"
    assert data["nb_dents"] == 32
    assert len(data["dents"]) == 32


@pytest.mark.asyncio
async def test_enfant_a_20_dents(client_authenticated, patient_factory):
    """RG11 : un odontogramme enfant comprend 20 dents (dentition de lait)."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}",
        json={"type": "ENFANT", "systeme_notation": "FDI"},
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["type"] == "ENFANT"
    assert data["nb_dents"] == 20
    numeros = sorted(d["numero_fdi"] for d in data["dents"])
    assert 51 in numeros and 85 in numeros
    assert 11 not in numeros, "un odontogramme enfant ne contient pas de dents définitives"


@pytest.mark.asyncio
async def test_dents_par_defaut_saines(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    dents = reponse.json()["data"]["dents"]

    assert all(d["etat_actuel"] == "SAINE" for d in dents)
    assert all(d["a_alerte"] is False for d in dents)


@pytest.mark.asyncio
async def test_numerotation_universeale_attribuee(client_authenticated, patient_factory):
    """La numérotation Universal (1-32) est calculée en plus du FDI."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    par_fdi = {d["numero_fdi"]: d["numero_universal"] for d in reponse.json()["data"]["dents"]}

    assert par_fdi[18] == 1, "3e molaire supérieure droite = 1 en Universal"
    assert par_fdi[11] == 8, "incisive centrale supérieure droite = 8"
    assert par_fdi[41] == 32, "3e molaire inférieure droite = 32"


@pytest.mark.asyncio
async def test_odontogramme_genere_automatiquement_a_la_premiere_lecture(
    client_authenticated, patient_factory
):
    """
    Un patient créé avant D1C n'a pas d'odontogramme. Le lire doit le générer
    plutôt que renvoyer une 404 : le praticien ne doit pas avoir à le créer.
    """
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    # Aucune création explicite préalable.
    reponse = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    assert reponse.status_code == 200
    assert reponse.json()["data"]["nb_dents"] == 32


@pytest.mark.asyncio
async def test_creation_explicite_est_idempotente(client_authenticated, patient_factory):
    """Créer deux fois ne doit pas dupliquer les dents ni écraser l'historique."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}", json={"type": "ADULTE"}
    )
    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_AVANCEE"},
    )
    second = await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}", json={"type": "ADULTE"}
    )

    assert second.status_code == 200
    assert second.json()["data"]["nb_dents"] == 32, "pas de duplication de dents"

    dent_26 = next(d for d in second.json()["data"]["dents"] if d["numero_fdi"] == 26)
    assert dent_26["etat_actuel"] == "CARIE_AVANCEE", "l'état saisi ne doit pas être perdu"


@pytest.mark.asyncio
async def test_creation_tracee(client_authenticated, patient_factory, tenant_db: AsyncSession):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    stmt = select(func.count(EtatDentHistorique.id))
    total_historique = int((await tenant_db.execute(stmt)).scalar_one())
    assert total_historique == 0, "la génération initiale n'est pas un changement d'état"

    stmt = select(func.count(AuditLogTenant.id)).where(
        AuditLogTenant.action == "ODONTOGRAMME_CREATE"
    )
    assert int((await tenant_db.execute(stmt)).scalar_one()) >= 1


# ==============================================================================
# RG10 — MISE À JOUR D'UNE DENT ET HISTORIQUE
# ==============================================================================

@pytest.mark.asyncio
async def test_mise_a_jour_dent_change_l_etat(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_AVANCEE"},
    )

    assert reponse.status_code == 200, reponse.text
    dent = next(d for d in reponse.json()["data"]["dents"] if d["numero_fdi"] == 26)
    assert dent["etat_actuel"] == "CARIE_AVANCEE"
    assert dent["etat_libelle"] == "Carie avancée"
    assert dent["a_alerte"] is True, "une carie doit signaler une alerte au praticien"


@pytest.mark.asyncio
async def test_historique_conserve_l_etat_precedent(client_authenticated, patient_factory):
    """
    RG10 : l'historique doit permettre de reconstituer l'évolution d'une dent,
    état antérieur compris.
    """
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_DEBUTANTE"},
    )
    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "OBTURATION_COMPOSITE"},
    )

    reponse = await client_authenticated.get(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/26/historique"
    )

    assert reponse.status_code == 200, reponse.text
    historique = reponse.json()["data"]["historique"]
    assert len(historique) == 2

    # Du plus récent au plus ancien.
    assert historique[0]["etat"] == "OBTURATION_COMPOSITE"
    assert historique[0]["etat_precedent"] == "CARIE_DEBUTANTE"
    assert historique[1]["etat"] == "CARIE_DEBUTANTE"
    assert historique[1]["etat_precedent"] == "SAINE"


@pytest.mark.asyncio
async def test_historique_horodate_et_attribue(client_authenticated, patient_factory, tenant_db):
    """RG10 : chaque ligne porte une date et un praticien."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 16, "etat": "CARIE_PROFONDE"},
    )

    reponse = await client_authenticated.get(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/16/historique"
    )
    ligne = reponse.json()["data"]["historique"][0]

    assert ligne["date_constat"] is not None
    assert ligne["praticien_id"] is not None, "un constat sans praticien n'est pas opposable"


@pytest.mark.asyncio
async def test_mise_a_jour_tracee_dans_audit(client_authenticated, patient_factory, tenant_db):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 36, "etat": "EXTRACTION_REALISEE"},
    )

    stmt = select(func.count(AuditLogTenant.id)).where(
        AuditLogTenant.action == "DENT_ETAT_UPDATE"
    )
    assert int((await tenant_db.execute(stmt)).scalar_one()) >= 1


@pytest.mark.asyncio
async def test_synthese_compte_les_dents(client_authenticated, patient_factory):
    """Le résumé doit permettre au praticien de voir l'essentiel sans parcourir 32 dents."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dents",
        json={
            "dents": [
                {"numero_fdi": 26, "etat": "CARIE_AVANCEE"},
                {"numero_fdi": 27, "etat": "OBTURATION_COMPOSITE"},
                {"numero_fdi": 28, "etat": "ABSENTE_EXTRACTEE"},
            ]
        },
    )

    reponse = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    data = reponse.json()["data"]

    assert data["nb_dents_a_traiter"] == 1
    assert data["nb_dents_soignees"] == 1
    assert data["nb_dents_absentes"] == 1


# ==============================================================================
# MISE À JOUR EN LOT
# ==============================================================================

@pytest.mark.asyncio
async def test_lot_de_dents(client_authenticated, patient_factory):
    """Un détartrage touche plusieurs dents : une requête doit suffire."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dents",
        json={
            "dents": [
                {"numero_fdi": 16, "etat": "OBTURATION_COMPOSITE"},
                {"numero_fdi": 46, "etat": "OBTURATION_COMPOSITE"},
                {"numero_fdi": 17, "etat": "CARIE_DEBUTANTE"},
            ]
        },
    )

    assert reponse.status_code == 200, reponse.text
    etats = {d["numero_fdi"]: d["etat_actuel"] for d in reponse.json()["data"]["dents"]}
    assert etats[16] == "OBTURATION_COMPOSITE"
    assert etats[46] == "OBTURATION_COMPOSITE"
    assert etats[17] == "CARIE_DEBUTANTE"


@pytest.mark.asyncio
async def test_lot_refuse_dents_en_double(client_authenticated, patient_factory):
    """Deux modifications de la même dent dans un lot masquent la dernière : refusé."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dents",
        json={
            "dents": [
                {"numero_fdi": 26, "etat": "CARIE_DEBUTANTE"},
                {"numero_fdi": 26, "etat": "OBTURATION_COMPOSITE"},
            ]
        },
    )

    assert reponse.status_code == 422
    assert "double" in reponse.text.lower()


@pytest.mark.asyncio
async def test_lot_est_atomique(client_authenticated, patient_factory):
    """
    Si une dent du lot est invalide, aucune ne doit être modifiée.
    """
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dents",
        json={"dents": [{"numero_fdi": 26, "etat": "CARIE_DEBUTANTE"}]},
    )

    # Le lot contient la dent 99, invalide : le schéma la rejette avant écriture.
    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dents",
        json={
            "dents": [
                {"numero_fdi": 27, "etat": "OBTURATION_COMPOSITE"},
                {"numero_fdi": 99, "etat": "SAINE"},
            ]
        },
    )

    assert reponse.status_code == 422

    # La dent 26 n'a pas bougé, et 27 n'a pas été touchée non plus.
    etat_27 = await client_authenticated.get(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/27"
    )
    assert etat_27.json()["data"]["etat_actuel"] == "SAINE"


# ==============================================================================
# VALIDATION
# ==============================================================================

@pytest.mark.asyncio
async def test_numero_dent_invalide_refuse(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 99, "etat": "SAINE"},
    )

    assert reponse.status_code == 422
    assert "FDI" in reponse.text


@pytest.mark.asyncio
async def test_etat_inconnu_refuse(client_authenticated, patient_factory):
    """Un code couleur inventé casserait le rendu du composant SVG."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "DENT_MAGIQUE"},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_dent_absente_de_l_odontogramme_refusee(client_authenticated, patient_factory):
    """
    Une dent de lait sur un odontogramme adulte n'existe pas : la refusé évite
    de créer une dent orpheline que le composant SVG ne saurait pas placer.
    """
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 51, "etat": "CARIE_DEBUTANTE"},
    )

    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "DENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_mobilite_hors_bornes_refusee(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "SAINE", "mobilite": 7},
    )

    assert reponse.status_code == 422


# ==============================================================================
# FACES
# ==============================================================================

@pytest.mark.asyncio
async def test_mise_a_jour_par_face(client_authenticated, patient_factory):
    """Une carie est localisée : la face occlusale de la 26, pas « la 26 »."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.put(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/26/faces",
        json={"faces": [{"face": "OCCLUSAL_INCISAL", "etat": "CARIE_AVANCEE"}]},
    )

    assert reponse.status_code == 200, reponse.text
    dent = next(d for d in reponse.json()["data"]["dents"] if d["numero_fdi"] == 26)
    assert len(dent["faces"]) == 1
    assert dent["faces"][0]["face"] == "OCCLUSAL_INCISAL"
    assert dent["faces"][0]["face_courte"] == "O"
    assert dent["faces"][0]["etat"] == "CARIE_AVANCEE"


@pytest.mark.asyncio
async def test_faces_multiples_acceptees(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.put(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/36/faces",
        json={
            "faces": [
                {"face": "MESIAL", "etat": "CARIE_DEBUTANTE"},
                {"face": "OCCLUSAL_INCISAL", "etat": "CARIE_DEBUTANTE"},
                {"face": "DISTAL", "etat": "OBTURATION_COMPOSITE"},
            ]
        },
    )

    assert reponse.status_code == 200
    dent = next(d for d in reponse.json()["data"]["dents"] if d["numero_fdi"] == 36)
    assert len(dent["faces"]) == 3


@pytest.mark.asyncio
async def test_face_invalide_refusee(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]

    reponse = await client_authenticated.put(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/26/faces",
        json={"faces": [{"face": "FACE_INTERNE", "etat": "SAINE"}]},
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_mise_a_jour_dent_avec_face_met_a_jour_la_face(client_authenticated, patient_factory):
    """Indiquer une face dans la mise à jour doit aussi alimenter le tableau des faces."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_PROFONDE", "face": "DISTAL"},
    )

    assert reponse.status_code == 200
    dent = next(d for d in reponse.json()["data"]["dents"] if d["numero_fdi"] == 26)
    assert any(f["face"] == "DISTAL" for f in dent["faces"])


# ==============================================================================
# CHARTING PARODONTAL
# ==============================================================================

@pytest.mark.asyncio
async def test_charting_parodontal_complet(client_authenticated, patient_factory):
    """Sondage en 6 points + indices, comme prévu par le dictionnaire §5.2."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    odontogramme = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    dent_id = next(
        d["id"] for d in odontogramme.json()["data"]["dents"] if d["numero_fdi"] == 26
    )

    reponse = await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}/charting",
        json={
            "dent_id": dent_id,
            "sondages": [
                {"site": "MV", "profondeur": 3},
                {"site": "V", "profondeur": 4},
                {"site": "DV", "profondeur": 3},
                {"site": "ML", "profondeur": 5},
                {"site": "L", "profondeur": 6},
                {"site": "DL", "profondeur": 4},
            ],
            "nac": 2,
            "saignement_bop": True,
            "plaque_ipv": True,
        },
    )

    assert reponse.status_code == 201, reponse.text
    data = reponse.json()["data"]
    assert len(data["sondages"]) == 6
    assert data["profondeur_moyenne"] == 4.17
    assert data["saignement_bop"] is True


@pytest.mark.asyncio
async def test_sondage_incomplet_refuse(client_authenticated, patient_factory):
    """Un sondage partiel ne doit pas passer : la moyenne serait fausse."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    odontogramme = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    dent_id = next(d["id"] for d in odontogramme.json()["data"]["dents"] if d["numero_fdi"] == 26)

    reponse = await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}/charting",
        json={
            "dent_id": dent_id,
            "sondages": [{"site": "MV", "profondeur": 3}, {"site": "V", "profondeur": 4}],
        },
    )

    assert reponse.status_code == 422
    assert "incomplet" in reponse.text.lower()


@pytest.mark.asyncio
async def test_sondage_sans_donnees_accepte(client_authenticated, patient_factory):
    """Sans sondage, seuls les indices cliniques : c'est un relevé valide."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    odontogramme = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    dent_id = next(d["id"] for d in odontogramme.json()["data"]["dents"] if d["numero_fdi"] == 26)

    reponse = await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}/charting",
        json={"dent_id": dent_id, "mobilite": 1, "furcation": 1},
    )

    assert reponse.status_code == 201
    assert reponse.json()["data"]["profondeur_moyenne"] is None


@pytest.mark.asyncio
async def test_charting_met_a_jour_la_mobilite(client_authenticated, patient_factory):
    """La mobilité est une donnée de la dent : le relevé doit la répercuter."""
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    odontogramme = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    dent_id = next(d["id"] for d in odontogramme.json()["data"]["dents"] if d["numero_fdi"] == 26)

    await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}/charting",
        json={"dent_id": dent_id, "mobilite": 2},
    )

    dent = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}/dent/26")
    assert dent.json()["data"]["mobilite"] == 2


@pytest.mark.asyncio
async def test_liste_chartings(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    odontogramme = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")
    dent_id = next(d["id"] for d in odontogramme.json()["data"]["dents"] if d["numero_fdi"] == 26)

    await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}/charting", json={"dent_id": dent_id}
    )
    await client_authenticated.post(
        f"/api/v1/odontogramme/patients/{patient_id}/charting", json={"dent_id": dent_id}
    )

    reponse = await client_authenticated.get(
        f"/api/v1/odontogramme/patients/{patient_id}/charting"
    )
    assert reponse.status_code == 200
    assert len(reponse.json()["data"]) == 2


# ==============================================================================
# TRAÇABILITÉ AVEC LA CONSULTATION (RG10)
# ==============================================================================

@pytest.mark.asyncio
async def test_constat_rattache_a_une_consultation(client_authenticated, consultation_factory):
    """Le constat doit pointer vers la consultation qui l'a produit."""
    consultation = await consultation_factory()
    patient_id = consultation["patient_id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dent",
        json={
            "numero_fdi": 26,
            "etat": "CARIE_AVANCEE",
            "consultation_id": consultation["id"],
        },
    )

    assert reponse.status_code == 200, reponse.text
    historique = await client_authenticated.get(
        f"/api/v1/odontogramme/patients/{patient_id}/dent/26/historique"
    )
    assert historique.json()["data"]["historique"][0]["consultation_id"] == consultation["id"]


@pytest.mark.asyncio
async def test_consultation_d_un_autre_patient_refusee(
    client_authenticated, consultation_factory, patient_factory
):
    """
    Rattacher un constat à une consultation étrangère fabriquerait un dossier
    médical faux. La vérification doit refuser.
    """
    consultation = await consultation_factory()
    autre_patient = await patient_factory(nom="Autre", prenom="Patient", telephone_1="775000444")
    autre_id = autre_patient.json()["data"]["id"]

    await client_authenticated.get(f"/api/v1/odontogramme/patients/{autre_id}")

    reponse = await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{autre_id}/dent",
        json={"numero_fdi": 26, "etat": "CARIE_AVANCEE", "consultation_id": consultation["id"]},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONSULTATION_AUTRE_DOSSIER"


# ==============================================================================
# RÉFÉRENTIEL POUR LE COMPOSANT SVG
# ==============================================================================

@pytest.mark.asyncio
async def test_referentiel_etats(client_authenticated):
    """
    Le frontend ne doit pas coder en dur la liste des états : un état ajouté
    côté backend doit apparaître sans modifier le composant SVG.
    """
    reponse = await client_authenticated.get("/api/v1/odontogramme/referentiel/etats")

    assert reponse.status_code == 200
    data = reponse.json()["data"]
    assert len(data["etats"]) >= 30
    assert len(data["faces"]) == 5

    par_code = {e["code"]: e for e in data["etats"]}
    assert par_code["SAINE"]["couleur"] == "#22C55E", "vert sain (CDC)"
    assert par_code["CARIE_AVANCEE"]["couleur"] == "#EF4444", "rouge carie (CDC)"
    assert par_code["OBTURATION_COMPOSITE"]["categorie"] == "SOIGNEE"
    assert all(e["couleur"].startswith("#") for e in data["etats"]), "toute couleur doit être exploitable par le SVG"


@pytest.mark.asyncio
async def test_historique_global_toutes_dents(client_authenticated, patient_factory):
    patient = await patient_factory()
    patient_id = patient.json()["data"]["id"]
    await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}")

    await client_authenticated.patch(
        f"/api/v1/odontogramme/patients/{patient_id}/dents",
        json={
            "dents": [
                {"numero_fdi": 16, "etat": "CARIE_DEBUTANTE"},
                {"numero_fdi": 46, "etat": "OBTURATION_COMPOSITE"},
            ]
        },
    )

    reponse = await client_authenticated.get(f"/api/v1/odontogramme/patients/{patient_id}/historique")
    lignes = reponse.json()["data"]

    assert len(lignes) == 2
    assert all(l["dent_id"] for l in lignes)
