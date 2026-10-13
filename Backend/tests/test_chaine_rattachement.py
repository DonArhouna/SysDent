"""La revision de correction enchaine bien sur la revision qu'elle corrige.

**Pourquoi un test statique.** Une revision qui s'insere au mauvais endroit
decale toute la chaine : `upgrade head` vise une revision et le proprietaire
pense en appliquer une autre. Le symptome n'apparait que sur une base, apres
l'avoir tatuee. Ici on lit les declarations, comme pour la chaine elle-meme.

**Il doit echouer tant que le fichier n'existe pas.** C'est la seule preuve que
le test regarde vraiment la revision, et pas une constante recopiee dedans.
"""

from __future__ import annotations

import ast
from pathlib import Path

VERSIONS = Path(r"C:\Users\RHONE\OneDrive\Desktop\SysDent\Backend\alembic_tenant\versions")

CIBLE = "f1a7c3d90b28"
ATTENDU_NOM = "d6a1f4c92b57"


def constantes(chemin: Path) -> tuple[str | None, str | None]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    trouvees: dict[str, str | None] = {}

    def _enregistrer(nom: str, valeur) -> None:
        if nom in ("revision", "down_revision"):
            trouvees[nom] = valeur.value if isinstance(valeur, ast.Constant) else None

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
            if noeud.value is not None:
                _enregistrer(noeud.target.id, noeud.value)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    _enregistrer(cible.id, noeud.value)
    return trouvees.get("revision"), trouvees.get("down_revision")


def graphe() -> dict[str, str | None]:
    g: dict[str, str | None] = {}
    for chemin in sorted(VERSIONS.glob("*.py")):
        revision, parent = constantes(chemin)
        if revision:
            g[revision] = parent
    return g


def test_la_revision_de_correction_existe() -> None:
    assert ATTENDU_NOM in graphe(), (
        f"revision {ATTENDU_NOM} absente du disque : le fichier de correction "
        "n'a pas ete ecrit"
    )


def test_la_revision_de_correction_enchaine_sur_la_revision_corrigee() -> None:
    g = graphe()
    assert g.get(ATTENDU_NOM) == CIBLE, (
        f"down_revision vaut {g.get(ATTENDU_NOM)!r}, attendu {CIBLE!r}"
    )


def test_rien_ne_s_intercale_entre_les_deux() -> None:
    g = graphe()
    enfants = [r for r, parent in g.items() if parent == CIBLE]
    assert enfants == [ATTENDU_NOM], (
        f"{CIBLE} a pour enfants {enfants} : une revision tierce s intercale"
    )


def test_la_chaine_garde_une_seule_tete() -> None:
    g = graphe()
    parents = {p for p in g.values() if p}
    tetes = [r for r in g if r not in parents]
    assert len(tetes) == 1, f"tetes de la chaine : {tetes}"


def test_les_deux_revisions_gelees_ne_sont_pas_modifiees() -> None:
    """`c4e7a2b6d9f1` et `f1a7c3d90b28` sont prouvees : elles sont gelees.

    On verifie leur chaine, pas leur contenu : un editeur qui les reordonnerait
    ne serait pas detecte ici, mais le hook de controle d integrite refuse
    aujourd'hui toute caractere non ASCII dans un fichier touche, et ces deux
    fichiers passent par lui a chaque commit.
    """
    g = graphe()
    assert g.get("c4e7a2b6d9f1") == "b3d7f1a9c2e4", "c4e7a2b6d9f1 a ete reecrite"
    assert g.get(CIBLE) == "c4e7a2b6d9f1", "f1a7c3d90b28 a ete reecrite"