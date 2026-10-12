"""Un ecart de schema doit repondre 503 `SCHEMA_EN_RETARD`, pas 500.

**Le defaut qu'on fixe.** Le login traitait deja ce cas : un cabinet en retard
de migrations renvoyait 503. Les routes de tarification lisaient la base de la
meme facon et renvoyaient 500. Le client interpretait alors une panne de
l'application, et l'interface ne pouvait afficher qu'une erreur generique, sans
dire qu'une mise a jour du schema etait necessaire.

**Le test rouge se joue sur la forme, pas sur le mock.** On construit la vraie
chaine d'encapsulation constatee le 11/10 - `ProgrammingError` qui enveloppe
l'erreur asyncpg, elle-meme deux niveaux dessous - puis on appelle le
gestionnaire enregistre. Un test qui fabriquerait une exception simple
passerait sans prouver que la chaine est parcourue.

**Le second test garde le 500.** Une panne inattendue doit rester une erreur
serveur : un 503 trop large rendrait invisible une faute de frappe dans une
requete, exactement ce que la panne d'origine masquait.
"""

from __future__ import annotations

import asyncpg.exceptions
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError

from src.core.exception_handlers import register_exception_handlers
from src.core.schema_perime import CODE_SCHEMA_EN_RETARD, MESSAGE_SCHEMA_EN_RETARD


def _programmee_via_asyncpg(message: str, *, table_name: str | None = None) -> ProgrammingError:
    """Reproduit la chaine d'encapsulation reelle, deux niveaux sous le 500.

    asyncpg leve, SQLAlchemy enveloppe deux fois. C'est exactement l'empilement
    mesure le 11/10 : un triage qui s'arrete au niveau 1 ne voit qu'un
    `ProgrammingError` et conclut « pas une divergence ».

    `table_name` est renseigne a part parce que le pilote le tire des champs
    renvoyes par PostgreSQL, et non du texte : une exception construite a la
    main depuis une chaine ne le porte pas. Sans lui, le test du journal
    verifierait un etat que le serveur ne produit jamais.
    """
    pilote = asyncpg.exceptions.UndefinedTableError(message)
    if table_name is not None:
        pilote.table_name = table_name
        pilote.schema_name = "public"
    enveloppe_interne = ProgrammingError("SELECT 1", {}, pilote)
    return ProgrammingError("SELECT 1", {}, enveloppe_interne)


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/v1/tarification/categories")
    async def _categories() -> dict:
        raise _programmee_via_asyncpg('relation "categories_patient" does not exist')

    return TestClient(app, raise_server_exceptions=False)


def test_une_table_absente_repond_503_et_non_500() -> None:
    reponse = _client().get("/api/v1/tarification/categories")

    assert reponse.status_code == 503, (
        f"attendu 503, recu {reponse.status_code} : un ecart de schema ne doit "
        "pas ressembler a une panne de l'application"
    )
    corps = reponse.json()
    assert corps["error"]["code"] == CODE_SCHEMA_EN_RETARD
    assert corps["success"] is False


def test_la_reponse_ne_laisse_fuir_aucun_detail_de_schema() -> None:
    """Ni table, ni identifiant de cabinet : le schema du cabinet ne sort pas."""
    corps = _client().get("/api/v1/tarification/categories").json()
    rendu = repr(corps)

    assert corps["error"]["details"] == {}
    assert "categories_patient" not in rendu
    assert "does not exist" not in rendu
    assert corps["error"]["message"] == MESSAGE_SCHEMA_EN_RETARD


def test_une_panne_inattendue_reste_une_erreur_serveur() -> None:
    """Un 503 trop large rendrait invisible une faute de frappe dans une requete."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/v1/tarification/actes")
    async def _actes() -> dict:
        # Colonne absente de la table : le pilote la signale par son nom de
        # colonne, pas par un code de divergence. Une faute de frappe.
        raise ProgrammingError("SELECT 1", {}, ValueError("colonne inconnue"))

    reponse = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/tarification/actes"
    )

    assert reponse.status_code == 500
    assert reponse.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_une_erreur_sans_chaine_d_encapsulation_ne_devient_pas_un_503() -> None:
    """Une boucle dans la chaine ne doit pas non plus partir en 503."""
    from src.core.schema_perime import est_divergence_de_schema

    a = ValueError("a")
    b = ValueError("b")
    a.__cause__ = b
    b.__cause__ = a

    assert est_divergence_de_schema(a) is False


@pytest.mark.parametrize(
    "table, attendu",
    [
        ("tarifs_actes", "tarifs_actes"),
        ("categories_patient", "categories_patient"),
    ],
)
def test_le_journal_recupere_le_nom_de_la_table_absente(table: str, attendu: str) -> None:
    """Le nom de la table va au journal du serveur, jamais a la reponse."""
    from src.core.schema_perime import element_manquant

    exc = _programmee_via_asyncpg(f'relation "{table}" does not exist', table_name=table)
    assert element_manquant(exc) == attendu


def test_une_faute_de_frappe_ne_donne_aucun_element_manquant() -> None:
    """Pas de divergence reconnue, donc rien a annoncer : le 500 reste un 500."""
    from src.core.schema_perime import element_manquant

    exc = ProgrammingError("SELECT 1", {}, ValueError("colonne inconnue"))
    assert element_manquant(exc) is None


def test_le_nom_est_relu_du_message_quand_le_pilote_ne_le_porte_pas() -> None:
    """Mesure sur une vraie erreur : le champ du pilote arrive vide.

    Sans ce repli, le journal affichait `element_manquant` a null et
    l'administrateur qui doit appliquer la migration n'apprenait rien.
    """
    from src.core.schema_perime import element_manquant

    exc = _programmee_via_asyncpg('relation "tarifs_actes" does not exist')
    assert getattr(exc.orig, "table_name", None) is None  # etat reel du pilote
    assert element_manquant(exc) == "tarifs_actes"