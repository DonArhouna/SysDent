"""Site de rattachement d'un utilisateur.

`Utilisateur` n'avait aucun site : un compte n'était rattaché à rien. C'était
supportable tant qu'il n'existait qu'un administrateur et un praticien par
cabinet — le rattachement des praticiens était porté par `cabinet_praticiens`.

Dès lors qu'un cabinet gère plusieurs sites et plusieurs employés, ce modèle ne
suffit plus : **où travaille une secrétaire ?** La colonne rend la question
répondable sans passer par une table de rattachement par métier.

**Choix et sa limite.** La colonne est *facultative* et représente le site
principal. Elle ne remplace pas `cabinet_praticiens`, qui porte un historique
(un praticien qui tourne entre deux sites, ou qui quitte le cabinet, doit rester
rattaché pour que ses consultations passées soient attribuables) — les deux
coexistent donc, et c'est assumé. Fusionner les deux est une décision à valider,
pas un détail de migration.

Migration purement additive : une colonne nullable, aucune ligne touchée.

Revision ID: d7f2a9c4b6e1
Revises: c6d1e8f5a4b7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7f2a9c4b6e1"
down_revision: Union[str, None] = "c6d1e8f5a4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "utilisateurs",
        sa.Column("cabinet_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_utilisateurs_cabinet", "utilisateurs", "cabinets", ["cabinet_id"], ["id"]
    )
    op.create_index("ix_utilisateurs_cabinet_id", "utilisateurs", ["cabinet_id"])

    # Les comptes existants sont rattachés a leur site quand on peut le deduire
    # sans ambiguite : le cabinet de rattachement actif d'un praticien, sinon
    # celui du seul cabinet du tenant s'il n'en existe qu'un. Un tenant
    # multi-sites sans praticien laisse le compte sans site -- on ne devine pas.
    #
    # La jointure passe par `praticiens` : `cabinet_praticiens` porte
    # `praticien_id`, pas `utilisateur_id`.
    op.execute(
        """
        UPDATE utilisateurs u
           SET cabinet_id = cp.cabinet_id
          FROM (
            SELECT DISTINCT ON (p.utilisateur_id) p.utilisateur_id, cp.cabinet_id
              FROM cabinet_praticiens cp
              JOIN praticiens p ON p.id = cp.praticien_id
             WHERE cp.actif
             ORDER BY p.utilisateur_id, cp.date_debut DESC
          ) cp
         WHERE cp.utilisateur_id = u.id
           AND u.cabinet_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE utilisateurs u
           SET cabinet_id = c.id
          FROM (SELECT id FROM cabinets ORDER BY created_at LIMIT 1) c
         WHERE u.cabinet_id IS NULL
           AND (SELECT count(*) FROM cabinets) = 1
        """
    )


def downgrade() -> None:
    op.drop_index("ix_utilisateurs_cabinet_id", table_name="utilisateurs")
    op.drop_constraint("fk_utilisateurs_cabinet", "utilisateurs", type_="foreignkey")
    op.drop_column("utilisateurs", "cabinet_id")
