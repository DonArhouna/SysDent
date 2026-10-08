"""Inventaire des routes GET de liste, a partir des routes enregistrees.

Ni memoire, ni documentation : la liste est extraite de l'objet `app` lui-meme
(spectre OpenAPI). C'est la seule facon de garantir qu'un endpoint ajoute
recemment ne soit pas oublie — c'est precisement la derive qui a valu deux bugs
de permissions.

Usage : `.venv\\Scripts\\python.exe tests\\inventaire_listes.py`
Code de sortie 1 si une liste volumineuse n'est pas paginee.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Python ajoute le dossier du script en tete de `sys.path`. Ici ce dossier
# contient un paquet `platform/` qui **masque le module standard** `platform`,
# dont SQLAlchemy a besoin a l'import : l'echec serait obscur et sans rapport
# avec l'objet du script. On retire donc ce dossier avant tout import.
_DOSSIER_SCRIPT = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p).resolve() != _DOSSIER_SCRIPT]
sys.path.insert(0, str(_DOSSIER_SCRIPT.parent))  # Backend/, ou vit le paquet `src`

from src.main import app  # noqa: E402

#: Chemins dont la liste croit sans borne : ils DOIVENT etre pagines.
#:
#: On raisonne sur le **chemin complet**, pas sur le module : un module peut
#: contenir a la fois une liste volumineuse (`/rendez-vous`) et des vues bornees
#: (`/rendez-vous/agenda`, qui ne montre qu'une journee). Les confondre ferait
#: paginer l'agenda — qui tient dans un ecran — et laisserait passer la vraie
#: liste, ce qui est l'inverse de l'effet voulu.
LISTES_VOLUMINEUSES = {
    "/api/v1/patients",
    "/api/v1/consultations",
    "/api/v1/rendez-vous",
    "/api/v1/devis",
    "/api/v1/ordonnances",
    "/api/v1/factures",
    "/api/v1/factures/journal-caisse",
    "/api/v1/caisse/paiements-hors-session",
    "/api/v1/stock/articles",
    "/api/v1/stock/mouvements",
    "/api/v1/stock/commandes",
    "/api/v1/stock/fournisseurs",
    "/api/v1/utilisateurs",
    "/api/v1/audit",
}

#: Chemins explicitement des **vues bornees** ou des **referentiels**. Les
#: paginer n'apporterait rien et compliquerait le contrat d'un cote comme de
#: l'autre. Cette liste est une decision, pas un oubli : elle se relit.
VIEWS_BORNEES = {
    "/api/v1/rendez-vous/agenda": "vue d'une journee",
    "/api/v1/rendez-vous/creneaux-libres": "creneaux d'un creneau de place",
    "/api/v1/rendez-vous/referentiel": "statuts de rendez-vous",
    "/api/v1/ordonnances/medicaments": "catalogue de medicaments",
    "/api/v1/stock/alertes": "produits sous le seuil",
    "/api/v1/cabinet-selector": "hors perimetre (route inexistante)",
}


def _sources_routers() -> str:
    """Concatene les sources des routers : sert a reperer les plafonds en dur."""
    morceaux = []
    for chemin in Path(__file__).resolve().parents[1].joinpath("src/modules").rglob("router.py"):
        morceaux.append(chemin.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(morceaux)


def _enveloppe(reponse: dict) -> str:
    """Nom de l'enveloppe de reponse : `PaginatedResponse` ou `APIResponse`."""
    contenu = reponse.get("content", {}).get("application/json", {})
    schema = contenu.get("schema", {})
    # Les enveloppes sont generiques : le nom apparait dans `anyOf`/`$ref`.
    texte = str(schema)
    if "Paginated" in texte:
        return "pagin"
    if "APIResponse" in texte or "APIResponse" in texte:
        return "ENTIER"
    # Reponses libres : ni enveloppe ni pagination, on le signale a part.
    return "LIBRE"


def analyser() -> list[dict]:
    sources = _sources_routers()
    lignes = []
    for chemin, operations in sorted(app.openapi().get("paths", {}).items()):
        get = operations.get("get")
        if not get:
            continue
        morceaux = chemin.split("/")
        # `/api/v1/<module>` : au-dela, ce n'est plus une liste de premier niveau.
        if len(morceaux) < 4 or morceaux[1] != "api" or morceaux[2] != "v1":
            continue
        if any("{" in m for m in morceaux[3:]):
            continue  # route de detail
        module = morceaux[3]
        enveloppe = _enveloppe(get.get("responses", {}).get("200", {}))
        # Un plafond en dur se lit dans la declaration de la route ; on cherche la
        # ligne `limit` la plus proche du chemin dans les sources.
        plafond = ""
        # La declaration porte le chemin **relatif** au router
        # (`@router.get("/commandes")`), pas le chemin complet monte.
        suffixe = "/" + "/".join(morceaux[3:])
        motif = re.search(
            rf'@router\.get\(\s*"{re.escape(suffixe)}"'
            r"[\s\S]{0,700}?limit: int = Query\((\d+)([^)]*)\)",
            sources,
        )
        if motif:
            maximum = re.search(r"le=(\d+)", motif.group(2) or "")
            plafond = f"defaut {motif.group(1)}" + (
                f" / max {maximum.group(1)}" if maximum else ""
            )
        elif re.search(
            rf'@router\.get\(\s*"{re.escape(suffixe)}"'
            r"[\s\S]{0,700}?params: PaginationParams = Depends\(\)",
            sources,
        ):
            plafond = "PaginationParams via Depends()"
        lignes.append(
            {
                "module": module,
                "chemin": chemin,
                "pagine": enveloppe == "pagin",
                "enveloppe": enveloppe,
                "plafond": plafond,
            }
        )
    return lignes


def main() -> int:
    lignes = analyser()
    non_conformes = [
        l for l in lignes if l["chemin"] in LISTES_VOLUMINEUSES and not l["pagine"]
    ]
    print(f"{len(lignes)} routes GET de liste\n")
    print(f"  {'module':<20}{'enveloppe':<11}{'plafond':<24}chemin")
    for l in lignes:
        marques = []
        bornee = VIEWS_BORNEES.get(l["chemin"])
        if bornee:
            # Décision explicite : la pagination n'apporterait rien et alourdirait
            # le contrat d'un côté comme de l'autre.
            marques.append(f"vue bornee — {bornee}")
        elif l["chemin"] in LISTES_VOLUMINEUSES and not l["pagine"]:
            marques.append("A PAGINER")
        if not l["pagine"] and l["plafond"] and not bornee:
            marques.append("PLAFOND SILENCIEUX")
        suffixe = ("  <== " + ", ".join(marques)) if marques else ""
        print(
            f"  {l['module']:<20}{l['enveloppe']:<11}{(l['plafond'] or '-'):<24}"
            f"{l['chemin']}{suffixe}"
        )
    print(
        f"\n  {len(lignes) - len(non_conformes)} conformes, "
        f"{len(non_conformes)} listes volumineuses non paginees."
    )
    return 1 if non_conformes else 0


if __name__ == "__main__":
    raise SystemExit(main())