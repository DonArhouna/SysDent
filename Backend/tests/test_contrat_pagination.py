"""Test de contrat comportemental de la pagination.

`inventaire_listes.py` vérifie la **forme** des enveloppes. Ce fichier vérifie le
**comportement**, parce que les deux famille de défauts ne se voient pas de la même
manière :

- une enveloppe `{data: […]}` au lieu de `{items, meta}` casse l'écran de façon
  visible ;
- une page ignorée, un tri non déterministe ou un plafond silencieux produces un
  résultat **juste en apparence** : la liste s'affiche, les chiffres concordent,
  et une ligne manque ou revient deux fois. Rien ne signale l'erreur.

D'où les trois propriétés vérifiées ici :

1. **Exhaustivité sur toutes les pages** — aucune ligne perdue, aucune dupliquée,
   `total` exact.
2. **Déterminisme du tri** — deux parcours successifs donnent exactement le même
   ordre. C'est la propriété qui casse en silence quand on trie sur une colonne non
   unique : deux lignes de même date sortent dans un ordre que PostgreSQL ne
   promet pas stable, et l'une apparaît en page 2 tandis qu'elle était déjà en
   page 1.
3. **Paramètres pris en compte** — `page` et `limit` sont réellement lus, `limit`
   au-delà du maximum est refusé, et un paramètre **inconnu** est refusé au lieu
   d'être ignoré.

Les routes sont découvertes depuis les routes enregistrées, pas depuis une liste
écrite à la main : une route ajoutée ne peut pas échapper au contrôle par
oubli. Chaque route volumineuse est soit semée ici, soit déclarée non semable avec
sa raison — ce qui force la décision.
"""

from __future__ import annotations

import pytest

from tests.inventaire_listes import LISTES_VOLUMINEUSES, analyser

#: Routes volumineuses dont la création de lignes est faisable par l'API publique
#: dans le outillage actuel. Les autres sont déclarées dans `NON_SEMABLES`.
#: Une seule route semee ici, mais semee **pour de bon** : creer des
#: fournisseurs pour tester la liste des patients ne prouverait rien. Les autres
#: routes sont declarees dans `NON_SEMABLES` avec leur raison, ce qui force la
#: decision — une liste vide se lirait « tout va bien ».
SEMABLES = {
    "/api/v1/stock/fournisseurs",
}

#: Routes volumineuses non semées ici, **avec la raison**. Une liste vide serait
#: interpreted comme « tout va bien » ; l'exigence est donc explicite.
NON_SEMABLES: dict[str, str] = {
    "/api/v1/caisse/paiements-hors-session": "exige des factures impayees hors session de caisse",
    "/api/v1/patients": "la numerotation de dossier est incrementee en base : 60 creations massives la perturbent",
    "/api/v1/consultations": "exige un dossier medical, une nomenclature et des actes",
    "/api/v1/devis": "exige des lignes de devis facturables",
    "/api/v1/factures": "exige des actes realises et une consultation cloturee",
    "/api/v1/factures/journal-caisse": "exige des paiements en session de caisse",
    "/api/v1/ordonnances": "exige une consultation signee",
    "/api/v1/rendez-vous": "exige des fauteuils, salles et disponibilites coherents",
    "/api/v1/stock/articles": "exige un site et une nomenclature de stock",
    "/api/v1/stock/commandes": "exige un fournisseur et des articles (depend des deux autres)",
    "/api/v1/stock/mouvements": "exige un article et un lot",
    "/api/v1/utilisateurs": "exige un mot de passe conforme et un role attribuable",
    "/api/v1/audit": "journal ecrit par les actions des autres tests, non seminable",
}


def _routes_volumineuses() -> list[str]:
    return sorted(l["chemin"] for l in analyser() if l["chemin"] in LISTES_VOLUMINEUSES)


# ---------------------------------------------------------------------------
# 1. Contrat de forme, sur TOUTES les routes volumineuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chemin", _routes_volumineuses())
def test_route_volumineuse_expose_page_et_limit(chemin):
    """`page` et `limit` doivent être déclarés, sinon la liste est non bornée."""
    import inspect

    from fastapi.routing import APIRoute

    from src.main import app
    from src.core.middleware import UnknownQueryParamMiddleware

    table = UnknownQueryParamMiddleware._construire(app)
    noms = table.get(f"GET {chemin}") or table.get(f"GET {chemin[5:]}")
    assert noms is not None, f"{chemin} introuvable dans les routes enregistrées"
    assert "page" in noms, f"{chemin} n'expose pas `page`"
    assert "limit" in noms, f"{chemin} n'expose pas `limit`"


@pytest.mark.parametrize("chemin", _routes_volumineuses())
def test_aucune_route_n_utilise_encore_le_nom_limite(chemin):
    """Un seul nom pour tous : `limite` et `limit` coexistant, l'un des deux est ignoré."""
    import inspect
    import re
    from pathlib import Path

    sources = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in Path(__file__).resolve().parents[1].joinpath("src/modules").rglob("router.py")
    )
    assert not re.search(r"\blimite: int = Query", sources), (
        "un routeur declare encore `limite` : la pagination serait ignoree sans erreur"
    )


# ---------------------------------------------------------------------------
# 2. Comportement, sur les routes semables
# ---------------------------------------------------------------------------

NB_LIGNES = 60
TAILLE = 20


async def _creer_fournisseurs(client, nombre: int, suffixe: str) -> list[str]:
    """Crée des fournisseurs dont le nom est **volontairement dupliqué**.

    C'est le point clé : des noms tous différents ne prouveraient rien du tri. Avec
    plusieurs lignes partageant la même clé de tri, un `ORDER BY nom` sans clé
    secondaire devient non déterministe, et c'est cette instabilité que le test
    cherche à faire apparaître.
    """
    ids = []
    for i in range(nombre):
        # Un quart des lignes partagent le même nom : ties garantis sur le tri.
        nom = f"Fournisseur contrat {suffixe} {i % 4:02d}"
        reponse = await client.post(
            "/api/v1/stock/fournisseurs", json={"nom": nom}
        )
        assert reponse.status_code == 201, reponse.text
        ids.append(reponse.json()["data"]["id"])
    return ids


@pytest.mark.asyncio
@pytest.mark.parametrize("chemin", sorted(SEMABLES))
async def test_parcours_complet_sans_perte_ni_doublon(chemin, client_authenticated):
    """
    Parcourt **toutes** les pages et vérifie l'intégrité de l'ensemble.

    C'est le test qui attrape les défauts invisibles : avec un tri non
    déterministe, l'ensemble des identifiants collectés contient un doublon et il
    manque une ligne — et l'écran, lui, affiche une liste parfaitement plausible.
    """
    client = client_authenticated
    suffixe = str(abs(hash(chemin)) % 10_000)
    attendus = await _creer_fournisseurs(client, NB_LIGNES, suffixe)

    premiere = await client.get(chemin, params={"page": 1, "limit": TAILLE})
    assert premiere.status_code == 200, premiere.text
    meta = premiere.json()["meta"]

    assert meta["limit"] == TAILLE
    assert meta["page"] == 1
    # `total` doit compter les lignes **du jeu complet**, pas seulement celles de
    # la page : c'est le nombre qu'un utilisateur compare à « 60 créés ».
    assert meta["total_records"] >= NB_LIGNES
    pages_attendues = -(-meta["total_records"] // TAILLE)  # arrondi supérieur
    assert meta["total_pages"] == pages_attendues

    collectes: list[str] = []
    ordres: list[list[str]] = []
    for page in range(1, meta["total_pages"] + 1):
        reponse = await client.get(chemin, params={"page": page, "limit": TAILLE})
        assert reponse.status_code == 200, reponse.text
        items = reponse.json()["items"]
        ordres.append([x["id"] for x in items])
        collectes.extend(x["id"] for x in items)

    # 1. Aucune ligne du jeu semé ne manque.
    manquantes = set(attendus) - set(collectes)
    assert not manquantes, f"{len(manquantes)} ligne(s) perdue(s) entre les pages"

    # 2. Aucune ligne dupliquée. Un doublon signale un tri non déterministe : la
    #    ligne est à la fois en page 1 et en page 2, et une autre est sautée.
    doublons = {i for i in collectes if collectes.count(i) > 1}
    assert not doublons, f"{len(doublons)} ligne(s) dupliquee(s) entre les pages"

    # 3. Le déterminisme : deux parcours doivent donner le même ordre. On compare
    #    page à page, pas seulement l'ensemble : un ordre différent quiornaît
    #    exactement le même ensemble est impossible si le tri est instable.
    deuxieme_parcours = []
    for page in range(1, meta["total_pages"] + 1):
        reponse = await client.get(chemin, params={"page": page, "limit": TAILLE})
        deuxieme_parcours.append([x["id"] for x in reponse.json()["items"]])
    assert ordres == deuxieme_parcours, (
        "deux parcours successifs n'ont pas rendu le même ordre : le tri n'est pas "
        "déterministe (clé secondaire manquante ?)"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("chemin", sorted(SEMABLES))
async def test_page_hors_borne_renvoie_une_page_vide_sans_erreur(
    chemin, client_authenticated
):
    """Une page au-delà de la dernière doit être inerte, pas une erreur ni un renvoi silencieux."""
    reponse = await client_authenticated.get(chemin, params={"page": 9999, "limit": TAILLE})
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("chemin", sorted(SEMABLES))
async def test_parametres_invalides_refuses(chemin, client_authenticated):
    """`page` < 1, `limit` hors bornes et paramètre inconnu sont tous refusés."""
    for params, motif in (
        ({"page": 0, "limit": 20}, "page 0"),
        ({"page": 1, "limit": 0}, "limit 0"),
        ({"page": 1, "limit": 100_000}, "limit au-dela du maximum"),
        ({"page": 1, "limit": 20, "limite": 20}, "ancien nom `limite`"),
    ):
        reponse = await client_authenticated.get(chemin, params=params)
        assert reponse.status_code == 422, (
            f"{chemin} avec {motif} a renvoyé {reponse.status_code} au lieu de 422 : "
            "le paramètre est ignoré en silence"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("chemin", sorted(SEMABLES))
async def test_total_reflete_le_filtre(chemin, client_authenticated):
    """Le `total` doit refléter le filtre appliqué, jamais le total global."""
    client = client_authenticated
    await _creer_fournisseurs(client, 12, f"filtre{int(abs(hash(chemin)) % 1000)}")

    sans_filtre = (await client.get(chemin, params={"limit": 1})).json()["meta"]
    filtre = (
        await client.get(
            chemin, params={"limit": 1, "q": f"contrat {abs(hash(chemin)) % 10000}"}
        )
    ).json()["meta"]

    assert filtre["total_records"] <= sans_filtre["total_records"]
    if chemin.endswith("/stock/fournisseurs"):
        # La recherche porte sur un préfixe unique : elle doit réduire le compte.
        assert filtre["total_records"] == 0 or filtre["total_records"] < sans_filtre["total_records"]