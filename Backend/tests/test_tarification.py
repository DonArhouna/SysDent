"""Tarification par cabinet et prise en charge (CDC 5.6 et 5.7).

Ce fichier couvre ce qui peut casser **en silence** :

1. **Le contrat de reponse.** Une liste typee sans enveloppe, ou un `dict`, ne
   casse rien a l'execution - le client decouvre le trou le jour ou il lit le
   champ. La garde OpenAPI le voit avant.
2. **La pagination reelle.** Une page ignoree, un plafond different entre la
   declaration et le modele, un parametre inconnu tolere : la liste s'affiche,
   les chiffres concordent, et une ligne manque.
3. **La matrice role x route.** Une permission dans le catalogue et non dans la
   route laisse passer tout le monde. Le test appelle les deux cotes.
4. **Le tarif fige.** C'est la regle explicite du cahier des charges : un
   changement de tarif ne doit jamais alterer une facture emise.
5. **L'isolation entre cabinets.** Deux bases, deux tenants : aucun droit ne doit
   apparaitre chez le cabinet qui n'est pas le sien.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.main import app
from src.modules.auth import dependencies as auth_deps
from src.modules.tenants.models import (
    ActeNomenclature,
    ActeRealise,
    Consultation,
    DroitPriseEnCharge,
    OrganismeAssurance,
    Utilisateur,
)

BASE = "/api/v1/tarification"


# ==============================================================================
# 1. Contrat de reponse
# ==============================================================================


def _schemas_bruts() -> dict:
    return app.openapi().get("components", {}).get("schemas", {})


def test_aucune_reponse_dict_sans_proprietes() -> None:
    """
    La nomenclature repondait `PaginatedResponse[dict]` et `APIResponse[dict]`.

    Un `dict` n'a aucune propriete : le contrat OpenAPI ne decrit rien, le
    client ne peut pas etre type, et une reponse qui perd un champ passe
    inapercue. Toute reponse des routes de tarification doit nommer un schema
    avec des proprietes.
    """
    chemins = [p for p in app.openapi()["paths"] if p.startswith(BASE)]
    assert len(chemins) >= 10, f"routes de tarification absentes : {chemins}"

    suspects: list[str] = []
    for chemin in chemins:
        for methode, operation in app.openapi()["paths"][chemin].items():
            if methode not in ("get", "post", "patch", "put"):
                continue
            for code, reponse in operation.get("responses", {}).items():
                contenu = reponse.get("content", {}).get("application/json", {})
                if not contenu:
                    continue  # 204 : pas de corps, par construction
                schema = contenu.get("schema", {})
                texte = str(schema)
                if '"type": "object"' in texte and "properties" not in texte:
                    suspects.append(f"{methode.upper()} {chemin} -> {code}")
                if "additionalProperties" in texte and '"type": "object"' in texte:
                    suspects.append(f"{methode.upper()} {chemin} -> {code} (libre)")

    assert not suspects, f"reponses `dict` sans proprietes : {suspects}"


def test_chaque_liste_a_une_enveloppe_items_meta() -> None:
    """Pas d'enveloppe `{data: [...]}`. Le contrat est `{items, meta}` partout."""
    listes = [
        f"{BASE}/actes",
        f"{BASE}/categories",
        f"{BASE}/organismes",
        f"{BASE}/actes/{{acte_id}}/tarifs",
        f"{BASE}/patients/{{patient_id}}/droits",
    ]
    schemas = _schemas_bruts()
    for chemin in listes:
        schema = app.openapi()["paths"][chemin]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert "PaginatedResponse" in str(schema), f"{chemin} : {schema}"
        generique = next(
            nom for nom, defi in schemas.items() if nom.startswith("PaginatedResponse_")
        )
        assert "items" in schemas[generique]["properties"], generique
        assert "meta" in schemas[generique]["properties"], generique


def test_aucun_plafond_en_dur_different_du_modele() -> None:
    """
    Une route qui annonce `le=200` alors que le modele refuse au-dela de 100
    accepte en query une valeur que la construction de page refuse ensuite.
    """
    for chemin in [p for p in app.openapi()["paths"] if p.startswith(BASE)]:
        operation = app.openapi()["paths"][chemin].get("get")
        if not operation:
            continue
        for parametre in operation.get("parameters", []):
            if parametre["name"] != "limit":
                continue
            maximum = parametre["schema"].get("maximum")
            assert maximum is not None, f"{chemin} : `limit` sans plafond"
            assert maximum == 100, f"{chemin} : plafond {maximum} au lieu de 100"


# ==============================================================================
# Outils partages
# ==============================================================================


async def _creer_acte(client: AsyncClient, code: str, tarif: str = "15000.00") -> dict:
    reponse = await client.post(
        f"{BASE}/actes",
        json={
            "code": code,
            "libelle": f"Acte {code}",
            "categorie": "SOINS",
            "tarif_base": tarif,
            "duree_estimee_min": 20,
            "unitaire": False,
        },
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]


async def _creer_organisme(client: AsyncClient, code: str) -> dict:
    reponse = await client.post(
        f"{BASE}/organismes",
        json={"code": code, "nom": f"Organisme {code}", "type_organisme": "MUTUELLE"},
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["data"]


@asynccontextmanager
async def _avec_role(client: AsyncClient, cabinet: dict, role: str):
    """
    Emprome le client avec les permissions d'un role, puis les rend.

    `client_authenticated` est un **objet unique** partage par tous les fixtures
    du fichier. Sans restauration, le premier test qui passe en praticien laisse
    tous les suivants en praticien - et les 403 attendus deviennent des 200,
    ou l'inverse. C'est un piege silencieux : les assertions continueient de
    passer sur un test et de echouer sur un autre, sans raison visible.
    """
    from src.common.permissions import format_permission, permissions_for_role

    precedent = client.headers.get("Authorization")
    jeton = create_access_token(
        user_id=str(cabinet["user"].id),
        tenant_id=cabinet["tenant_id"],
        role=role,
        permissions=[format_permission(m, a) for m, a in permissions_for_role(role)],
    )
    client.headers.update({"Authorization": f"Bearer {jeton}"})
    try:
        yield client
    finally:
        client.headers.update({"Authorization": precedent})


@pytest.fixture
def cabinet_admin(client_authenticated: AsyncClient, cabinet: dict):
    """Garde l'identite du cabinet pour construire des jetons de role."""
    return cabinet


def _jeton(*permissions: str) -> str:
    """
    Un jeton portant exactement les droits cites, et rien d'autre.

    C'est ce qui rend les tests 403 discriminants : un jeton sans droit n'est
    jamais passe, donc il ne prouve rien. Un jeton qui porte
    `CONSULTATIONS:CREATE` et pas `TARIFS:WRITE` est le profil reellement
    concerne par la correction.
    """
    return "Bearer " + create_access_token(
        user_id="00000000-0000-0000-0000-000000000001",
        tenant_id=str(uuid.uuid4()),
        role="PROFIL_SANS_DROIT",
        permissions=list(permissions),
    )


# ==============================================================================
# 2. Pagination reelle
# ==============================================================================


@pytest.mark.asyncio
async def test_les_listes_respectent_page_et_limit(client_authenticated: AsyncClient) -> None:
    for index in range(5):
        await _creer_acte(client_authenticated, f"PAG{index}")

    page1 = await client_authenticated.get(f"{BASE}/actes", params={"page": 1, "limit": 2})
    page2 = await client_authenticated.get(f"{BASE}/actes", params={"page": 2, "limit": 2})

    assert page1.status_code == 200, page1.text
    corps1, corps2 = page1.json(), page2.json()
    assert len(corps1["items"]) == 2, corps1
    assert corps1["meta"]["limit"] == 2
    assert corps1["meta"]["total_records"] == corps2["meta"]["total_records"]
    ids1 = {i["id"] for i in corps1["items"]}
    ids2 = {i["id"] for i in corps2["items"]}
    assert not ids1 & ids2, "une ligne ne doit pas apparaitre dans deux pages"


@pytest.mark.asyncio
async def test_le_tri_est_deterministe(client_authenticated: AsyncClient) -> None:
    """
    Deux parcours successifs donnent le meme ordre.

    `categorie` n'est pas unique : sans clef secondaire, PostgreSQL ne promet
    rien sur l'ordre des ex aequalo, et une ligne change de page entre deux
    appels. C'est le defaut que ce test attrape.
    """
    for index in range(6):
        await _creer_acte(client_authenticated, f"SORT{index}")

    parcours = []
    for _ in range(3):
        reponse = await client_authenticated.get(f"{BASE}/actes", params={"limit": 100})
        parcours.append([i["id"] for i in reponse.json()["items"]])
    assert parcours[0] == parcours[1] == parcours[2], "tri non deterministe"


@pytest.mark.asyncio
async def test_un_parametre_inconnu_est_refuse(client_authenticated: AsyncClient) -> None:
    """
    Un parametre inconnu tolere en silence fait croire a un filtre qui n'existe
    pas : la liste revient complete et l'ecran montre "tous les resultats".
    """
    reponse = await client_authenticated.get(f"{BASE}/actes", params={"tri": "code"})
    assert reponse.status_code == 422, reponse.text


@pytest.mark.asyncio
async def test_les_filtres_sont_apiques_cote_serveur(client_authenticated: AsyncClient) -> None:
    await _creer_acte(client_authenticated, "FILTRE_A")
    await _creer_acte(client_authenticated, "FILTRE_B")

    recherche = await client_authenticated.get(f"{BASE}/actes", params={"q": "FILTRE_A"})
    codes = {i["code"] for i in recherche.json()["items"]}
    assert codes == {"FILTRE_A"}, codes
    assert recherche.json()["meta"]["total_records"] == 1

    actifs = await client_authenticated.get(f"{BASE}/actes", params={"actif": False})
    assert actifs.json()["meta"]["total_records"] == 0, "aucun acte desactive"


@pytest.mark.asyncio
async def test_l_agenda_de_droits_est_borne_et_triee(client_authenticated: AsyncClient, patient_factory) -> None:
    patient = (await patient_factory()).json()["data"]["id"]
    for index in range(3):
        orga = await _creer_organisme(client_authenticated, f"droits-org-{index}")
        await client_authenticated.post(
            f"{BASE}/patients/{patient}/droits",
            json={"organisme_id": orga["id"], "taux_prise_en_charge": "70.00", "priorite": 3 - index},
        )

    reponse = await client_authenticated.get(f"{BASE}/patients/{patient}/droits")
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert [d["priorite"] for d in corps["items"]] == [1, 2, 3], corps["items"]
    assert corps["meta"]["total_records"] == 3


# ==============================================================================
# 3. Matrice role x route
# ==============================================================================


@pytest.mark.asyncio
async def test_matrice_role_sur_la_tarification(
    client_authenticated: AsyncClient,
    cabinet_admin: dict,
) -> None:
    """
    200 ou 403, route par route, role par role.

    Le cas interessant est le praticien : il **lit** la nomenclature - il doit
    pouvoir facturer - mais il ne la **fixe** pas. C'est exactement ce que
    `CONSULTATIONS:CREATE` permettaient avant, et que ce correctif ferme.
    """
    async def _role(nom: str) -> AsyncClient:
        return await _avec_role(client_authenticated, cabinet_admin, nom).__aenter__()

    async def _dans(nom: str, action):
        async with _avec_role(client_authenticated, cabinet_admin, nom) as client:
            return await action(client)

    # --- lecture : ouverte a tous les roles du cabinet
    for role in ("ADMIN_CABINET", "PRATICIEN", "SECRETAIRE", "COMPTABLE"):
        statut = await _dans(role, lambda c: c.get(f"{BASE}/actes"))
        assert statut.status_code == 200, f"lecture refusee pour {role} : {statut.status_code}"

    # --- creation d'un acte : administration seulement
    assert (await client_authenticated.get(f"{BASE}/actes")).status_code == 200
    for role in ("PRATICIEN", "SECRETAIRE", "COMPTABLE"):
        statut = await _dans(
            role,
            lambda c: c.post(
                f"{BASE}/actes",
                json={"code": "X", "libelle": "X", "categorie": "SOINS", "tarif_base": "1.00"},
            ),
        )
        assert statut.status_code == 403, f"{role} a pu creer un acte : {statut.text}"

    # --- ecriture d'un tarif : administration seulement
    acte = await _creer_acte(client_authenticated, "MTX")
    statut = await _dans(
        "PRATICIEN",
        lambda c: c.put(
            f"{BASE}/actes/{acte['id']}/tarifs",
            json={"categorie_code": "standard", "montant": "1.00"},
        ),
    )
    assert statut.status_code == 403, statut.text

    # --- prise en charge : l'accueil ecrit, le praticien non
    assert (await _dans("PRATICIEN", lambda c: c.get(f"{BASE}/organismes"))).status_code == 200
    statut = await _dans(
        "PRATICIEN",
        lambda c: c.post(
            f"{BASE}/organismes",
            json={"code": "x", "nom": "X", "type_organisme": "MUTUELLE"},
        ),
    )
    assert statut.status_code == 403, statut.text
    assert (await _dans("SECRETAIRE", lambda c: c.get(f"{BASE}/organismes"))).status_code == 200


@pytest.mark.asyncio
async def test_creer_un_acte_ne_passe_plus_par_consultations_create(
    client_authenticated: AsyncClient,
) -> None:
    """
    Le garde sur la **permission**, pas sur l'URL.

    `POST /nomenclature/actes` a longtemps demande `CONSULTATIONS:CREATE`. Le
    jeton de test porte justement ce droit, et **pas** `TARIFS:WRITE` : c'est le
    profil qui, hier, pouvait fixer le prix des actes du cabinet en passant par la
    porte de la consultation. Il doit etre refuse.

    Sans ce test, remettre `CONSULTATIONS:CREATE` ne ferait echouer aucun test :
    un jeton sans *aucun* des deux droits serait refuse dans les deux cas, et la
    distinction passerait inaperue.
    """
    corps = {
        "code": "VIA_CONSULT",
        "libelle": "Creer par la porte de la consultation",
        "categorie": "SOINS",
        "tarif_base": "1000.00",
    }

    refus = await client_authenticated.post(
        "/api/v1/nomenclature/actes", json=corps, headers={"Authorization": _jeton("CONSULTATIONS:CREATE")}
    )
    assert refus.status_code == 403, refus.text
    assert refus.json()["error"]["code"] == "PERMISSION_DENIED", refus.text

    # Le meme corps passe avec le bon droit : ce n'est pas le corps qui bloque.
    accepte = await client_authenticated.post(
        "/api/v1/nomenclature/actes", json=corps, headers={"Authorization": _jeton("TARIFS:WRITE")}
    )
    assert accepte.status_code == 201, accepte.text


@pytest.mark.asyncio
async def test_la_nomenclature_requiert_tarifs_read(client_authenticated: AsyncClient) -> None:
    """
    Lire la nomenclature n'est plus un effet de bord de `CONSULTATIONS:READ`.

    Le jeton porte `CONSULTATIONS:READ` et rien d'autre : c'est exactement le
    profil qui, hier, obtenait la liste des actes par la porte de la
    consultation.
    """
    reponse = await client_authenticated.get(
        "/api/v1/nomenclature/actes", headers={"Authorization": _jeton("CONSULTATIONS:READ")}
    )
    assert reponse.status_code == 403, reponse.text

    accepte = await client_authenticated.get(
        "/api/v1/nomenclature/actes", headers={"Authorization": _jeton("TARIFS:READ")}
    )
    assert accepte.status_code == 200, accepte.text


# ==============================================================================
# 4. Le tarif d'une facture est fige
# ==============================================================================


@pytest.mark.asyncio
async def test_un_changement_de_tarif_ne_touche_pas_une_facture(
    client_authenticated: AsyncClient,
    consultation_factory,
    nomenclature: dict,
    tenant_db: AsyncSession,
) -> None:
    """
    La regle du cahier des charges : le tarif est fige a l'emission.

    On enregistre un acte dans une consultation, on change le prix de l'acte
    dans la nomenclature **et** le tarif standard, puis on relit la ligne. Elle
    doit porter l'ancien montant.
    """
    consultation = await consultation_factory()
    acte_id = nomenclature["DETART"]["id"]

    ajout = await client_authenticated.post(
        f"/api/v1/consultations/{consultation['id']}/actes",
        json={"acte_id": acte_id, "dent_numero": 26, "quantite": 1},
    )
    assert ajout.status_code in (200, 201), ajout.text

    avant = (
        await tenant_db.execute(
            select(ActeRealise).where(ActeRealise.consultation_id == consultation["id"])
        )
    ).scalars().all()
    assert len(avant) == 1, avant
    tarif_fige = avant[0].tarif_applique
    assert tarif_fige == Decimal("7500.00"), tarif_fige

    # Le prix double, par les deux chemins : l'acte et son tarif standard.
    assert (
        await client_authenticated.patch(
            f"{BASE}/actes/{acte_id}", json={"libelle": "Detartrage (tarif revise)"}
        )
    ).status_code == 200
    assert (
        await client_authenticated.put(
            f"{BASE}/actes/{acte_id}/tarifs",
            json={"categorie_code": "standard", "montant": "15000.00"},
        )
    ).status_code == 200

    await tenant_db.refresh(avant[0])
    assert avant[0].tarif_applique == tarif_fige, (
        "le tarif applique a ete modifie par un changement de nomenclature : "
        f"{avant[0].tarif_applique} au lieu de {tarif_fige}"
    )

    # Et l'acte de nomenclature, lui, a bien bouge.
    acte = (
        await tenant_db.execute(select(ActeNomenclature).where(ActeNomenclature.id == acte_id))
    ).scalar_one()
    assert acte.tarif_base == Decimal("15000.00"), acte.tarif_base


@pytest.mark.asyncio
async def test_un_acte_ne_peut_pas_disparaitre(
    client_authenticated: AsyncClient, nomenclature: dict, tenant_db: AsyncSession
) -> None:
    """Un acte cite par une ligne de consultation se desactive, il ne se supprime pas."""
    code = nomenclature["CONS"]["code"]
    acte = await client_authenticated.get(f"{BASE}/actes", params={"q": code})
    acte_id = acte.json()["items"][0]["id"]

    desactive = await client_authenticated.patch(f"{BASE}/actes/{acte_id}", json={"actif": False})
    assert desactive.status_code == 200, desactive.text
    assert desactive.json()["data"]["actif"] is False

    # Une fois desactive, il sort de la liste des actes actifs, sans etre perdu.
    liste = await client_authenticated.get(f"{BASE}/actes", params={"actif": True})
    assert acte_id not in {i["id"] for i in liste.json()["items"]}
    avec = await client_authenticated.get(f"{BASE}/actes", params={"actif": False})
    assert acte_id in {i["id"] for i in avec.json()["items"]}

    # Et il n'y a pas de DELETE sur un acte : desactiver est le seul chemin.
    assert "delete" not in app.openapi()["paths"][f"{BASE}/actes/{{acte_id}}"]


# ==============================================================================
# 5. Contraintes et suppression protegee
# ==============================================================================


@pytest.mark.asyncio
async def test_une_categorie_utilisee_ne_se_supprime_pas(client_authenticated: AsyncClient) -> None:
    creation = await client_authenticated.post(
        f"{BASE}/categories", json={"code": "conventionne", "libelle": "Conventionne"}
    )
    assert creation.status_code == 201, creation.text

    acte = await _creer_acte(client_authenticated, "CAT")
    ecrit = await client_authenticated.put(
        f"{BASE}/actes/{acte['id']}/tarifs",
        json={"categorie_code": "conventionne", "montant": "12000.00"},
    )
    assert ecrit.status_code == 200, ecrit.text

    suppression = await client_authenticated.delete(f"{BASE}/categories/conventionne")
    assert suppression.status_code == 422, suppression.text
    assert suppression.json()["error"]["code"] == "CATEGORIE_UTILISEE", suppression.text


@pytest.mark.asyncio
async def test_le_tarif_standard_est_protege(client_authenticated: AsyncClient) -> None:
    acte = await _creer_acte(client_authenticated, "PROT")
    tarifs = await client_authenticated.get(f"{BASE}/actes/{acte['id']}/tarifs")
    standard = next(t for t in tarifs.json()["items"] if t["categorie_code"] == "standard")

    suppression = await client_authenticated.delete(
        f"{BASE}/actes/{acte['id']}/tarifs/{standard['id']}"
    )
    assert suppression.status_code == 422, suppression.text
    assert suppression.json()["error"]["code"] == "TARIF_STANDARD_PROTEGE", suppression.text


@pytest.mark.asyncio
async def test_la_categorie_standard_est_creee_automatiquement(
    client_authenticated: AsyncClient,
) -> None:
    """La migration la cree ; le service doit la retrouver, pas la creer."""
    liste = await client_authenticated.get(f"{BASE}/categories")
    codes = {c["code"] for c in liste.json()["items"]}
    assert "standard" in codes, codes

    duplication = await client_authenticated.post(
        f"{BASE}/categories", json={"code": "standard", "libelle": "Autre"}
    )
    assert duplication.status_code == 422, duplication.text


@pytest.mark.asyncio
async def test_un_organisme_porte_par_un_droit_ne_se_supprime_pas(
    client_authenticated: AsyncClient, patient_factory
) -> None:
    patient_id = (await patient_factory()).json()["data"]["id"]
    orga = await _creer_organisme(client_authenticated, "org-utilise")

    await client_authenticated.post(
        f"{BASE}/patients/{patient_id}/droits",
        json={"organisme_id": orga["id"], "taux_prise_en_charge": "80.00", "priorite": 1},
    )

    suppression = await client_authenticated.delete(f"{BASE}/organismes/{orga['id']}")
    assert suppression.status_code == 422, suppression.text
    assert suppression.json()["error"]["code"] == "ORGANISME_UTILISE", suppression.text


@pytest.mark.asyncio
async def test_un_taux_hors_bornes_est_refuse(client_authenticated: AsyncClient, patient_factory) -> None:
    patient_id = (await patient_factory()).json()["data"]["id"]
    orga = await _creer_organisme(client_authenticated, "org-bornes")

    for taux in ("101.00", "-5.00"):
        reponse = await client_authenticated.post(
            f"{BASE}/patients/{patient_id}/droits",
            json={"organisme_id": orga["id"], "taux_prise_en_charge": taux, "priorite": 1},
        )
        assert reponse.status_code == 422, f"taux {taux} : {reponse.text}"


@pytest.mark.asyncio
async def test_creation_dun_acte_donne_son_tarif_standard(client_authenticated: AsyncClient) -> None:
    """Pas de deux chemins de lecture pour le meme montant."""
    acte = await _creer_acte(client_authenticated, "AUTOTARIF", "9900.00")
    assert acte["tarif_base"] == "9900.00", acte
    assert [t["categorie_code"] for t in acte["tarifs"]] == ["standard"], acte["tarifs"]
    assert acte["tarifs"][0]["montant"] == "9900.00", acte["tarifs"]


@pytest.mark.asyncio
async def test_ecrire_le_tarif_standard_met_a_jour_le_tarif_base(
    client_authenticated: AsyncClient,
) -> None:
    """La seule ecriture de `tarif_base` hors creation, et elle est explicite."""
    acte = await _creer_acte(client_authenticated, "SYNC", "1000.00")
    assert (
        await client_authenticated.put(
            f"{BASE}/actes/{acte['id']}/tarifs",
            json={"categorie_code": "standard", "montant": "4200.00"},
        )
    ).status_code == 200

    relu = await client_authenticated.get(f"{BASE}/actes/{acte['id']}")
    assert relu.json()["data"]["tarif_base"] == "4200.00", relu.text


@pytest.mark.asyncio
async def test_ecrire_un_tarif_de_variante_ne_touche_pas_le_tarif_base(
    client_authenticated: AsyncClient,
) -> None:
    await client_authenticated.post(
        f"{BASE}/categories", json={"code": "tarif-ame", "libelle": "Tarif ameli"}
    )
    acte = await _creer_acte(client_authenticated, "VARIANTE", "5000.00")
    await client_authenticated.put(
        f"{BASE}/actes/{acte['id']}/tarifs",
        json={"categorie_code": "tarif-ame", "montant": "2500.00"},
    )

    relu = await client_authenticated.get(f"{BASE}/actes/{acte['id']}")
    assert relu.json()["data"]["tarif_base"] == "5000.00", relu.text
    codes = {t["categorie_code"]: t["montant"] for t in relu.json()["data"]["tarifs"]}
    assert codes == {"standard": "5000.00", "tarif-ame": "2500.00"}, codes


# ==============================================================================
# 6. Isolation entre cabinets
# ==============================================================================


@pytest.mark.asyncio
async def test_un_cabinet_ne_voit_pas_les_organismes_d_un_autre(
    client_authenticated: AsyncClient,
) -> None:
    """
    Deux clients, deux bases. Le second ne doit voir que ce qu'il a cree.

    Le test fabrique deux contextes sans base supplementaire : la separation
    reelle est faite par `get_tenant_db`, qui resout la base du tenant. On
    verifie donc que le service ne lit jamais hors de la session qu'il a recue.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.conftest import _url_base_de_tests

    nom = f"jetable_iso_{uuid.uuid4().hex[:8]}"
    await _creer_base_iso(nom)
    moteur = create_async_engine(_url_base_de_tests(nom))
    session = async_sessionmaker(bind=moteur, class_=AsyncSession, expire_on_commit=False)()

    try:
        await _inserer_organisme_iso(session, "iso-veillant")
        vus = (await session.execute(select(OrganismeAssurance))).scalars().all()
        assert {o.code for o in vus} == {"iso-veillant"}, vus

        # Le client du premier cabinet ne voit pas cette ligne.
        liste = await client_authenticated.get(f"{BASE}/organismes", params={"q": "iso-veillant"})
        assert liste.json()["meta"]["total_records"] == 0, liste.text
    finally:
        await session.close()
        await moteur.dispose()
        from tests.conftest import supprimer_base_jetable

        await supprimer_base_jetable(nom)


async def _creer_base_iso(nom: str) -> None:
    from tests.conftest import creer_base_jetable

    await creer_base_jetable(nom)


async def _inserer_organisme_iso(session: AsyncSession, code: str) -> None:
    session.add(
        OrganismeAssurance(
            code=code, nom="Organisme isole", type_organisme="ASSURANCE", actif=True
        )
    )
    await session.commit()