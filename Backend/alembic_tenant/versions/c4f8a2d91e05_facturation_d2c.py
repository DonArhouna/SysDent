"""facturation d2c : devis, echelonnement, traçabilité factures

Ajoute les tables du module Facturation (D2C) et les colonnes de traçabilité
sur `factures` et `paiements` (MLD §4.8 : #praticien_id, #emis_par,
#enregistre_par, devis.facture_id).

Revision ID: c4f8a2d91e05
Revises: a1c7d5e9b3f2
Create Date: 2026-10-03 14:30:00.000000

Notes
-----
- `devis.facture_id` est UNIQUE : un devis ne se convertit qu'une fois (RG14).
- `plans_echelonnement.facture_id` est UNIQUE : un seul plan actif par facture.
- Les FK utilisateurs sont en `SET NULL` à la suppression d'un compte : la
  trace financière reste, l'auteur devient anonyme (comme un reçu prénommé).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4f8a2d91e05"
down_revision: Union[str, None] = "a1c7d5e9b3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "devis",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "praticien_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("montant_total", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "statut",
            sa.Enum(
                "BROUILLON",
                "ENVOYE",
                "ACCEPTE",
                "REFUSE",
                "EXPIRE",
                name="statutdevisenum",
            ),
            nullable=False,
        ),
        sa.Column("date_validite", sa.Date(), nullable=True),
        sa.Column("signature_patient", sa.Boolean(), nullable=False),
        sa.Column("date_signature", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("facture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("emis_par_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["praticien_id"], ["praticiens.id"]),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"]),
        sa.ForeignKeyConstraint(["facture_id"], ["factures.id"]),
        sa.ForeignKeyConstraint(["emis_par_id"], ["utilisateurs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devis_numero", "devis", ["numero"], unique=True)
    op.create_index("ix_devis_id", "devis", ["id"], unique=False)
    op.create_index("ix_devis_statut", "devis", ["statut"], unique=False)
    op.create_index("ix_devis_patient_id", "devis", ["patient_id"], unique=False)
    # UNIQUE en contrainte (pas en index) : c'est ce que le modèle déclare.
    op.create_unique_constraint("uq_devis_facture_id", "devis", ["facture_id"])

    op.create_table(
        "lignes_devis",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("devis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acte_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("designation", sa.String(length=255), nullable=False),
        sa.Column("dent_numero", sa.Integer(), nullable=True),
        sa.Column("quantite", sa.Integer(), nullable=False),
        sa.Column("prix_unitaire", sa.Numeric(12, 2), nullable=False),
        sa.Column("montant", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["devis_id"], ["devis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acte_id"], ["actes_nomenclature.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lignes_devis_id", "lignes_devis", ["id"], unique=False)

    op.create_table(
        "plans_echelonnement",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("montant_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("nombre_echeances", sa.Integer(), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column(
            "frequence",
            sa.Enum("HEBDO", "BIMENSUEL", "MENSUEL", name="frequenceechelonnementenum"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["facture_id"], ["factures.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plans_echelonnement_id", "plans_echelonnement", ["id"], unique=False)
    # Index UNIQUE (unique=True + index=True dans le modèle).
    op.create_index(
        "ix_plans_echelonnement_facture_id",
        "plans_echelonnement",
        ["facture_id"],
        unique=True,
    )

    op.create_table(
        "echeances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("montant_prevu", sa.Numeric(12, 2), nullable=False),
        sa.Column("montant_paye", sa.Numeric(12, 2), nullable=False),
        sa.Column("date_prevue", sa.Date(), nullable=False),
        sa.Column("date_paiement", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paiement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "statut",
            sa.Enum("A_PAYER", "PAYEE", "EN_RETARD", "ANNULEE", name="statutecheanceenum"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plans_echelonnement.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paiement_id"], ["paiements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_echeances_id", "echeances", ["id"], unique=False)
    op.create_index("ix_echeances_plan_id", "echeances", ["plan_id"], unique=False)
    op.create_index("ix_echeances_statut", "echeances", ["statut"], unique=False)

    # Traçabilité (MLD §4.8) : qui a émis, qui a encaissé, praticien d'origine.
    op.add_column("factures", sa.Column("praticien_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("factures", sa.Column("emis_par_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_factures_praticien", "factures", "praticiens", ["praticien_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_factures_emis_par", "factures", "utilisateurs", ["emis_par_id"], ["id"]
    )
    op.add_column("paiements", sa.Column("enregistre_par_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_paiements_enregistre_par", "paiements", "utilisateurs", ["enregistre_par_id"], ["id"]
    )

    # Filtres de listes : caisse par jour/statut, factures par patient.
    op.create_index("ix_factures_statut", "factures", ["statut"], unique=False)
    op.create_index("ix_factures_patient_id", "factures", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_factures_patient_id", table_name="factures")
    op.drop_index("ix_factures_statut", table_name="factures")
    op.drop_column("paiements", "enregistre_par_id")
    op.drop_column("factures", "emis_par_id")
    op.drop_column("factures", "praticien_id")
    op.drop_index("ix_echeances_statut", table_name="echeances")
    op.drop_index("ix_echeances_plan_id", table_name="echeances")
    op.drop_index("ix_echeances_id", table_name="echeances")
    op.drop_table("echeances")
    op.drop_index("ix_plans_echelonnement_facture_id", table_name="plans_echelonnement")
    op.drop_index("ix_plans_echelonnement_id", table_name="plans_echelonnement")
    op.drop_table("plans_echelonnement")
    op.drop_index("ix_lignes_devis_id", table_name="lignes_devis")
    op.drop_table("lignes_devis")
    op.drop_constraint("uq_devis_facture_id", "devis", type_="unique")
    op.drop_index("ix_devis_patient_id", table_name="devis")
    op.drop_index("ix_devis_statut", table_name="devis")
    op.drop_index("ix_devis_id", table_name="devis")
    op.drop_index("ix_devis_numero", table_name="devis")
    op.drop_table("devis")
    sa.Enum(
        name="statutdevisenum"
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="frequenceechelonnementenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="statutecheanceenum").drop(op.get_bind(), checkfirst=True)
