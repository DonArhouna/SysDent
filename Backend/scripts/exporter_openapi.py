"""Exporte le schema OpenAPI du backend pour le client TypeScript.

Ce script est l'autre moitie du controle de contrat : le schema ecrit ici est la
source unique des types du backoffice. Sans lui, le front ne peut pas verifier un
nom de champ, et la regle « verifie des deux cotes dans le meme commit » n'a rien
sur quoi s'appuyer.

Usage, depuis ``Backend`` :

    .\\.venv\\Scripts\\python.exe scripts\\exporter_openapi.py

Ecrit ``Backoffice/openapi.json``. Le fichier est **versionne** : sans cela, une
modification d'API ne laisserait aucune trace, et la divergence ne se verrait
qu'a l'execution.

Aucune connexion a la base n'est requise : le schema est construit a partir des
annotations de l'application, pas de son etat.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CIBLE = RACINE.parent / "Backoffice" / "openapi.json"


def exporter() -> Path:
    sys.path.insert(0, str(RACINE))
    from src.main import app

    schema = app.openapi()

    # Une cle d'ecriture stable : le fichier versionne ne doit changer que si
    # l'API change. Sans cela, chaque regeneration produirait un diff enorme, et
    # le controle de contrat deviendrait illisible - donc ignore.
    schema = json.loads(json.dumps(schema, sort_keys=True, ensure_ascii=False))

    CIBLE.parent.mkdir(parents=True, exist_ok=True)
    CIBLE.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return CIBLE


if __name__ == "__main__":
    chemin = exporter()
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    print(f"  ecrit : {chemin}")
    print(
        f"  {len(donnees['paths'])} chemins, "
        f"{len(donnees.get('components', {}).get('schemas', {}))} schemas"
    )