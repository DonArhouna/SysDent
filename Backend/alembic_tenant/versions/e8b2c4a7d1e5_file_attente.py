"""File d'attente (salle d'attente).

Le statut `EN_SALLE_ATTENTE` existe déjà sur `rendez_vous`, mais il ne suffit pas à
porter une file d'attente :

- **un patient sans rendez-vous n'a aucune ligne où entrer.** C'est le cas le plus
  fréquent dans un cabinet, et le module ne permettait pas de l'enregistrer ;
- **l'ordre de passage ne se déduit pas d'un statut** : deux patients peuvent être
  `EN_SALLE_ATTENTE`, celui qui est arrivé avant doit passer avant ;
- **le temps d'attente n'était stocké nulle part** ;
- **« qui a appelé, et quand »** n'était pas tracé.

La migration crée donc une table dédiée, **purement additive** : aucune table
existante n'est touchée, aucune ligne existante n'est modifiée. Un patient ayant
un rendez-vous passé `EN_SALLE_ATTENTE` avant cette migration n'apparaît pas
automatiquement dans la file : le secrétariat l'enregistre à son arrivée, ce qui est
le comportement normal.

**`cabinet_id` est la frontière d'isolation.** La file est celle d'un *site*, pas
d'un tenant : deux sites d'un même cabinet ont deux files, et un utilisateur ne voit
que les sites qui lui sont accessibles.

**Le destinataire est un `utilisateurs.id`**, jamais un `praticiens.id` : c'est la
conséquence directe de la décision « le dentiste est un utilisateur ». Le jour de la
fusion des deux entités, cette colonne n'aura rien à migrer.

**Ordre d'arrivée, pas de score de priorité** — décision du propriétaire : un ordre
de passage pondéré (urgence × ancienneté × rendez-vous) produirait une file que
personne ne sait expliquer à un patient qui attend depuis une heure. La priorité se
gère donc par `prioritaire` + `ordre_passage` remonté explicitement, toujours
justifiable à l'écran.

Contrainte d'intégrité portée par la base, pas seulement par le service : deux
secrétaires qui enregistrent une arrivée au même instant ne passent pas par le même
code Python. L'index unique partiel ci-dessous est la seule garantie fiable.

Revision ID: e8b2c4a7d1e5
Revises: d7f2a9c4b6e1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8b2c4a7d1e5"
down_revision: Union[str, None] = "d7f2a9c4b6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_attente",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_medical_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rendez_vous_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "statut",
            sa.Enum(
                "EN_ATTENTE",
                "APPele",
                "EN_CONSULTATION",
                "TERMINE",
                "ABSENT",
                "ANNULE",
                name="statutfileattenteenum",
            ),
            nullable=False,
        ),
        sa.Column(
            "heure_arrivee",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Rang dans la file. Volontairement un entier unique et lisible plutôt
        # qu'un score calculé : la secrétaire doit pouvoir dire « il passe 3e »
        # et l'utilisateur doit pouvoir vérifier l'ordre.
        sa.Column("ordre_passage", sa.Integer(), nullable=False),
        sa.Column("prioritaire", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("motif_urgence", sa.Text(), nullable=True),
        # Un utilisateur destinataire : la fusion praticien -> utilisateur ne
        # Ragnera pas cette colonne.
        sa.Column("dentiste_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("appele_par_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("appele_par_email", sa.String(length=150), nullable=True),
        sa.Column("appele_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termine_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_file_attente_patient",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dossier_medical_id"],
            ["dossiers_medicaux.id"],
            name="fk_file_attente_dossier",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cabinet_id"],
            ["cabinets.id"],
            name="fk_file_attente_cabinet",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rendez_vous_id"],
            ["rendez_vous.id"],
            name="fk_file_attente_rendez_vous",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["dentiste_id"],
            ["utilisateurs.id"],
            name="fk_file_attente_dentiste",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["consultation_id"],
            ["consultations.id"],
            name="fk_file_attente_consultation",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["appele_par_id"],
            ["utilisateurs.id"],
            name="fk_file_attente_appele_par",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_attente"),
    )

    # La requête de la salle d'attente : la file d'un site, dans l'ordre.
    op.create_index(
        "ix_file_attente_cabinet_statut_ordre",
        "file_attente",
        ["cabinet_id", "statut", "ordre_passage"],
    )
    op.create_index("ix_file_attente_patient_id", "file_attente", ["patient_id"])
    op.create_index("ix_file_attente_dossier_medical_id", "file_attente", ["dossier_medical_id"])
    op.create_index("ix_file_attente_cabinet_id", "file_attente", ["cabinet_id"])
    op.create_index("ix_file_attente_statut", "file_attente", ["statut"])
    op.create_index("ix_file_attente_heure_arrivee", "file_attente", ["heure_arrivee"])
    op.create_index("ix_file_attente_dentiste_id", "file_attente", ["dentiste_id"])

    # Un rendez-vous ne peut alimenter la file qu'une fois.
    op.create_index(
        "uq_file_attente_rendez_vous",
        "file_attente",
        ["rendez_vous_id"],
        unique=True,
        postgresql_where=sa.text("rendez_vous_id IS NOT NULL"),
    )
    # Une consultation n'est issue que d'un seul appel en salle.
    op.create_index(
        "uq_file_attente_consultation",
        "file_attente",
        ["consultation_id"],
        unique=True,
        postgresql_where=sa.text("consultation_id IS NOT NULL"),
    )

    # **La contrainte qui compte** : au plus un passage actif par patient et par
    # site. Sans elle, deux arrivées simultanées créent deux lignes et le patient
    # est appelé deux fois.
    op.create_index(
        "uq_file_attente_actif",
        "file_attente",
        ["patient_id", "cabinet_id"],
        unique=True,
        postgresql_where=sa.text("statut IN ('EN_ATTENTE', 'APPele', 'EN_CONSULTATION')"),
    )


def downgrade() -> None:
    # Table purement additive : la supprimer ne perd que des données de file
    # d'attente, jamais de données métier. Les patients, consultations,
    # rendez-vous et factures sont intacts.
    op.drop_table("file_attente")

    # `op.drop_table` ne supprime pas le type énuméré créé par `create_table`.
    # Sans ce `DROP TYPE`, le aller-retour est cassé : réappliquer la migration
    # échoue sur « type already exists ». C'est un défaut de réversibilité réel,
    # pas une précaution théorique — il a été constaté sur la base de copie.
    op.execute("DROP TYPE IF EXISTS statutfileattenteenum")