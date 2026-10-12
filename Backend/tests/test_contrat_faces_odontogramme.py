"""Les codes de face envoyés par le client doivent exister côté serveur.

**Le 422 du praticien, expliqué.** Le tiroir de dent envoie **toujours les
cinq faces** à l'enregistrement, pas seulement celles qui ont changé. Donc un
seul code de face hors nomenclature fait échouer *toute* la sauvegarde — et le
praticien voit « 422 » sans comprendre quoi, alors que la dents est bien
valide.

**Le contrat est la cause, et il diverge.** Constaté le 12/10 :

| `dent-drawer.tsx` (client) | `dentaire.py` (serveur) |
|---|---|
| `OCCLUSALE`        | `OCCLUSAL_INCISAL` |
| `LINGUALE`         | `LINGUAL_PALATIN`  |
| `MESIALE`          | `MESIAL`           |
| `DISTALE`          | `DISTAL`           |
| `VESTIBULAIRE`     | `VESTIBULAIRE`     |

Quatre des cinq divergeaient. Le serveur est la source de la nomenclature :
`FACES_COURTES` y associe déjà le code court au code long, et c'est lui que
l'API renvoie dans `/odontogramme/referentiel/etats`.

**Pourquoi ce test lit un fichier TypeScript.** Le contrat n'est écrit nulle
part d'un seul côté : il est dans un `.tsx` et dans un `.py`. Un test qui
changerait de côté ne verrait pas la divergence. Celui-ci lit les deux, donc
les deux peuvent changer sans que personne ne s'en aperçoive.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "Backend"))

from src.common.dentaire import FACES_COURTES, FACES_DENT  # noqa: E402

TIROIR = RACINE / "Frontend" / "src" / "features" / "odontogramme" / "components" / "dent-drawer.tsx"


def _codes_du_client() -> dict[str, str]:
    """`{code: court}` déclarés par le client, lus dans le fichier source."""
    source = TIROIR.read_text(encoding="utf-8")
    bloc = re.search(r"const FACES_DECOUPEES = \[(.*?)\]", source, re.S)
    assert bloc, "FACES_DECOUPEES est introuvable dans dent-drawer.tsx"

    codes = re.findall(r"code:\s*'([^']+)'", bloc.group(1))
    courts = re.findall(r"court:\s*'([^']+)'", bloc.group(1))
    assert len(codes) == len(courts) == len(FACES_DENT), (
        f"le client declare {len(codes)} faces, le serveur {len(FACES_DENT)}"
    )
    return dict(zip(codes, courts))


def test_chaque_face_envoyee_existe_cote_serveur() -> None:
    """
    Le test de contrat. Il échouait le 12/10, sur quatre des cinq faces.
    """
    hors_nomenclature = [
        code for code in _codes_du_client() if code not in FACES_DENT
    ]

    assert hors_nomenclature == [], (
        f"le client envoie des faces que le serveur refuse : {hors_nomenclature}. "
        f"Valeurs acceptees : {list(FACES_DENT)}. "
        f"Comme le tiroit envoie toujours les cinq faces, une seule invalide "
        f"fait echouer toute la sauvegarde en 422."
    )


def test_chaque_face_court_est_la_bonne_abreviation() -> None:
    """L'abréviation sert à l'affichage : une inversion se voit à l'écran."""
    faux = [
        (code, court, FACES_COURTES[code])
        for code, court in _codes_du_client().items()
        if code in FACES_COURTES and court != FACES_COURTES[code]
    ]

    assert faux == [], f"abreviations divergentes (code, envoyee, attendue) : {faux}"


def test_le_client_envoie_bien_toutes_les_faces() -> None:
    """
    Ce qui transforme un code invalide en 422 *systematique* et non aleatoire.

    Le tiroit envoie `Object.entries(faces)` sans filtrer : les cinq faces
    partent a chaque enregistrement. Le test le verifie sur la source, parce
que c'est cette propriete qui rend le defaut visible a chaque fois,
    plutot que sporadique.
    """
    source = TIROIR.read_text(encoding="utf-8")

    assert "Object.entries(faces).map" in source, (
        "le tiroit envoie toutes les faces sans filtrer : toute face hors "
        "nomenclature rend l'enregistrement entier inutilisable"
    )


@pytest.mark.parametrize("face", FACES_DENT)
def test_le_serveur_accepte_la_face_du_client(face: str) -> None:
    """Chaque face du client passe la validation serveur."""
    from src.common.dentaire import valider_face

    assert valider_face(face) == face
    assert valider_face(face.lower()) == face, "la normalisation doit rester valable"
