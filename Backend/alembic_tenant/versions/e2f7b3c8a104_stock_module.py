"""Stock : catalogue par site, lots, mouvements, commandes et receptions.

Neuf tables nouvelles. Le module n'existait pas : le frontend appelait cinq
endpoints inexistants depuis le debut, avec un etat « module indisponible »
honnete. Aucune donnee existante n'est touchee : uniquement des CREATE TABLE.

Deux choix de modelisation meritent d'etre explicites, parce qu'ils ne sont pas
evidents :

1. La quantite n'est pas sur l'article mais sur `stocks_sites` (article, site).
   Un cabinet multi-sites n'a pas « 40 compresses » : il en a 40 repartis entre
   ses fauteuils, et c'est cette repartition qui permet de savoir ou chercher
   une ampoule en urgence.

2. La reception credite le stock automatiquement, sans validation a deux mains.
   Dans un cabinet d'une ou deux personnes, une double validation empeche la
   reception, donc le stock devient faux — et un stock faux, parce qu'il est
   faux, est cru. La securite vient de la tracabilite (qui, quand, quelle
   commande), pas de l'arret de l'ecriture.

La reception d'une commande ne peut pas non plus surpasser la quantite
commandee : c'est une contrainte de base (`ck_ligne_reception_quantite`), parce
qu'une regle verifiee uniquement en application finit toujours par etre
contournee par un script de reprise.

Revision ID: e2f7b3c8a104
Revises: d7e4a1b2c9f3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2f7b3c8a104"
down_revision: Union[str, None] = "d7e4a1b2c9f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALEURS_MOUVEMENT = (
    "ENTREE",
    "SORTIE_CONSULTATION",
    "PERTE_PEREMPTION",
    "AJUSTEMENT_INVENTAIRE",
)
VALEURS_COMMANDE = ("BROUILLON", "ENVOYEE", "PARTIELLEMENT_REÇUE", "RECUE", "ANNULEE")

TYPE_MOUVEMENT = postgresql.ENUM(*VALEURS_MOUVEMENT, name="typemouvementstockenum")
STATUT_COMMANDE = postgresql.ENUM(*VALEURS_COMMANDE, name="statutcommandeenum")

# SQLAlchemy recrée un ENUM dès qu'il apparaît dans un `create_table`, en plus de
# la création explicite ci-dessous : sans `create_type=False`, le type est créé
# deux fois et la migration échoue sur `DuplicateObject`. Ces deux instances ne
# servent donc qu'aux colonnes, jamais à la création.
TYPE_MOUVEMENT_COLONNE = postgresql.ENUM(
    *VALEURS_MOUVEMENT, name="typemouvementstockenum", create_type=False
)
STATUT_COMMANDE_COLONNE = postgresql.ENUM(
    *VALEURS_COMMANDE, name="statutcommandeenum", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    TYPE_MOUVEMENT.create(bind, checkfirst=True)
    STATUT_COMMANDE.create(bind, checkfirst=True)

    op.create_table(
        "fournisseurs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("contact", sa.String(150), nullable=True),
        sa.Column("telephone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("adresse", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fournisseurs_nom", "fournisseurs", ["nom"])

    op.create_table(
        "articles_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("designation", sa.String(200), nullable=False),
        sa.Column("categorie", sa.String(100), nullable=False),
        sa.Column("unite", sa.String(30), nullable=False),
        sa.Column("seuil_alerte", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prix_achat", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("date_peremption", sa.Date(), nullable=True),
        sa.Column("emplacement", sa.String(100), nullable=True),
        sa.Column("gere_par_lot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_article_stock_code"),
    )
    op.create_index("ix_articles_stock_categorie", "articles_stock", ["categorie"])
    op.create_index("ix_articles_stock_actif", "articles_stock", ["actif"])

    op.create_table(
        "stocks_sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles_stock.id"], ondelete="CASCADE", name="fk_stocks_sites_article"
        ),
        sa.ForeignKeyConstraint(
            ["cabinet_id"], ["cabinets.id"], ondelete="CASCADE", name="fk_stocks_sites_cabinet"
        ),
        sa.UniqueConstraint("article_id", "cabinet_id", name="uq_stock_site_article_cabinet"),
        # Une quantité négative signifierait que le comptage physique et le
        # comptage informatique divergent ; on refuse l'écriture plutôt que de
        # laisser un stock négatif se propager dans les mouvements.
        sa.CheckConstraint("quantite >= 0", name="ck_stock_site_quantite_positive"),
    )
    op.create_index("ix_stocks_sites_article_id", "stocks_sites", ["article_id"])
    op.create_index("ix_stocks_sites_cabinet_id", "stocks_sites", ["cabinet_id"])

    op.create_table(
        "lots_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_lot", sa.String(100), nullable=False),
        sa.Column("date_peremption", sa.Date(), nullable=True),
        sa.Column("quantite_initiale", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantite_restante", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles_stock.id"], ondelete="CASCADE", name="fk_lots_stock_article"
        ),
        sa.ForeignKeyConstraint(
            ["cabinet_id"], ["cabinets.id"], ondelete="CASCADE", name="fk_lots_stock_cabinet"
        ),
        sa.CheckConstraint(
            "quantite_restante >= 0 AND quantite_restante <= quantite_initiale",
            name="ck_lot_quantite_coherente",
        ),
    )
    op.create_index("ix_lots_stock_article_id", "lots_stock", ["article_id"])
    op.create_index("ix_lots_stock_date_peremption", "lots_stock", ["date_peremption"])

    op.create_table(
        "mouvements_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type_mouvement", TYPE_MOUVEMENT_COLONNE, nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False),
        sa.Column("stock_avant", sa.Integer(), nullable=False),
        sa.Column("stock_apres", sa.Integer(), nullable=False),
        sa.Column("motif", sa.String(300), nullable=True),
        sa.Column("auteur_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("auteur_email", sa.String(150), nullable=True),
        sa.Column("commande_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "date_mouvement",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["article_id"], ["articles_stock.id"], ondelete="CASCADE", name="fk_mouvements_stock_article"
        ),
        sa.ForeignKeyConstraint(
            ["cabinet_id"], ["cabinets.id"], ondelete="CASCADE", name="fk_mouvements_stock_cabinet"
        ),
        sa.ForeignKeyConstraint(["lot_id"], ["lots_stock.id"], name="fk_mouvements_stock_lot"),
        sa.ForeignKeyConstraint(
            ["auteur_id"], ["utilisateurs.id"], name="fk_mouvements_stock_auteur"
        ),
        # La quantité est un nombre positif ; le sens vient du type. Une ligne
        # négative ferait douter le lecteur au lieu de l'informer.
        sa.CheckConstraint("quantite > 0", name="ck_mouvement_quantite_positive"),
    )
    op.create_index("ix_mouvements_stock_article_id", "mouvements_stock", ["article_id"])
    op.create_index("ix_mouvements_stock_type_mouvement", "mouvements_stock", ["type_mouvement"])
    op.create_index("ix_mouvements_stock_date_mouvement", "mouvements_stock", ["date_mouvement"])

    op.create_table(
        "commandes_fournisseur",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("fournisseur_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statut", STATUT_COMMANDE_COLONNE, nullable=False, server_default="BROUILLON"),
        sa.Column("date_commande", sa.Date(), nullable=False, server_default=sa.func.now()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("auteur_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("auteur_email", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["fournisseur_id"], ["fournisseurs.id"], name="fk_commandes_fournisseur"
        ),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], name="fk_commandes_auteur"),
        sa.UniqueConstraint("numero", name="uq_commande_fournisseur_numero"),
    )
    op.create_index("ix_commandes_fournisseur_statut", "commandes_fournisseur", ["statut"])

    op.create_table(
        "lignes_commande",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("commande_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantite_commandee", sa.Integer(), nullable=False),
        sa.Column("quantite_recue", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prix_unitaire", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["commande_id"], ["commandes_fournisseur.id"], ondelete="CASCADE", name="fk_lignes_commande"
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles_stock.id"], name="fk_lignes_commande_article"),
        sa.CheckConstraint(
            "quantite_commandee > 0 AND quantite_recue >= 0 AND quantite_recue <= quantite_commandee",
            name="ck_ligne_commande_quantite_coherente",
        ),
    )
    op.create_index("ix_lignes_commande_commande_id", "lignes_commande", ["commande_id"])

    op.create_table(
        "receptions_fournisseur",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("commande_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date_reception", sa.Date(), nullable=False, server_default=sa.func.now()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("auteur_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("auteur_email", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["commande_id"], ["commandes_fournisseur.id"], name="fk_receptions_commande"
        ),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], name="fk_receptions_auteur"),
        sa.UniqueConstraint("numero", name="uq_reception_fournisseur_numero"),
    )

    op.create_table(
        "lignes_reception",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reception_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ligne_commande_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantite_recue", sa.Integer(), nullable=False),
        sa.Column("lot_code", sa.String(100), nullable=True),
        sa.Column("date_peremption", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reception_id"], ["receptions_fournisseur.id"], ondelete="CASCADE", name="fk_lignes_reception"
        ),
        sa.ForeignKeyConstraint(
            ["ligne_commande_id"], ["lignes_commande.id"], ondelete="CASCADE", name="fk_lignes_reception_ligne"
        ),
        sa.CheckConstraint("quantite_recue > 0", name="ck_ligne_reception_quantite_positive"),
    )
    op.create_index("ix_lignes_reception_reception_id", "lignes_reception", ["reception_id"])


def downgrade() -> None:
    op.drop_table("lignes_reception")
    op.drop_table("receptions_fournisseur")
    op.drop_table("lignes_commande")
    op.drop_table("commandes_fournisseur")
    op.drop_table("mouvements_stock")
    op.drop_table("lots_stock")
    op.drop_table("stocks_sites")
    op.drop_table("articles_stock")
    op.drop_table("fournisseurs")

    bind = op.get_bind()
    STATUT_COMMANDE.drop(bind, checkfirst=True)
    TYPE_MOUVEMENT.drop(bind, checkfirst=True)

