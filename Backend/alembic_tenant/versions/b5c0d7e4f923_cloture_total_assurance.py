"""Total « assurance » dans la clôture de caisse.

`ASSURANCE` fait partie des modes de paiement du catalogue, mais la clôture créée
pour les sessions de caisse ne portait que cinq colonnes de total. Un encaissement
assurance était donc **ignoré au moment de la clôture** : le rapport de journée
annonçait un chiffre inférieur au réel, sans aucun signal.

C'est le pire genre de défaut comptable — un faux qui a l'air vrai. On ajoute la
colonne manquante, et `tests/test_caisse_cloture.py` verrouille désormais que
tous les modes du catalogue ont une colonne.

Migration additive et réversible : une colonne nullable avec 0 par défaut. Les
sessions déjà closes gardent leurs totaux inchangés — on ne réécrit pas une pièce
comptable déjà constatée.

Revision ID: b5c0d7e4f923
Revises: a4b9e6c3d812
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5c0d7e4f923"
down_revision: Union[str, None] = "a4b9e6c3d812"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions_caisse",
        sa.Column("total_assurance", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    # Les sessions déjà closes ne sont pas recalculées : leurs totaux sont ce qui
    # a été constaté le jour de la clôture. Les éventuels encaissements
    # « assurance » de ces journées n'y figuraient pas — c'est le défaut que cette
    # migration corrige pour l'avenir, pas une réécriture du passé.


def downgrade() -> None:
    op.drop_column("sessions_caisse", "total_assurance")
