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


def test_le_corps_du_client_passe_la_validation() -> None:
    """
    Le test qui répond à « le 422 est-il encore possible ? ».

    Un 422 naît de la validation d'entrée, **avant** tout accès à la base. On
    construit donc le modèle que la route utilise avec le corps exact produit
    par le tiroir, sans base ni patient. Si ce corps passe, le 422 ne peut pas
    venir de ce corps-là : il vient d'un autre.
    """
    from pydantic import ValidationError

    from src.modules.odontogramme.schemas import FacesMiseAJour

    corps = {
        "faces": [{"face": code, "etat": etat_par_defaut()} for code in _codes_du_client()]
    }

    try:
        model = FacesMiseAJour.model_validate(corps)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])} : {e['msg']}" for e in exc.errors()
        )
        pytest.fail(f"le corps du client est refuse par le serveur : {details}")

    assert len(model.faces) == len(FACES_DENT)


def test_les_etats_proposes_par_l_interface_sont_tous_valides() -> None:
    """
    L'interface propose ses états depuis `LIBELLES_ETATS`, le serveur valide
    contre `ETATS_DENT`. Ce sont deux tables **séparées** : si la première
    contenait une valeur absente de la seconde, le praticien pourrait choisir
    un état que l'enregistrement refuse — un 422 sur un simple clic.

    Le contrat le garantit ; ce test le verrouille.
    """
    from src.common.dentaire import ETATS_DENT, valider_etat_dent
    from src.modules.odontogramme.services import LIBELLES_ETATS

    refuses = sorted(set(LIBELLES_ETATS) - set(ETATS_DENT))
    assert refuses == [], (
        f"l'interface propose des etats que le serveur refuse : {refuses}"
    )

    for code in LIBELLES_ETATS:
        assert valider_etat_dent(code) == code


def etat_par_defaut() -> str:
    """L'état d'une face non modifiee, tel que le tiroir l'initialise."""
    source = TIROIR.read_text(encoding="utf-8")
    trouve = re.search(
        r"initialFaces\[f\.code\]\s*=\s*found\s*\?\s*found\.etat\s*:\s*'([^']+)'", source
    )
    assert trouve, "l'etat par defaut est introuvable dans dent-drawer.tsx"
    return trouve.group(1)
