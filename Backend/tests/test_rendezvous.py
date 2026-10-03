"""
Tests du module Rendez-vous (D2B).

Règle couverte :
  RG09 — chaque rendez-vous est rattaché à un patient, un praticien et un site
         identifiés, et occupe un créneau qui ne peut être réservé qu'une fois

L'axe central n'est pas « le rendez-vous est créé » mais **ce qui l'empêche de
se chevaucher**, et selon quelle autorité :
  - le contrôle applicatif produit un message exploitable (« Mme Diop occupies
    09:00 ») ;
  - la contrainte d'exclusion PostgreSQL est la GARANTIE, y compris quand deux
    secrétaires valident au même instant.
"""

from datetime import date, datetime, timedelta, timezone
from typing import AsyncGenerator
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.models import (
    Consultation,
    CreneauFauteuil,
    Fauteuil,
    Patient,
    RendezVous,
    Utilisateur,
)

# 2026-10-05 est un lundi. Les tests de disponibilités en dépendent.
LUNDI = date(2026, 10, 5)

# 09:00 UTC : heure d'ouverture, largement dans les bornes 06h-23h.
def _a(heure: int, minute: int = 0, jour: date = LUNDI) -> str:
    return f"{jour.isoformat()}T{heure:02d}:{minute:02d}:00+00:00"


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest_asyncio.fixture
async def decor(client_authenticated, cabinet) -> dict:
    """
    Un cabinet prêt à prendre des rendez-vous : praticien rattaché, salle,
    fauteuil, disponibilités du lundi.

    Reproduit ce que fait le provisioning en D2A (rattachement) et ce que fait
    l'administrateur ensuite (salle, fauteuil, horaires).
    """
    cabinet_id = cabinet["cabinet"].id
    praticien_id = cabinet["praticien"].id

    r = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement", json={}
    )
    assert r.status_code == 200, r.text

    salle = (
        await client_authenticated.post(
            f"/api/v1/cabinets/{cabinet_id}/salles", json={"nom": "Salle 1"}
        )
    ).json()["data"]["id"]

    fauteuil_1 = (
        await client_authenticated.post(
            f"/api/v1/salles/{salle}/fauteuils", json={"numero": "F1"}
        )
    ).json()["data"]["id"]
    fauteuil_2 = (
        await client_authenticated.post(
            f"/api/v1/salles/{salle}/fauteuils", json={"numero": "F2"}
        )
    ).json()["data"]["id"]

    # Disponibilité du lundi 09:00-12:00, comme un dentiste qui travaille le matin.
    dispo = await client_authenticated.post(
        f"/api/v1/praticiens/{praticien_id}/disponibilites",
        json={"jour_semaine": 0, "heure_debut": "09:00", "heure_fin": "12:00"},
    )
    assert dispo.status_code == 201, dispo.text

    return {
        "cabinet_id": str(cabinet_id),
        "praticien_id": str(praticien_id),
        "salle_id": str(salle),
        "fauteuil_1": str(fauteuil_1),
        "fauteuil_2": str(fauteuil_2),
    }


@pytest_asyncio.fixture
async def second_praticien(tenant_db, cabinet, client_authenticated) -> str:
    """
    Second praticien rattaché au même site.

    Indispensable pour isoler la contrainte « fauteuil » de la contrainte
    « praticien » : sans un second praticien, tout conflit passerait d'abord par
    le praticien et la contrainte fauteuil ne serait jamais réellement exercée.
    """
    from src.core.security import get_password_hash
    from src.modules.rbac.services import RbacService
    from src.modules.tenants.models import Role

    await RbacService.bootstrap_complet(tenant_db)
    role = (await tenant_db.execute(select(Role).where(Role.nom == "ASSISTANT"))).scalar_one()
    utilisateur = Utilisateur(
        email="dr.second@clinique-test.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Docteur",
        nom="Second",
        actif=True,
    )
    tenant_db.add(utilisateur)
    await tenant_db.commit()

    creation = await client_authenticated.post(
        "/api/v1/praticiens", json={"utilisateur_id": str(utilisateur.id)}
    )
    assert creation.status_code == 201, creation.text
    praticien_id = creation.json()["data"]["id"]

    rattachement = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet['cabinet'].id}/praticiens/{praticien_id}/rattachement",
        json={},
    )
    assert rattachement.status_code == 200, rattachement.text
    return praticien_id


@pytest_asyncio.fixture
async def patient_id(client_authenticated) -> str:
    r = await client_authenticated.post(
        "/api/v1/patients",
        json={
            "prenom": "Aminata",
            "nom": "Diop",
            "date_naissance": "1990-05-12",
            "sexe": "F",
            "telephone_1": "771234567",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def prendre(client, decor, patient: str, debut: str, **kw):
    """Raccourci : crée un rendez-vous, avec le fauteuil par défaut."""
    payload = {
        "patient_id": patient,
        "praticien_id": decor["praticien_id"],
        "debut": debut,
        "duree_minutes": 30,
        "motif": "Contrôle dentaire",
        "fauteuil_id": decor["fauteuil_1"],
        **kw,
    }
    return await client.post("/api/v1/rendez-vous", json=payload)


# ==============================================================================
# MOTEUR (pur, sans base)
# ==============================================================================

def test_creneaux_adjacents_ne_se_chevauchent_pas():
    """
    Deux rendez-vous de 30 minutes s'enchaînent à 09:00 et 09:30. Si les bornes
    étaient fermées, le cabinet ne pourrait pas remplir une matinée de 9h-12h
    que par un rendez-vous sur deux.
    """
    from src.common.rendezvous import chevauchent

    base = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)
    assert chevauchent(base, base + timedelta(minutes=30),
                       base + timedelta(minutes=30), base + timedelta(minutes=60)) is False
    assert chevauchent(base, base + timedelta(minutes=30),
                       base + timedelta(minutes=20), base + timedelta(minutes=50)) is True


def test_cycle_de_vie_est_ferme():
    """
    Un rendez-vous annulé ne se rouvre pas, et un rendez-vous terminé ne
    remonte pas le temps : c'est ce qui rend l'historique de l'agenda fiable.
    """
    from src.common.rendezvous import (
        ANNULE,
        EN_SALLE_ATTENTE,
        PLANIFIE,
        TERMINEE,
        TransitionInterdite,
        transition_possible,
        verifier_transition,
    )

    assert transition_possible(PLANIFIE, EN_SALLE_ATTENTE)
    assert transition_possible(PLANIFIE, ANNULE)
    assert transition_possible(EN_SALLE_ATTENTE, TERMINEE) is False  # passe par consultation

    with pytest.raises(TransitionInterdite):
        verifier_transition(ANNULE, PLANIFIE)
    with pytest.raises(TransitionInterdite):
        verifier_transition(TERMINEE, PLANIFIE)


def test_transition_identique_est_idempotente():
    """Re-confirmer un rendez-vous confirmé, ou double-cliquer sur « annuler »,
    ne doit pas échouer : c'est un cas réel d'interface."""
    from src.common.rendezvous import CONFIRME, verifier_transition

    verifier_transition(CONFIRME, CONFIRME)  # ne lève pas


def test_message_de_transition_dite_ce_qu_on_peut_faire():
    """Le message doit guider le secrétariat, pas citer une règle de code."""
    from src.common.rendezvous import ANNULE, PLANIFIE, TransitionInterdite, verifier_transition

    with pytest.raises(TransitionInterdite) as exc:
        verifier_transition(PLANIFIE, "TERMINEE")
    assert "Impossible" in exc.value.message
    assert "Confirmé" in exc.value.message, "les transitions possibles doivent être listées"


@pytest.mark.parametrize(
    "debut, duree, attendu",
    [
        ("2026-10-05T05:00:00+00:00", 30, "avant l'ouverture"),
        ("2026-10-05T23:00:00+00:00", 30, "après la fermeture"),
        ("2026-10-05T23:30:00+00:00", 30, "traverse minuit"),
        ("2026-10-05T22:30:00+00:00", 30, None),
    ],
)
def test_creneaux_hors_bornes_refuses(debut, duree, attendu):
    """
    Bornes de sécurité sur la saisie. Une prise à 5h du matin, une fin après la
    fermeture, ou un créneau qui traverse minuit (signe d'une date saisie de
    travers) sont presque toujours des fautes de frappe.
    """
    from src.common.rendezvous import HEURE_FERMETURE, HEURE_OUVERTURE, borne_horaire

    d = datetime.fromisoformat(debut)
    message = borne_horaire(d, d + timedelta(minutes=duree))

    if attendu is None:
        assert message is None, message
    else:
        assert message is not None, "ce créneau aurait dû être refusé"
        assert attendu in message


def test_fermeture_a_23h_pas_a_minuit():
    """
    Non-régression de la règle : 23h00 est la dernière minute admissible, pas
    23h59. Une borne mal comprise laisserait planifier des soins de nuit.
    """
    from src.common.rendezvous import HEURE_FERMETURE, borne_horaire

    d = datetime(2026, 10, 5, HEURE_FERMETURE - 1, 30, tzinfo=timezone.utc)
    assert borne_horaire(d, d + timedelta(minutes=30)) is None


# ==============================================================================
# CRÉATION
# ==============================================================================

@pytest.mark.asyncio
async def test_creation_rendez_vous(client_authenticated, decor, patient_id):
    r = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert r.status_code == 201, r.text
    data = r.json()["data"]

    assert data["patient_id"] == patient_id
    assert data["praticien_id"] == decor["praticien_id"]
    assert data["fauteuil_id"] == decor["fauteuil_1"]
    assert data["fauteuil_numero"] == "F1"
    assert data["statut"] == "PLANIFIE"
    assert data["statut_libelle"] == "Planifié"
    assert data["duree_minutes"] == 30
    assert data["numero_dossier"], "le dossier patient est pré-jointe pour l'affichage"
    assert data["praticien_nom"] == "Test"
    assert "CONFIRME" in data["transitions_possibles"]


@pytest.mark.asyncio
async def test_hors_disponibilites_signale_mais_accepte(
    client_authenticated, decor, patient_id
):
    """
    Le cabinet n'a déclaré que le lundi 09:00-12:00 : un rendez-vous le mardi est
    ACCEPTE (une urgence ne peut pas attendre), mais la réponse le signale.
    """
    r = await prendre(client_authenticated, decor, patient_id, _a(9, jour=date(2026, 10, 6)))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["hors_disponibilites"] is True
    assert "hors des disponibilités" in r.json()["message"]


@pytest.mark.asyncio
async def test_dans_les_disponibilites_non_signale(
    client_authenticated, decor, patient_id
):
    r = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert r.json()["data"]["hors_disponibilites"] is False


@pytest.mark.asyncio
async def test_creation_avec_patient_inexistant(client_authenticated, decor):
    r = await prendre(
        client_authenticated, decor, "00000000-0000-0000-0000-000000000000", _a(9)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_creation_sans_fauteuil_autorisee(client_authenticated, decor, patient_id):
    """Une visite d'évaluation ou une urgence peut n'avoir pas de fauteuil."""
    r = await prendre(
        client_authenticated, decor, patient_id, _a(9), fauteuil_id=None
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["fauteuil_id"] is None


@pytest.mark.asyncio
async def test_fauteuil_d_un_autre_cabinet_refuse(
    client_authenticated, decor, patient_id, cabinet
):
    """Réserver un fauteuil d'un autre site produirait un rendez-vous impossible."""
    import uuid as _uuid

    # Un fauteuil qui n'existe pas est un 404, pas un 422 métier.
    r = await prendre(
        client_authenticated, decor, patient_id, _a(9),
        fauteuil_id=str(_uuid.uuid4()),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patient_archives_refuse(client_authenticated, decor, patient_id):
    archivage = await client_authenticated.post(
        f"/api/v1/patients/{patient_id}/archiver", json={"motif": "Test"}
    )
    assert archivage.status_code == 200, archivage.text

    r = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PATIENT_ARCHIVE"


@pytest.mark.asyncio
async def test_statut_terminal_refuse_a_la_creation(client_authenticated, decor, patient_id):
    """Un rendez-vous ne se saisit pas « terminé » : c'est un résultat."""
    r = await prendre(client_authenticated, decor, patient_id, _a(9), statut="TERMINEE")
    assert r.status_code == 422


# ==============================================================================
# CONFLITS — le contrôle applicatif
# ==============================================================================

@pytest.mark.asyncio
async def test_conflit_sur_le_praticien_refuse(client_authenticated, decor, patient_id):
    """
    Le cas central : un créneau déjà pris par un autre patient, MÊME praticien,
    mais fauteuil DIFFÉRENT. C'est le praticien qui est la ressource rare.
    """
    premier = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert premier.status_code == 201, premier.text

    autre = (
        await client_authenticated.post(
            "/api/v1/patients",
            json={
                "prenom": "Babacar",
                "nom": "Fall",
                "date_naissance": "1985-01-01",
                "sexe": "M",
                "telephone_1": "771000222",
            },
        )
    ).json()["data"]["id"]

    second = await prendre(
        client_authenticated, decor, autre, _a(9, 15), fauteuil_id=decor["fauteuil_2"]
    )
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "CRENEAU_DEJA_OCCUPE"


@pytest.mark.asyncio
async def test_le_message_de_conflit_nomme_l_obstacle(client_authenticated, decor, patient_id):
    """
    Un message « créneau occupé » est inexploitable au téléphone. La réponse doit
    dire AVEC QUI et POUR QUOI : c'est ce qui permet de proposer 09:30.
    """
    await prendre(client_authenticated, decor, patient_id, _a(9))

    r = await prendre(
        client_authenticated, decor, patient_id, _a(9, 15), fauteuil_id=decor["fauteuil_2"]
    )
    assert r.status_code == 422
    conflits = r.json()["error"]["details"]["conflits"]

    praticien = [c for c in conflits if c["ressource"] == "PRATICIEN"]
    assert len(praticien) == 1
    assert praticien[0]["patient_nom"] == "Diop"
    assert praticien[0]["motif"] == "Contrôle dentaire"
    assert "Diop" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_conflit_sur_le_fauteuil_refuse(
    client_authenticated, decor, patient_id, second_praticien
):
    """
    Deux rendez-vous sur le même fauteuil, avec deux praticiens DIFFÉRENTS :
    le praticien n'est pas en cause, c'est le fauteuil qui est saturé.
    """
    premier = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert premier.status_code == 201, premier.text

    r = await client_authenticated.post(
        "/api/v1/rendez-vous",
        json={
            "patient_id": patient_id,
            "praticien_id": second_praticien,
            "debut": _a(9, 15),
            "duree_minutes": 30,
            "motif": "Urgence dentaire",
            "fauteuil_id": decor["fauteuil_1"],
        },
    )
    assert r.status_code == 422
    conflits = r.json()["error"]["details"]["conflits"]
    assert any(c["ressource"] == "FAUTEUIL" for c in conflits)
    assert not any(c["ressource"] == "PRATICIEN" for c in conflits), (
        "les deux praticiens sont distincts : seul le fauteuil doit être en cause"
    )


@pytest.mark.asyncio
async def test_rendez_vous_adjacents_autorises(client_authenticated, decor, patient_id):
    """
    09:00-09:30 puis 09:30-10:00 doivent passer. Si les bornes étaient
    fermées, un cabinet ne pourrait pas remplir sa matinée.
    """
    premier = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert premier.status_code == 201, premier.text

    second = await prendre(
        client_authenticated, decor, patient_id, _a(9, 30), fauteuil_id=decor["fauteuil_2"]
    )
    assert second.status_code == 201, second.text


@pytest.mark.asyncio
async def test_meme_patient_peut_avoir_deux_rendez_voisins(client_authenticated, decor, patient_id):
    """Rien n'interdit à un patient d'avoir deux rendez-vous consécutifs."""
    await prendre(client_authenticated, decor, patient_id, _a(9))
    second = await prendre(
        client_authenticated, decor, patient_id, _a(9, 30), fauteuil_id=decor["fauteuil_2"]
    )
    assert second.status_code == 201, second.text


# ==============================================================================
# CONFLITS — la garantie de la base
# ==============================================================================

@pytest.mark.asyncio
async def test_contrainte_dexclusion_refuse_le_double_reservation(
    client_authenticated, decor, patient_id, tenant_db
):
    """
    Non-régression : la garantie vient de PostgreSQL, pas du service.

    On écrit directement en base, sans passer par l'API : c'est exactement ce que
    ferait un second secrétariat dont la vérification applicative s'est exécutée
    avant le premier INSERT. Le service ne peut pas l'empêcher ; seule la
    contrainte peut.
    """
    import uuid as _uuid

    await prendre(client_authenticated, decor, patient_id, _a(9))

    debut = datetime(2026, 10, 5, 9, 15, tzinfo=timezone.utc)
    intrus = RendezVous(
        id=_uuid.uuid4(),
        patient_id=patient_id,
        cabinet_id=_uuid.UUID(decor["cabinet_id"]),
        praticien_id=_uuid.UUID(decor["praticien_id"]),
        debut=debut,
        fin=debut + timedelta(minutes=30),
        motif="Écriture directe, hors API",
        type_motif="AUTRE",
        statut="PLANIFIE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    tenant_db.add(intrus)

    with pytest.raises(IntegrityError) as exc:
        await tenant_db.commit()
    await tenant_db.rollback()

    assert "ex_rendez_vous_praticien" in str(exc.value)


@pytest.mark.asyncio
async def test_annulation_libere_automatiquement_le_creneau(
    client_authenticated, decor, patient_id
):
    """
    Un rendez-vous annulé ne réserve plus le créneau : la contrainte ignore les
    statuts ANNULE et ABSENT. Aucune requête de nettoyage n'est nécessaire.
    """
    premier = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = premier.json()["data"]["id"]

    annulation = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut",
        params={"statut": "ANNULE", "motif": "Patient empêché"},
    )
    assert annulation.status_code == 200, annulation.text

    second = await prendre(
        client_authenticated, decor, patient_id, _a(9), fauteuil_id=decor["fauteuil_2"]
    )
    assert second.status_code == 201, (
        "le créneau n'a pas été libéré après annulation"
    )


@pytest.mark.asyncio
async def test_absent_libere_aussi_le_creneau(client_authenticated, decor, patient_id):
    """Un rendez-vous manqué libère aussi la place : le patient ne viendra pas."""
    premier = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = premier.json()["data"]["id"]

    absence = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": "ABSENT"}
    )
    assert absence.status_code == 200, absence.text

    second = await prendre(
        client_authenticated, decor, patient_id, _a(9), fauteuil_id=decor["fauteuil_2"]
    )
    assert second.status_code == 201, second.text


# ==============================================================================
# CYCLE DE VIE
# ==============================================================================

@pytest.mark.asyncio
async def test_parcours_complet_du_rendez_vous(client_authenticated, decor, patient_id):
    """Planifié -> Confirmé -> Salle d'attente -> Consultation."""
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    url = f"/api/v1/rendez-vous/{rendez_vous_id}"

    for statut, attendu in (
        ("CONFIRME", "Confirmé"),
        ("EN_SALLE_ATTENTE", "En salle d'attente"),
        ("EN_CONSULTATION", "En consultation"),
    ):
        r = await client_authenticated.post(f"{url}/statut", params={"statut": statut})
        assert r.status_code == 200, f"{statut} -> {r.text}"
        assert r.json()["data"]["statut_libelle"] == attendu


@pytest.mark.asyncio
async def test_transition_interdite_refusee(client_authenticated, decor, patient_id):
    """Sauter l'étape « salle d'attente » doit échouer, pas passer inaperçu."""
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": "TERMINEE"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "TRANSITION_INTERDITE"


@pytest.mark.asyncio
async def test_annulation_exige_un_motif(client_authenticated, decor, patient_id):
    """Un rendez-vous annulé sans motif est inexploitable six mois plus tard."""
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": "ANNULE"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "MOTIF_ANNULATION_REQUIS"


@pytest.mark.asyncio
async def test_annulation_conserve_le_motif(client_authenticated, decor, patient_id):
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut",
        params={"statut": "ANNULE", "motif": "Patient empêché"},
    )
    assert r.json()["data"]["motif_annulation"] == "Patient empêché"


@pytest.mark.asyncio
@pytest.mark.parametrize("statut_final", ["ANNULE", "ABSENT", "TERMINEE"])
async def test_statut_terminal_libere_le_fauteuil(
    client_authenticated, decor, patient_id, tenant_db, statut_final
):
    """
    Non-régression : un rendez-vous arrivé à son terme rend le fauteuil.

    La contrainte d'exclusion de `creneaux_fauteuil` ne regarde PAS le statut du
    rendez-vous (il vit dans une autre table), et elle est inconditionnelle par
    choix — un fauteuil en panne doit rester bloqué. C'est donc le service qui
    libère. Sans cela, le fauteuil d'un rendez-vous annulé resterait occupé
    à jamais, et le cabinet finirait sans une seule place libre.

    Paramétré sur les trois statuts terminaux : les trois doivent libérer.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    assert creation.status_code == 201, creation.text
    rendez_vous_id = creation.json()["data"]["id"]

    # Le fauteuil est bien occupé tant que le rendez-vous vit.
    occupation = (
        await tenant_db.execute(
            select(CreneauFauteuil).where(CreneauFauteuil.rendez_vous_id == rendez_vous_id)
        )
    ).scalar_one()
    assert occupation.fauteuil_id == uuid.UUID(decor["fauteuil_1"])

    params = {"statut": statut_final}
    if statut_final == "ANNULE":
        params["motif"] = "Patient empêché"

    # « Terminé » ne s'atteint qu'après une consultation : le cycle est
    # Planifié → Confirmé → Salle d'attente → Consultation → Terminé. Sauter
    # l'étape intermédiaire est refusé, et c'est voulu.
    if statut_final == "TERMINEE":
        for etape in ("CONFIRME", "EN_SALLE_ATTENTE", "EN_CONSULTATION"):
            r = await client_authenticated.post(
                f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": etape}
            )
            assert r.status_code == 200, f"{etape} -> {r.text}"

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params=params
    )
    assert r.status_code == 200, r.text

    restantes = (
        await tenant_db.execute(
            select(CreneauFauteuil).where(CreneauFauteuil.rendez_vous_id == rendez_vous_id)
        )
    ).scalars().all()
    assert restantes == [], "le fauteuil n'a pas été libéré"

    # Et le fauteuil redevient réservable.
    autre = await prendre(
        client_authenticated, decor, patient_id, _a(9), fauteuil_id=decor["fauteuil_1"]
    )
    assert autre.status_code == 201, autre.text


@pytest.mark.asyncio
async def test_changer_statut_idempotent(client_authenticated, decor, patient_id):
    """Double-clic sur le même bouton : pas d'erreur."""
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    url = f"/api/v1/rendez-vous/{rendez_vous_id}/statut"

    assert (await client_authenticated.post(url, params={"statut": "CONFIRME"})).status_code == 200
    assert (await client_authenticated.post(url, params={"statut": "CONFIRME"})).status_code == 200


# ==============================================================================
# REPORT
# ==============================================================================

@pytest.mark.asyncio
async def test_report_libere_l_ancien_creneau(client_authenticated, decor, patient_id):
    """
    Reporter déplace le rendez-vous : l'ancien créneau ET l'ancien fauteuil
    doivent être libérés, sinon le cabinet perd une place.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/planifier",
        params={"debut": _a(10), "duree_minutes": 30, "motif_report": "Patient en retard"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["debut"].startswith("2026-10-05T10:00")

    # L'ancien créneau est réutilisable.
    autre = await prendre(
        client_authenticated, decor, patient_id, _a(9), fauteuil_id=decor["fauteuil_1"]
    )
    assert autre.status_code == 201, autre.text


@pytest.mark.asyncio
async def test_report_sur_creneau_occupe_refuse(client_authenticated, decor, patient_id):
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    await prendre(
        client_authenticated, decor, patient_id, _a(10), fauteuil_id=decor["fauteuil_2"]
    )

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/planifier",
        params={"debut": _a(10), "duree_minutes": 30},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CRENEAU_DEJA_OCCUPE"


@pytest.mark.asyncio
async def test_report_ne_conflite_pas_avec_lui_meme(
    client_authenticated, decor, patient_id
):
    """
    Reporter un rendez-vous sur son PROPRE créneau doit être possible : c'est le
    cas réel quand on change seulement sa durée ou son fauteuil. L'exclusion de
    soi-même est ce qui l'autorise.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/planifier",
        params={"debut": _a(9), "duree_minutes": 45},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["duree_minutes"] == 45


@pytest.mark.asyncio
async def test_report_apres_debut_refuse(client_authenticated, decor, patient_id):
    """Un patient déjà en salle d'attente ne se reprogramme pas."""
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": "EN_SALLE_ATTENTE"}
    )

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/planifier",
        params={"debut": _a(11), "duree_minutes": 30},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "REPORT_NON_AUTORISE"


# ==============================================================================
# OUVERTURE DE CONSULTATION
# ==============================================================================

@pytest.mark.asyncio
async def test_ouvrir_consultation_reprend_le_fauteuil(
    client_authenticated, decor, patient_id
):
    """
    C'est le SEUL endroit où `consultations.fauteuil_id` est posé : le fauteuil
    vient de l'occupation du rendez-vous. C'est ce qui empêche l'agenda et le
    dossier de diverger sur le lieu du soin.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": "CONFIRME"}
    )

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/consultation"
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]

    assert data["rendez_vous_id"] == rendez_vous_id
    assert data["fauteuil_id"] == decor["fauteuil_1"]
    assert data["statut"] == "EN_COURS"

    relu = await client_authenticated.get(f"/api/v1/rendez-vous/{rendez_vous_id}")
    assert relu.json()["data"]["statut"] == "EN_CONSULTATION"
    assert relu.json()["data"]["consultation_id"] == data["id"]


@pytest.mark.asyncio
async def test_ouvrir_consultation_exige_un_rdv_confirme(
    client_authenticated, decor, patient_id
):
    """Un rendez-vous planifié mais non confirmé peut ne pas avoir lieu."""
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/consultation"
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "RENDEZ_VOUS_NON_CONFIRME"


@pytest.mark.asyncio
async def test_une_seule_consultation_par_rendez_vous(
    client_authenticated, decor, patient_id
):
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut", params={"statut": "CONFIRME"}
    )

    assert (
        await client_authenticated.post(f"/api/v1/rendez-vous/{rendez_vous_id}/consultation")
    ).status_code == 201

    second = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/consultation"
    )
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "CONSULTATION_DEJA_OUVERTE"


@pytest.mark.asyncio
async def test_consultation_refusee_si_rdv_annule(client_authenticated, decor, patient_id):
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/statut",
        params={"statut": "ANNULE", "motif": "Patient empêché"},
    )

    r = await client_authenticated.post(
        f"/api/v1/rendez-vous/{rendez_vous_id}/consultation"
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "RENDEZ_VOUS_NON_JOIGNABLE"


# ==============================================================================
# BLOCAGE DE FAUTEUIL
# ==============================================================================

@pytest.mark.asyncio
async def test_bloquer_un_fauteuil_hors_service(client_authenticated, decor):
    r = await client_authenticated.post(
        "/api/v1/rendez-vous/fauteuils/blocage",
        json={
            "fauteuil_id": decor["fauteuil_2"],
            "debut": _a(14),
            "duree_minutes": 120,
            "motif": "MAINTENANCE",
            "motif_detail": "Compresseur HS",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["motif_libelle"] == "Maintenance"


@pytest.mark.asyncio
async def test_motif_ren_dez_vous_refuse_a_la_saisie(client_authenticated, decor):
    """
    « RENDEZ_VOUS » est posé par le module. Le laisser saisissable
    permettrait de fabriquer une occupation sans rendez-vous associated.
    """
    r = await client_authenticated.post(
        "/api/v1/rendez-vous/fauteuils/blocage",
        json={
            "fauteuil_id": decor["fauteuil_2"],
            "debut": _a(14),
            "duree_minutes": 60,
            "motif": "RENDEZ_VOUS",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_bloquer_un_fauteuil_deja_reserve_refuse(client_authenticated, decor, patient_id):
    """On ne bloque pas un fauteuil qui a un rendez-vous : on le déplace."""
    await prendre(client_authenticated, decor, patient_id, _a(14))

    r = await client_authenticated.post(
        "/api/v1/rendez-vous/fauteuils/blocage",
        json={
            "fauteuil_id": decor["fauteuil_1"],
            "debut": _a(14),
            "duree_minutes": 60,
            "motif": "MAINTENANCE",
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CRENEAU_DEJA_OCCUPE"


@pytest.mark.asyncio
async def test_rendez_vous_refuse_sur_fauteuil_bloque(
    client_authenticated, decor, patient_id, second_praticien
):
    """Le blocage doit empêcher la réservation, pas seulement l'afficher."""
    await client_authenticated.post(
        "/api/v1/rendez-vous/fauteuils/blocage",
        json={
            "fauteuil_id": decor["fauteuil_1"],
            "debut": _a(14),
            "duree_minutes": 120,
            "motif": "REPARATION",
        },
    )

    r = await client_authenticated.post(
        "/api/v1/rendez-vous",
        json={
            "patient_id": patient_id,
            "praticien_id": second_praticien,
            "debut": _a(14, 30),
            "duree_minutes": 30,
            "motif": "Contrôle",
            "fauteuil_id": decor["fauteuil_1"],
        },
    )
    assert r.status_code == 422
    conflits = r.json()["error"]["details"]["conflits"]
    fauteuil = [c for c in conflits if c["ressource"] == "FAUTEUIL"]
    assert fauteuil and "Réparation" in fauteuil[0]["motif"]


@pytest.mark.asyncio
async def test_debloquer_un_fauteuil(client_authenticated, decor):
    creation = await client_authenticated.post(
        "/api/v1/rendez-vous/fauteuils/blocage",
        json={
            "fauteuil_id": decor["fauteuil_2"],
            "debut": _a(14),
            "duree_minutes": 60,
            "motif": "MAINTENANCE",
        },
    )
    creneau_id = creation.json()["data"]["id"]

    r = await client_authenticated.delete(f"/api/v1/rendez-vous/fauteuils/blocage/{creneau_id}")
    assert r.status_code == 204, r.text


@pytest.mark.asyncio
async def test_supprimer_une_occupation_de_rendez_vous_refuse(
    client_authenticated, decor, patient_id, tenant_db
):
    """
    L'occupation d'un rendez-vous ne se supprime pas : c'est le rendez-vous
    qu'il faut annuler, sinon le fauteuil resterait réservé sans que personne
    ne le sache.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(14))
    rendez_vous_id = creation.json()["data"]["id"]

    occupation = (
        await tenant_db.execute(
            select(CreneauFauteuil).where(CreneauFauteuil.rendez_vous_id == rendez_vous_id)
        )
    ).scalar_one()

    r = await client_authenticated.delete(
        f"/api/v1/rendez-vous/fauteuils/blocage/{occupation.id}"
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "OCCUPATION_LIEE_A_UN_RDV"


# ==============================================================================
# AGENDA & CRÉNEAUX LIBRES
# ==============================================================================

@pytest.mark.asyncio
async def test_agenda_renvoie_rendez_vous_et_indisponibilites(
    client_authenticated, decor, patient_id
):
    """
    Les deux dans la même réponse : un planning qui ignore un fauteuil en
    réparation propose un créneau qu'on ne pourra pas honorer.
    """
    await prendre(client_authenticated, decor, patient_id, _a(9))
    await client_authenticated.post(
        "/api/v1/rendez-vous/fauteuils/blocage",
        json={
            "fauteuil_id": decor["fauteuil_2"],
            "debut": _a(10),
            "duree_minutes": 120,
            "motif": "MAINTENANCE",
            "motif_detail": "Compresseur HS",
        },
    )

    r = await client_authenticated.get(
        "/api/v1/rendez-vous/agenda", params={"date": LUNDI.isoformat()}
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["nb_rendez_vous"] == 1
    assert len(data["indisponibilites"]) == 1
    assert data["indisponibilites"][0]["fauteuil_numero"] == "F2"
    assert data["indisponibilites"][0]["motif_libelle"] == "Maintenance"
    assert data["rendez_vous"][0]["numero_dossier"]


@pytest.mark.asyncio
async def test_agenda_compte_les_annules_separement(
    client_authenticated, decor, patient_id
):
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    await client_authenticated.post(
        f"/api/v1/rendez-vous/{creation.json()['data']['id']}/statut",
        params={"statut": "ANNULE", "motif": "Empêché"},
    )

    r = await client_authenticated.get(
        "/api/v1/rendez-vous/agenda", params={"date": LUNDI.isoformat()}
    )
    data = r.json()["data"]
    assert data["nb_rendez_vous"] == 0, "un rendez-vous annulé n'occupe plus l'agenda"
    assert data["nb_annules"] == 1


@pytest.mark.asyncio
async def test_creneaux_libres_retranchent_le_rendez_vous(
    client_authenticated, decor, patient_id
):
    """
    09:00-12:00 donne six créneaux de 30 min. Après un rendez-vous de 30 min à
    09:00, il doit en rester cinq.
    """
    avant = await client_authenticated.get(
        "/api/v1/rendez-vous/creneaux-libres",
        params={"praticien_id": decor["praticien_id"], "date": LUNDI.isoformat()},
    )
    assert avant.status_code == 200, avant.text
    assert len(avant.json()["data"]) == 6

    await prendre(client_authenticated, decor, patient_id, _a(9))

    apres = await client_authenticated.get(
        "/api/v1/rendez-vous/creneaux-libres",
        params={"praticien_id": decor["praticien_id"], "date": LUNDI.isoformat()},
    )
    restants = apres.json()["data"]
    assert len(restants) == 5
    assert all(not c["debut"].endswith("T09:00:00+00:00") for c in restants)


@pytest.mark.asyncio
async def test_creneaux_libres_respectent_la_duree_demandee(
    client_authenticated, decor, patient_id
):
    """Une prothèse ne se propose pas en 30 minutes."""
    r = await client_authenticated.get(
        "/api/v1/rendez-vous/creneaux-libres",
        params={
            "praticien_id": decor["praticien_id"],
            "date": LUNDI.isoformat(),
            "duree_minutes": 60,
        },
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 3


@pytest.mark.asyncio
async def test_creneaux_libres_ignorent_le_rendez_ous_en_cours_de_report(
    client_authenticated, decor, patient_id
):
    """
    Pendant qu'on reporte un rendez-vous, son ancien créneau doit rester
    proposable — sinon on se l'interdit soi-même.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.get(
        "/api/v1/rendez-vous/creneaux-libres",
        params={
            "praticien_id": decor["praticien_id"],
            "date": LUNDI.isoformat(),
            "exclure_rendez_vous": rendez_vous_id,
        },
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 6


@pytest.mark.asyncio
async def test_creneaux_libres_sans_disponibilite(client_authenticated, decor, patient_id):
    """Pas de disponibilités déclarées : aucun créneau, et c'est silencieux."""
    mardi = date(2026, 10, 6)
    r = await client_authenticated.get(
        "/api/v1/rendez-vous/creneaux-libres",
        params={"praticien_id": decor["praticien_id"], "date": mardi.isoformat()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"] == []


# ==============================================================================
# RÉFÉRENTIEL
# ==============================================================================

@pytest.mark.asyncio
async def test_referentiel_expose_le_graphe_des_transitions(client_authenticated):
    """
    Publier le graphe évite que le frontend invente un bouton « Terminer » sur un
    rendez-vous planifié, et n'affiche que les actions possibles.
    """
    r = await client_authenticated.get("/api/v1/rendez-vous/referentiel")
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert {s["code"] for s in data["statuts"]} == {
        "PLANIFIE", "CONFIRME", "EN_SALLE_ATTENTE", "EN_CONSULTATION",
        "TERMINEE", "ANNULE", "ABSENT",
    }
    assert "EN_CONSULTATION" in data["transitions"]["EN_SALLE_ATTENTE"]
    assert "TERMINEE" not in data["transitions"]["EN_SALLE_ATTENTE"]
    assert data["transitions"]["ANNULE"] == []
    assert data["duree_par_defaut_minutes"] == 30
    assert {m["code"] for m in data["motifs_blocage"]} == {
        "RENDEZ_VOUS", "MAINTENANCE", "REPARATION", "RESERVATION",
    }


# ==============================================================================
# MODIFICATIONS
# ==============================================================================

@pytest.mark.asyncio
async def test_modification_bloquee_des_la_salle_d_attente(
    client_authenticated, decor, patient_id
):
    """
    Un rendez-vous planifié ou confirmé se corrige encore — le patient a le droit
    de changer d'avis sur le motif. Dès qu'il est en salle d'attente, non : le
    dossier fait foi et le praticien a pu commencer ses notes.
    """
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]
    url = f"/api/v1/rendez-vous/{rendez_vous_id}"

    await client_authenticated.post(f"{url}/statut", params={"statut": "CONFIRME"})

    r = await client_authenticated.patch(f"{url}", json={"motif": "Douleur aiguë"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["motif"] == "Douleur aiguë"

    await client_authenticated.post(f"{url}/statut", params={"statut": "EN_SALLE_ATTENTE"})
    fige = await client_authenticated.patch(f"{url}", json={"motif": "Autre chose"})
    assert fige.status_code == 422
    assert fige.json()["error"]["code"] == "RENDEZ_VOUS_FIGE"


@pytest.mark.asyncio
async def test_changement_de_fauteuil_avant_confirmation(
    client_authenticated, decor, patient_id
):
    creation = await prendre(client_authenticated, decor, patient_id, _a(9))
    rendez_vous_id = creation.json()["data"]["id"]

    r = await client_authenticated.patch(
        f"/api/v1/rendez-vous/{rendez_vous_id}", json={"fauteuil_id": decor["fauteuil_2"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["fauteuil_id"] == decor["fauteuil_2"]
    assert r.json()["data"]["fauteuil_numero"] == "F2"


# ==============================================================================
# FILTRES
# ==============================================================================

@pytest.mark.asyncio
async def test_filtres_de_liste(client_authenticated, decor, patient_id):
    await prendre(client_authenticated, decor, patient_id, _a(9))
    await prendre(
        client_authenticated, decor, patient_id, _a(10), fauteuil_id=decor["fauteuil_2"]
    )

    par_patient = await client_authenticated.get(
        "/api/v1/rendez-vous", params={"patient_id": patient_id}
    )
    assert len(par_patient.json()["data"]) == 2

    par_fauteuil = await client_authenticated.get(
        "/api/v1/rendez-vous", params={"fauteuil_id": decor["fauteuil_1"]}
    )
    assert len(par_fauteuil.json()["data"]) == 1

    par_statut = await client_authenticated.get(
        "/api/v1/rendez-vous", params={"statut": "PLANIFIE"}
    )
    assert len(par_statut.json()["data"]) == 2

    # 09h45 doit inclure le rendez-vous de 09h30 (filtre sur l'intervalle).
    intervalle = await client_authenticated.get(
        "/api/v1/rendez-vous",
        params={
            "du": "2026-10-05T09:45:00+00:00",
            "au": "2026-10-05T10:15:00+00:00",
        },
    )
    assert len(intervalle.json()["data"]) == 1


# ==============================================================================
# RBAC
# ==============================================================================

@pytest.mark.asyncio
async def test_secretaire_programme_mais_ne_change_pas_les_horaires(
    client_authenticated, cabinet, decor, patient_id, tenant_db
):
    """
    Le secrétariat programme des rendez-vous (`AGENDA:*`), mais ne modifie ni le
    décor du cabinet ni les disponibilités des dentistes (`DISPONIBILITES:*` en
    écriture). C'est la matrice des rôles qui l'impose.
    """
    from src.core.security import create_access_token, get_password_hash
    from src.main import app
    from src.modules.auth import dependencies as auth_deps
    from src.modules.rbac.services import RbacService
    from src.modules.tenants.models import Role

    await RbacService.bootstrap_complet(tenant_db)
    role = (await tenant_db.execute(select(Role).where(Role.nom == "SECRETAIRE"))).scalar_one()
    secretaire = Utilisateur(
        email="secretariat@clinique-test.dz",
        mot_de_passe=get_password_hash("MotDePasse123!"),
        role_id=role.id,
        prenom="Seynabou",
        nom="Diallo",
        actif=True,
    )
    tenant_db.add(secretaire)
    await tenant_db.commit()

    permissions = await RbacService.permissions_d_un_role(tenant_db, str(role.id))
    assert "AGENDA:CREATE" in permissions
    assert "DISPONIBILITES:CREATE" not in permissions

    async def _override_user():
        return secretaire

    app.dependency_overrides[auth_deps.get_current_user] = _override_user
    client_authenticated.headers.update(
        {
            "Authorization": "Bearer "
            + create_access_token(
                user_id=str(secretaire.id),
                tenant_id=cabinet["tenant_id"],
                role="SECRETAIRE",
                permissions=permissions,
            )
        }
    )

    try:
        # Prendre un rendez-vous : autorisé.
        creation = await prendre(client_authenticated, decor, patient_id, _a(11))
        assert creation.status_code == 201, creation.text

        # Modifier les disponibilités : refusé.
        disponibilite = await client_authenticated.post(
            f"/api/v1/praticiens/{decor['praticien_id']}/disponibilites",
            json={"jour_semaine": 1, "heure_debut": "09:00", "heure_fin": "12:00"},
        )
        assert disponibilite.status_code == 403
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)
