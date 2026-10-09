"""Separation du secret prepare et du secret actif, et regeneration des codes.

**Le defaut que cette migration corrige.** `/2fa/preparation` ecrivait le secret
TOTP directement dans `secret_2fa_chiffre` — le secret ACTIF. Au login suivant,
le backend testait « un secret existe ? » et emettait un defi ; la saisie du
code sur ce defi activait la 2FA **sans emettre de codes de secours**. Deux
voies d activation, une seule emettant les codes : un telephone perdu ne
laissait plus aucune voie de recours.

**Trois ajouts :**

1. `secret_2fa_en_attente` — la preparation n ecrit QUE la, et la colonne est
   ecrasee a chaque preparation. Un secret prepare n a jamais ete scanne : il ne
   doit pouvoir activer personne. L activation le PROMOUT dans
   `secret_2fa_chiffre` et le vide.
2. `codes_secours_a_regenerer` — indicateur expose dans `/platform/auth/me`.
   Vrai sur un compte dont la 2FA est active mais qui n a PAS de codes de
   secours : c est exactement la situation du Super Admin actuel. La banniere
   du backoffice le guide vers la regeneration.
3. Contrainte `CHECK` **tolerante** : `deux_facteurs_actif` exige des codes de
   secours OU le drapeau de regeneration. Tolerante parce que les comptes
   existants sont backfills avec le drapeau avant l ajout : aucun compte actif
   n est casse, mais tout NOUVEAU compte actif doit avoir ses codes — l invariant
   « 2FA active implique un recours » devient impossible a violer a l'ecriture.

Tout est reversibil : le downgrade retire le drapeau et les colonnes, sans
toucher au secret actif ni aux sessions. Un secret en attente perdu est sans
effet de bord — il etait ephemere par nature.

Revision ID: f2c9e5d7a3b1
Revises: a3e7d1b95c24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f2c9e5d7a3b1"
down_revision: Union[str, None] = "a3e7d1b95c24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Colonne du secret PREPARE, jamais utilise pour authentifier.
    op.execute(
        """
        ALTER TABLE utilisateurs_plateforme
            ADD COLUMN IF NOT EXISTS secret_2fa_en_attente TEXT
        """
    )

    # 2. Indicateur de regeneration des codes de secours.
    op.execute(
        """
        ALTER TABLE utilisateurs_plateforme
            ADD COLUMN IF NOT EXISTS codes_secours_a_regenerer
            BOOLEAN NOT NULL DEFAULT false
        """
    )

    # 3. Backfill AVANT la contrainte : tout compte actif sans codes de secours
    #    est signale pour regeneration. Sans ce passage, l'ajout du CHECK
    #    echouerait sur les comptes existants — dont le Super Admin actif, qui
    #    n'a aucun code. Le backfill le preserve exactement : 2FA conservee,
    #    secret actif intact, sessions intactes.
    op.execute(
        """
        UPDATE utilisateurs_plateforme
        SET codes_secours_a_regenerer = true
        WHERE deux_facteurs_actif = true
          AND (codes_secours_haches IS NULL OR codes_secours_haches = '[]'::jsonb)
        """
    )

    # 4. L'invariant, tolerante : actif implique des codes OU un drapeau de
    #    regeneration. `IF NOT EXISTS` (via pg_constraint) rend la migration
    #    rejouable apres un echec partiel.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_2fa_active_exige_secours'
                  AND conrelid = 'utilisateurs_plateforme'::regclass
            ) THEN
                ALTER TABLE utilisateurs_plateforme
                    ADD CONSTRAINT ck_2fa_active_exige_secours
                    CHECK (
                        deux_facteurs_actif = false
                        OR codes_secours_haches IS NOT NULL
                        OR codes_secours_a_regenerer = true
                    );
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    # La valeur d'information (quel compte doit regenerer) et le secret en
    # attente sont perdus : c'est la logique du downgrade, comme pour
    # `a3e7d1b95c24`. Le secret ACTIF, les sessions et les codes de secours
    # existants ne sont pas touches.
    op.execute(
        "ALTER TABLE utilisateurs_plateforme DROP CONSTRAINT IF EXISTS ck_2fa_active_exige_secours"
    )
    op.execute(
        "ALTER TABLE utilisateurs_plateforme DROP COLUMN IF EXISTS codes_secours_a_regenerer"
    )
    op.execute(
        "ALTER TABLE utilisateurs_plateforme DROP COLUMN IF EXISTS secret_2fa_en_attente"
    )
