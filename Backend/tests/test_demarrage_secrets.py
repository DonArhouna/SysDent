"""Le demarrage doit refuser un mot de passe de developpement, ou son absence.

**Pourquoi.** Une variable de connexion avec une valeur de repli est un
silence : le poste demarre, l'application se connecte, et rien ne dit a
l'ecran que le secret employe est celui du depot. Le defaut a deja ete
commite et pousse sur un depot public. Retirer la valeur ne suffit pas si
l'application peut encore demarrer sans elle : il faut que le demarrage
echoue, et qu'il dise laquelle.

**Ce que le message ne doit pas contenir.** Aucune valeur, meme pas
partiellement. Le message nomme la variable et ce qu il faut faire ; il ne
reprend jamais ce que la variable vaut. Un message de configuration recopiant
la valeur l insererait dans un journal, une capture d ecran ou une
conversation.

**Pourquoi la valeur de reserve est refusee aussi bien que l absence.** Une
variable presente mais egale au gabarit est le cas le plus trompeur : tout
semble configure. Elle est donc refusee au meme titre que l absence.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

RACINE = Path(r"C:\Users\RHONE\OneDrive\Desktop\SysDent\Backend")

#: Les trois variables de mot de passe de connexion.
OBLIGATOIRES = ("PLATFORM_DB_PASSWORD", "MASTER_DB_PASSWORD", "TENANT_DB_PASSWORD")

#: Valeur de reserve, jamais acceptee. Le nom de la constante est ce qu on peut
#: ecrire dans un test ; sa valeur, non.
REFUS = "changer-moi"
VALEUR_REFUS = REFUS


def _config_sans(modifier: dict[str, str]):
    """Recharge la configuration en ne laissant que les variables demandees.

    Les autres variables de l'environnement sont retirees pour que le test ne
    depende pas de la machine sur laquelle il tourne. `settings` etant cree a
    l'import du module, il faut le recharger entierement.
    """
    for nom in OBLIGATOIRES:
        os.environ.pop(nom, None)
    os.environ.update(modifier)
    for nom in list(sys.modules):
        if nom.startswith("src.core.config"):
            del sys.modules[nom]
    module = importlib.import_module("src.core.config")
    # `_env_file=None` neutralise la lecture du `.env` du poste. Sans cela, le
    # fichier reel fournirait les variables et le test de l'absence ne
    # declencherait jamais : il passerait vert sans rien prouver.
    return module, module.Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _restaurer():
    sauvegarde = {n: os.environ.get(n) for n in OBLIGATOIRES}
    yield
    for nom, valeur in sauvegarde.items():
        if valeur is None:
            os.environ.pop(nom, None)
        else:
            os.environ[nom] = valeur
    for nom in list(sys.modules):
        if nom.startswith("src.core.config"):
            del sys.modules[nom]


@pytest.mark.parametrize("manquante", OBLIGATOIRES)
def test_le_demarrage_echoue_si_une_variable_est_absente(manquante: str) -> None:
    presentes = {n: "valeur-suffisamment-longue" for n in OBLIGATOIRES if n != manquante}
    with pytest.raises(Exception) as info:
        _config_sans(presentes)[1]
    message = str(info.value)
    assert manquante in message, f"le message ne nomme pas {manquante} : {message[:200]}"


@pytest.mark.parametrize("variable", OBLIGATOIRES)
def test_le_demarrage_echoue_si_la_valeur_est_le_gabarit(variable: str) -> None:
    presentes = {n: "valeur-suffisamment-longue" for n in OBLIGATOIRES}
    presentes[variable] = REFUS
    with pytest.raises(Exception) as info:
        _config_sans(presentes)[1]
    message = str(info.value)
    assert variable in message, f"le message ne nomme pas {variable} : {message[:200]}"


@pytest.mark.parametrize("variable", OBLIGATOIRES)
def test_le_message_n_affiche_jamais_la_valeur(variable: str) -> None:
    """Un message qui recopie la valeur la fait finir dans un journal."""
    presente = "valeur-suffisamment-longue"
    autres = {n: presente for n in OBLIGATOIRES if n != variable}
    with pytest.raises(Exception) as info:
        _config_sans(autres)[1]
    message = str(info.value)
    assert presente not in message, f"le message divulgue une valeur : {message[:200]}"
    assert VALEUR_REFUS not in message, f"le message divulgue le gabarit : {message[:200]}"


def test_le_demarrage_reussit_avec_les_trois_variables() -> None:
    module, _ = _config_sans({n: "valeur-suffisamment-longue" for n in OBLIGATOIRES})
    assert module.Settings(_env_file=None).MASTER_DB_PASSWORD