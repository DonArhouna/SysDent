"""Enrôlement 2FA avant session complète, et codes de secours.

**Pourquoi cette migration.** La 2FA est obligatoire sur la plateforme, mais sa
seule voie d'activation exige une session déjà ouverte. La connexion renvoie donc
`DEUX_FACTEURS_NON_ACTIVE` et l'enrôlement est inatteignable : sur une
plateforme à un seul Super Admin, il n'existe aucune sortie. Le secret TOTP
n'ayant jamais été connu, le compte est bloqué.

Le correctif est dans le flux (voir `services/auth.py`) : quand les identifiants
sont justes mais que la 2FA n'est pas active, la connexion émet un **jeton
d'enrôlement** à portée limitée au lieu de refuser. Cette migration lui ouvre les
colonnes dont il a besoin.

**Trois ajouts, tous réversibles :**

1. `usage_jeton.ENROLEMENT_2FA` — un jeton opaque, usage unique, dix minutes,
   qui n'ouvre que la préparation et l'activation. Sans lui, il faudrait
   distinguer le challenge « je connais mon code » de « je n'ai pas encore de
   secret », ce que l'existant ne sait pas faire.
2. `changement_mot_de_passe_obligatoire` — l'opérateur réinitialise un mot de
   passe qu'il n'a pas choisi ; le mot de passe connu de l'opérateur ne doit pas
   devenir un mot de passe durable.
3. `codes_secours_haches` — les codes de secours remplacent le code TOTP quand le
   téléphone n'est pas là. Ils sont **hachés**, comme les mots de passe : une
   lecture de la base ne doit pas permettre de se connecter à la place du
   propriétaire.

Revision ID: a3e7d1b95c24
Revises: b92f0e5c17d4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3e7d1b95c24"
down_revision: Union[str, None] = "b92f0e5c17d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Un usage de jeton de plus. `IF NOT EXISTS` rend la migration rejouable :
    #    une reprise après échec ne doit pas échouer sur ce point.
    op.execute("ALTER TYPE usage_jeton ADD VALUE IF NOT EXISTS 'ENROLEMENT_2FA'")

    # 2. Mot de passe à changer obligatoirement à la prochaine connexion.
    op.execute(
        """
        ALTER TABLE utilisateurs_plateforme
            ADD COLUMN IF NOT EXISTS changement_mot_de_passe_obligatoire
            BOOLEAN NOT NULL DEFAULT false
        """
    )

    # 3. Codes de secours HACHÉS. Jamais en clair : un vidage de la base ne doit
    #    pas rendre la plateforme accessible.
    op.execute(
        """
        ALTER TABLE utilisateurs_plateforme
            ADD COLUMN IF NOT EXISTS codes_secours_haches JSONB
        """
    )

    # Un compte ne peut pas avoir de codes de secours sans 2FA active : l'inverse
    # laisserait des codes orphelins impossibles à consommer.
    op.execute(
        """
        ALTER TABLE utilisateurs_plateforme
            ADD CONSTRAINT ck_codes_secours_exigent_2fa
            CHECK (codes_secours_haches IS NULL OR deux_facteurs_actif = true)
        """
    )


def downgrade() -> None:
    # La valeur d'énumération ne se retire pas en PostgreSQL avant la v12 de
    # manière transactionnelle ; et retirer une colonne de codes de secours
    # effacerait des codes encore valides. La réversibilité est donc
    # **logique** : on neutralise l'usage et on supprime les colonnes, la valeur
    # d'énumération restante étant inoffensive (aucune ligne ne la porte).
    op.execute("ALTER TABLE utilisateurs_plateforme DROP CONSTRAINT IF EXISTS ck_codes_secours_exigent_2fa")
    op.execute("ALTER TABLE utilisateurs_plateforme DROP COLUMN IF EXISTS codes_secours_haches")
    op.execute("ALTER TABLE utilisateurs_plateforme DROP COLUMN IF EXISTS changement_mot_de_passe_obligatoire")