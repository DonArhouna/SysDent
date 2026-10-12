"""L'ordonnance part d'une consultation, et le corps qu'on envoie est valide.

**Ce que le propriétaire demandait.** Le champ « ID consultation associée »
était saisi à la main. Une ordonnance pouvait donc partir rattachée à une
consultation qui n'était pas celle du patient affiché, et la saisie d'un UUID
était fausse la plupart du temps.

La fiche de consultation passe déjà `?consultation_id=` : le point d'entrée
fait la liaison. Ouverte sans, la modale affiche un message et **ne construit
rien** - le garde de soumission existait déjà, ce test le verrouille.

Ce test vérifie trois choses :

- le corps émis passe le vrai schéma serveur ;
- le champ manuel a disparu du composant ;
- le garde de soumission tient toujours, pour qu'aucune ordonnance partielle ne
  parte.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "Backend"))

from pydantic import ValidationError  # noqa: E402

from src.modules.ordonnances.schemas import OrdonnanceCreate  # noqa: E402

MODAL = RACINE / "Frontend" / "src" / "features" / "ordonnances" / "components" / "ordonnance-modal.tsx"


def test_le_corps_emis_passe_le_schema_serveur() -> None:
    """Le corps construit par le modal, tel quel."""
    OrdonnanceCreate.model_validate(
        {
            "patient_id": str(uuid.uuid4()),
            "consultation_id": str(uuid.uuid4()),
            "lignes": [
                {"medicament_texte": "Amoxicilline 500 mg", "posologie": "1 cp x 3 / jour"}
            ],
            "notes_generales": "Poursuivre 7 jours.",
        }
    )


def test_sans_consultation_le_schema_refuse() -> None:
    """Le garde de contrat : une ordonnance sans consultation n'existe pas."""
    with pytest.raises(ValidationError):
        OrdonnanceCreate.model_validate(
            {
                "patient_id": str(uuid.uuid4()),
                "consultation_id": "",
                "lignes": [{"medicament_texte": "X", "posologie": "Y"}],
            }
        )


def test_il_n_y_a_plus_de_champ_de_saisie_de_la_consultation() -> None:
    """
    Le garde sur le **composant**.

    Sans lui, remettre un `<Input>` éditable ne ferait échouer aucun test : le
    schéma serveur refuserait toujours une chaîne vide, mais rien ne dirait que
    c'est l'écran qui la propose.
    """
    source = MODAL.read_text(encoding="utf-8")

    assert "onChange={(e) => setConsultationId(e.target.value)}" not in source, (
        "l'identifiant de consultation ne doit plus etre saisi : il vient du "
        "point d'entree"
    )
    assert "readOnly" in source, "l'identifiant repris doit etre affiche en lecture seule"


def test_le_garde_de_soumission_tient() -> None:
    """Aucune ordonnance partielle ne part quand la consultation manque."""
    source = MODAL.read_text(encoding="utf-8")

    assert "if (!consultationId)" in source, (
        "sans consultation, la soumission doit s'arreter avant tout appel"
    )
    garde = source.split("if (!consultationId)")[1].split("return")[0]
    assert "ordonnancesApi.creer" not in garde, (
        "l'appel de creation ne doit pas preceder le retour"
    )