"""consultations_actes

Revision ID: acaeddf74a3e
Revises: f81d897fd9db
Create Date: 2026-10-01 20:22:10.863449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'acaeddf74a3e'
down_revision: Union[str, None] = 'f81d897fd9db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Colonne NOT NULL sur une table déjà peuplée : on crée d'abord le type ENUM,
    # puis on ajoute la colonne avec un défaut explicite, et seulement ensuite on
    # pose la contrainte NOT NULL. Un `add_column(..., nullable=False)` sans
    # server_default échouerait sur une base contenant déjà des consultations.
    motif_consultation_enum = postgresql.ENUM(
        'DOULEUR', 'CONTROLE', 'URGENCE', 'ESTHETIQUE', 'SUIVI', 'PROTHESE', 'ORTHODONTIE', 'AUTRE',
        name='motifconsultationenum',
    )
    motif_consultation_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'actes_nomenclature',
        sa.Column('unitaire', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f('ix_actes_nomenclature_categorie'), 'actes_nomenclature', ['categorie'], unique=False)

    op.add_column('actes_realises', sa.Column('description', sa.Text(), nullable=True))

    op.add_column('consultations', sa.Column('motif_detail', sa.Text(), nullable=True))
    op.add_column(
        'consultations',
        sa.Column(
            'type_motif',
            postgresql.ENUM(
                'DOULEUR', 'CONTROLE', 'URGENCE', 'ESTHETIQUE', 'SUIVI', 'PROTHESE', 'ORTHODONTIE', 'AUTRE',
                name='motifconsultationenum',
            ),
            nullable=False,
            server_default='AUTRE',
        ),
    )
    op.add_column('consultations', sa.Column('examen_exobuccal', sa.Text(), nullable=True))
    op.add_column('consultations', sa.Column('diagnostics_differentiels', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('consultations', sa.Column('codes_cim10', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('consultations', sa.Column('recommandations', sa.Text(), nullable=True))
    op.add_column('consultations', sa.Column('prochain_rdv_prevu', sa.Date(), nullable=True))

    op.create_index(op.f('ix_consultations_date_consultation'), 'consultations', ['date_consultation'], unique=False)
    op.create_index(op.f('ix_consultations_dossier_medical_id'), 'consultations', ['dossier_medical_id'], unique=False)
    op.create_index(op.f('ix_consultations_praticien_id'), 'consultations', ['praticien_id'], unique=False)
    op.create_index(op.f('ix_consultations_statut'), 'consultations', ['statut'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_consultations_statut'), table_name='consultations')
    op.drop_index(op.f('ix_consultations_praticien_id'), table_name='consultations')
    op.drop_index(op.f('ix_consultations_dossier_medical_id'), table_name='consultations')
    op.drop_index(op.f('ix_consultations_date_consultation'), table_name='consultations')
    op.drop_column('consultations', 'prochain_rdv_prevu')
    op.drop_column('consultations', 'recommandations')
    op.drop_column('consultations', 'codes_cim10')
    op.drop_column('consultations', 'diagnostics_differentiels')
    op.drop_column('consultations', 'examen_exobuccal')
    op.drop_column('consultations', 'type_motif')
    op.drop_column('consultations', 'motif_detail')
    op.drop_column('actes_realises', 'description')
    op.drop_index(op.f('ix_actes_nomenclature_categorie'), table_name='actes_nomenclature')
    op.drop_column('actes_nomenclature', 'unitaire')
    postgresql.ENUM(name='motifconsultationenum').drop(op.get_bind(), checkfirst=True)
