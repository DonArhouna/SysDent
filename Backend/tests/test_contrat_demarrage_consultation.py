"""Démarrer une consultation ne doit jamais partir avec un corps refusé.

**Les deux 422, prouvés sur le schéma.**

`ConsultationCreate` exige `patient_id`, un `motif` d'au moins deux caractères,
et refuse toute valeur non-UUID pour `cabinet_id`. La page de liste construisait
son corps avec deux pièges :

- `cabinet_id: cabinetId || cabinetActifId || (cabinets[0]?.id ?? '')` — sans
  site résolu, le repli produisait une **chaîne vide**, et la validation UUID
  la refusait. Le propriétaire ne pouvait pas démarrer une consultation alors
  que le champ n'était pas le sien ;
- `motif` partait tel quel : vide, il était refusé par `min_length=2`.

Ironie du sort : la même ligne portait, sur `praticien_id`, un commentaire
expliquant exactement ce piège pour UUID — et le champ voisin, soumis au même
validateur, restait ouvert.

Ce test construit les corps que la page peut produire et les fait passer par le
vrai schéma du serveur. Il lit aussi la page pour vérifier que le repli n'est
plus une chaîne vide.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "Backend"))

from pydantic import ValidationError  # noqa: E402

from src.modules.consultations.schemas import ConsultationCreate  # noqa: E402

PAGE = RACINE / "Frontend" / "src" / "features" / "consultations" / "pages" / "consultations-list-page.tsx"


def _valider(corps: dict) -> None:
    try:
        ConsultationCreate.model_validate(corps)
    except ValidationError as exc:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])} : {e['msg']}" for e in exc.errors()
        )
        pytest.fail(f"le serveur refuse ce corps : {detail}")


def test_le_nominal_passe() -> None:
    """Le cas de référence : tout est résolu."""
    _valider(
        {
            "patient_id": str(uuid.uuid4()),
            "cabinet_id": str(uuid.uuid4()),
            "praticien_id": str(uuid.uuid4()),
            "motif": "Suivi",
        }
    )


def test_patient_seul_sans_cabinet_passe() -> None:
    """
    Aucun site résolu : le champ doit être **absent**, pas vide.

    C'est le cas du profil qui n'a pas `CABINETS:READ` — précisément le profil
    qui a hierarchicalement ne peut pas charger la liste des sites.
    """
    _valider({"patient_id": str(uuid.uuid4()), "motif": "Suivi"})


def test_une_chaine_vide_pour_un_uuid_est_refusee() -> None:
    """Le défaut qu'on veut voir disparaître : on le fixe comme|Non."""
    with pytest.raises(ValidationError):
        ConsultationCreate.model_validate(
            {"patient_id": str(uuid.uuid4()), "cabinet_id": "", "motif": "Suivi"}
        )


def test_un_motif_trop_court_est_refuse() -> None:
    with pytest.raises(ValidationError):
        ConsultationCreate.model_validate(
            {"patient_id": str(uuid.uuid4()), "motif": "x"}
        )


def test_la_page_n_envoie_plus_de_chaine_vide() -> None:
    """
    Le garde sur le **code de la page**, pas sur le schéma.

    Sans lui, réintroduire `?? ''` ne ferait échouer aucun test : le schéma
    refuserait bien la chaîne vide, mais rien ne dirait que c'est la page qui
    l'a produite.
    """
    source = PAGE.read_text(encoding="utf-8")

    assert "cabinet_id: cabCible || undefined" in source, (
        "cabinet_id doit partir absent quand aucun site n'est resolu, jamais vide"
    )
    assert "'')" not in source.split("const cabCible")[-1].split("\n")[0], (
        "le repli de cabinet_id ne doit plus produire une chaine vide"
    )
    assert "motif.trim().length < 2" in source, (
        "le motif doit etre verifie avant l'envoi, pas refuse par le serveur"
    )
