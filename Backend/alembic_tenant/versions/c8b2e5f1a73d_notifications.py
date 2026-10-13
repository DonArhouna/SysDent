"""Notifications : table d'adressage par utilisateur, sans emetteur.

**Placement.** Cette revision enchaine apres `d6a1f4c92b57`, le correctif qui
rattache `ASSURANCE:WRITE_PATIENT` au secretariat. Elle enchainait
auparavant sur `f1a7c3d90b28`, ce qui donnait deux enfants a cette revision, donc
deux tetes et un `upgrade head` dont la cible n'etait plus deterministe. Elle
n'est appliquee a aucune base, donc le deplacement est sans risque.

**Pourquoi une table maintenant.** Aucun emetteur n'existe : aucun evenement
metier ne cree de notification dans cette tranche. La table est nee quand
meme, parce que le modele, le cloisonnement et le contrat de pagination se
prouvent sans avoir invente les evenements. Les emetteurs viendront apres
decision sur leurs types et leurs destinataires, et n'auront rien a reecrire.

**Cloisonnement porte, pas deduit.** `cabinet_id` est denormalise alors que
`utilisateur_id` suffirait : une base par cabinet rend le filtre implicite, et
une notification fuit vers un autre cabinet des que le mecanisme change. Le
porter rend la contrainte explicite, donc testable.

**Pas de contrainte d unicite.** Une notification est un evenement, pas un etat :
deux evenements identiques pour le meme destinataire sont deux notifications
legitimes. Un `UNIQUE` les fusionnerait silencieusement et perdrait un evenement.

**Reversibilite.** `downgrade` retire la table. Aucun lien ne la pointe, donc
aucun retrait ordonne n'est necessaire.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8b2e5f1a73d"
down_revision: Union[str, None] = "d6a1f4c92b57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("titre", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("lu", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "cabinet_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "utilisateur_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["cabinet_id"],
            ["cabinets.id"],
            name=op.f("fk_notifications_cabinet_id_cabinets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["utilisateur_id"],
            ["utilisateurs.id"],
            name=op.f("fk_notifications_utilisateur_id_utilisateurs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    # Le compteur non lu de la barre de navigation se pose sur
    # (utilisateur_id, lu). Sans cet index, chaque badge ferait un balayage.
    op.create_index(
        "ix_notifications_utilisateur_lu",
        "notifications",
        ["utilisateur_id", "lu"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_utilisateur_id",
        "notifications",
        ["utilisateur_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_cabinet_id",
        "notifications",
        ["cabinet_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_cabinet_id", table_name="notifications")
    op.drop_index("ix_notifications_utilisateur_id", table_name="notifications")
    op.drop_index("ix_notifications_utilisateur_lu", table_name="notifications")
    op.drop_table("notifications")