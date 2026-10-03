"""rendez_vous_terminaux_ne_bloquent_plus

Correction de la contrainte d'exclusion `ex_rendez_vous_praticien`.

Revision ID: a1c7d5e9b3f2
Revises: f4433b308196
Create Date: 2026-10-03 12:05:00.000000

Pourquoi cette révision
----------------------
La contrainte exclut `ANNULE` et `ABSENT` de son périmètre, mais pas
`TERMINEE`. Conséquence : un rendez-vous terminé continuait de réserver son
créneau, si bien qu'il devenait impossible de reprendre une heure déjà
honorée. Le service, lui, excluait les trois statuts terminaux — d'où l'écart
entre ce que l'API refusait et ce que la base tolérait.

« Terminé » est un passé : rien ne doit bloquer une fois le patient reparti.
La trace du soin reste ailleurs : `consultations.fauteuil_id` et l'historique
d'actes.

Correction par une nouvelle révision plutôt qu'en réécrivant `f4433b308196`,
déjà appliquée et versionnée : réécrire une révision en vigueur produirait un
historique qui ne correspond plus à ce qui a réellement tourné.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c7d5e9b3f2"
down_revision: Union[str, None] = "f4433b308196"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `op.drop_constraint` ne connaît pas le type « exclude » : SQL brut.
_SUPPRIMER = "ALTER TABLE rendez_vous DROP CONSTRAINT ex_rendez_vous_praticien"

_CONTRAINTE = """
    ALTER TABLE rendez_vous
    ADD CONSTRAINT ex_rendez_vous_praticien
    EXCLUDE USING gist (
        praticien_id WITH =,
        tstzrange(debut, fin, '[)') WITH &&
    )
    WHERE (%s)
"""


def upgrade() -> None:
    op.execute(_SUPPRIMER)
    op.execute(_CONTRAINTE % "statut NOT IN ('ANNULE', 'ABSENT', 'TERMINEE')")


def downgrade() -> None:
    # Retour à l'état précédent : seuls ANNULE et ABSENT sortent du périmètre.
    op.execute(_SUPPRIMER)
    op.execute(_CONTRAINTE % "statut NOT IN ('ANNULE', 'ABSENT')")
