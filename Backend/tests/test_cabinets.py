"""
Tests du module Cabinets & Ressources (D2A).

Règles couvertes :
  RG09 — chaque acte est rattaché à un cabinet et à un praticien identifiés

Le module a trois décisions qui ne se déduisent pas du code et que ces tests
protègent explicitement :
  1. un fauteuil utilisé se désactive, il ne se supprime pas ;
  2. un praticien est toujours un compte existant (jamais une identité orpheline) ;
  3. horaires d'ouverture et disponibilités sont deux notions distinctes.
"""

from datetime import date, time
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.tenants.models import (
    Cabinet,
    CabinetPraticien,
    Consultation,
    Disponibilite,
    Fauteuil,
    Salle,
    Utilisateur,
)

LUNDI = 0  # convention src/common/disponibilite.py : 0 = lundi


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest_asyncio.fixture
async def referentiel(client_authenticated, cabinet) -> dict:
    """
    Décor minimal réaliste : un praticien rattaché, une salle, deux fauteuils.

    Nommé `referentiel` plutôt que `cabinet` pour ne pas entrer en collision
    avec la fixture homonyme de conftest.
    """
    cabinet_id = cabinet["cabinet"].id
    praticien_id = cabinet["praticien"].id

    # Rattachement du praticien au site, comme le fait le provisioning. Sans
    # lui, `/praticiens?cabinet_id=` renvoie une liste vide.
    r = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement", json={}
    )
    assert r.status_code == 200, r.text

    r = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/salles", json={"nom": "Salle 1", "etage": "RDC"}
    )
    assert r.status_code == 201, r.text
    salle_id = r.json()["data"]["id"]

    fauteuil_1 = (
        await client_authenticated.post(
            f"/api/v1/salles/{salle_id}/fauteuils",
            json={"numero": "F1", "equipements": ["radiologie"]},
        )
    ).json()["data"]["id"]
    fauteuil_2 = (
        await client_authenticated.post(
            f"/api/v1/salles/{salle_id}/fauteuils", json={"numero": "F2"}
        )
    ).json()["data"]["id"]

    return {
        "cabinet_id": str(cabinet_id),
        "praticien_id": str(praticien_id),
        "praticien": cabinet["praticien"],
        "utilisateur_id": str(cabinet["user"].id),
        "salle_id": str(salle_id),
        "fauteuil_1": str(fauteuil_1),
        "fauteuil_2": str(fauteuil_2),
    }


# ==============================================================================
# VOCABULAIRE DES DISPONIBILITÉS (pur, sans base)
# ==============================================================================

class _Dispo:
    """Objet minimal conforme au contrat de `creneaux_proposables`."""

    def __init__(self, debut, fin, type="CONSULTATION", actif=True, jour=None, date=None):
        self.heure_debut = debut
        self.heure_fin = fin
        self.type = type
        self.actif = actif
        self.jour_semaine = jour
        self.date_specifique = date


def test_convention_des_jours_de_la_semaine():
    """
    Non-régression : 0 = lundi. Si quelqu'un alignait sur `date.weekday()` sans y
    penser, l'erreur décalerait toute la semaine de planning sans qu'aucun test
    ne la remarque.
    """
    from src.common.disponibilite import jour_de_la_semaine, libelle_jour

    assert jour_de_la_semaine(date(2026, 10, 5)) == 0  # lundi 5 octobre 2026
    assert jour_de_la_semaine(date(2026, 10, 11)) == 6  # dimanche
    assert libelle_jour(0) == "Lundi"
    assert libelle_jour(6) == "Dimanche"


def test_plages_adjacentes_ne_se_chevauchent_pas():
    """
    09:00-10:00 et 10:00-11:00 ne se chevauchent PAS : deux rendez-vous doivent
    pouvoir s'enchaîner sans qu'on invente un trou d'une heure entre les deux.
    """
    from src.common.disponibilite import chevauche

    assert chevauche(time(9, 0), time(10, 0), time(10, 0), time(11, 0)) is False
    assert chevauche(time(9, 0), time(10, 0), time(9, 30), time(10, 30)) is True
    assert chevauche(time(9, 0), time(10, 0), time(8, 0), time(9, 0)) is False


def test_dernier_creneau_ecourte_sans_deborder():
    """Une plage 09:00-09:50 donne 09:00-09:30 puis 09:30-09:50, pas 09:30-10:00."""
    from src.common.disponibilite import compacter, decouper_en_creneaux

    assert compacter(decouper_en_creneaux(time(9, 0), time(9, 50))) == [
        ("09:00", "09:30"),
        ("09:30", "09:50"),
    ]


def test_plages_se_recouvrant_ne_produisent_pas_de_doublon():
    """
    08:00-12:00 et 09:00-10:00 couvrent la même matinée. Sans fusion, le créneau
    09:00-09:30 serait proposé deux fois à l'écran.
    """
    from src.common.disponibilite import compacter, creneaux_proposables

    jour = date(2026, 10, 5)
    creneaux = creneaux_proposables(
        [_Dispo(time(8, 0), time(12, 0), jour=LUNDI), _Dispo(time(9, 0), time(10, 0), jour=LUNDI)],
        jour,
    )
    assert len(creneaux) == 8
    assert len(set(creneaux)) == len(creneaux), "créneau dupliqué"


def test_indisponibilite_retire_des_creneaux():
    """
    Une plage BLOCKING (congé, remplacement) RETIRE des créneaux, alors qu'elle
    en crée. Confondre les deux ferait proposer un créneau à un dentiste absent.
    """
    from src.common.disponibilite import compacter, creneaux_proposables

    jour = date(2026, 10, 5)
    creneaux = creneaux_proposables(
        [
            _Dispo(time(9, 0), time(12, 0), jour=LUNDI),
            _Dispo(time(10, 0), time(10, 30), type="BLOCKING", jour=LUNDI),
        ],
        jour,
    )
    resultat = compacter(creneaux)
    assert ("10:00", "10:30") not in resultat
    assert ("09:00", "09:30") in resultat
    assert ("10:30", "11:00") in resultat


def test_disponibilite_inactive_ignoree():
    from src.common.disponibilite import creneaux_proposables

    jour = date(2026, 10, 5)
    assert creneaux_proposables([_Dispo(time(9, 0), time(10, 0), actif=False, jour=LUNDI)], jour) == []


def test_exception_de_date_ne_pertube_pas_les_autres_jours():
    """
    Une plage déclarée pour le 24/12 ne doit rien changer au 5/10 : c'est tout
    l'intérêt d'une exception plutôt que d'une récurrence à date fixe.
    """
    from src.common.disponibilite import creneaux_proposables

    jour = date(2026, 10, 5)
    disponibilites = [
        _Dispo(time(9, 0), time(12, 0), jour=LUNDI),
        _Dispo(time(14, 0), time(16, 0), date=date(2026, 12, 24)),
    ]
    assert len(creneaux_proposables(disponibilites, jour)) == 6  # que le matin


def test_plage_sans_jour_est_refusee():
    from src.common.disponibilite import PlageInvalide, valider_plage

    with pytest.raises(PlageInvalide) as exc:
        valider_plage(
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
            jour_semaine=None,
            date_specifique=None,
            type_plage="CONSULTATION",
        )
    assert exc.value.code == "PLAGE_SANS_JOUR"


def test_gravite_de_plage_inconnue_tombe_en_blocage():
    """
    Non-régression : une valeur de `type` corrompue ne doit jamais être
    interprétée comme « Creates des créneaux ». Le défaut est le plus restrictif.
    """
    from src.common.disponibilite import PlageInvalide, valider_plage

    with pytest.raises(PlageInvalide) as exc:
        valider_plage(
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
            jour_semaine=LUNDI,
            date_specifique=None,
            type_plage="CONSULTATION_DEBUTANTE",
        )
    assert exc.value.code == "TYPE_PLAGE_INCONNU"


# ==============================================================================
# SCHÉMAS — messages destinés au praticien
# ==============================================================================

@pytest.mark.parametrize(
    "payload, fragment_attendu",
    [
        (
            {"jour_semaine": 0, "heure_debut": "12:00", "heure_fin": "09:00"},
            "doit précéder",
        ),
        (
            {"heure_debut": "09:00", "heure_fin": "12:00"},
            "jour de semaine",
        ),
        (
            {"jour_semaine": 0, "heure_debut": "09:00", "heure_fin": "12:00", "type": "NIMPORTE"},
            "Type de plage inconnu",
        ),
    ],
)
def test_messages_de_validation_utilisables(payload, fragment_attendu):
    """
    Le message doit expliquer la faute au praticien, pas à nommer une règle de code.
    """
    from src.modules.cabinets.schemas import DisponibiliteCreate

    with pytest.raises(ValueError) as exc:
        DisponibiliteCreate(**payload)
    assert fragment_attendu in str(exc.value)


# ==============================================================================
# RÉFÉRENTIEL
# ==============================================================================

@pytest.mark.asyncio
async def test_referentiel_expose_la_convention(client_authenticated):
    """
    Le frontend ne doit pas deviner que 0 = lundi : le référentiel le publie.
    """
    r = await client_authenticated.get("/api/v1/referentiel/disponibilites")
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    jours = {j["index"]: j for j in data["jours"]}
    assert jours[0]["libelle"] == "Lundi"
    assert jours[6]["libelle"] == "Dimanche"
    assert len(data["jours"]) == 7

    codes = {t["code"] for t in data["types_plage"]}
    assert codes == {"CONSULTATION", "URGENCE", "BLOCKING"}
    assert data["duree_creneau_minutes"] == 30


# ==============================================================================
# SALLES & FAUTEUILS
# ==============================================================================

@pytest.mark.asyncio
async def test_creation_salle_et_fauteuils(client_authenticated, cabinet):
    cabinet_id = cabinet["cabinet"].id

    r = await client_authenticated.get(f"/api/v1/cabinets/{cabinet_id}/salles")
    assert r.status_code == 200
    assert r.json()["data"] == []

    salle = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/salles", json={"nom": "Bloc opératoire"}
    )
    assert salle.status_code == 201, salle.text
    salle_id = salle.json()["data"]["id"]

    await client_authenticated.post(
        f"/api/v1/salles/{salle_id}/fauteuils", json={"numero": "F1"}
    )
    await client_authenticated.post(
        f"/api/v1/salles/{salle_id}/fauteuils", json={"numero": "F2"}
    )

    r = await client_authenticated.get(f"/api/v1/cabinets/{cabinet_id}/salles")
    donnees = r.json()["data"]
    assert donnees[0]["nb_fauteuils"] == 2
    assert donnees[0]["nb_fauteuils_actifs"] == 2

    # La vue planning renvoie les fauteuils toutes salles confondues, avec le
    # nom du site : c'est ce qu'un écran de placement de patient consomme.
    r = await client_authenticated.get(f"/api/v1/cabinets/{cabinet_id}/fauteuils")
    fauteuils = r.json()["data"]
    assert {f["numero"] for f in fauteuils} == {"F1", "F2"}
    assert all(f["cabinet_nom"] == cabinet["cabinet"].nom for f in fauteuils)


@pytest.mark.asyncio
async def test_salle_dupliquee_refusee(client_authenticated, cabinet):
    cabinet_id = cabinet["cabinet"].id
    payload = {"nom": "Salle 1"}

    assert (await client_authenticated.post(f"/api/v1/cabinets/{cabinet_id}/salles", json=payload)).status_code == 201
    # La casse ne doit pas créer un doublon.
    r = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/salles", json={"nom": "  salle 1  "}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SALLE_DUPLIQUEE"


@pytest.mark.asyncio
async def test_salle_non_vide_non_supprimable(client_authenticated, referentiel):
    cabinet_id = referentiel["cabinet_id"]
    salle_id = referentiel["salle_id"]

    r = await client_authenticated.delete(f"/api/v1/cabinets/{cabinet_id}/salles/{salle_id}")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SALLE_NON_VIDE"
    assert "Désactivez-les" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_fauteuil_utilise_ne_se_supprime_pas(
    client_authenticated, referentiel, consultation_factory, tenant_db
):
    """
    Règle 1 du module : un fauteuil qui a servi ne se supprime pas.

    `consultations.fauteuil_id` est en ON DELETE SET NULL : supprimer le fauteuil
    effacerait de la trace le lieu du soin. On renvoie vers la désactivation.

    Le fauteuil est posé directement en base, et non via l'API Consultations :
    ce module n'expose pas encore ce champ, D2B le branchera quand une
    consultation sera ouverte depuis un rendez-vous. Ce test valide la règle de
    suppression, pas le contrat d'écriture du module Consultations.
    """
    consultation = await consultation_factory()

    ligne = (
        await tenant_db.execute(
            select(Consultation).where(Consultation.id == consultation["id"])
        )
    ).scalar_one()
    ligne.fauteuil_id = referentiel["fauteuil_1"]
    await tenant_db.commit()

    r = await client_authenticated.delete(f"/api/v1/fauteuils/{referentiel['fauteuil_1']}")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "FAUTEUIL_UTILISE"
    assert r.json()["error"]["details"]["nb_consultations"] == 1

    # Le fauteuil n'a pas disparu : sa désactivation reste la seule voie.
    r = await client_authenticated.get(
        f"/api/v1/cabinets/{referentiel['cabinet_id']}/fauteuils",
        params={"inclure_inactifs": True},
    )
    assert "F1" in {f["numero"] for f in r.json()["data"]}


@pytest.mark.asyncio
async def test_fauteuil_inutilise_supprimable(client_authenticated, referentiel):
    """Le fauteuil jamais servi, lui, se supprime. La règle ne doit pas tout bloquer."""
    r = await client_authenticated.delete(f"/api/v1/fauteuils/{referentiel['fauteuil_2']}")
    assert r.status_code == 204, r.text

    r = await client_authenticated.get(f"/api/v1/cabinets/{referentiel['cabinet_id']}/fauteuils")
    assert {f["numero"] for f in r.json()["data"]} == {"F1"}


@pytest.mark.asyncio
async def test_fauteuil_desactive_retire_du_planning_mais_reste_consultable(
    client_authenticated, referentiel
):
    """
    Désactiver retire le fauteuil des propositions sans effacer son historique :
    c'est ce qui rend la règle « pas de suppression » acceptable en pratique.
    """
    r = await client_authenticated.patch(
        f"/api/v1/fauteuils/{referentiel['fauteuil_1']}", json={"actif": False}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["actif"] is False

    r = await client_authenticated.get(f"/api/v1/cabinets/{referentiel['cabinet_id']}/fauteuils")
    assert "F1" not in {f["numero"] for f in r.json()["data"]}

    r = await client_authenticated.get(
        f"/api/v1/cabinets/{referentiel['cabinet_id']}/fauteuils",
        params={"inclure_inactifs": True},
    )
    assert "F1" in {f["numero"] for f in r.json()["data"]}

    reactivation = await client_authenticated.post(
        f"/api/v1/fauteuils/{referentiel['fauteuil_1']}/reactiver"
    )
    assert reactivation.status_code == 200
    assert reactivation.json()["data"]["actif"] is True


@pytest.mark.asyncio
async def test_salle_d_un_autre_cabinet_invisible(client_authenticated, cabinet, referentiel, tenant_db):
    """
    Un fauteuil d'un site ne doit pas être modifiable via l'URL d'un autre site.
    La coherence des identifiants se vérifie côté serveur, pas côté UI.
    """
    autre_cabinet = await tenant_db.execute(
        select(func.count(Cabinet.id)).where(Cabinet.id != referentiel["cabinet_id"])
    )
    assert autre_cabinet.scalar_one() == 0  # un seul site dans ce test

    # Le fauteuil existe bien mais sous un autre préfixe de route : 404 attendu
    # parce que la salle n'appartient pas au cabinet demandé.
    faux_cabinet = "00000000-0000-0000-0000-000000000000"
    r = await client_authenticated.patch(
        f"/api/v1/cabinets/{faux_cabinet}/salles/{referentiel['salle_id']}",
        json={"nom": "Pirate"},
    )
    assert r.status_code == 404


# ==============================================================================
# PRATICIENS
# ==============================================================================

@pytest.mark.asyncio
async def test_praticien_herite_du_compte_et_du_profil(client_authenticated):
    """Le profil praticien affiche l'identité du compte porteur."""
    r = await client_authenticated.get("/api/v1/praticiens")
    assert r.status_code == 200, r.text
    praticiens = r.json()["data"]
    assert len(praticiens) == 1

    p = praticiens[0]
    assert p["email"] == "admin@clinique-test.dz"
    assert p["specialite"] == "Chirurgien-Dentiste"
    assert p["compte_actif"] is True


@pytest.mark.asyncio
async def test_rattacher_un_compact_existant(client_authenticated, cabinet, tenant_db):
    """
    Un praticien est toujours un compte existant : c'est ce qui rend la
    signature d'un acte rattachable à une personne physique.
    """
    from src.modules.rbac.services import RbacService
    from src.modules.tenants.models import Role

    # Le role ASSISTANT n'existe que si le RBAC a ete seedé : la fixture
    # `cabinet` ne crée que ADMIN_CABINET.
    await RbacService.bootstrap_complet(tenant_db)
    role = (await tenant_db.execute(select(Role).where(Role.nom == "ASSISTANT"))).scalar_one()
    nouveau = Utilisateur(
        email="dr.sarr@clinique-test.dz",
        mot_de_passe=cabinet["user"].mot_de_passe,
        role_id=role.id,
        prenom="Awa",
        nom="Sarr",
        actif=True,
    )
    tenant_db.add(nouveau)
    await tenant_db.commit()

    r = await client_authenticated.post(
        "/api/v1/praticiens",
        json={
            "utilisateur_id": str(nouveau.id),
            "specialite": "Orthodontiste",
            "numero_ordre": "ORD-SARR-001",
            "cabinet_id": str(cabinet["cabinet"].id),
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["email"] == "dr.sarr@clinique-test.dz"
    assert data["specialite"] == "Orthodontiste"
    assert str(cabinet["cabinet"].id) in data["cabinets"]

    # Le rattachement initial est actif.
    r = await client_authenticated.get(
        f"/api/v1/cabinets/{cabinet['cabinet'].id}/praticiens/{data['id']}/rattachement"
    )
    assert r.status_code == 200
    assert r.json()["data"]["actif"] is True


@pytest.mark.asyncio
async def test_utilisateur_inexistant_refuse(client_authenticated):
    r = await client_authenticated.post(
        "/api/v1/praticiens",
        json={"utilisateur_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_compte_deja_praticien_refuse(client_authenticated, cabinet):
    r = await client_authenticated.post(
        "/api/v1/praticiens", json={"utilisateur_id": str(cabinet["user"].id)}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PRATICIEN_EXISTANT"


@pytest.mark.asyncio
async def test_numero_ordre_duplique_refuse(client_authenticated, cabinet, tenant_db):
    """
    Le numéro d'ordre identifie un praticien auprès de l'Ordre professionnel :
    deux praticiens ne peuvent pas le porter.
    """
    from src.modules.rbac.services import RbacService
    from src.modules.tenants.models import Role

    # Le role ASSISTANT n'existe que si le RBAC a ete seedé : la fixture
    # `cabinet` ne crée que ADMIN_CABINET.
    await RbacService.bootstrap_complet(tenant_db)
    role = (await tenant_db.execute(select(Role).where(Role.nom == "ASSISTANT"))).scalar_one()

    async def creer_compte(email: str):
        u = Utilisateur(
            email=email,
            mot_de_passe=cabinet["user"].mot_de_passe,
            role_id=role.id,
            prenom="P",
            nom=email.split("@")[0],
            actif=True,
        )
        tenant_db.add(u)
        await tenant_db.commit()
        return u

    premier = await creer_compte("dr.diop@x.dz")
    r = await client_authenticated.post(
        "/api/v1/praticiens",
        json={"utilisateur_id": str(premier.id), "numero_ordre": "ORD-DIOP-1"},
    )
    assert r.status_code == 201, r.text

    # Un second praticien ne peut pas porter le même numéro, quelle que soit
    # la casse : c'est précisément ce que compare la règle.
    second = await creer_compte("dr.sow@x.dz")
    r = await client_authenticated.post(
        "/api/v1/praticiens",
        json={"utilisateur_id": str(second.id), "numero_ordre": "ord-diop-1"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "NUMERO_ORDRE_DUPLIQUE"


@pytest.mark.asyncio
async def test_detacher_clot_sans_supprimer(client_authenticated, cabinet, referentiel, tenant_db):
    """
    Détacher un praticien ne supprime pas son rattachement : le rôle est conservé
    pour que ses consultations passées restent attribuables.
    """
    cabinet_id = referentiel["cabinet_id"]
    praticien_id = referentiel["praticien_id"]

    r = await client_authenticated.delete(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement"
    )
    assert r.status_code == 204, r.text

    r = await client_authenticated.get(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement"
    )
    assert r.status_code == 200
    donnees = r.json()["data"]
    assert donnees["actif"] is False
    assert donnees["date_fin"] is not None

    lignes = (
        await tenant_db.execute(
            select(func.count(CabinetPraticien.id)).where(
                CabinetPraticien.praticien_id == praticien_id
            )
        )
    ).scalar_one()
    assert lignes == 1, "le rattachement aurait dû être clôturé, pas supprimé"


@pytest.mark.asyncio
async def test_rattacher_apres_detachement_reutilise_la_ligne(
    client_authenticated, referentiel, tenant_db
):
    """
    Rattacher à nouveau ne crée pas un second enregistrement : il rouvre
    l'existant. Sinon le praticien finit avec deux lignes pour le même site.
    """
    cabinet_id = referentiel["cabinet_id"]
    praticien_id = referentiel["praticien_id"]

    await client_authenticated.delete(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement"
    )
    r = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement", json={}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["actif"] is True

    lignes = (
        await tenant_db.execute(
            select(func.count(CabinetPraticien.id)).where(
                CabinetPraticien.praticien_id == praticien_id
            )
        )
    ).scalar_one()
    assert lignes == 1


@pytest.mark.asyncio
async def test_rattacher_deux_fois_refuse(client_authenticated, referentiel):
    """La fixture a déjà rattaché le praticien : un second POST doit échouer."""
    cabinet_id = referentiel["cabinet_id"]
    praticien_id = referentiel["praticien_id"]

    r = await client_authenticated.post(
        f"/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement", json={}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "RATTACHEMENT_EXISTANT"


@pytest.mark.asyncio
async def test_praticiens_filtres_par_site(client_authenticated, cabinet, tenant_db, referentiel):
    """`?cabinet_id=` ne renvoie que les praticiens rattachés à ce site."""
    from src.modules.rbac.services import RbacService
    from src.modules.tenants.models import Role

    # Le role ASSISTANT n'existe que si le RBAC a ete seedé : la fixture
    # `cabinet` ne crée que ADMIN_CABINET.
    await RbacService.bootstrap_complet(tenant_db)
    role = (await tenant_db.execute(select(Role).where(Role.nom == "ASSISTANT"))).scalar_one()
    u = Utilisateur(
        email="dr.non.rattache@x.dz",
        mot_de_passe=cabinet["user"].mot_de_passe,
        role_id=role.id,
        prenom="N",
        nom="Detache",
        actif=True,
    )
    tenant_db.add(u)
    await tenant_db.commit()
    await client_authenticated.post("/api/v1/praticiens", json={"utilisateur_id": str(u.id)})

    tous = await client_authenticated.get("/api/v1/praticiens")
    assert len(tous.json()["data"]) == 2

    filtres = await client_authenticated.get(
        "/api/v1/praticiens", params={"cabinet_id": referentiel["cabinet_id"]}
    )
    assert [p["email"] for p in filtres.json()["data"]] == ["admin@clinique-test.dz"]


# ==============================================================================
# DISPONIBILITÉS
# ==============================================================================

@pytest.mark.asyncio
async def test_declarer_une_disponibilite_hebdo(client_authenticated, referentiel):
    r = await client_authenticated.post(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites",
        json={
            "jour_semaine": LUNDI,
            "heure_debut": "09:00",
            "heure_fin": "12:00",
            "cabinet_id": referentiel["cabinet_id"],
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["libelle_jour"] == "Lundi"
    assert data["plage"] == "09:00 - 12:00"
    assert data["duree_minutes"] == 180


@pytest.mark.asyncio
async def test_plage_inversee_refusee_avec_message_clair(client_authenticated, referentiel):
    r = await client_authenticated.post(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites",
        json={"jour_semaine": LUNDI, "heure_debut": "18:00", "heure_fin": "09:00"},
    )
    assert r.status_code == 422
    assert "doit précéder" in r.text


@pytest.mark.asyncio
async def test_disponibilite_identique_refusee(client_authenticated, referentiel):
    payload = {"jour_semaine": LUNDI, "heure_debut": "09:00", "heure_fin": "12:00"}
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"

    assert (await client_authenticated.post(url, json=payload)).status_code == 201
    r = await client_authenticated.post(url, json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "DISPONIBILITE_DUPLIQUEE"


@pytest.mark.asyncio
async def test_formation_superposee_aux_horaires_de_travail(client_authenticated, referentiel):
    """
    Non-régression : une formation doit pouvoir recouvrir EXACTEMENT les horaires
    de travail déclarés.

    C'est la façon normale d'exprimer « je travaille l'après-midi, sauf
    formation ce jour-là ». Si le contrôle de doublon ignorait le `type`, cette
    déclaration serait refusée et l'absence serait inexprimable.
    """
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    r = await client_authenticated.post(
        url, json={"jour_semaine": LUNDI, "heure_debut": "14:00", "heure_fin": "17:00"}
    )
    assert r.status_code == 201, r.text

    formation = await client_authenticated.post(
        url,
        json={
            "jour_semaine": LUNDI,
            "heure_debut": "14:00",
            "heure_fin": "17:00",
            "type": "BLOCKING",
        },
    )
    assert formation.status_code == 201, formation.text

    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05"},
    )
    assert r.json()["data"]["creneaux"] == []


@pytest.mark.asyncio
async def test_meme_type_meme_horaires_refuse(client_authenticated, referentiel):
    """La non-régression ci-dessus ne doit pas désactiver le contrôle de doublon."""
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    payload = {"jour_semaine": LUNDI, "heure_debut": "14:00", "heure_fin": "17:00"}

    assert (await client_authenticated.post(url, json=payload)).status_code == 201
    assert (await client_authenticated.post(url, json=payload)).status_code == 422

    # Même chose en URGENCE : même type de doublon attendu, car seul diffère le
    # libellé.
    urgence = {**payload, "type": "URGENCE"}
    assert (await client_authenticated.post(url, json=urgence)).status_code == 201
    assert (await client_authenticated.post(url, json=urgence)).status_code == 422


@pytest.mark.asyncio
async def test_meme_plage_pour_une_autre_date_autorisee(client_authenticated, referentiel):
    """
    09:00-12:00 le lundi ET le mardi sont deux plages légitimes : la détection de
    doublon ne doit pas confondre « même horaire » et « même jour ».
    """
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    assert (
        await client_authenticated.post(
            url, json={"jour_semaine": 0, "heure_debut": "09:00", "heure_fin": "12:00"}
        )
    ).status_code == 201
    assert (
        await client_authenticated.post(
            url, json={"jour_semaine": 1, "heure_debut": "09:00", "heure_fin": "12:00"}
        )
    ).status_code == 201


@pytest.mark.asyncio
async def test_supprimer_disponibilite(client_authenticated, referentiel):
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    creation = await client_authenticated.post(
        url, json={"jour_semaine": 2, "heure_debut": "14:00", "heure_fin": "18:00"}
    )
    disponibilite_id = creation.json()["data"]["id"]

    r = await client_authenticated.delete(f"/api/v1/disponibilites/{disponibilite_id}")
    assert r.status_code == 204

    liste = await client_authenticated.get(url)
    assert liste.json()["data"] == []


# ==============================================================================
# CRÉNEAUX PROPOSABLES
# ==============================================================================

@pytest.mark.asyncio
async def test_creneaux_proposables_du_lundi(client_authenticated, referentiel):
    """2026-10-05 est un lundi : 09:00-12:00 donne 6 créneaux de 30 minutes."""
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    await client_authenticated.post(
        url, json={"jour_semaine": LUNDI, "heure_debut": "09:00", "heure_fin": "12:00"}
    )

    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["creneaux"] == [
        ["09:00", "09:30"],
        ["09:30", "10:00"],
        ["10:00", "10:30"],
        ["10:30", "11:00"],
        ["11:00", "11:30"],
        ["11:30", "12:00"],
    ]
    assert data["avertissement"] is None


@pytest.mark.asyncio
async def test_creneaux_absents_avec_avertissement(client_authenticated, referentiel):
    """
    Un praticien sans disponibilité ne doit pas laisser croire qu'il est
    simplement saturé : la panne doit être visible par l'avertissement.
    """
    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["creneaux"] == []
    assert "Aucune disponibilité déclarée" in data["avertissement"]


@pytest.mark.asyncio
async def test_indisponibilite_reduit_les_creneaux_proposes(client_authenticated, referentiel):
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    await client_authenticated.post(
        url, json={"jour_semaine": LUNDI, "heure_debut": "09:00", "heure_fin": "12:00"}
    )
    await client_authenticated.post(
        url,
        json={
            "jour_semaine": LUNDI,
            "heure_debut": "10:00",
            "heure_fin": "11:00",
            "type": "BLOCKING",
        },
    )

    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05"},
    )
    data = r.json()["data"]
    assert data["creneaux"] == [
        ["09:00", "09:30"],
        ["09:30", "10:00"],
        ["11:00", "11:30"],
        ["11:30", "12:00"],
    ]
    assert data["nb_plages_bloquantes"] == 1
    assert data["avertissement"] is None


@pytest.mark.asyncio
async def test_jour_bloque_integralement(client_authenticated, referentiel):
    """
    Une journée entièrement déclarée en indisponibilité ne doit pas laisser une
    liste vide silencieuse : le secrétariat doit comprendre que le dentiste a
    signé une absence, et non que son agenda est saturé.
    """
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    r = await client_authenticated.post(
        url,
        json={
            "jour_semaine": LUNDI,
            "heure_debut": "09:00",
            "heure_fin": "12:00",
            "type": "BLOCKING",
        },
    )
    assert r.status_code == 201, r.text

    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05"},
    )
    data = r.json()["data"]
    assert data["creneaux"] == []
    assert data["nb_plages_consultation"] == 0
    assert data["nb_plages_bloquantes"] == 1
    assert "absence" in data["avertissement"]


@pytest.mark.asyncio
async def test_indisponibilite_partielle_laisse_le_reste_du_jour(client_authenticated, referentiel):
    """
    Une demi-journée bloquée doit laisser la matinée libre proposable, sans
    avertissement : le praticien est joignable ce jour-là.
    """
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    await client_authenticated.post(
        url, json={"jour_semaine": LUNDI, "heure_debut": "08:00", "heure_fin": "12:00"}
    )
    await client_authenticated.post(
        url,
        json={
            "jour_semaine": LUNDI,
            "heure_debut": "09:00",
            "heure_fin": "12:00",
            "type": "BLOCKING",
        },
    )

    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05"},
    )
    data = r.json()["data"]
    assert data["creneaux"] == [["08:00", "08:30"], ["08:30", "09:00"]]
    assert data["avertissement"] is None


@pytest.mark.asyncio
async def test_date_malformee_refusee(client_authenticated, referentiel):
    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "05-10-2026"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "DATE_INVALIDE"


@pytest.mark.asyncio
async def test_duree_de_creneau_parametrable(client_authenticated, referentiel):
    """Un acte long (prothèse) ne se propose pas en 30 minutes."""
    url = f"/api/v1/praticiens/{referentiel['praticien_id']}/disponibilites"
    await client_authenticated.post(
        url, json={"jour_semaine": LUNDI, "heure_debut": "09:00", "heure_fin": "12:00"}
    )

    r = await client_authenticated.get(
        f"/api/v1/praticiens/{referentiel['praticien_id']}/creneaux",
        params={"date": "2026-10-05", "duree_minutes": 60},
    )
    data = r.json()["data"]
    assert len(data["creneaux"]) == 3
    assert data["creneaux"][0] == ["09:00", "10:00"]


# ==============================================================================
# COHÉRENCE CABINET
# ==============================================================================

@pytest.mark.asyncio
async def test_desactiver_le_dernier_cabinet_refuse(client_authenticated, cabinet):
    """
    Un tenant sans cabinet actif ne peut plus enregistrer aucune consultation.
    Laisser faire produirait un blocage découvert beaucoup plus tard.
    """
    r = await client_authenticated.patch(
        f"/api/v1/cabinets/{cabinet['cabinet'].id}", json={"actif": False}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "DERNIER_CABINET_ACTIF"


@pytest.mark.asyncio
async def test_horaires_ouverture_enregistrables(client_authenticated, cabinet):
    """Horaires d'ouverture et disponibilités sont deux notions distinctes."""
    horaires = {"jours": {"0": [["08:00", "12:00"], ["14:00", "18:00"]], "6": []}}
    r = await client_authenticated.patch(
        f"/api/v1/cabinets/{cabinet['cabinet'].id}", json={"horaires_ouverture": horaires}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["horaires_ouverture"] == horaires


@pytest.mark.asyncio
async def test_compteurs_de_la_fiche_cabinet(client_authenticated, referentiel):
    r = await client_authenticated.get(f"/api/v1/cabinets/{referentiel['cabinet_id']}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["nb_salles"] == 1
    assert data["nb_fauteuils_actifs"] == 2
    assert data["nb_praticiens_actifs"] == 1


# ==============================================================================
# RBAC
# ==============================================================================

@pytest.mark.asyncio
async def test_secretaire_lit_mais_ne_modifie_pas(client_authenticated, cabinet, tenant_db):
    """
    Le secrétariat programme : il doit voir les salles et les fauteuils pour
    placer un patient, mais pas modifier le décor du cabinet ni les
    disponibilités des dentistes.
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
    assert "CABINETS:READ" in permissions
    assert "CABINETS:CREATE" not in permissions
    assert "DISPONIBILITES:CREATE" not in permissions

    async def _override_user():
        return secretaire

    app.dependency_overrides[auth_deps.get_current_user] = _override_user
    cabinet_id = cabinet["cabinet"].id

    # `require_permissions` lit le JWT : il faut remplacer l'en-tête.
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
        lecture = await client_authenticated.get(f"/api/v1/cabinets/{cabinet_id}/salles")
        assert lecture.status_code == 200, "le secrétariat doit voir les salles"

        creation = await client_authenticated.post(
            f"/api/v1/cabinets/{cabinet_id}/salles", json={"nom": "Salle pirates"}
        )
        assert creation.status_code == 403, creation.text

        disponibilite = await client_authenticated.post(
            "/api/v1/praticiens", json={"utilisateur_id": str(secretaire.id)}
        )
        assert disponibilite.status_code == 403
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)
