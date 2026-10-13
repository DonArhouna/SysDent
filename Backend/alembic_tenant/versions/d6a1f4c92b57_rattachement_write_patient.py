"""Correction : rattacher `ASSURANCE:WRITE_PATIENT` au secretariat.

**Le trou.** `c4e7a2b6d9f1` cree `ASSURANCE:WRITE_PATIENT` et reporte le lien
depuis l'ancien `ASSURANCE:WRITE`, mais **seulement si le lien existait deja** :
le report est conditionne par un `EXISTS` sur l'ancien droit. Un cabinet dont le
catalogue n'avait jamais ete seme - donc qui n'avait aucun droit `ASSURANCE` -
se voit creer la permission sans le lien. L'accueil ne peut alors pas enregistrer
le droit d'un patient, alors que la matrice validée le lui accorde.

`f1a7c3d90b28` ne comble pas le trou : elle sème `TARIFS` et `ASSURANCE:READ`,
et laisse `ASSURANCE:WRITE_PATIENT` a `c4e7a2b6d9f1`. Elle est donc gelée, et
corrigee par une revision distincte.

**La permission doit deja exister.** Cette revision ne seme rien : si
`ASSURANCE:WRITE_PATIENT` est absente, elle echoue avec un message clair. Semer
silencieusement une permission dont personne n'a decide qu'elle existe
transformerait une faute de sequence en etat accepte.

**Le downgrade ne retire que ce qu'il a ajoute.** Un lien de role peut avoir ete
cree ici ou etre deja present. Sans trace, un `downgrade` supprimerait le lien
d'origine d'un cabinet qui l'avait deja, ce qui n'est pas un retour arriere mais
une perte. Une table de provenance enregistre donc chaque lien cree, et le
`downgrade` ne supprime que ceux-la. La table disparait avec elle.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6a1f4c92b57"
down_revision: Union[str, None] = "f1a7c3d90b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Cible du rattachement, figee comme la matrice l'a arretee.
MODULE = "ASSURANCE"
ACTION = "WRITE_PATIENT"

#: Role concerne. Fige, non lu depuis `MATRICE_ROLES` : une migration doit
#: produire le meme resultat dans deux ans.
ROLE = "SECRETAIRE"

#: `scope` est `NOT NULL` sans valeur par defaut cote base.
SCOPE = "CABINET_LOCAL"

#: Table de provenance. Elle ne sert qu'a distinguer un lien cree ici d'un
#: lien deja present : sans elle, le downgrade ne peut pas faire la difference,
#: et le retour arriere devient une perte de donnee.
PROVENANCE = "permission_roles_provenance"


def _exiger(liaison, requete: str, parametres: dict, message: str) -> None:
    """Leve si la requete ne ramene rien. L echec annule la transaction.

    Le controle est fait avant toute ecriture : une migration qui echoue apres
    avoir pose sa table de provenance laisse un etat partiel que le downgrade
    ne rattraperait pas puisque la revision serait encore marquee appliquee.
    """
    if liaison.execute(sa.text(requete), parametres).first() is None:
        raise RuntimeError(message)


def upgrade() -> None:
    op.create_table(
        PROVENANCE,
        sa.Column("revision", sa.String(length=32), nullable=False),
        sa.Column("role_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "permission_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_permission_roles_provenance_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_permission_roles_provenance_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "revision", "role_id", "permission_id", name=op.f("pk_permission_roles_provenance")
        ),
    )

    # Les deux controles qui suivent sont faits en Python, et non par un bloc
    # `DO`. Un bloc `DO` est une instruction utilitaire : PostgreSQL n'accepte
    # aucune borne sur une requete, et la premiere version de cette migration
    # y liait le nom du role. L'erreur qui en sortait parlait de "0 argument
    # attendu, 1 passe", sans dire du role ni de la permission.

    # Le secretariat doit exister : un role manquant passerait silencieusement,
    # et la migration serait annoncee reussie alors qu elle n aurait rien fait.
    _exiger(
        op.get_bind(),
        "SELECT 1 FROM roles WHERE nom = :valeur",
        {"valeur": ROLE},
        f"role {ROLE} introuvable : le catalogue des roles du cabinet est incomplet",
    )

    # La permission doit deja exister : cette revision ne seme rien. Semer
    # silencieusement une permission dont personne n'a decide qu'elle existe
    # transformerait une faute de sequence en etat accepte.
    _exiger(
        op.get_bind(),
        "SELECT 1 FROM permissions WHERE module = :module AND action = :action",
        {"module": MODULE, "action": ACTION},
        f"permission {MODULE}:{ACTION} introuvable : "
        "appliquer c4e7a2b6d9f1 avant cette revision",
    )

    # Le lien, avec sa trace. Le `NOT EXISTS` sur le couple rend l'operation
    # idempotente, et c'est lui qui decide si la provenance est ecrite.
    op.execute(
        sa.text("""
            WITH nouveau AS (
                SELECT gen_random_uuid() AS id, r.id AS role_id, p.id AS permission_id
                FROM roles r
                JOIN permissions p
                  ON p.module = :module AND p.action = :action
                WHERE r.nom = :role
                  AND NOT EXISTS (
                        SELECT 1 FROM permission_roles pr
                        WHERE pr.role_id = r.id AND pr.permission_id = p.id
                  )
            ), insere AS (
                INSERT INTO permission_roles (id, role_id, permission_id, scope)
                SELECT id, role_id, permission_id, :scope FROM nouveau
                RETURNING role_id, permission_id
            )
            INSERT INTO permission_roles_provenance (revision, role_id, permission_id)
            SELECT :revision, role_id, permission_id FROM insere
        """).bindparams(module=MODULE, action=ACTION, role=ROLE, scope=SCOPE, revision=revision)
    )


def downgrade() -> None:
    # Seuls les liens traces ici. Un lien deja present avant cette revision
    # n'est pas dans la table, donc n'est pas retire.
    op.execute(
        sa.text(f"""
            DELETE FROM permission_roles
            WHERE (role_id, permission_id) IN (
                SELECT role_id, permission_id FROM {PROVENANCE}
                WHERE revision = :revision
            )
        """).bindparams(revision=revision)
    )
    op.drop_table(PROVENANCE)