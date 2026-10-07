"""Cloture de caisse : sessions de caisse et rattachement des paiements.

Une session de caisse est la journee de travail d'un caissier. Ce qu'elle
apporte, et que le journal de caisse n'apportait pas :

- une **borne temporelle** qui rend un rapport de journée reproductible ;
- des **totaux par mode figes** a la cloture, qu'un paiement saisi apres coup ne
  peut pas reecrire ;
- un **ecart de caisse** annonce et motive, signe de la cloture.

Deux contraintes portent le sens du module :

1. **Une seule session ouverte par cabinet.** Deux caissiers encaissant dans le
   meme tiroir sans session commune produiraient un rapport faux sans qu'on
   puisse le voir. L'index unique partiel ci-dessous l'interdit en base, pas
   seulement en application : une regle verifiee uniquement dans le code finit
   toujours par etre contournee.

2. **Un paiement doit etre rattache.** La colonne est nullable pour les
   paiements anterieurs a ce deploiement — on ne réécrit pas l'historique — mais
   tout nouveau paiement exige une session ouverte. Le « rattachement au tiroir »
   est ce qui distingue une caisse qui se ferme de receipts empiles.

Migration purement additive : aucune ligne n'est reecrite.

Revision ID: f3a8d5b2c701
Revises: e2f7b3c8a104
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a8d5b2c701"
down_revision: Union[str, None] = "e2f7b3c8a104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUT_SESSION = postgresql.ENUM("OUVERTE", "CLOSE", name="statutsessioncaisseenum")
# SQLAlchemy recrée un ENUM dès qu'il apparaît dans un `create_table`, en plus de
# la création explicite : sans `create_type=False`, le type est créé deux fois et
# la migration échoue sur `DuplicateObject`.
STATUT_SESSION_COLONNE = postgresql.ENUM(
    "OUVERTE", "CLOSE", name="statutsessioncaisseenum", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    STATUT_SESSION.create(bind, checkfirst=True)

    op.create_table(
        "sessions_caisse",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statut", STATUT_SESSION_COLONNE, nullable=False, server_default="OUVERTE"),
        sa.Column(
            "ouverte_le",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ouverte_par_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ouverte_par_email", sa.String(150), nullable=True),
        sa.Column("ouverture_especes", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("close_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_par_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("close_par_email", sa.String(150), nullable=True),
        sa.Column("especes_comptees", sa.Numeric(12, 2), nullable=True),
        sa.Column("ecart_especes", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_especes", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_carte", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_virement", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_mobile_money", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_cheque", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("nb_paiements", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("motif_ecart", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["cabinet_id"], ["cabinets.id"], ondelete="CASCADE", name="fk_sessions_caisse_cabinet"
        ),
        sa.ForeignKeyConstraint(
            ["ouverte_par_id"], ["utilisateurs.id"], name="fk_sessions_caisse_ouverte_par"
        ),
        sa.ForeignKeyConstraint(
            ["close_par_id"], ["utilisateurs.id"], name="fk_sessions_caisse_close_par"
        ),
        sa.UniqueConstraint("numero", name="uq_session_caisse_numero"),
        # Une session close ne porte ni espèces comptées ni écart : les deux sont
        # des résultats de clôture, pas des données d'ouverture.
        sa.CheckConstraint(
            "(statut = 'OUVERTE') OR (especes_comptees IS NOT NULL)",
            name="ck_session_close_exige_comptage",
        ),
    )
    op.create_index("ix_sessions_caisse_statut", "sessions_caisse", ["statut"])
    op.create_index("ix_sessions_caisse_cabinet_id", "sessions_caisse", ["cabinet_id"])

    # Une seule session ouverte par cabinet. Index unique partiel : c'est
    # l'infrastructure qui tient la règle, pas l'application.
    op.create_index(
        "uq_session_caisse_ouverte_par_cabinet",
        "sessions_caisse",
        ["cabinet_id"],
        unique=True,
        postgresql_where=sa.text("statut = 'OUVERTE'"),
    )

    op.add_column(
        "paiements",
        sa.Column("session_caisse_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_paiements_session_caisse",
        "paiements",
        "sessions_caisse",
        ["session_caisse_id"],
        ["id"],
    )
    op.create_index("ix_paiements_session_caisse_id", "paiements", ["session_caisse_id"])


def downgrade() -> None:
    op.drop_index("ix_paiements_session_caisse_id", table_name="paiements")
    op.drop_constraint("fk_paiements_session_caisse", "paiements", type_="foreignkey")
    op.drop_column("paiements", "session_caisse_id")

    op.drop_index("uq_session_caisse_ouverte_par_cabinet", table_name="sessions_caisse")
    op.drop_index("ix_sessions_caisse_cabinet_id", table_name="sessions_caisse")
    op.drop_index("ix_sessions_caisse_statut", table_name="sessions_caisse")
    op.drop_table("sessions_caisse")

    bind = op.get_bind()
    STATUT_SESSION.drop(bind, checkfirst=True)
