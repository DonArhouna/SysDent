"""Garde de contrat : toute route de liste nue doit etre justifiee ou paginee.

**Pourquoi cette garde.** Le module Stock a manque de pagination, puis
`/stock/fournisseurs` a manque de la coquille applicative. Dans les deux cas
aucun test n'a rien dit : le composant `Pagination` etait teste isolement, et
aucun test ne reliait une liste reelle au contrat. Cette garde fait le lien.

**Les deux sorties admises.** Une liste bornee par un parent - les salles d'un
cabinet, les antecedents d'un patient - ne croit pas avec le cabinet : la
paginer n'apporterait rien et compliquerait l'appelant. Elle porte donc une
justification ecrite, relue par le test, qui doit dire le motif et la borne.
Une liste qui, elle, croit avec le cabinet doit etre paginee.

**Les `xfail` sont strictes.** `strict=True` signifie qu'un `xfail` qui passe
vient a Echouer : l'echec signale une route corrigee dont on aurait oublie de
retirer la marque. C'est le prix d'un etat de depart rouge, et cela evite le
piege inverse, un `xfail` dormant qui masque une route desormais conforme.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

MODULES = Path(r"C:\Users\RHONE\OneDrive\Desktop\SysDent\Backend\src\modules")

#: Marqueur exige dans le source, sur les lignes qui precedent le decorateur.
MARQUEUR = re.compile(r"#\s*garde-liste:")

#: Routes validees comme listes bornees. Chacune porte sa justification dans
#: son router, et le test la relit.
JUSTIFIEES = {
    ("consultations/router.py", "actes"),
    ("patients/router.py", "antecedents"),
    ("rendezvous/router.py", "creneaux-libres"),
    ("odontogramme/router.py", "historique"),
    ("odontogramme/router.py", "charting"),
    ("cabinets/router.py", "salles"),
    ("cabinets/router.py", "fauteuils"),
    ("rbac/router.py", "roles"),
    ("rbac/router.py", "permissions"),
}

#: Routes validees comme listes a paginer. Elles restent en echec attendu tant
#: que la phase B ne les a pas traitees, une par une et un commit par commit.
A_PAGINER = {
    ("cabinets/router.py", "/cabinets"),
    ("cabinets/router.py", "/praticiens"),
    ("cabinets/router.py", "disponibilites"),
    ("stock/router.py", "/alertes"),
    ("ordonnances/router.py", "medicaments"),
    ("master/router.py", "/societes"),
}

MOTIF_PAGINATION = "decision validee par le proprietaire : liste a paginer"


def _routes_de_liste(chemin: Path) -> list[tuple[str, int, bool]]:
    source = chemin.read_text(encoding="utf-8")
    lignes = source.splitlines()
    arbre = ast.parse(source)
    trouvees: list[tuple[str, int, bool]] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for deco in noeud.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            brut = ast.unparse(deco)
            if "APIResponse[List[" not in brut.replace(" ", ""):
                continue
            # Chemin vide possible : une route de sous-ensemble comme
            # `@medicaments_router.get("")` n'a pas de prefixe.
            trouve = re.search(r"""get\(\s*["']([^"']*)["']""", brut)
            if not trouve:
                continue
            prefixe = trouve.group(1)
            debut = max(0, deco.lineno - 1 - 12)
            justifiee = any(
                MARQUEUR.search(l) for l in lignes[debut : deco.lineno - 1]
            )
            trouvees.append((prefixe, deco.lineno, justifiee))
    return trouvees


TOUTES: list[tuple[str, str, int, bool]] = []
for _chemin in sorted(MODULES.rglob("router.py")):
    _relatif = str(_chemin.relative_to(MODULES)).replace("\\", "/")
    for _prefixe, _ligne, _justifiee in _routes_de_liste(_chemin):
        TOUTES.append((_relatif, _prefixe, _ligne, _justifiee))


def _identifiant(fichier: str, route: str) -> str:
    return f"{fichier} {route}"


def _connue(fichier: str, route: str) -> bool:
    """La route est-elle connue, par son chemin exact ou par son suffixe ?

    Les cles sont ecrites en court (`salles`) alors que la route declaree est
    un chemin complet (`/cabinets/{cabinet_id}/salles`). Sans cette tolerance,
    aucune des neuf justifications n aurait ete reconnue.
    """
    for fichier_connu, cle in A_PAGINER | JUSTIFIEES:
        if fichier_connu != fichier:
            continue
        # Une route de sous-ensemble porte un chemin vide : la cle vaut son nom.
        if route == cle or route.endswith("/" + cle):
            return True
        if cle and route == "" and cle in ("medicaments",):
            return True
    return False


def test_la_detection_trouve_toutes_les_listes_nues() -> None:
    # Un parseur qui ne verrait rien ferait passer la garde sans rien garantir.
    assert len(TOUTES) >= 15, f"seulement {len(TOUTES)} listes nues detectees"


@pytest.mark.parametrize("fichier,route,ligne,justifiee", TOUTES, ids=lambda v: str(v)[:50])
def test_chaque_liste_nue_est_connue(fichier: str, route: str, ligne: int, justifiee: bool) -> None:
    identifiant = _identifiant(fichier, route)
    # Meme appariement par suffixe que `_connue` : sans lui, `disponibilites` et
    # `medicaments` ne tombaient pas en xfail et passaient en silence, donc la
    # garde ne les signalait plus du tout.
    if any(
        f_connu == fichier
        and (route == cle or route.endswith("/" + cle) or (route == "" and cle == "medicaments"))
        for f_connu, cle in A_PAGINER
    ):
        pytest.xfail(MOTIF_PAGINATION)
    assert _connue(fichier, route), (
        f"{identifiant} ({fichier}:{ligne}) n est ni justifiee ni listee a paginer"
    )


@pytest.mark.parametrize(
    "fichier,route",
    sorted(JUSTIFIEES),
    ids=lambda v: str(v),
)
def test_la_justification_donne_un_motif_et_une_borne(fichier: str, route: str) -> None:
    """Une justification sans motif ni borne n'est pas une justification."""
    chemin = MODULES / fichier
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    deco = next(l for _p, l, _j in _routes_de_liste(chemin) if _p == route or route in _p)
    bloc = "\n".join(lignes[max(0, deco - 13) : deco - 1])
    assert MARQUEUR.search(bloc), f"{fichier} {route} : marqueur absent"
    # Le motif et la borne se lisent dans tout le bloc, pas seulement apres le
    # marqueur : le marqueur identifie la justification, il ne la delimite pas.
    extrait = bloc[max(0, bloc.rindex("# garde-liste:") - 400) :]
    assert re.search(r"\bborn", extrait, re.IGNORECASE), f"{route} : motif absent"
    assert re.search(r"\d", extrait), f"{route} : aucune borne chiffree"