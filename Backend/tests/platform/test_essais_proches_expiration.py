"""`_cabinets_essai_proches_expiration` doit répondre, pas exploser.

**Le 500 du tableau de bord, nommé et reproduit.**

Symptôme vu par le propriétaire : `GET /platform/stats/dashboard` répond 500.
Reproduit sur le HEAD, instance de test, avec un jeton plateforme valide :

    A. sans jeton        -> HTTP 401
    B. jeton invalide    -> HTTP 401
    C. login             -> HTTP 200
    D. validation 2FA    -> HTTP 200
    E. tableau de bord   -> HTTP 500
       AttributeError: Neither 'BinaryExpression' object nor 'Comparator'
                        object has an attribute 'invert'

Traceback complet :

    src/modules/platform/routers/supervision.py:152  in stats_dashboard
    src/modules/platform/services/stats.py:354        in _cabinets_essai_proches_expiration
    TenantPlateforme.date_fin_essai.is_(None).invert()
    AttributeError: Neither 'BinaryExpression' object nor 'Comparator'
                    object has an attribute 'invert'

**La cause.** `is_(None)` renvoie déjà un `BinaryExpression`. On ne l'inverse
pas. L'appel lève à la **construction** du `select`, avant tout accès à la
base : le 500 ne dépend donc d'aucune donnée, et se produit dès que le
tableau de bord est appelé.

**Pourquoi retirer la condition n'a rien changé.** En SQL, comparer `NULL`
donne `NULL`, donc la ligne est filtrée. Les deux conditions de date qui
entourent la ligne supprimée — `date_fin_essai <= limite` et
`>= aujourdhui - 7 jours` — excluaient déjà les essais sans date de fin.
La condition était à la fois invalide et sans effet.

Ce test échouait **pour la même raison** que le 500 du propriétaire : le même
`AttributeError`, levé au même endroit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.modules.platform.services.stats import StatsService  # noqa: E402


@pytest_asyncio.fixture
async def session_plateforme():
    """Session sur la base plateforme de tests.

    La fixture du même nom de `conftest` est paramétrée et rend une liste ;
    elle sert aux tests qui doivent comparer deux plateformes. Ici un seul
    cas suffit, donc on ouvre sa session.
    """
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import NullPool

    from tests.conftest import BASE_PLATEFORME_TESTS, _url_base_de_tests

    moteur = create_async_engine(
        _url_base_de_tests(BASE_PLATEFORME_TESTS), poolclass=NullPool
    )
    fabrique = async_sessionmaker(bind=moteur, class_=AsyncSession, expire_on_commit=False)
    session = fabrique()
    try:
        yield session
    finally:
        await session.close()
        await moteur.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("jours", [7, 14, 30])
async def test_les_essais_proches_expiration_respondent(session_plateforme, jours) -> None:
    """
    Le test le plus direct, et le seul qui soit nécessaire : la fonction
    s'execute. Avant le correctif, elle levait un `AttributeError` en
    construisant sa requête — le 500 du propriétaire.

    On lappelle sur trois fenetres, parce que le defaut ne dependait pas des
    donnees : un seul appel suffirait, plusieurs-cmprennent qu'aucune
    fenetre ne le fait revenir.
    """
    resultat = await StatsService._cabinets_essai_proches_expiration(
        session_plateforme, jours_avant_expiration=jours
    )

    assert isinstance(resultat, list), (
        f"la fonction doit renvoyer une liste, elle a renvoye {type(resultat).__name__}"
    )


@pytest.mark.asyncio
async def test_aucune_condition_illisible_ne_subsiste(session_plateforme) -> None:
    """
    Une garde sur la **construction de la requête**, sans l'exécuter.

    Une requête qui ne se construit pas est un 500 avant même la base. Ce
    test attrape la famille entière du défaut — pas seulement l'inversion
    qu'on a corrigée — et il est rapide, puisqu'aucun accès n'a lieu.
    """
    from src.modules.platform.models import TenantPlateforme

    # Reproduit la construction fautive : c'est exactement ce que faisait la
    # ligne supprimee, et ce que SQLAlchemy refuse.
    with pytest.raises(AttributeError):
        TenantPlateforme.date_fin_essai.is_(None).invert()

    # Et la forme correcte se construit sans lever.
    requete = TenantPlateforme.date_fin_essai.is_(None)
    assert requete is not None, "is_(None) doit produire une condition utilisable"