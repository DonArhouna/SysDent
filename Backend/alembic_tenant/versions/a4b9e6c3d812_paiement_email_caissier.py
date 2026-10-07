"""Identité du caissier sur le paiement : email dénormalisé.

`paiements.enregistre_par_id` pointe vers le compte, mais un compte supprimé emporte
la preuve avec lui. Sur une pièce comptable, « qui a encaissé » doit survivre à la
suppression du compte — exactement la raison pour laquelle `sessions_caisse`
porte déjà `ouverte_par_email` et `close_par_email`.

Migration additive et réversible :

- la colonne est nullable : un encaissement fait sans utilisateur authentifié
  (script, reprise manuelle) reste possible, il ne portera simplement pas d'email ;
- le remplissage reprend l'email des paiements existants via leur
  `enregistre_par_id`, ce qui rend l'historique lisible sans ressaisie ;
- `downgrade` supprime la colonne : rien n'est perdu, la jointure sur
  `enregistre_par_id` reste possible.

Revision ID: a4b9e6c3d812
Revises: f3a8d5b2c701
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4b9e6c3d812"
down_revision: Union[str, None] = "f3a8d5b2c701"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paiements",
        sa.Column("enregistre_par_email", sa.String(150), nullable=True),
    )

    # Remplissage : on recopie l'email du compte encore présent. Les paiements
    # dont le compte a disparu restent sans email — on ne l'invente pas.
    op.execute(
        """
        UPDATE paiements p
           SET enregistre_par_email = u.email
          FROM utilisateurs u
         WHERE u.id = p.enregistre_par_id
           AND p.enregistre_par_email IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("paiements", "enregistre_par_email")
