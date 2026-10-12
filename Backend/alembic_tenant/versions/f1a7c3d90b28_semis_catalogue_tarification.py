"""Catalogue : semer les permissions de tarification et de lecture assurance.

**Pourquoi une revision.** Les permissions vivent en base, et `GET
/rbac/permissions` lit cette table : l'ecran Roles et Permissions rend donc
exactement ce qui existe. `RbacService.semer_permissions()` sait semer le
catalogue et est idempotent, mais il n'est appele que par `bootstrap_complet()`,
donc au seul provisionnement d'un cabinet. Un cabinet provisionne avant la
phase tarification ne recoit jamais ces lignes, et son administrateur ne peut
pas attribuer des droits que le serveur exige deja.

**Ce que porte cette revision.** Trois permissions absentes de tout cabinet
existant, plus les liens de la matrice. `ASSURANCE:WRITE_PATIENT` n'est pas ici :
`c4e7a2b6d9f1` l'a deja semee, et la dupliquer serait une deuxieme source de
verite.

**Placement.** Cette revision enchaine apres `c4e7a2b6d9f1`, qui enchaine
apres `b3d7f1a9c2e4`. La poser directement sur `b3d7f1a9c2e4` creerait une
branche : deux tetes dans la chaine tenant, et donc un `upgrade head` dont la
cible ne serait plus deterministe. Une chaine a une seule tete, ou rien.

**Idempotence.** `WHERE NOT EXISTS` sur la permission, puis sur chaque lien.
`ON CONFLICT` est exclu : `permission_roles` n'a aucune contrainte d'unicite,
donc `ON CONFLICT` n'y aurait rien astituer et laisserait passer le doublon.

**Reversibilite.** `downgrade` retire les liens, puis les permissions, dans cet
ordre : `permission_roles.permission_id` reference `permissions.id`, et l'ordre
inverse echouerait sur la cle etrangere.

**Listes figees.** Les roles sont nommes explicitement, et non lus depuis
`MATRICE_ROLES` : une migration doit produire le meme resultat dans deux ans,
quand la matrice aura evolue. Changer la matrice ne doit pas reecrire le passe.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a7c3d90b28"
down_revision: Union[str, None] = "c4e7a2b6d9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: `scope` est `NOT NULL` sans valeur par defaut cote base : un INSERT brut doit
#: donc le fournir, sinon la migration echoue sur une contrainte qu'aucune
#: lecture du modele ne montre.
SCOPE = "CABINET_LOCAL"

#: Les trois permissions semees, avec leur libelle affiche dans l'ecran.
PERMISSIONS_A_SEMER = (
    ("TARIFS", "READ", "Consulter la tarification et les tarifs d'un acte"),
    ("TARIFS", "WRITE", "Definir les tarifs d'un acte et les organismes d'assurance"),
    ("ASSURANCE", "READ", "Consulter les organismes et les droits de prise en charge"),
)

#: Roles qui portent chaque permission, au 12/10.
#:
#: `TARIFS:READ` : tous les roles. Le praticien doit voir le prix d'un acte pour
#: le facturer et l'expliquer ; le comptable facture au tarif applique ; le
#: magasinier commande au prix du cabinet ; l'accueil saisit le prix du ticket.
#:
#: `TARIFS:WRITE` : `ADMIN_CABINET` seul. Un tarif se decide au cabinet.
#:
#: `ASSURANCE:READ` : tous les roles sauf `GESTIONNAIRE_STOCK`, qui n'a besoin
#: ni du taux d'un organisme ni des droits d'un patient pour commander.
ROLES_TARIFS_READ = (
    "ADMIN_CABINET",
    "PRATICIEN",
    "ASSISTANT",
    "SECRETAIRE",
    "COMPTABLE",
    "GESTIONNAIRE_STOCK",
)
ROLES_TARIFS_WRITE = ("ADMIN_CABINET",)
ROLES_ASSURANCE_READ = (
    "ADMIN_CABINET",
    "PRATICIEN",
    "ASSISTANT",
    "SECRETAIRE",
    "COMPTABLE",
)

LIENS_A_POSER = (
    ("TARIFS", "READ", ROLES_TARIFS_READ),
    ("TARIFS", "WRITE", ROLES_TARIFS_WRITE),
    ("ASSURANCE", "READ", ROLES_ASSURANCE_READ),
)


def _in_litteral(prefixe: str, valeurs: Sequence[str]) -> str:
    """Un `IN (...)` litteral : les placeholders portent la liste figee."""
    return ", ".join(f":{prefixe}{i}" for i in range(len(valeurs)))


def _parametres_roles(prefixe: str, valeurs: Sequence[str]) -> dict[str, str]:
    return {f"{prefixe}{i}": nom for i, nom in enumerate(valeurs)}


def upgrade() -> None:
    for module, action, description in PERMISSIONS_A_SEMER:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, module, action, description)
                SELECT gen_random_uuid(), :module, :action, :description
                WHERE NOT EXISTS (
                    SELECT 1 FROM permissions WHERE module = :module AND action = :action
                )
                """
            ).bindparams(module=module, action=action, description=description)
        )

    for module, action, roles in LIENS_A_POSER:
        op.execute(
            sa.text(
                f"""
                INSERT INTO permission_roles (id, role_id, permission_id, scope)
                SELECT gen_random_uuid(), r.id, p.id, :scope
                FROM roles r
                JOIN permissions p
                  ON p.module = :module AND p.action = :action
                WHERE r.nom IN ({_in_litteral("role_", roles)})
                  AND NOT EXISTS (
                        SELECT 1 FROM permission_roles pr
                        WHERE pr.role_id = r.id AND pr.permission_id = p.id
                  )
                """
            ).bindparams(
                module=module,
                action=action,
                scope=SCOPE,
                **_parametres_roles("role_", roles),
            )
        )


def downgrade() -> None:
    # Les liens d'abord : `permission_roles.permission_id` n'a pas de CASCADE.
    for module, action, _roles in LIENS_A_POSER:
        op.execute(
            sa.text(
                """
                DELETE FROM permission_roles
                WHERE permission_id IN (
                    SELECT id FROM permissions
                    WHERE module = :module AND action = :action
                )
                """
            ).bindparams(module=module, action=action)
        )

    for module, action, _description in PERMISSIONS_A_SEMER:
        op.execute(
            sa.text(
                """
                DELETE FROM permissions
                WHERE module = :module AND action = :action
                """
            ).bindparams(module=module, action=action)
        )