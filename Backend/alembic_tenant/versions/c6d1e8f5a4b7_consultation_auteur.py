"""Découplage de la consultation et du profil praticien.

Aujourd'hui, `consultations.praticien_id` est `NOT NULL` vers `praticiens.id`, ce
qui oblige à créer un profil de praticien — titre, spécialité, rattachement par
cabinet, disponibilités — pour la seule raison de pouvoir enregistrer *qui* a
fait un geste. Or `praticiens.numero_ordre` est déjà nullable : la garde est
donc **plus stricte que le modèle de données qu'elle prétend protéger**.

Ce que la migration fait :

- `auteur_id` devient le compte authentifié qui a fait l'acte. Il vient du JWT :
  il est connu, horodaté, et ne peut pas être inventé.
- `auteur_email` est figé au moment de l'écriture, comme sur `paiements` et
  `sessions_caisse` : supprimer un compte ne doit pas emporter la preuve de
  l'auteur d'un acte.
- `praticien_id` devient **facultatif**. Il reste ce qu'il est réellement : une
  attribution réglementaire optionnelle (numéro d'Ordre, spécialité).

**Contrôle bloquant.** Le remplissage ne recopie que des faits existants :
`auteur_id` vient de `praticien.utilisateur_id`, `auteur_email` de l'email de ce
compte. Si une consultation n'a pas de praticien, elle reste sans auteur et la
migration **échoue en comptant ces lignes** plutôt que d'inventer un auteur.
Un auteur inventé serait plus grave qu'un auteur absent.

Les consultations existantes gardent leur `praticien_id` : on ne réécrit pas
l'historique, on le rend facultatif pour l'avenir.

**Downgrade** : `praticien_id` redevient `NOT NULL`. Si des consultations ont été
créées sans profil depuis, le downgrade **refuse et le dit** — il ne supprime
jamais une consultation pour faire passer une contrainte.

Revision ID: c6d1e8f5a4b7
Revises: b5c0d7e4f923
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6d1e8f5a4b7"
down_revision: Union[str, None] = "b5c0d7e4f923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Auteur : nullable d'abord. On ne peut pas poser une contrainte NOT NULL
    #    tant que les consultations existantes n'ont pas de valeur à y mettre.
    op.add_column(
        "consultations",
        sa.Column("auteur_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("consultations", sa.Column("auteur_email", sa.String(150), nullable=True))
    op.create_foreign_key(
        "fk_consultations_auteur", "consultations", "utilisateurs", ["auteur_id"], ["id"]
    )
    op.create_index("ix_consultations_auteur_id", "consultations", ["auteur_id"])

    # 2. Remplissage : uniquement des faits déjà écrits dans la base.
    op.execute(
        """
        UPDATE consultations c
           SET auteur_id = p.utilisateur_id,
               auteur_email = u.email
          FROM praticiens p
          JOIN utilisateurs u ON u.id = p.utilisateur_id
         WHERE c.praticien_id = p.id
           AND c.auteur_id IS NULL
        """
    )

    # 3. Contrôle bloquant : une consultation sans auteur ne doit pas survivre.
    #    On compte avant de contraindre, pour pouvoir nommer le problème.
    orphelines = op.get_bind().execute(
        sa.text("SELECT count(*) FROM consultations WHERE auteur_id IS NULL")
    ).scalar_one()
    if orphelines:
        raise RuntimeError(
            f"{orphelines} consultation(s) sans auteur après remplissage : "
            "elles n'ont pas de praticien, donc pas de compte à recopier. "
            "Il faut les traiter explicitement avant de poser la contrainte — "
            "attribuer un auteur au hasard produirait une fausse traçabilité."
        )

    # 4. L'auteur devient obligatoire, le profil facultatif.
    op.alter_column(
        "consultations", "auteur_id", existing_type=sa.dialects.postgresql.UUID(), nullable=False
    )
    op.alter_column(
        "consultations",
        "praticien_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "consultations",
        "praticien_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=False,
    )
    op.drop_index("ix_consultations_auteur_id", table_name="consultations")
    op.drop_constraint("fk_consultations_auteur", "consultations", type_="foreignkey")
    op.drop_column("consultations", "auteur_email")
    op.drop_column("consultations", "auteur_id")
