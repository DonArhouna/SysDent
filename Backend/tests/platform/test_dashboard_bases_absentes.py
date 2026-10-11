"""Le tableau de bord ne doit pas annoncer « tout va bien » quand il n'y va pas.

**Le mensonge qu'on veut interdire.** Un écran qui affiche « 42 cabinets
ACTIVE » sans dire combien ont une base laisse croire que 42 cabinets
fonctionnent. Aujourd'hui, un dossier ACTIVE sans base a un login cassé : le
chiffre seul est faux.

**La contrainte de conception qui compte.** Le registre compte plus de 130
lignes. Construire ce decompte en ouvrant une connexion par cabinet ouvrirait
autant de connexions vers l'instance qui porte les donnees, la rendrait
indisponible, et rendrait le temps de reponse imprévisible. Le decompte doit
venir du registre et du catalogue `pg_database`, jamais d'une base de cabinet.

Ce test verifie les deux choses : le chiffre, et l'absence de connexion.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.config import settings  # noqa: E402
from src.modules.platform.services.health import HealthService  # noqa: E402


@pytest_asyncio.fixture
async def registre_de_surveillance(master_db):
    """Deux lignes ACTIVE : l'une avec base, l'autre sans.

    Sans base est plus interessant qu'une base vide : il faut que le controle
    distingue « la base n'existe pas » de « la base existe mais n'a pas de
    table de migrations ».
    """
    from sqlalchemy import text as _text

    from tests.conftest import creer_base_jetable, supprimer_base_jetable

    from src.modules.master.models import Societe, TenantDB

    suffixe = uuid.uuid4().hex[:6]
    avec_base = f"jetable_dash_avec_{suffixe}"
    sans_base = f"jetable_dash_sans_{suffixe}"

    await creer_base_jetable(avec_base, migrer=True)
    noms = [avec_base, sans_base]
    try:
        for nom in noms:
            societe_id = uuid.uuid4()
            master_db.add(
                Societe(
                    id=societe_id,
                    nom=f"Dashboard {nom}",
                    pays="SN",
                    actif=True,
                    date_creation=datetime.now(timezone.utc),
                )
            )
            master_db.add(
                TenantDB(
                    id=uuid.uuid4(),
                    societe_id=societe_id,
                    db_name=nom,
                    db_host=settings.TENANT_DB_HOST,
                    db_port=settings.TENANT_DB_PORT,
                    db_user=settings.TENANT_DB_USER,
                    db_password="chiffre-de-test",
                    statut="ACTIVE",
                    schema_version="tete",
                )
            )
        await master_db.commit()
        yield {"avec_base": avec_base, "sans_base": sans_base}
    finally:
        await master_db.rollback()
        await supprimer_base_jetable(avec_base)


@pytest.mark.asyncio
async def test_le_controle_expose_le_total_par_statut(master_db) -> None:
    """
    `total_par_statut` doit venir de la **meme** lecture que les absences.

    Sans lui, l'ecran ne peut comparer que le total du registre a l'absence
    d'une autre source : le ratio serait faux des que les deux tables ne
    contiendraient pas exactement les memes lignes.
    """
    resultat = await HealthService.bases_absentes(master_db)

    assert "total_par_statut" in resultat, (
        "le total par statut est indispensable pour comparer avec les absences"
    )
    assert sum(resultat["total_par_statut"].values()) == resultat["total_registre"], (
        "chaque ligne du registre doit compter dans exactement un statut"
    )
    for statut, compte in resultat["absentes_par_statut"].items():
        assert compte <= resultat["total_par_statut"].get(statut, 0), (
            f"on ne peut pas avoir plus d'absences que de lignes pour {statut}"
        )


@pytest.mark.asyncio
async def test_une_base_absente_est_comptee_sans_se_connecter(
    master_db, registre_de_surveillance, monkeypatch
) -> None:
    """
    **Le controle ne doit ouvrir aucune connexion vers une base de cabinet.**

    On le prouve par la negation : on rend la creation de moteur vers une base
    de cabinet impossible, et le controle doit produire le meme resultat. Si
    quelqu'un ajoute un jour une connexion par cabinet pour completer le
    decompte, ce test echoue au lieu de le faire decouvrir en production, le
    jour ou l'instance de donnees est a genoux.
    """
    from sqlalchemy.ext.asyncio import create_async_engine as _create

    nom_avec_base = registre_de_surveillance["avec_base"]
    nom_sans_base = registre_de_surveillance["sans_base"]

    reel = _create

    def _interdit(*args, **kwargs):
        cible = str(args[0]) if args else str(kwargs.get("url", ""))
        if f"/{nom_avec_base}" in cible or f"/{nom_sans_base}" in cible:
            raise AssertionError(
                "le controle a tente de se connecter a une base de cabinet : "
                "le decompte doit venir du registre et du catalogue"
            )
        return reel(*args, **kwargs)

    monkeypatch.setattr(
        "src.modules.platform.services.health.create_async_engine", _interdit
    )

    resultat = await HealthService.bases_absentes(master_db)

    # `exemples` porte des objets, pas des noms : on en extrait le nom de base.
    absentes = {
        e["db_name"] if isinstance(e, dict) else e for e in resultat["exemples"]
    }
    assert resultat["absentes"] >= 1, "la ligne sans base doit etre comptee"
    assert nom_avec_base not in absentes, "une base presente n'est pas absente"
    # Les deux lignes sont ACTIVE : le total ACTIVE doit donc au moins couvrir
    # le nombre d'absentes ACTIVE. C'est la coherence que l'ecran va afficher.
    assert (
        resultat["absentes_par_statut"].get("ACTIVE", 0)
        <= resultat["total_par_statut"].get("ACTIVE", 0)
    ), "une absence ne peut pas depasser le total de son statut"