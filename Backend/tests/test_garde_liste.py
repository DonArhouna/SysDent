"""Garde de contrat : toute route de liste nue doit etre justifiee par ecrit.

**Pourquoi cette garde.** Le module Stock a manque de pagination, puis
`/stock/fournisseurs` a manque de la coquille applicative. Dans les deux cas,
aucun test n'a rien dit : le composant `Pagination` etait teste isolement, et
aucun test ne reliait une liste reelle au contrat. Une garde lie les deux.

**Ce qui est exige.** Une route GET qui renvoie `APIResponse[List[...]]` est
admise si, et seulement si, elle porte le marqueur `# garde-liste:` suivi d'un
motif et d'une borne. Une liste bornee par un parent - les salles d'un cabinet,
les antécédents d'un patient - ne cresce pas avec le cabinet : la paginer
n'apporterait rien et compliquerait l'appelant. Une liste qui, elle, croit avec
le cabinet, doit etre paginee.

**Ce que la garde ne fait pas.** Elle ne verifie pas la pagination : une route
paginee et une route justifiee sont les deux sorties admises. La pagination
elle-meme a ses propres tests de contrat, route par route.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

MODULES = Path(r"C:\Users\RHONE\OneDrive\Desktop\SysDent\Backend\src\modules")

#: Marqueur exige dans le source, sur la ligne qui precede le decorateur.
MARQUEUR = re.compile(r"#\s*garde-liste:")


def _lignes_avant(source: str, ligne_decorateur: int, fenetre: int = 12) -> list[str]:
    lignes = source.splitlines()
    debut = max(0, ligne_decorateur - 1 - fenetre)
    return lignes[debut : ligne_decorateur - 1]


def routes_de_liste_nue() -> list[tuple[str, str, int, bool]]:
    """(fichier relatif, route, ligne, justifiee) pour chaque liste nue."""
    trouvees: list[tuple[str, str, int, bool]] = []
    for chemin in sorted(MODULES.rglob("router.py")):
        source = chemin.read_text(encoding="utf-8")
        lignes = source.splitlines()
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for deco in noeud.decorator_list:
                appel = deco.func if isinstance(deco, ast.Call) else deco
                if not isinstance(appel, ast.Attribute) or appel.attr != "get":
                    continue
                # La reponse doit etre une liste nue : APIResponse[List[X]].
                brut = ast.unparse(deco)
                if not re.search(r"APIResponse\[\s*List\[", brut):
                    continue
                # Le chemin peut valoir la chaine vide : une route de sous-ensemble
                # comme `@medicaments_router.get("")` n'a pas de prefixe. Un motif
                # exigeant un `/` la laissait passer, et la garde ne veillait donc
                # pas sur elle.
                trouve = re.search(r"""get\(\s*["']([^"']*)["']""", brut)
                if not trouve:
                    continue
                prefixe = trouve.group(1)
                justifiee = any(
                    MARQUEUR.search(l) for l in _lignes_avant(source, deco.lineno)
                )
                trouvees.append(
                    (
                        str(chemin.relative_to(MODULES)).replace("\\", "/"),
                        prefixe,
                        deco.lineno,
                        justifiee,
                    )
                )
    return trouvees


TOUTES = routes_de_liste_nue()
NON_JUSTIFIEES = [r for r in TOUTES if not r[3]]


def test_la_detection_trouve_des_listes_nues() -> None:
    # Un parseur qui ne verrait rien ferait passer la garde sans rien garantir.
    assert len(TOUTES) >= 15, f"seulement {len(TOUTES)} listes nues detectees"


def test_chaque_liste_nue_est_paginationnee_ou_justifiee() -> None:
    assert not NON_JUSTIFIEES, (
        "routes de liste nue sans justification ecrite (marqueur `# garde-liste:` "
        "a poser sur la ligne qui precede le decorateur) :\n"
        + "\n".join(f"  {f}:{l}  {r}" for f, r, l, _ in NON_JUSTIFIEES)
    )


@pytest.mark.parametrize("fichier,route,ligne,justifiee", TOUTES, ids=lambda v: str(v)[:40])
def test_la_justification_donne_un_motif_et_une_borne(
    fichier: str, route: str, ligne: int, justifiee: bool
) -> None:
    """Une justification sans motif ni borne n'est pas une justification."""
    if not justifiee:
        pytest.skip("traite par la garde d'ensemble")

    chemin = MODULES / fichier
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    texte = "\n".join(_lignes_avant("\n".join(lignes), ligne))
    bloc = texte[texte.rindex("# garde-liste:") :]
    assert re.search(r"\bborn", bloc, re.IGNORECASE), f"{route} : motif absent"
    assert re.search(r"\d", bloc), f"{route} : aucune borne chiffree"