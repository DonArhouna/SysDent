"""Une panne dans un controle de sante ne doit pas devenir un 500.

**Ce que la docstring promet.** `HealthService.global_` ecrit noir sur
blanc : « un seul echec de la base plateforme doit apparaitre dans le corps de
la reponse plutot que de faire echouer l'appel : une page de supervision qui
affiche "service indisponible" ne montre pas QUEL service ».

**Ce que le code fait.** `global_` appelle ses controles dans une liste, sans
`try` autour de chacun. Chaque petit controle rattrape *son* erreur en interne,
mais seulement un `SQLAlchemyError`. Or un echec de connexion n'est **pas**
encapsule par SQLAlchemy : il remonte nu, en `ConnectionRefusedError` ou en
`OSError`. On l'a mesure le 11/10 sur le login, et c'est la meme panne ici.

Un seul de ces controles suffit donc a transformer la page de sante - et le
tableau de bord, qui l'appelle - en 500.

Ce test ne suppose rien du declencheur : il rend un controle incapable de
repondre, et exige que la reponse reste une reponse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.modules.platform.services.health import HealthService  # noqa: E402


@pytest.mark.parametrize(
    "erreur",
    [
        # Formes mesurees le 11/10 sur une connexion reellement close : ces
        # exceptions ne passent par aucun encapsulant SQLAlchemy.
        ConnectionRefusedError(111, "Connection refused"),
        OSError(
            "Multiple exceptions: [Errno 10061] Connect call failed ('::1', 55435, 0, 0)"
        ),
    ],
)
def test_un_controle_en_panne_ne_produit_pas_de_500(monkeypatch, erreur) -> None:
    """
    Un controle qui leve doit degrader la reponse, pas la faire echouer.

    Le message doit nommer le composant en panne : c'est precisement ce que la
    docstring demande, et ce qu'un operateur doit pouvoir lire sans ouvrir les
    journaux.
    """
    async def _en_panne(*args, **kwargs):
        raise erreur

    async def _va(*args, **kwargs):
        return {"composant": "sain", "ok": True}

    from src.modules.platform.services import health as module

    for nom in (
        "base_plateforme",
        "base_master",
        "files_clients",
        "bases_absentes",
        "migrations_par_tenant",
        "catalogue",
        "jobs_planifies",
    ):
        monkeypatch.setattr(HealthService, nom, _va)
    monkeypatch.setattr(HealthService, "schemas_tenants", _en_panne)

    import asyncio

    resultat = asyncio.run(HealthService.global_(None, None))

    assert resultat["statut"] == "degrade", (
        f"une panne doit degrader la reponse, pas la faire echouer "
        f"(obtenu : {type(resultat).__name__})"
    )
    assert "schemas_tenants" in resultat["en_panne"], (
        "la page doit nommer le composant en panne"
    )