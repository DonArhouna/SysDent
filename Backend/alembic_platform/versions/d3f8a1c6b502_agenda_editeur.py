"""Agenda de l'éditeur : rendez-vous avec les cabinets et les prospects

Revision ID: d3f8a1c6b502
Revises: c7e4a2f19d63
Create Date: 2026-10-15 09:00:00.000000

Type et statut en texte contrôlé par l'application (pas d'énumération
PostgreSQL) : ajouter un type de rendez-vous ne doit pas exiger une migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3f8a1c6b502"
down_revision: Union[str, None] = "c7e4a2f19d63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rendez_vous_plateforme",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("titre", sa.String(150), nullable=False),
        sa.Column("type_rdv", sa.String(20), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="PLANIFIE"),
        sa.Column("debut", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duree_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prospect_nom", sa.String(150), nullable=True),
        sa.Column("contact_nom", sa.String(150), nullable=True),
        sa.Column("contact_email", sa.String(150), nullable=True),
        sa.Column("contact_telephone", sa.String(30), nullable=True),
        sa.Column("lieu", sa.String(255), nullable=True),
        sa.Column("lien_visio", sa.String(500), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("utilisateurs_plateforme.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("motif_annulation", sa.Text(), nullable=True),
        sa.Column("cree_par", sa.String(150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("duree_minutes BETWEEN 5 AND 600", name="ck_rdv_plateforme_duree"),
        sa.CheckConstraint(
            "statut IN ('PLANIFIE','CONFIRME','EFFECTUE','ANNULE')", name="ck_rdv_plateforme_statut"
        ),
    )
    for colonne in ("type_rdv", "statut", "debut", "tenant_id", "agent_id"):
        op.create_index(f"ix_rendez_vous_plateforme_{colonne}", "rendez_vous_plateforme", [colonne])


def downgrade() -> None:
    op.drop_table("rendez_vous_plateforme")
