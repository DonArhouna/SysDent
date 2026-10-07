"""usage_jeton : ajouter CHALLENGE_2FA

Revision ID: b92f0e5c17d4
Revises: a41d7c93e2b6
Create Date: 2026-10-04 21:15:00.000000

Le défi 2FA (jeton opaque de 5 minutes émis entre la vérification du mot de passe
et la saisie du code TOTP) réutilise la table `jetons_usage_unique` : même
propriétés que les jetons de vérification e-mail — opaque, haché, à usage unique,
à durée limitée. Ajouter une table entière pour un usage de plus aurait dupliqué
un modèle déjà correct ; ajouter une valeur d'énumération suffit.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b92f0e5c17d4'
down_revision: Union[str, None] = 'a41d7c93e2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `IF NOT EXISTS` : sur une base déjà mise à jour à la main, la migration
    # reste idempotente au lieu de faire échouer le déploiement.
    op.execute("ALTER TYPE usage_jeton ADD VALUE IF NOT EXISTS 'CHALLENGE_2FA'")


def downgrade() -> None:
    # PostgreSQL ne permet pas de retirer une valeur d'énumération. La
    # réversibilité est donc « la valeur reste, inoffensive » : aucun code ne la
    # produit si la fonctionnalité est désactivée. Retirer la valeur exigerait
    # une reconstruction de la table, ce qui, sur un journal d'usage, coûterait
    # plus cher que l'inconvénient.
    op.execute("COMMENT ON TYPE usage_jeton IS 'valeur CHALLENGE_2FA ajoutee par b92f0e5c17d4, non retirable en PostgreSQL'")