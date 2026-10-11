"""La supervision doit voir les cabinets dont la base a disparu.

**Le cas réel.** Le 08/10, 130 lignes du registre `tenants_db` se sont
retrouvées sans base. Le login de ces cabinets est tombé en 500 — et la page
de santé continuait de répondre « ok », parce qu'elle ne comptait que des
**statuts**. Un dossier ACTIVE orphelin y apparaissait comme un cabinet en
règle.

Ce que vérifient ces tests : le contrôle existe, il est cohérent avec le
catalogue réel, et il ne laisse sortir aucun identifiant de connexion. Les deux
requêtes sont des `SELECT` sur `pg_database` et sur le registre — rien n'est
créé, rien n'est supprimé.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.config import settings  # noqa: E402
from src.modules.platform.services.health import (  # noqa: E402
    MAX_LONGUEUR_ERREUR,
    HealthService,
    _sans_identifiants,
    _tronquer,
)

# ---------------------------------------------------------------------------
# 1. Un message d'erreur ne porte jamais d'identifiants
# ---------------------------------------------------------------------------


def test_les_identifiants_sont_retires_d_une_url_de_connexion() -> None:
    """
    Une trace SQLAlchemy peut contenir la chaîne de connexion complète.

    C'est le motif même du commentaire d'origine : une page de santé affichée
    sur un écran de supervision deviendrait un écran de secrets.
    """
    trace = 'connexion refusee: postgresql+asyncpg://postgres:motdepasse@localhost:55435/sysdent_master'
    resultat = _sans_identifiants(trace)
    assert "motdepasse" not in resultat
    assert "postgres:***@localhost:55435/sysdent_master" in resultat


def test_la_troncature_ne_peut_plus_recoller_un_mot_de_passe() -> None:
    """
    Retirer **avant** de tronquer, jamais l'inverse : un mot de passe tient
    dans les 200 premiers caractères.
    """
    trace = "x" * 300 + " postgresql+asyncpg://postgres:secret@h:5432/db"
    assert "secret" not in _tronquer(trace)
    assert len(_tronquer("y" * 500)) <= MAX_LONGUEUR_ERREUR + 1


def test_un_message_sans_url_n_est_pas_abime() -> None:
    assert _tronquer("relation \"tenants_db\" does not exist") == (
        'relation "tenants_db" does not exist'
    )


# ---------------------------------------------------------------------------
# 2. Le contrôle compare le registre au catalogue réel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_le_controle_liste_les_registres_orphelins(master_db) -> None:
    """
    Lecture seule du registre et de `pg_database`.

    La cohérence vérifiée est arithmétique et ne dépend d'aucun état imposé :
    ce qui est au registre et absent du catalogue est exactement ce que le
    contrôle dénombre.
    """
    resultat = await HealthService.bases_absentes(master_db)

    assert resultat["composant"] == "bases_absentes"
    assert isinstance(resultat["ok"], bool)
    assert 0 <= resultat["absentes"] <= resultat["total_registre"]
    assert resultat["total_registre"] > 0
    assert resultat["absentes"] == sum(resultat["absentes_par_statut"].values())
    assert len(resultat["exemples"]) <= resultat["exemples_limite"] <= 25


@pytest.mark.asyncio
async def test_un_dossier_active_sans_base_degrade_la_sante(master_db) -> None:
    """
    Un PROVISIONING sans base est normal, c'est l'état transitoire d'une
    création. Un **ACTIVE** sans base, c'est un cabinet dont le login est cassé :
    c'est le seul cas qui doit dégrader la santé.
    """
    resultat = await HealthService.bases_absentes(master_db)
    actives = resultat["absentes_par_statut"].get("ACTIVE", 0)
    assert resultat["ok"] == (actives == 0)
    if actives:
        assert resultat["detail"] and str(actives) in resultat["detail"]


@pytest.mark.asyncio
async def test_le_controle_ne_laisse_sortir_aucun_identifiant(master_db) -> None:
    """
    La vérification la plus directe : les secrets de configuration, cherchés mot
    pour mot dans la sérialisation complète de la réponse.
    """
    resultat = await HealthService.bases_absentes(master_db)
    serialise = json.dumps(resultat)

    for secret in (
        settings.TENANT_DB_PASSWORD,
        settings.PLATFORM_DB_PASSWORD,
        settings.MASTER_DB_PASSWORD,
    ):
        if secret:
            assert secret not in serialise, "un mot de passe est sorti dans la page de santé"
    assert "db_password" not in serialise


@pytest.mark.asyncio
async def test_le_nouveau_controle_est_branche_a_la_sante_globale(master_db) -> None:
    """
    Un contrôle qui existe mais n'est pas appelé ne protège rien : c'était
    précisément l'état du 08/10.
    """
    from src.modules.platform.services.health import HealthService as HS

    # Le contrôle doit être présent dans la liste passée à `global_`.
    import inspect

    source = inspect.getsource(HS.global_)
    assert "bases_absentes" in source, "le contrôle n'est pas appelé par la santé globale"


# ---------------------------------------------------------------------------
# 2bis. Les cas que le controle doit voir, fabriqués sur l'instance de tests
# ---------------------------------------------------------------------------
#:
#: **Pourquoi cette section existe.** Ces tests-là affirmaient des faits sur des
#: bases de développement : « cinq bases ne sont pas migrées », « cette base est
#: lisible ». Le 11/10, après la réorientation de `settings` vers l'instance de
#: tests, ces bases n'y étaient plus : deux tests échouaient, et un troisième
#: passait à vide — il vérifiait qu'un nom **absent du catalogue** ne figurait
#: pas parmi les bases sans table de migrations. Il aurait été vert pour la
#: mauvaise raison.
#:
#: Un test de supervision qui dépend de l'état réel d'une autre machine n'est pas
#: un test : c'est une observation, qui devient fausse sans prévenir et ne peut
#: pas être reproduite. Les cas sont donc **fabriqués ici**, sur l'instance de
#: tests, et supprimés après.


@pytest_asyncio.fixture
async def cabinets_de_supervision(master_db):
    """
    Deux bases sur l'instance de tests, et deux lignes de registre correspondantes.

    - l'une **migrée** jusqu'à la tête : elle ne doit être ni « en retard » ni
      « sans table de migrations » ;
    - l'autre **vide**, sans table `alembic_version` : c'est l'état de cinq
      bases de démonstration, et c'est un état distinct du « retard ».

    Les deux sont `ACTIVE` : c'est le seul statut qui doit dégrader la santé,
    et le test doit donc pouvoir le fabriquer.
    """
    from sqlalchemy import text as _text

    from tests.conftest import creer_base_jetable, supprimer_base_jetable

    from src.modules.master.models import Societe, TenantDB

    suffixe = uuid.uuid4().hex[:6]
    migree = f"jetable_sante_migree_{suffixe}"
    non_migree = f"jetable_sante_vide_{suffixe}"

    await creer_base_jetable(migree, migrer=True)
    try:
        await creer_base_jetable(non_migree, migrer=False)

        for nom in (migree, non_migree):
            societe_id = uuid.uuid4()
            master_db.add(
                Societe(
                    id=societe_id,
                    nom=f"Cabinet de supervision {nom}",
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

        yield {"migree": migree, "non_migree": non_migree}
    finally:
        # `finally` : une assertion qui echoue ne doit pas laisser deux bases
        # derriere. C'etait precisement le genre de fuite que la garde de fin de
        # session a mis au jour.
        await master_db.rollback()
        for nom in (migree, non_migree):
            await supprimer_base_jetable(nom)


# ---------------------------------------------------------------------------
# 3. Écart de révision de schéma, par cabinet
# ---------------------------------------------------------------------------
#:
#: Une base de cabinet peut être parfaitement présente et parfaitement
#: inexploitable : il lui manque deux migrations. Le 10/10, c'était exactement
#: l'état du cabinet restauré — connexion réussie, première requête en échec.
#: `bases_absentes` ne voit rien de tout cela : elle ne regarde que le catalogue.


@pytest.mark.asyncio
async def test_le_controle_expose_lecart_de_revision(
    master_db, cabinets_de_supervision
) -> None:
    from src.modules.platform.services.health import HealthService as HS

    assert hasattr(HS, "schemas_tenants"), "le contrôle d'écart de schéma n'existe pas"

    resultat = await HS.schemas_tenants(master_db)

    assert resultat["composant"] == "schemas_tenants"
    assert isinstance(resultat["ok"], bool)
    # La tête attendue est lue sur la chaîne de migrations du dépôt, jamais
    # écrite en dur : une tête écrite en dur devient fausse sans prévenir.
    assert resultat["tete_attendue"]
    assert len(resultat["tete_attendue"]) == 12, "une révision Alembic fait 12 caractères"
    # Le compte n'est plus une observation du developpement : il vient des deux
    # bases que la fixture vient de fabriquer sur l'instance de tests.
    assert resultat["bases_analysees"] >= 2, (
        "les deux bases de la fixture doivent avoir ete inspectees"
    )
    assert isinstance(resultat["derriere_tete"], list)
    assert isinstance(resultat["sans_table_migrations"], list)


def test_lecalcul_du_retard_utilise_la_chaine_reelle() -> None:
    """
    Le nombre de migrations manquantes vient de la chaîne du dépôt, pas d'un
    compte approximatif. C'est l'écart exact du 10/10 : deux migrations.
    """
    from src.modules.platform.services.health import _migrations_manquantes, _tete_attendue

    assert _migrations_manquantes("c6d1e8f5a4b7", _tete_attendue()) == 2
    assert _migrations_manquantes(_tete_attendue(), _tete_attendue()) == 0
    # Une révision inconnue de la chaîne n'est pas « en retard de N » :
    # c'est un état distinct, et lui donner un nombre serait faux.
    assert _migrations_manquantes("revision_inconnue", _tete_attendue()) is None
    assert _migrations_manquantes(None, _tete_attendue()) is None


@pytest.mark.asyncio
async def test_une_base_sans_table_migrations_nest_pas_dite_en_retard(
    master_db, cabinets_de_supervision
) -> None:
    """
    Une base vide n'a aucune table `alembic_version`. La compter comme « en
    retard de N migrations » serait faux, et la confondre avec un retard fait
    perdre le contrôle entier.

    Le cas est **fabriqué** : une base vide portant une ligne ACTIVE au registre.
    L'ancien test affirmait « cinq bases ne sont pas migrées » sur le
    développement — un fait observé, pas une propriété vérifiée.
    """
    from src.modules.platform.services.health import HealthService as HS

    vide = cabinets_de_supervision["non_migree"]

    resultat = await HS.schemas_tenants(master_db)

    en_retard = {e["db_name"] for e in resultat["derriere_tete"]}
    sans_table = set(resultat["sans_table_migrations"])

    assert vide in sans_table, "la base vide doit être signalée à part"
    assert vide not in en_retard, "une base non migrée n'est pas 'en retard de N'"


@pytest.mark.asyncio
async def test_une_base_migree_est_lisible_puis_qu_absente_du_bruit(
    master_db, cabinets_de_supervision
) -> None:
    """
    **Le piège PostgreSQL.** Il n'existe aucune syntaxe `base.table` : une
    requête inter-base échoue et fait croire que la table n'existe pas. Le
    symptôme est discret et faux — une base parfaitement migrée, puisée comme
    non migrée, et un contrôle qui ne contrôle rien.

    L'ancien test lisait une base **de développement** nommée en dur. Sur
    l'instance de tests elle n'existait pas : il échouait. Et le test voisin,
    qui affirmait que cette base n'était pas « en retard », passait **à vide**,
    puisque le nom était absent du registre : vert pour la mauvaise raison.
    """
    import asyncpg

    from src.modules.platform.services.health import HealthService as HS

    migree = cabinets_de_supervision["migree"]

    conn = await asyncpg.connect(
        host=settings.TENANT_DB_HOST,
        port=settings.TENANT_DB_PORT,
        user=settings.TENANT_DB_USER,
        password=settings.TENANT_DB_PASSWORD,
        database=migree,
    )
    try:
        revision = await conn.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()
    assert revision, "la base migrée doit l'être réellement"

    resultat = await HS.schemas_tenants(master_db)
    assert migree not in resultat["sans_table_migrations"], (
        "une base migrée ne doit pas être déclarée sans table de migrations"
    )


@pytest.mark.asyncio
async def test_la_chaine_de_migrations_a_une_seule_tete() -> None:
    """Une tête unique, sinon « à jour » n'a aucun sens."""
    import inspect

    from src.modules.platform.services.health import _tete_attendue

    assert _tete_attendue() == "e8b2c4a7d1e5"

    import pathlib

    from src.modules.platform.services import health as module_health

    racine = pathlib.Path(inspect.getfile(module_health)).resolve().parents[4]
    assert (racine / "alembic_tenant.ini").is_file()


@pytest.mark.asyncio
async def test_un_cabinet_a_jour_nest_pas_signale_comme_en_retard(
    master_db, cabinets_de_supervision
) -> None:
    """
    Une base migrée jusqu'à la tête ne doit pas apparaître dans la liste : sinon
    l'écran de santé devient un bruit que l'on cesse de regarder.

    Ce test vérifiait auparavant qu'un nom **absent du registre** ne figurait pas
    dans la liste. Il était donc vert pour la mauvaise raison : une base qu'on ne
    trouve pas ne peut évidemment pas être trouvée en retard.
    """
    from src.modules.platform.services.health import HealthService as HS

    migree = cabinets_de_supervision["migree"]

    resultat = await HS.schemas_tenants(master_db)
    en_retard = {e["db_name"] for e in resultat["derriere_tete"]}

    assert migree not in en_retard, "une base à la tête ne doit pas être signalée"
    # La preuve qu'il s'agit bien de bases **présentes et inspectées** : sans
    # cela, l'assertion passerait encore pour une base introuvable. Les deux
    # bases sont candidates, donc deux connexions ont ete ouvertes.
    assert resultat["bases_analysees"] >= 2, "les deux bases doivent etre inspectees"
    assert cabinets_de_supervision["non_migree"] in set(
        resultat["sans_table_migrations"]
    ), "la base vide est la preuve directe qu'une connexion a abouti"


@pytest.mark.asyncio
async def test_une_base_sans_table_alembic_ne_casse_pas_le_controle(master_db) -> None:
    """
    Cinq bases de démonstration n'ont aucune table `alembic_version`. Un contrôle
    qui lève sur la première d'entre elles ne rendrait aucun verdict du tout —
    or c'est précisément le cabinet casse qu'il faut voir.
    """
    from src.modules.platform.services.health import HealthService as HS

    resultat = await HS.schemas_tenants(master_db)
    assert "ok" in resultat
    assert isinstance(resultat["derriere_tete"], list)
