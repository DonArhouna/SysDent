"""usage_jeton : ajouter CODE_2FA_EMAIL

Revision ID: c7e4a2f19d63
Revises: f2c9e5d7a3b1
Create Date: 2026-10-14 12:00:00.000000

Le code a 6 chiffres envoye par e-mail (alternative au TOTP) reutilise la table
`jetons_usage_unique`, comme le defi 2FA : haché, a usage unique, a duree
limitee. Une valeur d'enumeration suffit.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c7e4a2f19d63'
down_revision: Union[str, None] = 'f2c9e5d7a3b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE usage_jeton ADD VALUE IF NOT EXISTS 'CODE_2FA_EMAIL'")


def downgrade() -> None:
    # PostgreSQL ne permet pas de retirer une valeur d'enumeration : elle reste,
    # inoffensive, aucun code ne la produit si la fonctionnalite est retiree.
    op.execute("COMMENT ON TYPE usage_jeton IS 'valeur CODE_2FA_EMAIL ajoutee par c7e4a2f19d63, non retirable en PostgreSQL'")
