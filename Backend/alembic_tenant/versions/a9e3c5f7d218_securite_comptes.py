"""Sécurité des comptes : activation par lien, mot de passe à changer, 2FA

Revision ID: a9e3c5f7d218
Revises: c8b2e5f1a73d
Create Date: 2026-10-14 16:00:00.000000

- `activation_requise` : compte créé par invitation, dont le titulaire n'a pas
  encore choisi son mot de passe. La connexion est refusée tant qu'il est vrai.
- `doit_changer_mot_de_passe` : mot de passe temporaire (réinitialisation,
  création par un tiers) ; la connexion passe d'abord par son changement.
- 2FA : secret préparé (jamais actif tant qu'il n'est pas confirmé), date de
  confirmation, codes de secours hachés. `secret_2fa` passe en TEXT : un secret
  chiffré (Fernet) dépasse les 100 caractères de la colonne d'origine.
- `jetons_auth` : jetons à usage unique (activation, étapes de connexion, codes
  e-mail), **hachés** : une lecture de la base ne permet ni d'activer un compte
  ni de franchir une étape de connexion.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9e3c5f7d218"
down_revision: Union[str, None] = "c8b2e5f1a73d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("utilisateurs", sa.Column("activation_requise", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("utilisateurs", sa.Column("doit_changer_mot_de_passe", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("utilisateurs", sa.Column("secret_2fa_en_attente", sa.Text(), nullable=True))
    op.add_column("utilisateurs", sa.Column("deux_facteurs_confirme_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("utilisateurs", sa.Column("codes_secours_haches", postgresql.JSONB(), nullable=True))
    op.alter_column("utilisateurs", "secret_2fa", type_=sa.Text(), existing_type=sa.String(length=100), existing_nullable=True)

    op.create_table(
        "jetons_auth",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("utilisateur_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usage", sa.String(length=30), nullable=False),
        sa.Column("hash_jeton", sa.String(length=64), nullable=False, unique=True),
        sa.Column("contexte", sa.String(length=64), nullable=True),
        sa.Column("expire_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilise", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jetons_auth_utilisateur_usage", "jetons_auth", ["utilisateur_id", "usage"])


def downgrade() -> None:
    op.drop_index("ix_jetons_auth_utilisateur_usage", table_name="jetons_auth")
    op.drop_table("jetons_auth")
    op.alter_column("utilisateurs", "secret_2fa", type_=sa.String(length=100), existing_type=sa.Text(), existing_nullable=True)
    for colonne in ("codes_secours_haches", "deux_facteurs_confirme_at", "secret_2fa_en_attente", "doit_changer_mot_de_passe", "activation_requise"):
        op.drop_column("utilisateurs", colonne)
