"""La garde de démarrage : où les tests ont-il le droit d'aller ?

**Pourquoi ce module existe.** Pendant des mois, les tests ont écrit dans la
vraie base master etosaicé des bases sur l'instance de développement. La garde
de purge a été renforcée, mais tant que les tests visent l'instance de
développement, un garde-fou reste un garde-fou : la purge ne s'exécute plus,
mais `CREATE DATABASE` continue de s'exécuter.

**Une session qui démarre dans le mauvais endroit doit s'arrêter tout de suite.**
Pas « avertir », pas « continuer en espérant » : s'arrêter, avant le premier
test, avec un message qui dit quoi faire.

Ces tests sont **purs** : ils n'ouvrent aucune connexion. La vérification du
marqueur, qui elle en a besoin, est vérifiée séparément.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import conftest  # noqa: E402

#: Instance de développement **telle qu'elle est configurée**, capturée par
#: `conftest` avant que la configuration applicative soit réorientée vers
#: l'instance de tests. Prendre `settings` ici donnerait le port de l'instance
#: de tests : la garde se comparerait à elle-même et refuserait tout.
HOTE_DEV, PORT_DEV = conftest.INSTANCE_DEVELOPPEMENT

#: Une URL de test acceptable, sur l'instance de tests dédiée.
URL_TESTS = "postgresql+asyncpg://utilisateur:secret@localhost:55436/postgres"


def raison(**surcharge) -> str | None:
    arguments = {"url": URL_TESTS, "hote_dev": HOTE_DEV, "port_dev": PORT_DEV}
    arguments.update(surcharge)
    return conftest.raison_de_refus_de_tests(**arguments)


# ---------------------------------------------------------------------------
# 1. Les refus
# ---------------------------------------------------------------------------


def test_une_url_absente_est_refusee() -> None:
    """Pas de valeur par défaut : sans URL, la session ne démarre pas."""
    assert raison(url=None) is not None
    assert raison(url="") is not None
    assert raison(url="   ") is not None


def test_l_url_de_developpement_est_refusee() -> None:
    """
    Le cas réel : une URL pointant sur l'instance qui porte les données.

    Le refus ne dit pas le mot de passe, et ne le demande pas : il dit quoi
    lancer pour corriger.
    """
    refus = raison(url=f"postgresql+asyncpg://u:motdepasse@{HOTE_DEV}:{PORT_DEV}/postgres")
    assert refus is not None
    assert str(PORT_DEV) in refus
    assert "55436" in refus or "docker compose" in refus


def test_le_port_de_developpement_est_refuse_meme_hote_different() -> None:
    """Le port est le discriminant le plus fiable : deux hôtes, un même port."""
    refus = raison(url="postgresql+asyncpg://u:motdepasse@autre-hote:55435/postgres")
    assert refus is not None


@pytest.mark.parametrize(
    "nom_base",
    [
        "sysdent_master",
        "sysdent_platform",
        "sysdent_tenant_clinique_cabinet_sn_5bd215",
        "sysdent_tenant_clinique_partage_b_8881de",
    ],
)
def test_une_base_reelle_est_refusee(nom_base: str) -> None:
    """
    Une base de production ne se teste pas, même depuis une instance de tests :
    le nom suffit à le dire, sans avoir à interroger le serveur.
    """
    refus = raison(url=f"postgresql+asyncpg://u:motdepasse@localhost:55436/{nom_base}")
    assert refus is not None
    assert nom_base in refus


def test_une_url_illisible_est_refusee() -> None:
    assert raison(url="pas-une-url") is not None


# ---------------------------------------------------------------------------
# 2. L'acceptation
# ---------------------------------------------------------------------------


def test_l_url_de_l_instance_de_tests_est_acceptee() -> None:
    assert raison() is None


@pytest.mark.parametrize(
    "nom_base",
    ["postgres", "sysdent_master_test", "sysdent_platform_test", "sysdent_modele_tenant_test"],
)
def test_les_bases_de_test_sont_acceptees(nom_base: str) -> None:
    assert raison(url=f"postgresql+asyncpg://u:motdepasse@localhost:55436/{nom_base}") is None


# ---------------------------------------------------------------------------
# 3. Injection de défaut : la garde doit tenir si une de ses règles disparaît
# ---------------------------------------------------------------------------
#:
#: Une garde reposant sur une seule règle est une garde à une règle de la
#: distance. Chacune est testée **seule** : retirer la liste des noms exacts ne
#: doit pas laisser passer une base de cabinet, et retirer le préfixe ne doit
#: pas laisser passer `sysdent_master`.


def test_la_garde_tient_si_la_liste_des_noms_exacts_disparait(monkeypatch) -> None:
    """Défaut injecté : plus aucun nom exact interdit.

    Le préfixe des bases de cabinet doit continuer de les refus : c'est la
    seule règle qui les couvre, la liste exacte n'en contient aucun.
    """
    monkeypatch.setattr(conftest, "NOMS_DE_BASES_REELLES", frozenset())
    refus = raison(
        url="postgresql+asyncpg://u:motdepasse@localhost:55436/sysdent_tenant_clinique_cabinet_sn_5bd215"
    )
    assert refus is not None, "une base de cabinet doit rester refusee sans la liste des noms"


def test_la_garde_tient_si_la_regle_de_prefixe_disparait(monkeypatch) -> None:
    """Défaut injecté : le préfixe des bases de cabinet n'est plus reconnu.

    `sysdent_master` n'est couvert que par la liste exacte : il doit donc rester
    refusé. Si cette liste disparaissait aussi, la base de production deviendrait
    acceptable — ce que le test suivant vérifie.
    """
    monkeypatch.setattr(conftest, "PREFIXE_BASE_CABINET", "sysdent_tenant_inexistant_")
    refus = raison(url="postgresql+asyncpg://u:motdepasse@localhost:55436/sysdent_master")
    assert refus is not None, "sysdent_master doit rester refuse sans la regle de prefixe"


def test_la_garde_refuse_une_url_de_development_meme_avec_un__prefixe_inexistant(
    monkeypatch,
) -> None:
    """Défaut injecté combiné : ni le port ni le nom ne doivent laisser passer."""
    monkeypatch.setattr(conftest, "PREFIXE_BASE_CABINET", "sysdent_tenant_inexistant_")
    monkeypatch.setattr(conftest, "NOMS_DE_BASES_REELLES", frozenset())
    refus = raison(url=f"postgresql+asyncpg://u:motdepasse@{HOTE_DEV}:{PORT_DEV}/postgres")
    assert refus is not None, "le refus de l'instance de developpement est independant"