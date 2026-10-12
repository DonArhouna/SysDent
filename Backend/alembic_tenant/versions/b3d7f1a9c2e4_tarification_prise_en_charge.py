"""Tarification par cabinet et prise en charge (CDC 5.6 et 5.7).

Ce que cette migration ajoute, et pourquoi c'est quatre tables et non une
colonne de plus sur `actes_nomenclature`.

**5.6 - tarifs parametrables par cabinet.** `actes_nomenclature.tarif_base`
porte un montant unique par acte. Le cahier des charges demande des tarifs
parametrables : le meme acte ne coute pas la meme chose selon la situation du
patient. Un cabinet doit donc pouvoir definir ses propres categories tarifaires
(`categories_patient`) et le prix d'un acte pour chacune (`tarifs_actes`). La
categorie `standard` existe pour tout cabinet et porte le tarif de reference,
pour qu'un acte reste toujours tarifable sans configuration prealable.

**5.7 - prise en charge.** Assurance et mutuelle ont exactement les memes donnees
- un organisme, un numero de police, un taux, une priorite. Les modeler
separement obligerait a dupliquer le schema et les regles pour une difference
qui n'est qu'un libelle. `type_organisme` porte donc la difference, et
`droits_prise_en_charge` porte les droits ouverts par un patient, plusieurs par
patient.

**Migration de donnees, et pas seulement de schema.** La colonne `tarif_base`
existe deja et porte le tarif reellement utilise par la facturation en place.
Cette migration la recopie dans `tarifs_actes` sous la categorie `standard`, sans
rien supprimer ni modifier : apres coup, chaque acte a un tarif de reference
repris a l'identique, et la facturation existante continue de lire la colonne
qu'elle lit deja. Un acte cree entre l'ecriture de la migration et son
application n'est pas touche - la recopie se fait au moment de l'application.

**Contraintes portees par la base.** Un taux hors de 0 a 100, un montant
negatif, deux tarifs pour le meme acte et la meme categorie : PostgreSQL refuse,
pas seulement le formulaire. Deux secretaires qui tarifent au meme instant ne
passent pas par le meme code Python.

**Ce que la migration ne fait pas**, et qui reste a faire : la ventilation
assurance / patient d'une facture. `droits_prise_en_charge` enregistre qui
couvre quoi, mais aucune ligne de facture ne ventile encore le montant. C'est
volontaire - hors perimetre de cette migration, et trace dans `docs/PROGRESS.md`.

Revision ID: b3d7f1a9c2e4
Revises: e8b2c4a7d1e5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3d7f1a9c2e4"
down_revision: Union[str, None] = "e8b2c4a7d1e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Code de la categorie de reference. Volontairement une constante partagee avec
#: le service : une divergence entre la migration et le code creerait une
#: categorite que personne ne sait nommer.
CODE_CATEGORIE_STANDARD = "standard"


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Categories de patient
    # -------------------------------------------------------------------------
    op.create_table(
        "categories_patient",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("libelle", sa.String(length=200), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("par_defaut", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories_patient"),
        sa.UniqueConstraint("code", name="uq_categories_patient_code"),
        sa.CheckConstraint("ordre >= 0", name="ck_categories_patient_ordre"),
    )
    op.create_index("ix_categories_patient_code", "categories_patient", ["code"])

    # -------------------------------------------------------------------------
    # Tarifs par acte et par categorie
    # -------------------------------------------------------------------------
    op.create_table(
        "tarifs_actes",
        sa.Column("acte_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("categorie_code", sa.String(length=50), nullable=False),
        sa.Column("montant", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tarifs_actes"),
        sa.ForeignKeyConstraint(
            ["acte_id"],
            ["actes_nomenclature.id"],
            name="fk_tarifs_actes_acte_id_actes_nomenclature",
            ondelete="CASCADE",
        ),
        # Reference au code de categorie, pas a son id : un tarif se saisit par
        # code, et c'est ce code qui apparaitra sur une facture. `RESTRICT` pour
        # qu'une categorie utilisee ne puisse pas disparaitre.
        sa.ForeignKeyConstraint(
            ["categorie_code"],
            ["categories_patient.code"],
            name="fk_tarifs_actes_categorie_code_categories_patient",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("acte_id", "categorie_code", name="uq_tarifs_actes_acte_categorie"),
        sa.CheckConstraint("montant >= 0", name="ck_tarifs_actes_montant_positif"),
    )
    op.create_index("ix_tarifs_actes_categorie_code", "tarifs_actes", ["categorie_code"])
    op.create_index("ix_tarifs_actes_acte_id", "tarifs_actes", ["acte_id"])

    # -------------------------------------------------------------------------
    # Organismes payeurs
    # -------------------------------------------------------------------------
    type_organisme = postgresql.ENUM(
        "ASSURANCE",
        "MUTUELLE",
        name="typeorganismeenum",
        create_type=False,
    )
    type_organisme.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organismes_assurance",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("nom", sa.String(length=200), nullable=False),
        sa.Column(
            "type_organisme",
            postgresql.ENUM("ASSURANCE", "MUTUELLE", name="typeorganismeenum", create_type=False),
            nullable=False,
            server_default="ASSURANCE",
        ),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organismes_assurance"),
        sa.UniqueConstraint("code", name="uq_organismes_assurance_code"),
    )
    op.create_index("ix_organismes_assurance_code", "organismes_assurance", ["code"])

    # -------------------------------------------------------------------------
    # Droits de prise en charge par patient
    # -------------------------------------------------------------------------
    op.create_table(
        "droits_prise_en_charge",
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organisme_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("numero_police", sa.String(length=80), nullable=True),
        sa.Column("taux_prise_en_charge", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("priorite", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_droits_prise_en_charge"),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name="fk_droits_prise_en_charge_patient_id_patients",
            ondelete="CASCADE",
        ),
        # `RESTRICT` et non `CASCADE` : supprimer un organisme ne doit pas effacer
        # silencieusement les droits de tous les patients qui y etaient rattaches.
        # Le comportement voulu est un refus, que l'appelant peut lever
        # explicitement.
        sa.ForeignKeyConstraint(
            ["organisme_id"],
            ["organismes_assurance.id"],
            name="fk_droits_prise_en_charge_organisme_id_organismes_assurance",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "taux_prise_en_charge >= 0 AND taux_prise_en_charge <= 100",
            name="ck_droits_prise_en_charge_taux_dans_0_100",
        ),
        sa.CheckConstraint("priorite >= 1", name="ck_droits_prise_en_charge_priorite"),
    )
    op.create_index(
        "ix_droits_prise_en_charge_patient_id", "droits_prise_en_charge", ["patient_id"]
    )

    # -------------------------------------------------------------------------
    # Donnees : la categorie de reference, puis la reprise de `tarif_base`.
    # -------------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO categories_patient (id, code, libelle, ordre, par_defaut, created_at, updated_at)
            VALUES (gen_random_uuid(), :code, :libelle, 0, true, now(), now())
            """
        ).bindparams(
            code=CODE_CATEGORIE_STANDARD,
            libelle="Tarif standard",
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO tarifs_actes (id, acte_id, categorie_code, montant, created_at, updated_at)
            SELECT gen_random_uuid(), a.id, :code, a.tarif_base, now(), now()
            FROM actes_nomenclature a
            ON CONFLICT (acte_id, categorie_code) DO NOTHING
            """
        ).bindparams(code=CODE_CATEGORIE_STANDARD)
    )


def downgrade() -> None:
    op.drop_index("ix_droits_prise_en_charge_patient_id", table_name="droits_prise_en_charge")
    op.drop_table("droits_prise_en_charge")

    op.drop_index("ix_organismes_assurance_code", table_name="organismes_assurance")
    op.drop_table("organismes_assurance")
    # `op.drop_table` ne supprime pas le type enum cree par `create_table`.
    postgresql.ENUM(name="typeorganismeenum").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_tarifs_actes_acte_id", table_name="tarifs_actes")
    op.drop_index("ix_tarifs_actes_categorie_code", table_name="tarifs_actes")
    op.drop_table("tarifs_actes")

    op.drop_index("ix_categories_patient_code", table_name="categories_patient")
    op.drop_table("categories_patient")

    # `actes_nomenclature.tarif_base` n'a jamais ete touche : c'est la reprise
    # qui est faite dans la colonne nouvelle, pas une deplacement. Le downgrade
    # supprime donc la copie sans avoir rien a restaurer.