"""journal audit : interdire TRUNCATE

Revision ID: a41d7c93e2b6
Revises: bc633ae8cd75
Create Date: 2026-10-04 21:00:00.000000

Pourquoi une seconde révision alors que la baseline vient d'être écrite : les
migrations sont un historique. On n'altère jamais une révision déjà appliquée —
sur un poste de démonstration comme en production — on en ajoute une. La
baseline posait un déclencheur `FOR EACH ROW`, qui n'intercepte pas `TRUNCATE` :

    UPDATE journal_audit_plateforme ...  -> refusé (ligne)
    DELETE FROM journal_audit_plateforme -> refusé (ligne)
    TRUNCATE journal_audit_plateforme     -> ACCEPTÉ  <-- trou

`TRUNCATE` est une opération d'instruction : un déclencheur ligne ne peut pas
la voir. Il faut un second déclencheur, `FOR EACH STATEMENT`, sur le même garde-fou.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a41d7c93e2b6'
down_revision: Union[str, None] = 'bc633ae8cd75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TRIGGER journal_audit_plateforme_no_truncate
        BEFORE TRUNCATE ON journal_audit_plateforme
        FOR EACH STATEMENT EXECUTE FUNCTION plateforme_journal_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS journal_audit_plateforme_no_truncate ON journal_audit_plateforme;")