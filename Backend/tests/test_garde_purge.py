"""La garde de purge : ce qu'elle supprime, et surtout ce qu'elle refuse.

**Pourquoi ces tests.** Une garde destructive n'a pas de test « elle marche » :
elle n'a que des tests « elle n'a pas fait ce qu'on ne voulait pas ». Une base
de démonstration, un tenant réel, la plateforme elle-même : ce sont des choses
qu'une erreur de motif supprime sans laisser de trace, parce que la suite passe
toujours au vert.

Le critère de sélection est donc exposé tel quel et vérifié cas par cas.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import conftest  # noqa: E402

#: Bases présentes avant la session de tests.
AVANT = frozenset(
    {
        "sysdent_test_aaaaaabbbbbb",
        "sysdent_demo_cafe",
        "sysdent_cabinet_2",
    }
)

#: Tenants réels, référencés par le registre `tenants_db`.
TENANTS_REELS = frozenset(
    {
        "sysdent_tenant_clinique_demo_dakar_050843",
        "sysdent_tenant_clinique_demo_2_70631b",
        "sysdent_tenant_clinique_diagnostic_dakar_d22db3",
        "sysdent_tenant_clinique_essai_3cae37",
    }
)


def classer(nom: str) -> str:
    return conftest.classer_base(nom, AVANT, TENANTS_REELS)


# ---------------------------------------------------------------------------
# 1. La liste de protection, jamais contournable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nom",
    [
        "postgres",
        "template0",
        "template1",
        "sysdent_master",
        "sysdent_modele_tenant",
        "sysdent_platform",
        "sysdent_tenant_ref",
    ],
)
def test_les_bases_de_travail_sont_protegees(nom: str) -> None:
    """La plateforme, son registre, son modèle et son tenant de référence."""
    assert classer(nom) == "protege", f"{nom} n'est plus protegee"


def test_un_tenant_du_registre_est_protege_meme_avec_un_nom_de_test() -> None:
    """
    Une base de tenant référencée par `tenants_db` est protégée, même si son nom
    ressemble à un résidu.

    C'est le cas qui a manqué à la purge du 08/10 : des bases de test
    registered ont été supprimées, laissant plus de 100 lignes orphelines dans le
    registre. Le registre est la seule source qui dise si une base est un tenant
    réel ou un résidu.
    """
    nom = "sysdent_tenant_clinique_essai_3cae37"
    assert conftest._motif_jetable(nom), "le motif doit reconnaître ce nom"
    assert classer(nom) == "protege", "le registre doit primer sur le motif"


def test_le_registre_prime_meme_sur_le_prefixe_le_plus_evident() -> None:
    """Le registre prime sur le motif, et le motif prime sur le prefixe plausible."""
    # Nom de base de test, donc motif positif...
    nom = "sysdent_test_51581be343f2"
    assert conftest._motif_jetable(nom)
    # ...mais porte au registre : protege.
    assert conftest.classer_base(nom, frozenset(), TENANTS_REELS | {nom}) == "protege"
    # Et une base de test presente avant la session, inconnue du registre, est
    # conservee : la garde ne devine pas l'origine d'une base qu'elle n'a pas vue
    # naitre.
    assert conftest.classer_base("sysdent_test_aaaaaabbbbbb", AVANT, TENANTS_REELS) == "conserve"


# ---------------------------------------------------------------------------
# 2. Ce qui ne doit surtout PAS être supprimé
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nom",
    ["sysdent_demo_cafe", "sysdent_cabinet_2", "sysdent_demo_dead"],
)
def test_une_base_nommee_a_la_main_est_conservee(nom: str) -> None:
    """
    Un nom lisible, sans fragment hexadécimal, n'est jamais un résidu.

    Le critère « se terminait par de l'hexa » rendait la règle instable : le même
    nom pouvait être supprimé un jour et conservé le lendemain selon sa longueur.
    """
    assert classer(nom) == "conserve"


def test_une_base_mal_connue_est_conservee_par_defaut() -> None:
    """
    **Une base qu'on ne reconnaît pas est une base qu'on garde.**

    Une garde destructive doit établir par l'absence de doute, jamais par
    l'absence de preuve. Le cas par défaut est donc `conserve`, jamais `indice`.
    """
    assert classer("sysdent_quelque_chose_de_neuf") == "conserve"
    assert classer("production_like") == "conserve"


# ---------------------------------------------------------------------------
# 3. Ce qui doit être supprimé, et pourquoi c'est sûr
# ---------------------------------------------------------------------------


def test_une_base_creee_par_la_session_est_supprimee_sans_doute() -> None:
    """
    **Certitude, pas indice.** Une base que la session vient de créer ne peut pas
    être un tenant réel : elle n'existait pas au départ.
    """
    nom = "sysdent_tenant_clinique_partage_c_deadbe"
    conftest.BASES_CREEES_PAR_LA_SESSION.add(nom)
    try:
        assert classer(nom) == "session"
    finally:
        conftest.BASES_CREEES_PAR_LA_SESSION.discard(nom)


@pytest.mark.parametrize(
    "nom",
    [
        # Formes relevees sur les 53 noms reellement purges le 08/10.
        "sysdent_test_51581be343f2",
        "sysdent_iso_a_1b523d0b",
        "sysdent_iso_b_f0a113b8",
        "sysdent_tenant_cabinet_recette_6b6298",
        "sysdent_tenant_cabinet_verif_b_18be1a24_2e1316",
        "sysdent_tenant_cabinet_onboarding_45bd3409_e06428",
        "sysdent_tenant_clinique_cabinet_sn_2f36e8",
        "sysdent_tenant_clinique_partage_b_0865ff",
        "sysdent_tenant_clinique_essai_3cae37",
        "sysdent_platform_enrolement_abcdef123456",
    ],
)
def test_le_motif_reconnait_les_residus_reels(nom: str) -> None:
    """Les bases réellement purgées restent reconnues comme résidus."""
    assert conftest._motif_jetable(nom), f"{nom} n'est plus reconnu comme residu"


def test_un_residu_dune_session_precedente_est_supprime() -> None:
    """
    Absent au départ, absent du registre, nom de test : c'est un résidu.

    Les longueurs sont celles **reelles** de chaque préfixe : `nom_jetable` fait 12
    caractères, l'isolation 8, le partage 6. Un résidu au mauvais nombre de
    caractères n'est pas reconnu - et c'est voulu : mieux vaut laisser une base
    que supprimer une base dont on n'est pas sûr du nom.
    """
    assert classer("sysdent_test_abcdef123456") == "indice"
    assert classer("sysdent_iso_b_12345678") == "indice"
    assert classer("sysdent_tenant_clinique_partage_b_0865ff") == "indice"


@pytest.mark.parametrize(
    "nom",
    [
        # Longueurs de suffixe non conformes.
        "sysdent_test_zzz",
        "sysdent_test_abc",
        "sysdent_test_abcdefa",
        "sysdent_test_abcdefabcdefa",
        "sysdent_iso_a_1234567",
        # Préfixe inconnu.
        "sysdent_demo_abcdef",
        "sysdent_cabinet_abcdef",
        # Caractères hors hexadécimal.
        "sysdent_test_abcdeg",
        "sysdent_test_ABCDEF",
        # Pas de suffixe.
        "sysdent_test_",
        # Formes voisines mais fausses.
        "sysdent_tenant_cabinet_verif_b_18be1a24_2e1316a",
        "sysdent_tenant_clinique_partage_c_deadbe",
        "sysdent_tenant_clinique_essai_3cae3",
    ],
)
def test_le_motif_refuse_les_noms_trop_proches(nom: str) -> None:
    """
    Une forme **fixe** par préfixe. Un suffixe de 3 ou de 13 caractères n'est pas
    un fragment produit par les tests ; l'accepter, c'est accepter n'importe quoi.
    """
    assert not conftest._motif_jetable(nom), f"{nom} passe le motif a tort"


@pytest.mark.parametrize(
    "nom",
    [
        "sysdent_tenant_clinique_demo_dakar_050843",
        "sysdent_tenant_clinique_demo_2_70631b",
        "sysdent_tenant_clinique_d_mo_dakar_69a2de",
        "sysdent_tenant_clinique_trace_3_e3db15",
        "sysdent_tenant_clinique_diagnostic_dakar_d22db3",
        "sysdent_tenant_cabinet_rollback_825c06d3_d48d93",
    ],
)
def test_une_base_de_demonstration_nest_pas_un_residu(nom: str) -> None:
    """
    Les bases de démonstration du propriétaire ne doivent **jamais** ressembler à
    un résidu.

    `d_mo_dakar_69a2de` a d'abord été attrapé par le motif : sa forme de nom est
    indiscernable de celle d'un résidu. Elle est donc sortie du motif, et ne
    repose plus que sur le registre — plus prudent que l'inverse.
    """
    assert not conftest._motif_jetable(nom), f"{nom} ressemble a un residu"


# ---------------------------------------------------------------------------
# 4. La purge ne s'exécute que sur autorisation explicite
# ---------------------------------------------------------------------------


def test_la_purge_exige_une_variable_d_explicit_environment(monkeypatch) -> None:
    """
    Sans `SYSDENT_TESTS_PURGE=1`, la garde ne supprime rien.

    Une purge qui s'exécute sur le mauvais serveur est irrattrapable ; une purge
    qui ne s'exécute pas se relance. Le défaut est donc l'inaction.
    """
    assert conftest.VARS_PURGE == "SYSDENT_TESTS_PURGE"
    monkeypatch.delenv(conftest.VARS_PURGE, raising=False)
    assert os.environ.get(conftest.VARS_PURGE) != "1"
    monkeypatch.setenv(conftest.VARS_PURGE, "1")
    assert os.environ.get(conftest.VARS_PURGE) == "1"


def test_une_base_de_registre_reste_protegee_meme_armee(monkeypatch) -> None:
    """
    **Armer la purge ne doit pas élargir son pouvoir.**

    Le cas réel du 08/10 : la purge était armée, et des bases portées au registre
    `tenants_db` ont disparu malgré tout. La liste de protection doit primer sur
    l'autorisation, pas l'inverse.
    """
    monkeypatch.setenv(conftest.VARS_PURGE, "1")
    nom = "sysdent_tenant_clinique_demo_2_70631b"
    assert conftest.classer_base(nom, frozenset(), TENANTS_REELS) == "protege"
    assert conftest.classer_base("sysdent_platform", frozenset(), TENANTS_REELS) == "protege"


# ---------------------------------------------------------------------------
# 5. La garde reste inerte tant que l'instance ne lui est pas designee
# ---------------------------------------------------------------------------
#:
#: Aucun de ces tests ne touche une base : la decision de supprimer est une
#: fonction pure, et c'est elle qui est verifiee. C'est aussi le seul endroit ou
#: on peut encore supprimer la base du proprietaire - donc le seul endroit ou
#: il faut un test.

#: URL d'une instance **autre** que celle des tenants. Le mot de passe est
#: fictif : il sert precisement a verifier qu'il n'en sort jamais.
URL_TESTS = "postgresql+asyncpg://postgres:motdepasse@127.0.0.1:55436/postgres"

#: L'instance reelle des tenants, telle que configuree.
HOTE_REEL = conftest.settings.TENANT_DB_HOST
PORT_REEL = conftest.settings.TENANT_DB_PORT


def supprimer(
    noms: list[str],
    *,
    tenants: frozenset[str] = TENANTS_REELS,
    session: set[str] | None = None,
    url: str | None = URL_TESTS,
) -> list[str]:
    return conftest.bases_a_supprimer(
        noms,
        tenants_reels=tenants,
        session=session or set(),
        url_tests=url,
        hote_ref=HOTE_REEL,
        port_ref=PORT_REEL,
    )


def test_sans_url_de_tests_la_garde_ne_supprime_rien(monkeypatch) -> None:
    """
    **Le défaut est l'inaction.** `TEST_DATABASE_URL` absente : la garde ne
    supprime rien, même une base dont le nom est sans équivoque.
    """
    monkeypatch.delenv(conftest.VARS_URL_TESTS, raising=False)
    assert conftest.url_de_tests() is None
    assert supprimer(["sysdent_test_abcdef123456"], url=conftest.url_de_tests()) == []


def test_un_url_vers_l_instance_des_tenants_est_refuse() -> None:
    """
    Le cas réel : `TEST_DATABASE_URL` posée par erreur sur l'instance qui
    héberge les cabinets. Hôte et port identiques à la référence : refusé, même
    si la base-temoin y figure.
    """
    url = f"postgresql+asyncpg://postgres:x@{HOTE_REEL}:{PORT_REEL}/postgres"
    noms = [conftest.MARQUEUR_INSTANCE_DE_TESTS, "sysdent_test_abcdef123456"]
    assert supprimer(noms, url=url) == []


def test_un_autre_port_suffit_a_designer_une_autre_instance() -> None:
    """C'est le port qui distingue les instances ici : 55435 contre 5432."""
    assert conftest.cible_distincte(URL_TESTS, HOTE_REEL, PORT_REEL)
    assert not conftest.cible_distincte(
        f"postgresql+asyncpg://postgres:x@{HOTE_REEL}:{PORT_REEL}/postgres",
        HOTE_REEL,
        PORT_REEL,
    )


def test_un_url_sans_base_temoin_ne_suffit_pas() -> None:
    """Une instance de test qui n'a jamais été marquée n'est pas une instance de test."""
    noms = ["postgres", "sysdent_master", "sysdent_test_abcdef123456"]
    assert conftest.instance_explicitement_marquee(noms) is False
    assert supprimer(noms) == []


def test_la_base_temoin_ne_supprime_que_lexception() -> None:
    """La base-temoin autorise la purge des autres bases - pas la sienne."""
    marqueur = conftest.MARQUEUR_INSTANCE_DE_TESTS
    assert conftest.instance_explicitement_marquee([marqueur]) is True
    assert supprimer([marqueur]) == []


def test_la_base_du_proprietaire_n_est_jamais_supprimee() -> None:
    """
    **Le 08/10, rejoué.** `sysdent_tenant_clinique_cabinet_sn_5bd215` : nom de
    cabinet réel, forme exacte d'un résidu de test, absente de la session. La
    garde doit la refuser même si le registre est vide - c'est-à-dire même si
    personne ne peut plus dire qu'elle est réelle.

    C'est cette base qui a fait tomber le login du client en 500.
    """
    nom = "sysdent_tenant_clinique_cabinet_sn_5bd215"
    assert conftest._motif_jetable(nom), "le motif reconnaît ce nom : c'est le danger"
    noms = [conftest.MARQUEUR_INSTANCE_DE_TESTS, nom]
    assert supprimer(noms, tenants=frozenset()) == []


def test_une_base_de_cabinet_non_creee_par_la_session_ne_sort_jamais() -> None:
    for nom in (
        "sysdent_tenant_clinique_cabinet_sn_2f36e8",
        "sysdent_tenant_cabinet_verif_b_18be1a24_2e1316",
        "sysdent_tenant_clinique_partage_b_0865ff",
        "sysdent_tenant_clinique_essai_3cae37",
    ):
        reste = supprimer([conftest.MARQUEUR_INSTANCE_DE_TESTS, nom], tenants=frozenset())
        assert nom not in reste, f"{nom} ne doit jamais sortir du registre de session"


def test_le_registre_empeche_la_suppression_meme_dun_nom_de_test() -> None:
    """Le registre prime sur le motif, et le motif sur rien du tout."""
    nom = "sysdent_test_51581be343f2"
    assert nom in supprimer([conftest.MARQUEUR_INSTANCE_DE_TESTS, nom], tenants=frozenset())
    assert nom not in supprimer(
        [conftest.MARQUEUR_INSTANCE_DE_TESTS, nom], tenants=frozenset({nom})
    )


def test_une_base_creee_par_la_session_est_supprimee() -> None:
    """Le seul cas où la certitude existe : nous l'avons créée, nous la retirons."""
    nom = "sysdent_tenant_clinique_partage_b_0865ff"
    assert supprimer([conftest.MARQUEUR_INSTANCE_DE_TESTS, nom], session={nom}) == [nom]


def test_resume_url_ne_fuit_jamais_d_identifiants() -> None:
    """Un journal, ça s'imprime : l'URL de connexion, elle, ne s'y trouve pas."""
    url = "postgresql+asyncpg://postgres:motdepasse@127.0.0.1:55436/sysdent_test"
    resume = conftest.resume_url(url)
    assert "motdepasse" not in resume
    assert "postgres:" not in resume
    assert resume == "127.0.0.1:55436/sysdent_test"