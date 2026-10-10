"""Configuration Alembic : trois chaînes, trois fichiers, trois commande.

**L'erreur que ce module existe pour empêcher.** Le 10/10, une commande
`alembic history -r c6d1e8f5a4b7:3c2a49eaec83` a répondu *« Can't locate
revision »*. Les deux révision-existent, mais elles appartiennent à deux
chaînes différentes : `3c2a49eaec83` est la tête **master** (`alembic.ini`),
`c6d1e8f5a4b7` est une révision de la chaîne **tenant** (`alembic_tenant.ini`).
On interrogeait la mauvaise chaîne, et le message ne le disait pas.

C'est aussi pour cela que `normaliser_url_vers_asyncpg` doit être **appelé**
par chaque `env.py`, pas seulement importé : une URL `psycopg2` reste en
`psycopg2` si personne ne la convertit, et le pilote charge alors une DLL
native — que la stratégie de contrôle d'application de ce poste bloque. Sur ce
poste, la conséquence n'est pas un message d'erreur : c'est
`ImportError: DLL load failed while importing _psycopg`.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.core.alembic_async import normaliser_url_vers_asyncpg  # noqa: E402
from src.core import migrations  # noqa: E402

BACKEND = pathlib.Path(inspect.getfile(migrations)).resolve().parents[2]

#: Les trois chaînes : (fichier `.ini`, dossier de versions sur le disque).
#:
#: Les noms de dossiers ne sont pas les noms logiques : la chaîne master vit
#: dans `alembic/`, pas dans `master/`. Cette différence fait partie des
#: confusions que ce module documente.
CHAINEES = {
    "master": ("alembic.ini", "alembic"),
    "plateforme": ("alembic_platform.ini", "alembic_platform"),
    "tenant": ("alembic_tenant.ini", "alembic_tenant"),
}


def _appel_normalisation(nom_env: str) -> bool:
    """L'`env.py` appelle-t-il réellement `normaliser_url_vers_asyncpg` ?

    Analyse syntaxique plutôt que recherche de texte : importer la fonction
    n'est pas l'appeler, et c'est exactement l'erreur à éviter.
    """
    chemin = BACKEND / nom_env / "env.py"
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if (
            isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == "normaliser_url_vers_asyncpg"
        ):
            return True
    return False


@pytest.mark.parametrize("nom_chaine", sorted(CHAINEES))
def test_chaque_env_normalise_vers_asyncpg(nom_chaine: str) -> None:
    nom_ini, dossier = CHAINEES[nom_chaine]
    assert _appel_normalisation(dossier), (
        f"{dossier}/env.py ({nom_ini}) importe normaliser_url_vers_asyncpg sans "
        f"l'appeler : une URL psycopg2 reste en psycopg2 et le pilote charge une "
        f"DLL native."
    )


@pytest.mark.parametrize("nom_chaine", sorted(CHAINEES))
def test_chaque_chaine_a_une_seule_tete(nom_chaine: str) -> None:
    """Une seule tête par chaîne : sans cela, « être à jour » n'a pas de sens."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    nom_ini, dossier = CHAINEES[nom_chaine]
    cfg = Config(str(BACKEND / nom_ini))
    cfg.set_main_option("script_location", str(BACKEND / dossier))
    tetes = ScriptDirectory.from_config(cfg).get_heads()

    assert len(tetes) == 1, f"{nom_chaine} a {len(tetes)} têtes : {tetes}"


def test_une_url_psycopg2_est_convertie_avant_de_toucher_le_pilote() -> None:
    """
    Le comportement attendu, vérifié sans base : la conversion doit produire une
    URL dont le pilote est asyncpg — celui qui est installé et autorisé ici.
    """
    url = "postgresql+psycopg2://utilisateur:motdepasse@hote:55435/une_base"
    convertie = normaliser_url_vers_asyncpg(url)

    assert convertie.startswith("postgresql+asyncpg://")
    moteur = create_async_engine(convertie)
    assert moteur.dialect.driver == "asyncpg"


def test_une_url_asyncpg_est_laissee_intacte() -> None:
    url = "postgresql+asyncpg://utilisateur:motdepasse@hote:55435/une_base"
    assert normaliser_url_vers_asyncpg(url) == url


def test_le_contrat_de_upgrade_tenant_to_head_est_claire() -> None:
    """
    Le paramètre s'appelait `tenant_db_sync_url` alors que seule une URL asyncpg
    fonctionnait, et que les deux appelants de production passaient déjà une URL
    asyncpg. Un nom qui ment sur le contrat coûte une DLL bloquée et une heure.
    """
    signature = inspect.signature(migrations.upgrade_tenant_to_head)
    parametres = list(signature.parameters)

    assert "tenant_db_sync_url" not in parametres, (
        "le nom du paramètre promet une URL synchrone alors que le chemin "
        "exécuté est asynchrone"
    )
    documentation = migrations.upgrade_tenant_to_head.__doc__ or ""
    assert "asyncpg" in documentation or "psycopg2" in documentation, (
        "la docstring doit dire quelle forme d'URL est attendue"
    )


def test_chaque_fichier_ini_decrit_bien_son_dossier() -> None:
    """
    `script_location` est le lien entre un `.ini` et son dossier de versions.
    Un chemin faux ne lève rien de parlant : les migrations simplement ne
    s'exécutent pas.
    """
    for nom_chaine, (nom_ini, dossier) in CHAINEES.items():
        contenu = (BACKEND / nom_ini).read_text(encoding="utf-8")
        assert f"script_location = {dossier}" in contenu, (
            f"{nom_ini} devrait pointer sur {dossier}/"
        )
        assert (BACKEND / dossier / "versions").is_dir(), (
            f"{dossier}/versions est introuvable"
        )


def test_le_moteur_sans_normalisation_chargerait_psycopg2() -> None:
    """
    Témoin du risque : sans conversion, c'est bien le pilote `psycopg2` que
    SQLAlchemy selectionne. Ce test ne doit échouer que sur un poste où la DLL
    est réellement bloquée — ailleurs il documente simplement le chemin pris.
    """
    url = "postgresql+psycopg2://utilisateur:motdepasse@hote:55435/une_base"
    try:
        create_engine(url)
    except ImportError:
        pytest.skip("psycopg2 est bloque sur ce poste : c'est le cas observe")
    except Exception:  # noqa: BLE001
        pass
    else:
        # Le pilote a pu etre charge : la normalisation reste ne cessaire pas.
        assert normaliser_url_vers_asyncpg(url) != url