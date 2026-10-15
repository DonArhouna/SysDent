"""Logo des sociétés stocké en base

Revision ID: e5b1c9a24f70
Revises: 3c2a49eaec83
Create Date: 2026-10-15 11:00:00.000000

Le logo vit dans la base master plutôt que sur le disque du serveur : il suit
les sauvegardes et le changement de serveur. Quelques dizaines de Ko par
cabinet, plafonnés à 512 Ko par l'application.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b1c9a24f70"
down_revision: Union[str, None] = "3c2a49eaec83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("societes", sa.Column("logo_contenu", sa.LargeBinary(), nullable=True))
    op.add_column("societes", sa.Column("logo_type", sa.String(30), nullable=True))
    op.add_column("societes", sa.Column("logo_maj", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for colonne in ("logo_maj", "logo_type", "logo_contenu"):
        op.drop_column("societes", colonne)
