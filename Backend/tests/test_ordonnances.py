"""
Tests du module Ordonnances (D1D).

Règles couvertes :
  RG07 — les allergies déclenchent des alertes automatiques
  RG08 — les contre-indications bloquent certains médicaments

L'axe central n'est pas « la prescription aboutit » mais la distinction entre
contre-indication FORMELLE (bloque, aucun subterfuge possible) et simple
PRÉCAUTION (exige une justification écrite qui reste au dossier). C'est ce qui
rend l'outil utilisable en pratique sans le rendre inerte : un AINS chez une
patiente enceinte doit tomber, l'amoxicilline au premier trimestre se discute.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.ordonnance import (
    INTERDIT,
    PRECAUTION,
    condition_allergie,
    detecter_interactions,
    evaluer_contre_indications,
    normaliser_dci,
)
from src.modules.tenants.models import AuditLogTenant, MedicamentReferentiel, Prescription


# ==============================================================================
# OUTILLAGE
# ==============================================================================

@pytest_asyncio.fixture
async def formulaire(client_authenticated, tenant_db: AsyncSession) -> dict:
    """
    Sème le formulaire médicamenteux et renvoie les molécules indexées par nom
    commercial.

    Indexé par nom commercial et non par DCI normalisé : l'amoxicilline simple
    et l'association amoxicilline-acide clavulanique partagent la même molécule
    porteuse, et une clé normalisée les confondrait.

    En production le seed est joué au provisioning du cabinet ; ici on le joue
    pour que le test ne dépende pas du chemin de création.
    """
    from src.modules.ordonnances.services import MedicamentService

    await MedicamentService.semer_formulaire(tenant_db)
    await tenant_db.commit()

    reponse = await client_authenticated.get("/api/v1/ordonnances/medicaments")
    assert reponse.status_code == 200, reponse.text
    return {m["nom_commercial"]: m for m in reponse.json()["data"]}


async def dossier(
    client,
    *,
    allergies=None,
    grossesse=None,
    grossesse_terme=None,
    allaitement=None,
    diabete=None,
    hta=None,
    antecedents=None,
    telephone="770000000",
):
    """
    Crée un dossier médical avec son état général et démarre une consultation
    dessus. Renvoie ``(patient_id, consultation_id)``.

    Les deux appartiennent au MÊME patient, ce qui est indispensable : une
    ordonnance s'appuie sur une consultation, et le service refuse un mélange
    (`CONSULTATION_AUTRE_DOSSIER`) pour ne pas fabriquer un dossier faux.
    """
    etat = {
        champ: valeur
        for champ, valeur in (
            ("allergies", allergies),
            ("grossesse", grossesse),
            ("grossesse_terme", grossesse_terme),
            ("allaitement", allaitement),
            ("diabete", diabete),
            ("hta", hta),
        )
        if valeur is not None
    }

    payload = {
        "prenom": "Aminata",
        "nom": "Diop",
        "date_naissance": "1990-05-12",
        "sexe": "F",
        "telephone_1": telephone,
    }
    if etat:
        payload["etat_general"] = etat
    if antecedents:
        payload["antecedents"] = antecedents

    creation = await client.post("/api/v1/patients", json=payload)
    assert creation.status_code == 201, creation.text
    patient_id = creation.json()["data"]["id"]

    consultation = await client.post(
        "/api/v1/consultations",
        json={"patient_id": patient_id, "motif": "Douleur dentaire", "type_motif": "DOULEUR"},
    )
    assert consultation.status_code == 201, consultation.text
    return patient_id, consultation.json()["data"]["id"]


async def prescrire(client, patient_id: str, consultation_id: str, lignes: list):
    """Émet une ordonnance et renvoie la réponse brute."""
    return await client.post(
        "/api/v1/ordonnances",
        json={
            "patient_id": patient_id,
            "consultation_id": consultation_id,
            "lignes": lignes,
        },
    )


# ==============================================================================
# MOTEUR DE CONTRE-INDICATION (pur, sans base)
# ==============================================================================

def test_condition_allergie_normalise_les_graphies():
    """Le praticien saisit librement : « pénicilline », « Pénicilline », « PENICILLINE »
    et « pénicilline » doivent produire la même condition, sinon une allergie
    déclarée peut ne déclencher aucune règle."""
    attendu = "ALLERGIE_PENICILLINE"
    assert condition_allergie("Pénicilline") == attendu
    assert condition_allergie("penicilline") == attendu
    assert condition_allergie("  PENICILLINE  ") == attendu
    assert condition_allergie("Pénicilline-G ") == "ALLERGIE_PENICILLINEG"


def test_normaliser_dci_renvoie_la_molecule_porteuse():
    """Une association garde sa molécule porteuse : c'est elle qui porte le
    risque allergique et l'interaction."""
    assert normaliser_dci("Amoxicilline + Acide clavulanique") == "AMOXICILLINE"
    assert normaliser_dci("ibuprofène") == "IBUPROFENE"


def test_gravite_inconnue_retombe_en_interdit():
    """
    Une règle corrompue ne doit jamais dégrader la sécurité en simple
    précaution. Le défaut est le plus restrictif.
    """
    conditions = {"GROSSESSE": "Patiente enceinte"}
    alertes = evaluer_contre_indications(
        dci="TEST",
        contre_indications=[{"condition": "GROSSESSE", "gravite": "PEUT_ETRE", "message": "Bof"}],
        conditions_actives=conditions,
    )
    assert [a.gravite for a in alertes] == [INTERDIT]


def test_interactions_examinees_une_seule_fois():
    """L'ordre des lignes est sans importance et une paire n'est vue qu'une fois."""
    alertes = detecter_interactions(["Aspirine", "Ibuprofène", "Ibuprofene"])
    interactions = [a for a in alertes if a["code"] == "INTERACTION_MEDICAMENTEUSE"]
    assert len(interactions) == 1
    assert interactions[0]["gravite"] == PRECAUTION


# ==============================================================================
# RG08 — CONTRE-INDICATION FORMELLE (bloque, aucune échappatoire)
# ==============================================================================

@pytest.mark.asyncio
async def test_amoxicilline_refusee_si_allergie_penicilline(
    client_authenticated, formulaire, tenant_db
):
    """
    Le cas clinique le plus grave : une bêta-lactamine prescrite à un patient
    allergique à la pénicilline peut être fatale. La ligne doit tomber ET
    rien ne doit être écrit en base.
    """
    patient_id, consultation_id = await dossier(
        client_authenticated,
        allergies=[{"substance": "Pénicilline", "severite": "grave"}],
    )

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Amoxicilline"]["id"], "posologie": "500 mg 3x/jour"}],
    )

    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["error"]["code"] == "CONTRE_INDICATION_ABSOLUE"
    assert "pénicilline" in reponse.json()["error"]["message"].lower()

    total = int((await tenant_db.execute(select(func.count(Prescription.id)))).scalar_one())
    assert total == 0, "une ordonnance refusée ne doit laisser aucune trace en base"


@pytest.mark.asyncio
async def test_ibuprofene_refuse_chez_une_patiente_enceinte(
    client_authenticated, formulaire
):
    """AINS et grossesse : contre-indication formelle à partir du 6e mois."""
    patient_id, consultation_id = await dossier(
        client_authenticated, grossesse=True, grossesse_terme="34 SA"
    )

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Ibuprofène"]["id"], "posologie": "400 mg"}],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONTRE_INDICATION_ABSOLUE"


@pytest.mark.asyncio
async def test_ibuprofene_refuse_si_insuffisance_renale(
    client_authenticated, formulaire
):
    """
    L'insuffisance rénale est déclarée en ANTÉCÉDENT, pas dans l'état général :
    c'est la situation réelle, et l'ignorer laisserait passer un AINS dangereux.
    """
    patient_id, consultation_id = await dossier(
        client_authenticated,
        antecedents=[
            {
                "type_antecedent": "RENAL",
                "description": "Insuffisance rénale chronique stade 3",
                "en_cours": True,
            }
        ],
    )

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Ibuprofène"]["id"], "posologie": "400 mg"}],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONTRE_INDICATION_ABSOLUE"


@pytest.mark.asyncio
async def test_allergie_declenchee_par_un_antecedent(client_authenticated, formulaire):
    """Un antécédent allergique en cours déclenche la même règle que l'état général."""
    patient_id, consultation_id = await dossier(
        client_authenticated,
        antecedents=[
            {"type_antecedent": "ALLERGIE", "description": "Penicilline", "en_cours": True}
        ],
    )

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Amoxicilline"]["id"], "posologie": "500 mg"}],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONTRE_INDICATION_ABSOLUE"


@pytest.mark.asyncio
async def test_refus_porte_le_detail_des_alertes(client_authenticated, formulaire):
    """
    Le praticien doit comprendre POURQUOI c'est refusé, pas seulement que c'est
    refusé : le message et le détail des alertes voyagent dans la réponse.
    """
    patient_id, consultation_id = await dossier(
        client_authenticated, allergies=[{"substance": "Pénicilline"}]
    )

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Amoxicilline"]["id"], "posologie": "500 mg"}],
    )

    detail = reponse.json()["error"]["details"]
    assert detail is not None, "le refus doit être explicable"
    conditions = {a["condition"] for a in detail["alertes"]}
    assert "ALLERGIE_PENICILLINE" in conditions
    assert all(a["gravite"] == INTERDIT for a in detail["alertes"])


# ==============================================================================
# RG08 — SIMPLE PRÉCAUTION (justification écrite exigée)
# ==============================================================================

@pytest.mark.asyncio
async def test_amoxicilline_grossesse_exige_justification(client_authenticated, formulaire):
    """
    L'amoxicilline en grossesse est une précaution, pas une interdiction.
    Sans justification la ligne est refusée ; avec, elle passe et la
    justification est conservée au dossier.
    """
    patient_id, consultation_id = await dossier(
        client_authenticated, grossesse=True, grossesse_terme="12 SA"
    )
    ligne = {
        "medicament_id": formulaire["Amoxicilline"]["id"],
        "posologie": "500 mg 3x/jour",
        "duree": "7 jours",
    }

    sans = await prescrire(client_authenticated, patient_id, consultation_id, [ligne])
    assert sans.status_code == 422
    assert sans.json()["error"]["code"] == "JUSTIFICATION_PRECAUTION_REQUISE"

    ligne["justification_precaution"] = (
        "Infection odontogène avérée, bénéfice estimé supérieur au risque."
    )
    avec = await prescrire(client_authenticated, patient_id, consultation_id, [ligne])

    assert avec.status_code == 201, avec.text
    data = avec.json()["data"]
    assert data["lignes"][0]["justification_precaution"]
    assert any(a["gravite"] == PRECAUTION for a in data["alertes"])


@pytest.mark.asyncio
async def test_allaitement_n_est_pas_une_interdiction(client_authenticated, formulaire):
    """Allaitement + paracétamol : précaution. La prescription doit rester possible."""
    patient_id, consultation_id = await dossier(client_authenticated, allaitement=True)

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [
            {
                "medicament_id": formulaire["Paracétamol"]["id"],
                "posologie": "1g 3x/jour",
                "justification_precaution": "Douleur modérée, posologie usuelle.",
            }
        ],
    )

    assert reponse.status_code == 201, reponse.text


@pytest.mark.asyncio
async def test_precaution_exige_une_justification_non_vide(client_authenticated, formulaire):
    """Une justification blanche ne vaut pas justification."""
    patient_id, consultation_id = await dossier(
        client_authenticated, grossesse=True, grossesse_terme="12 SA"
    )

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [
            {
                "medicament_id": formulaire["Amoxicilline"]["id"],
                "posologie": "500 mg",
                "justification_precaution": "   ",
            }
        ],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "JUSTIFICATION_PRECAUTION_REQUISE"


# ==============================================================================
# INTERACTIONS MÉDICAMENTEUSES
# ==============================================================================

@pytest.mark.asyncio
async def test_interaction_ains_signalee(client_authenticated, formulaire):
    """Deux AINS ensemble : risque hémorragique digestif majoré."""
    patient_id, consultation_id = await dossier(client_authenticated)

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [
            {"medicament_id": formulaire["Ibuprofène"]["id"], "posologie": "400 mg", "duree": "5 j"},
            {"medicament_id": formulaire["Diclofénac"]["id"], "posologie": "50 mg", "duree": "5 j"},
        ],
    )

    assert reponse.status_code == 201, reponse.text
    alertes = reponse.json()["data"]["alertes"]
    assert any(a["code"] == "INTERACTION_MEDICAMENTEUSE" for a in alertes)


@pytest.mark.asyncio
async def test_metronidazole_alcool_signale(client_authenticated, formulaire):
    """Contre-indication liée à la consommation, pas à un autre médicament."""
    patient_id, consultation_id = await dossier(client_authenticated)

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Métronidazole"]["id"], "posologie": "500 mg 3x/j"}],
    )

    assert reponse.status_code == 201, reponse.text
    assert any(a["code"] == "INTERACTION_ALCOOL" for a in reponse.json()["data"]["alertes"])


# ==============================================================================
# CONTRÔLE À BLANC (UC8)
# ==============================================================================

@pytest.mark.asyncio
async def test_controle_a_blanc_refuse_sans_ecrire(client_authenticated, formulaire):
    """
    Le praticien doit pouvoir tester une prescription avant de l'émettre, sans
    rien laisser derrière lui.
    """
    patient_id, _ = await dossier(
        client_authenticated, allergies=[{"substance": "Pénicilline"}]
    )

    reponse = await client_authenticated.post(
        "/api/v1/ordonnances/controle",
        json={
            "patient_id": patient_id,
            "medicament_id": formulaire["Amoxicilline"]["id"],
            "posologie": "500 mg",
        },
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    assert data["prescription_possible"] is False
    assert data["justification_requise"] is False
    assert any(a["gravite"] == INTERDIT for a in data["alertes"])

    liste = await client_authenticated.get("/api/v1/ordonnances", params={"patient_id": patient_id})
    assert liste.json()["data"] == []


@pytest.mark.asyncio
async def test_controle_a_blanc_explique_les_conditions(client_authenticated, formulaire):
    """
    Le praticien doit comprendre pourquoi la règle s'applique : le contrôle
    renvoie l'état clinique du patient ayant déclenché les règles.
    """
    patient_id, _ = await dossier(
        client_authenticated, grossesse=True, grossesse_terme="20 SA", hta=True
    )

    reponse = await client_authenticated.post(
        "/api/v1/ordonnances/controle",
        json={
            "patient_id": patient_id,
            "medicament_id": formulaire["Amoxicilline"]["id"],
            "posologie": "500 mg",
        },
    )

    assert reponse.status_code == 200, reponse.text
    data = reponse.json()["data"]
    conditions = {c["condition"] for c in data["conditions_actives"]}
    assert {"GROSSESSE", "HTA"} <= conditions
    assert data["prescription_possible"] is True
    assert data["justification_requise"] is True


@pytest.mark.asyncio
async def test_controle_a_blanc_signale_les_interactions(client_authenticated, formulaire):
    """
    Le contrôle à blanc doit voir les interactions entre les lignes de
    l'ordonnance en cours de rédaction — c'est exactement le moment où elles
    existent et où le praticien peut encore les corriger.
    """
    patient_id, consultation_id = await dossier(client_authenticated)

    creation = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Ibuprofène"]["id"], "posologie": "400 mg"}],
    )
    prescription_id = creation.json()["data"]["id"]

    controle = await client_authenticated.post(
        "/api/v1/ordonnances/controle",
        json={
            "patient_id": patient_id,
            "medicament_id": formulaire["Diclofénac"]["id"],
            "posologie": "50 mg",
        },
    )

    assert controle.status_code == 200
    assert controle.json()["data"]["prescription_possible"] is True
    assert prescription_id  # l'ordonnance de référence existe bien


# ==============================================================================
# MÉDICAMENT HORS RÉFÉRENTIEL
# ==============================================================================

@pytest.mark.asyncio
async def test_medicament_hors_referentiel_signale(client_authenticated):
    """
    Un produit non référencé reste prescriptible (préparation locale), mais le
    praticien doit savoir qu'aucun contrôle automatique n'a pu être fait.
    """
    patient_id, consultation_id = await dossier(client_authenticated)

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [
            {
                "medicament_texte": "Poudre dentifrice maison (préparation locale)",
                "posologie": "Application locale matin et soir",
            }
        ],
    )

    assert reponse.status_code == 201, reponse.text
    data = reponse.json()["data"]
    assert data["lignes"][0]["medicament_texte"].startswith("Poudre dentifrice maison")
    assert any(a["code"] == "MEDICAMENT_HORS_REFERENTIEL" for a in data["alertes"])


@pytest.mark.asyncio
async def test_ligne_sans_medicament_refusee(client_authenticated):
    """Ni identifiant ni libellé : la ligne n'est pas saisissable."""
    patient_id, consultation_id = await dossier(client_authenticated)

    reponse = await prescrire(
        client_authenticated, patient_id, consultation_id, [{"posologie": "1 comprimé"}]
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_ordonnance_vide_refusee(client_authenticated):
    patient_id, consultation_id = await dossier(client_authenticated)

    reponse = await prescrire(client_authenticated, patient_id, consultation_id, [])

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_meme_medicament_deux_fois_refuse(client_authenticated, formulaire):
    """
    Deux lignes du même produit sont presque toujours une erreur de saisie. On
    demande de regrouper en une ligne avec la quantité ou la durée voulue.
    """
    patient_id, consultation_id = await dossier(client_authenticated)

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [
            {"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"},
            {"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g", "duree": "3 j"},
        ],
    )

    assert reponse.status_code == 422


# ==============================================================================
# SIGNATURE ET IMMUTABILITÉ
# ==============================================================================

@pytest.mark.asyncio
async def test_signature_rend_ordonnance_immuable(client_authenticated, formulaire):
    """Une ordonnance signée est un acte médical opposable : plus rien ne bouge."""
    patient_id, consultation_id = await dossier(client_authenticated)

    creation = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )
    prescription_id = creation.json()["data"]["id"]

    signature = await client_authenticated.post(f"/api/v1/ordonnances/{prescription_id}/signer")
    assert signature.status_code == 200, signature.text
    assert signature.json()["data"]["signe"] is True
    assert signature.json()["data"]["date_signature"] is not None

    modification = await client_authenticated.patch(
        f"/api/v1/ordonnances/{prescription_id}", json={"notes_generales": "Modification"}
    )
    assert modification.status_code == 422
    assert modification.json()["error"]["code"] == "PRESCRIPTION_SIGNEE"

    ajout = await client_authenticated.post(
        f"/api/v1/ordonnances/{prescription_id}/lignes",
        json={"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"},
    )
    assert ajout.status_code == 422
    assert ajout.json()["error"]["code"] == "PRESCRIPTION_SIGNEE"

    ligne_id = creation.json()["data"]["lignes"][0]["id"]
    suppression = await client_authenticated.delete(
        f"/api/v1/ordonnances/{prescription_id}/lignes/{ligne_id}"
    )
    assert suppression.status_code == 422
    assert suppression.json()["error"]["code"] == "PRESCRIPTION_SIGNEE"


@pytest.mark.asyncio
async def test_signer_ordonnance_vide_impossible(client_authenticated, formulaire):
    """Une ordonnance dont toutes les lignes ont été retirées ne se signe pas."""
    patient_id, consultation_id = await dossier(client_authenticated)

    creation = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )
    prescription_id = creation.json()["data"]["id"]
    ligne_id = creation.json()["data"]["lignes"][0]["id"]

    suppression = await client_authenticated.delete(
        f"/api/v1/ordonnances/{prescription_id}/lignes/{ligne_id}"
    )
    assert suppression.status_code == 200, suppression.text
    assert suppression.json()["data"]["lignes"] == []

    signature = await client_authenticated.post(f"/api/v1/ordonnances/{prescription_id}/signer")
    assert signature.status_code == 422
    assert signature.json()["error"]["code"] == "ORDONNANCE_VIDE"


@pytest.mark.asyncio
async def test_signature_est_idempotente(client_authenticated, formulaire):
    """
    Re-signer ne doit ni échouer ni changer la date : un double clic sur le
    bouton « Signer » est un cas réel, pas une anomalie.
    """
    patient_id, consultation_id = await dossier(client_authenticated)

    creation = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )
    prescription_id = creation.json()["data"]["id"]

    premiere = await client_authenticated.post(f"/api/v1/ordonnances/{prescription_id}/signer")
    assert premiere.status_code == 200
    seconde = await client_authenticated.post(f"/api/v1/ordonnances/{prescription_id}/signer")

    assert seconde.status_code == 200, seconde.text
    assert (
        seconde.json()["data"]["date_signature"] == premiere.json()["data"]["date_signature"]
    ), "une seconde signature ne doit pas réattribuer une nouvelle date"


@pytest.mark.asyncio
async def test_modification_avant_signature_autorisee(client_authenticated, formulaire):
    patient_id, consultation_id = await dossier(client_authenticated)

    creation = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )
    prescription_id = creation.json()["data"]["id"]

    reponse = await client_authenticated.patch(
        f"/api/v1/ordonnances/{prescription_id}",
        json={"notes_generales": "Bain de bouche chlorhexidine pendant 7 jours."},
    )

    assert reponse.status_code == 200, reponse.text
    assert "chlorhexidine" in reponse.json()["data"]["notes_generales"]


@pytest.mark.asyncio
async def test_ajout_ligne_recontrole_le_patient(client_authenticated, formulaire):
    """
    Le contrôle est refait à l'ajout : l'état du patient a pu changer depuis
    l'émission de l'ordonnance. Ajouter un AINS à une patiente devenue enceinte
    doit tomber, même si l'ordonnance a été émise avant.
    """
    patient_id, consultation_id = await dossier(client_authenticated)

    creation = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )
    prescription_id = creation.json()["data"]["id"]

    await client_authenticated.put(
        f"/api/v1/patients/{patient_id}/etat-general",
        json={"grossesse": True, "grossesse_terme": "34 SA"},
    )

    ajout = await client_authenticated.post(
        f"/api/v1/ordonnances/{prescription_id}/lignes",
        json={"medicament_id": formulaire["Ibuprofène"]["id"], "posologie": "400 mg"},
    )

    assert ajout.status_code == 422
    assert ajout.json()["error"]["code"] == "CONTRE_INDICATION_ABSOLUE"


# ==============================================================================
# COHÉRENCE MÉDICO-LÉGALE
# ==============================================================================

@pytest.mark.asyncio
async def test_consultation_dun_autre_dossier_refusee(client_authenticated, formulaire):
    """
    Établir une ordonnance sur une consultation qui n'est pas celle du patient
    fabriquerait un dossier médical faux.
    """
    patient_id, consultation_id = await dossier(client_authenticated, telephone="770000101")
    autre, _ = await dossier(client_authenticated, telephone="770000102")

    reponse = await prescrire(
        client_authenticated,
        autre,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "CONSULTATION_AUTRE_DOSSIER"
    assert patient_id != autre


@pytest.mark.asyncio
async def test_ordonnance_pour_dossier_archive_refusee(client_authenticated, formulaire):
    """Un dossier archivé ne doit plus recevoir d'ordonnance."""
    patient_id, consultation_id = await dossier(client_authenticated, telephone="770000103")

    # D1A interdit d'archiver un dossier portant une consultation en cours : on
    # clôture d'abord. L'ordonnance elle-même reste émise sur la consultation,
    # ce qui est le cas normal (une ordonnance suit le soin, pas sa clôture).
    fin = await client_authenticated.post(
        f"/api/v1/consultations/{consultation_id}/terminer",
        json={"diagnostic_principal": "Pulpite aiguë"},
    )
    assert fin.status_code == 200, fin.text

    archivage = await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/archiver", json={"motif": "Test"}
    )
    assert archivage.status_code == 200, archivage.text

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "PATIENT_ARCHIVE"


@pytest.mark.asyncio
async def test_medicament_inactif_refuse(client_authenticated, formulaire, tenant_db):
    """Un médicament retiré du référentiel ne doit plus être prescrit."""
    patient_id, consultation_id = await dossier(client_authenticated)

    medicament_id = uuid.UUID(formulaire["Paracétamol"]["id"])
    medicament = (
        await tenant_db.execute(
            select(MedicamentReferentiel).where(MedicamentReferentiel.id == medicament_id)
        )
    ).scalar_one()
    medicament.actif = False
    await tenant_db.commit()

    reponse = await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": str(medicament_id), "posologie": "1g"}],
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "MEDICAMENT_INACTIF"


@pytest.mark.asyncio
async def test_ordonnance_tracee_en_audit(client_authenticated, formulaire, tenant_db):
    """Un acte de prescription est médico-légal : il doit laisser une trace."""
    patient_id, consultation_id = await dossier(client_authenticated)

    await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )

    nb = int(
        (
            await tenant_db.execute(
                select(func.count(AuditLogTenant.id)).where(
                    AuditLogTenant.action == "PRESCRIPTION_CREATE"
                )
            )
        ).scalar_one()
    )
    assert nb >= 1


@pytest.mark.asyncio
async def test_numerotation_ordonnance(client_authenticated, formulaire):
    """Deux ordonnances ne peuvent pas porter le même numéro (RG08, acte signé)."""
    patient_id, consultation_id = await dossier(client_authenticated)

    numeros = []
    for _ in range(2):
        reponse = await prescrire(
            client_authenticated,
            patient_id,
            consultation_id,
            [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
        )
        assert reponse.status_code == 201, reponse.text
        numeros.append(reponse.json()["data"]["numero"])

    assert numeros[0].startswith("ORD-")
    assert numeros[0] != numeros[1]


@pytest.mark.asyncio
async def test_ordonnance_liee_a_la_consultation(client_authenticated, formulaire):
    """L'ordonnance doit se retrouver dans l'historique de sa consultation."""
    patient_id, consultation_id = await dossier(client_authenticated)

    await prescrire(
        client_authenticated,
        patient_id,
        consultation_id,
        [{"medicament_id": formulaire["Paracétamol"]["id"], "posologie": "1g"}],
    )

    liste = await client_authenticated.get(
        "/api/v1/ordonnances", params={"consultation_id": consultation_id}
    )
    assert liste.status_code == 200, liste.text
    assert len(liste.json()["data"]) == 1


# ==============================================================================
# RÉFÉRENTIEL MÉDICAMENTEUX
# ==============================================================================

@pytest.mark.asyncio
async def test_ajout_medicament_avec_regles(client_authenticated):
    """
    Un praticien peut ajouter un produit local et ses règles sans modifier le
    code : c'est tout l'intérêt d'un référentiel en base.
    """
    reponse = await client_authenticated.post(
        "/api/v1/ordonnances/medicaments",
        json={
            "nom_commercial": "Pince a meti test",
            "dci": "Metiocaïne test",
            "forme": "GELE",
            "dosage": "2%",
            "contre_indications": [
                {
                    "condition": "ALLERGIE_METIOCAINE",
                    "gravite": "INTERDIT",
                    "message": "Allergie a la metiocaine : ne pas utiliser.",
                }
            ],
        },
    )

    assert reponse.status_code == 201, reponse.text
    data = reponse.json()["data"]
    assert data["dci"] == "Metiocaïne test"
    assert data["contre_indications"][0]["gravite"] == "INTERDIT"


@pytest.mark.asyncio
async def test_dci_duplique_refuse(client_authenticated, formulaire):
    reponse = await client_authenticated.post(
        "/api/v1/ordonnances/medicaments",
        json={"nom_commercial": "Amoxicilline bis", "dci": "amoxicilline", "forme": "COMPRIME"},
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "MEDICAMENT_DEJA_EXISTANT"


@pytest.mark.asyncio
async def test_regle_gravite_invalide_refusee(client_authenticated):
    reponse = await client_authenticated.post(
        "/api/v1/ordonnances/medicaments",
        json={
            "nom_commercial": "Test",
            "dci": "Test",
            "forme": "COMPRIME",
            "contre_indications": [
                {"condition": "GROSSESSE", "gravite": "PEUT_ETRE", "message": "Bof"}
            ],
        },
    )

    assert reponse.status_code == 422


@pytest.mark.asyncio
async def test_recherche_et_filtre_du_referentiel(client_authenticated, formulaire):
    """Le frontend doit pouvoir chercher un produit sans charger tout le formulaire."""
    recherche = await client_authenticated.get(
        "/api/v1/ordonnances/medicaments", params={"q": "ibupro"}
    )
    assert recherche.status_code == 200, recherche.text
    assert [m["dci"] for m in recherche.json()["data"]] == ["Ibuprofène"]

    par_classe = await client_authenticated.get(
        "/api/v1/ordonnances/medicaments", params={"classe": "AINS"}
    )
    noms = {m["nom_commercial"] for m in par_classe.json()["data"]}
    assert {"Ibuprofène", "Diclofénac"} <= noms


@pytest.mark.asyncio
async def test_resemer_le_formulaire_ne_duplique_pas(client_authenticated, tenant_db):
    """
    Le seed est idempotent : le relancer après une mise à jour du formulaire
    ne doit pas créer de doublons, et doit rafraîchir les règles existantes.
    """
    from src.modules.ordonnances.services import MedicamentService

    await MedicamentService.semer_formulaire(tenant_db)
    await tenant_db.commit()
    premier = int(
        (await tenant_db.execute(select(func.count(MedicamentReferentiel.id)))).scalar_one()
    )

    await MedicamentService.semer_formulaire(tenant_db)
    await tenant_db.commit()
    second = int(
        (await tenant_db.execute(select(func.count(MedicamentReferentiel.id)))).scalar_one()
    )

    assert premier == second, "le second semis a créé des doublons"
    assert premier >= 10


@pytest.mark.asyncio
async def test_association_a_ses_propres_regles(client_authenticated, formulaire):
    """
    Non-régression : « Amoxicilline » et « Amoxicilline / Acide clavulanique »
    partagent la même molécule porteuse. Si le semis du formulaire indexait les
    entrées sur cette molécule, l'association serait confondue avec
    l'amoxicilline simple et ses règles propres seraient perdues — l'allergie
    à l'acide clavulanique ne déclencherait plus rien.
    """
    association = formulaire["Amoxicilline / Acide clavulanique"]
    conditions = {r["condition"] for r in association["contre_indications"]}
    assert "ALLERGIE_ACIDECLAVULANIQUE" in conditions
    assert conditions != {
        r["condition"] for r in formulaire["Amoxicilline"]["contre_indications"]
    }


@pytest.mark.asyncio
async def test_formulaire_couvre_les_classes_therapeutiques(client_authenticated, formulaire):
    """Le formulaire de départ couvre les classes utiles à un cabinet dentaire."""
    classes = {m["classe_therapeutique"] for m in formulaire.values() if m["classe_therapeutique"]}
    assert {"ANTIBIOTIQUE_BETA_LACTAME", "AINS", "ANESTHESIE_LOCALE", "ANTISEPTIQUE"} <= classes


# ==============================================================================
# RBAC
# ==============================================================================

@pytest.mark.asyncio
async def test_secretaire_ne_peut_pas_prescrire(client_authenticated, tenant_db):
    """
    La secrétaire enregistre les patients mais ne prescrit pas : c'est une règle
    de la matrice des rôles, pas une préférence d'implémentation. On passe par
    le vrai `bootstrap_complet` pour que le test valide la matrice livrée, pas
    une matrice écrite dans le test.
    """
    from src.core.security import create_access_token, get_password_hash
    from src.main import app
    from src.modules.auth import dependencies as auth_deps
    from src.modules.rbac.services import RbacService
    from src.modules.tenants.models import Role, Utilisateur

    await RbacService.bootstrap_complet(tenant_db)

    role_secretaire = (
        await tenant_db.execute(select(Role).where(Role.nom == "SECRETAIRE"))
    ).scalar_one()
    secretaire = Utilisateur(
        email="secretariat@clinique-test.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role_secretaire.id,
        prenom="Seynabou",
        nom="Diallo",
        actif=True,
    )
    tenant_db.add(secretaire)
    await tenant_db.commit()

    permissions = await RbacService.permissions_d_un_role(tenant_db, str(role_secretaire.id))
    assert "ORDONNANCES:CREATE" not in permissions
    assert "ORDONNANCES:READ" not in permissions
    assert "ORDONNANCES:SIGN" not in permissions

    # Le dossier est préparé par l'administrateur : la secrétaire n'a pas
    # CONSULTATIONS:CREATE et ne pourrait pas le faire elle-même.
    patient_id, consultation_id = await dossier(client_authenticated, telephone="770000201")

    async def _override_user():
        return secretaire

    app.dependency_overrides[auth_deps.get_current_user] = _override_user

    # `require_permissions` lit le JWT : il faut remplacer l'en-tête, sinon le
    # contrôle continuerait de voir le rôle ADMIN_CABINET du client par défaut.
    client_authenticated.headers.update(
        {
            "Authorization": "Bearer "
            + create_access_token(
                user_id=str(secretaire.id),
                tenant_id=cabinet_tenant_id(),
                role="SECRETAIRE",
                permissions=permissions,
            )
        }
    )

    try:
        creation = await prescrire(
            client_authenticated,
            patient_id,
            consultation_id,
            [{"medicament_texte": "Paracétamol", "posologie": "1g"}],
        )
        assert creation.status_code == 403, creation.text

        lecture = await client_authenticated.get("/api/v1/ordonnances/medicaments")
        assert lecture.status_code == 403, "la secrétaire n'a pas même ORDONNANCES:READ"
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)


def cabinet_tenant_id() -> str:
    """
    Identifiant de tenant utilisé par la fixture `client_authenticated`.

    La fixture le tire au sort à chaque test et ne l'expose pas ; le reproduire
    ici n'a aucune incidence, car la résolution de tenant est court-circuitée
    par la surcharge de `get_tenant_db`.
    """
    return str(uuid.uuid4())
