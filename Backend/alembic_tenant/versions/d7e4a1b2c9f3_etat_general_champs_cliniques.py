"""Etat general : traitements, groupe sanguin, antecedents familiaux.

Quatre champs cliniques exiges par le cahier des charges qui n'existaient ni
dans le schema de saisie ni en base. Le service les acceptait puis les jetait en
silence : une saisie de traitement de diabete repondait 200 et disparaisait.

Toutes les colonnes sont nullable et sans valeur par defaut : un patient dont
l'etat general n'a jamais ete saisi ne doit pas se retrouver avec un groupe
sanguin vide, qui se lirait comme « renseigne et inconnu ».

Migration purely additive : aucune ligne n'est lue ni reecrite, donc aucune
donnee de sante n'est exposee a un risque de perte.

Revision ID: d7e4a1b2c9f3
Revises: c4f8a2d91e05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7e4a1b2c9f3"
down_revision: Union[str, None] = "c4f8a2d91e05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLONNES = (
    ("diabete_traitement", sa.String(200)),
    ("hta_traitement", sa.String(200)),
    ("groupe_sanguin", sa.String(10)),
    ("antecedents_familiaux", sa.Text()),
)


def upgrade() -> None:
    for nom, type_ in COLONNES:
        op.add_column("etats_generaux", sa.Column(nom, type_, nullable=True))


def downgrade() -> None:
    for nom, _ in reversed(COLONNES):
        op.drop_column("etats_generaux", nom)
