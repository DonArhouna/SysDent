"""security_sprint_0bis_tenant

Revision ID: 3d0a79ee3880
Revises: acaeddf74a3e
Create Date: 2026-10-01 21:05:41.801706

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d0a79ee3880'
down_revision: Union[str, None] = 'acaeddf74a3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_permissions_action'), 'permissions', ['action'], unique=False)
    op.create_index(op.f('ix_permissions_module'), 'permissions', ['module'], unique=False)

    # `jti` devient NOT NULL : on le crée nullable, on remplit les sessions
    # existantes avec une valeur unique dérivée de leur refresh_token (quitte à
    # invalider ces sessions,Contrainte bien plus sûre que de laisser la colonne
    # vide), puis on pose la contrainte.
    op.add_column('sessions_utilisateurs', sa.Column('jti', sa.String(length=64), nullable=True))
    op.add_column(
        'sessions_utilisateurs',
        sa.Column('derniere_activite', sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill : une session sans identifiant exploitable ne peut pas être
    # tournée. On la marque révoquée et on lui attribue un jti dérivé de son
    # refresh_token, ce qui évite toute violation de contrainte unique.
    op.execute(
        """
        UPDATE sessions_utilisateurs
        SET jti = 'legacy_' || substring(md5(refresh_token) from 1 for 40),
            derniere_activite = COALESCE(updated_at, NOW()),
            est_revoque = TRUE
        WHERE jti IS NULL
        """
    )

    op.alter_column(
        'sessions_utilisateurs',
        'jti',
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        'sessions_utilisateurs',
        'derniere_activite',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.create_index(op.f('ix_sessions_utilisateurs_jti'), 'sessions_utilisateurs', ['jti'], unique=True)
    op.create_index(
        op.f('ix_sessions_utilisateurs_utilisateur_id'),
        'sessions_utilisateurs',
        ['utilisateur_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_sessions_utilisateurs_utilisateur_id'), table_name='sessions_utilisateurs')
    op.drop_index(op.f('ix_sessions_utilisateurs_jti'), table_name='sessions_utilisateurs')
    op.drop_column('sessions_utilisateurs', 'derniere_activite')
    op.drop_column('sessions_utilisateurs', 'jti')
    op.drop_index(op.f('ix_permissions_module'), table_name='permissions')
    op.drop_index(op.f('ix_permissions_action'), table_name='permissions')
