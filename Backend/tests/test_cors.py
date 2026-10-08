"""CORS — liste blanche explicite, jamais `*`.

Pourquoi ce test existe à part : une régression de CORS ne se voit pas dans les
tests de métier. Toutes les requêtes partent du même origine en développement,
donc tout passe ; et le jour où le CORS casse, **tout** casse d'un coup en
production, avec un message côté navigateur que personne ne sait relier à une
ligne de configuration.

Deux propriétés à garantir :

1. l'origine du backoffice (5174) obtient bien un préflight ;
2. une origine inconnue est refusée — c'est la moitié de sécurité du test, et
   celle qu'un configuration trop permissive casse sans bruit.

Un accès support donne accès à **tous** les cabinets. Une origine réfléchie, ou un
`*`, suffirait à ouvrir la porte depuis n'importe quel site.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import settings
from src.main import app

ORIGINE_CLIENT = "http://127.0.0.1:5173"
ORIGINE_BACKOFFICE = "http://127.0.0.1:5174"
ORIGINE_INCONNUE = "http://site-inconnu.example"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as c:
        yield c


async def test_preflight_depuis_le_backoffice_reussi(client):
    reponse = await client.options(
        "/api/v1/platform/auth/login",
        headers={
            "Origin": ORIGINE_BACKOFFICE,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert reponse.status_code == 200, reponse.text
    autorise = reponse.headers.get("access-control-allow-origin")
    assert autorise == ORIGINE_BACKOFFICE, (
        f"le préflight du backoffice a renvoyé {autorise!r} au lieu de {ORIGINE_BACKOFFICE!r}"
    )


async def test_preflight_depuis_le_client_reussi(client):
    """L'application client doit continuer de fonctionner : c'est une régression sinon."""
    reponse = await client.options(
        "/api/v1/platform/auth/login",
        headers={"Origin": ORIGINE_CLIENT, "Access-Control-Request-Method": "POST"},
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.headers.get("access-control-allow-origin") == ORIGINE_CLIENT


async def test_origine_inconnue_refusee(client):
    reponse = await client.options(
        "/api/v1/platform/auth/login",
        headers={"Origin": ORIGINE_INCONNUE, "Access-Control-Request-Method": "POST"},
    )
    # Une origine inconnue ne doit jamais recevoir d'en-tête d'autorisation.
    # La réponse peut être 400 : le refus est fait par le middleware.
    assert reponse.headers.get("access-control-allow-origin") is None, (
        "une origine inconnue a reçu un en-tête d'autorisation : la liste blanche est "
        "trop permissive"
    )


def test_la_liste_blanche_ne_contient_jamais_le_joker():
    """`*` et l'origine réfléchie sont explicitement exclus de la configuration."""
    assert "*" not in settings.CORS_ORIGINS, "CORS_ORIGINS ne doit jamais contenir `*`"
    for origine in settings.CORS_ORIGINS:
        assert origine != "*"
        assert origine.startswith(("http://", "https://")), (
            f"origine absente du schéma : {origine}"
        )
    # Les deux applications doivent être autorisées : les oublier casse l'une des
    # deux sans que l'autre ne le signale.
    assert ORIGINE_BACKOFFICE in settings.CORS_ORIGINS
    assert ORIGINE_CLIENT in settings.CORS_ORIGINS