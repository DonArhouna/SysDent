"""Catalogue : `ASSURANCE:WRITE` devient `ASSURANCE:WRITE_PATIENT`.

Les permissions vivent en base (`permissions`, `permission_roles`). Un cabinet
provisionne **avant** cette version porte donc `ASSURANCE:WRITE` dans ses lignes
et n'a jamais entendu parler de `WRITE_PATIENT` : sans cette migration, ses
roles non-administrateur n'auraient aucun droit d'ecriture, et le secretariat ne
pourrait plus saisir une carte de mutuelle a l'accueil.

Quatre operations, dans cet ordre :

1. **`ASSURANCE:WRITE_PATIENT` est ajoutee.**
2. **Les liens sont reportes** sur le nouveau droit, role par role.
3. **Les liens de l'ancien droit sont supprimes**, puis l'ancien droit.
4. Rien d'autre n'est touche : ni `tarif_base`, ni les tarifs d'un acte. Cette
   migration ne parle que du RBAC.

L'ordre compte. Supprimer avant d'ajouter laisserait le secretariat sans aucun
droit entre les deux operations, et une migration interrompue a mi-parcours
laisse une base a moitie migree - le pire des etats, parce qu'elle parait
fonctionnelle.

**Deux details qui ne sont pas negociables.**

`permission_roles` n'a **pas** de contrainte d'unicite sur
`(role_id, permission_id)`. Un `ON CONFLICT DO NOTHING` ne s'y appuierait sur
rien : la migration serait rejouable, et chaque rejeu **dupliquerait** un lien.
Les gardes sont donc des `WHERE NOT EXISTS`, explicites et verifiables.

`permission_id` est une cle etrangere **sans** `ON DELETE CASCADE` - contrairement
a `role_id`. Supprimer le droit avant ses liens echouerait. D'ou l'etape 3, qui
supprime les liens d'abord.

Revision ID: c4e7a2b6d9f1
Revises: b3d7f1a9c2e4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e7a2b6d9f1"
down_revision: Union[str, None] = "b3d7f1a9c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Ancien droit et nouveau. Les deux sont nommes explicitement : une migration
#: qui laisse un droit mort en base laisse une illusion de securite.
ANCIEN_MODULE = "ASSURANCE"
ANCIEN_ACTION = "WRITE"
NOUVEAU_MODULE = "ASSURANCE"
NOUVEAU_ACTION = "WRITE_PATIENT"

#: Roles qui portaient l'ancien droit et qui doivent porter le nouveau. Liste
#: figee, et non lue depuis `MATRICE_ROLES` : une migration doit produire le
#: meme resultat dans deux ans, quand la matrice aura evolue.
ROLES_A_REPORTER = ("SECRETAIRE",)

#: `scope` est `NOT NULL` sans valeur par defaut cote base : un INSERT brut doit
#: donc le fournir, sinon la migration echoue sur une contrainte qu'aucune
#: lecture du modele ne montre.
SCOPE = "CABINET_LOCAL"


def _conditions_roles(suffixe: str) -> str:
    """Un `IN (...)` litteral : les placeholders sont sur la liste figee."""
    valeurs = ", ".join(f":role_{i}{suffixe}" for i in range(len(ROLES_A_REPORTER)))
    return valeurs


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            INSERT INTO permissions (id, module, action, description)
            SELECT gen_random_uuid(), :module, :action,
                   'Declarer le droit de prise en charge d''un patient'
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE module = :module AND action = :action
            )
            """
        ).bindparams(module=NOUVEAU_MODULE, action=NOUVEAU_ACTION)
    )

    parametres_roles = {f"role_{i}": nom for i, nom in enumerate(ROLES_A_REPORTER)}
    op.execute(
        sa.text(
            f"""
            INSERT INTO permission_roles (id, role_id, permission_id, scope)
            SELECT gen_random_uuid(), r.id, nouveau.id, :scope
            FROM roles r
            JOIN permissions nouveau
              ON nouveau.module = :module AND nouveau.action = :action
            WHERE r.nom IN ({_conditions_roles("")})
              AND EXISTS (
                    SELECT 1 FROM permission_roles pr
                    JOIN permissions ancien ON ancien.id = pr.permission_id
                    WHERE pr.role_id = r.id
                      AND ancien.module = :ancien_module
                      AND ancien.action = :ancien_action
              )
              AND NOT EXISTS (
                    SELECT 1 FROM permission_roles pr
                    WHERE pr.role_id = r.id AND pr.permission_id = nouveau.id
              )
            """
        ).bindparams(
            module=NOUVEAU_MODULE,
            action=NOUVEAU_ACTION,
            ancien_module=ANCIEN_MODULE,
            ancien_action=ANCIEN_ACTION,
            scope=SCOPE,
            **parametres_roles,
        )
    )

    # Les liens d'abord : `permission_roles.permission_id` n'a pas de CASCADE.
    op.execute(
        sa.text(
            """
            DELETE FROM permission_roles
            WHERE permission_id IN (
                SELECT id FROM permissions
                WHERE module = :module AND action = :action
            )
            """
        ).bindparams(module=ANCIEN_MODULE, action=ANCIEN_ACTION)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM permissions WHERE module = :module AND action = :action
            """
        ).bindparams(module=ANCIEN_MODULE, action=ANCIEN_ACTION)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO permissions (id, module, action, description)
            SELECT gen_random_uuid(), :module, :action,
                   'Permission WRITE sur le module ASSURANCE'
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE module = :module AND action = :action
            )
            """
        ).bindparams(module=ANCIEN_MODULE, action=ANCIEN_ACTION)
    )

    parametres_roles = {f"role_{i}": nom for i, nom in enumerate(ROLES_A_REPORTER)}
    op.execute(
        sa.text(
            f"""
            INSERT INTO permission_roles (id, role_id, permission_id, scope)
            SELECT gen_random_uuid(), r.id, ancien.id, :scope
            FROM roles r
            JOIN permissions ancien
              ON ancien.module = :module AND ancien.action = :action
            WHERE r.nom IN ({_conditions_roles("")})
              AND NOT EXISTS (
                    SELECT 1 FROM permission_roles pr
                    WHERE pr.role_id = r.id AND pr.permission_id = ancien.id
              )
            """
        ).bindparams(module=ANCIEN_MODULE, action=ANCIEN_ACTION, scope=SCOPE, **parametres_roles)
    )

    op.execute(
        sa.text(
            """
            DELETE FROM permission_roles
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE module = :module AND action = :action
            )
            """
        ).bindparams(module=NOUVEAU_MODULE, action=NOUVEAU_ACTION)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM permissions WHERE module = :module AND action = :action
            """
        ).bindparams(module=NOUVEAU_MODULE, action=NOUVEAU_ACTION)
    )