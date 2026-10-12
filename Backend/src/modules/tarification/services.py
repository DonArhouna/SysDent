"""
Regles metier de la tarification et de la prise en charge (CDC 5.6 et 5.7).

Trois invariants tiennent ici, et chacun a une raison d'etre :

**Un tarif ne touche jamais une facture emise.** `actes_realises.tarif_applique`
est fige a l'emission, et ce module n'ecrit jamais dedans. Modifier le prix d'un
acte ne touche que `tarifs_actes` et `actes_nomenclature.tarif_base`. C'est la
regle du cahier des charges, et elle est prouvee par
`tests/test_tarification.py::test_un_changement_de_tarif_ne_touche_pas_une_facture`.

**Chaque liste est paginee, triee, et filtree cote serveur.** Le tri a toujours
une **clef secondaire** : trier sur une colonne non unique laisse PostgreSQL
choisir l'ordre des ex aequalo, et une ligne peut alors changer de page entre
deux parcours. Le test de contrat de pagination echoue sur cette famille de
defauts.

**Une suppression est refusee, pas silencieuse.** Une categorie utilisee par un
tarif, un organisme utilise par un droit : la base porte un `RESTRICT`, et le
service renvoie un message nomme. Desactiver existe pour ce cas - on ne retire
jamais une reference d'un document deja emis.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.tarification.schemas import CODE_CATEGORIE_STANDARD
from src.modules.tenants.models import (
    ActeNomenclature,
    CategoriePatient,
    DroitPriseEnCharge,
    OrganismeAssurance,
    Patient,
    TarifActe,
    Utilisateur,
)


async def _journaliser(
    db: AsyncSession,
    *,
    action: str,
    ressource: str,
    ressource_id: str,
    auteur: Optional[Utilisateur],
    changements: Optional[dict] = None,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
) -> None:
    await AuditService.log_action(
        db=db,
        action=action,
        resource_type=ressource,
        resource_id=ressource_id,
        user_id=auteur.id if auteur else None,
        user_email=auteur.email if auteur else None,
        changes=changements or {},
        ip_address=ip,
        user_agent=ua,
    )


# ==============================================================================
# Categories de patient
# ==============================================================================


class CategorieService:
    @staticmethod
    async def lister(
        db: AsyncSession, *, offset: int, limit: int
    ) -> Tuple[List[CategoriePatient], int]:
        """Tri `(ordre, code)`. `code` est unique : c'est la clef secondaire."""
        total = int((await db.execute(select(func.count(CategoriePatient.id)))).scalar_one())
        stmt = (
            select(CategoriePatient)
            .order_by(CategoriePatient.ordre, CategoriePatient.code)
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all()), total

    @staticmethod
    async def obtenir_par_code(db: AsyncSession, code: str) -> CategoriePatient:
        categorie = (
            await db.execute(select(CategoriePatient).where(CategoriePatient.code == code))
        ).scalar_one_or_none()
        if categorie is None:
            raise EntityNotFoundException("Categorie de patient", code)
        return categorie

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        code: str,
        libelle: str,
        ordre: int,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> CategoriePatient:
        code_normalise = code.strip().lower()
        if code_normalise == CODE_CATEGORIE_STANDARD:
            raise BusinessRuleViolationException(
                "La categorie 'standard' existe deja et ne peut pas etre recreee.",
                code="CATEGORIE_STANDARD_RESERVEE",
            )
        existant = (
            await db.execute(select(CategoriePatient).where(CategoriePatient.code == code_normalise))
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                f"Une categorie '{code_normalise}' existe deja.",
                code="CATEGORIE_CODE_EXISTANT",
            )

        categorie = CategoriePatient(
            code=code_normalise,
            libelle=libelle.strip(),
            ordre=ordre,
            par_defaut=False,
        )
        db.add(categorie)
        await db.flush()
        await _journaliser(
            db,
            action="CATEGORIE_PATIENT_CREATE",
            ressource="CategoriePatient",
            ressource_id=str(categorie.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={"code": categorie.code, "libelle": categorie.libelle},
        )
        await db.commit()
        return categorie

    @staticmethod
    async def modifier(
        db: AsyncSession,
        categorie: CategoriePatient,
        *,
        libelle: Optional[str],
        ordre: Optional[int],
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> CategoriePatient:
        if libelle is not None:
            categorie.libelle = libelle.strip()
        if ordre is not None:
            categorie.ordre = ordre
        await db.flush()
        await _journaliser(
            db,
            action="CATEGORIE_PATIENT_UPDATE",
            ressource="CategoriePatient",
            ressource_id=str(categorie.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={"libelle": categorie.libelle, "ordre": categorie.ordre},
        )
        await db.commit()
        return categorie

    @staticmethod
    async def supprimer(db: AsyncSession, categorie: CategoriePatient) -> None:
        """
        Refuse si des tarifs s'y rattachent.

        Le `RESTRICT` de la base est le dernier rempart ; ce message est le
        premier, parce qu'un 500 n'apprend rien a personne.
        """
        if categorie.par_defaut:
            raise BusinessRuleViolationException(
                "La categorie de reference ne peut pas etre supprimee : elle porte "
                "le tarif de reference des actes.",
                code="CATEGORIE_DEFAUT_PROTEGEE",
            )
        utilisee = (
            await db.execute(
                select(func.count(TarifActe.id)).where(TarifActe.categorie_code == categorie.code)
            )
        ).scalar_one()
        if utilisee:
            raise BusinessRuleViolationException(
                f"La categorie '{categorie.code}' porte {utilisee} tarif(s). "
                "Desactivez-la plutot que de la supprimer.",
                code="CATEGORIE_UTILISEE",
            )
        await db.delete(categorie)
        await db.commit()


# ==============================================================================
# Nomenclature des actes
# ==============================================================================


class ActeService:
    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        q: Optional[str] = None,
        categorie: Optional[str] = None,
        actif: Optional[bool] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ActeNomenclature], int]:
        conditions = []
        if actif is not None:
            conditions.append(ActeNomenclature.actif.is_(actif))
        if categorie:
            conditions.append(ActeNomenclature.categorie == categorie.strip().upper())
        if q:
            like = f"%{q.strip()}%"
            conditions.append(
                or_(
                    ActeNomenclature.libelle.ilike(like),
                    ActeNomenclature.code.ilike(like),
                )
            )

        count_stmt = select(func.count(ActeNomenclature.id))
        data_stmt = select(ActeNomenclature)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            data_stmt = data_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())
        # Clef secondaire `id` : `code` est unique mais `categorie` ne l'est pas,
        # et c'est sur elle que commence le tri.
        data_stmt = (
            data_stmt.order_by(ActeNomenclature.categorie, ActeNomenclature.code, ActeNomenclature.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(data_stmt)).scalars().all()), total

    @staticmethod
    async def obtenir(db: AsyncSession, acte_id: uuid.UUID) -> ActeNomenclature:
        acte = (
            await db.execute(select(ActeNomenclature).where(ActeNomenclature.id == acte_id))
        ).scalar_one_or_none()
        if acte is None:
            raise EntityNotFoundException("Acte de nomenclature", acte_id)
        return acte

    @staticmethod
    async def tarifs_de(
        db: AsyncSession, acte_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, List[TarifActe]]:
        """
        Tarifs de plusieurs actes en une requete.

        Une liste de 50 actes qui ferait 50 requetes de tarifs est une liste qui
        s'affiche lentement - et le tri des tarifs ne serait pas deterministe
        d'une ligne a l'autre.
        """
        if not acte_ids:
            return {}
        stmt = (
            select(TarifActe)
            .where(TarifActe.acte_id.in_(acte_ids))
            .order_by(TarifActe.categorie_code, TarifActe.id)
        )
        groupes: dict[uuid.UUID, List[TarifActe]] = {}
        for tarif in (await db.execute(stmt)).scalars().all():
            groupes.setdefault(tarif.acte_id, []).append(tarif)
        return groupes

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        code: str,
        libelle: str,
        categorie: str,
        tarif_base: Decimal,
        duree_estimee_min: int = 30,
        unitaire: bool = False,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> ActeNomenclature:
        code_normalise = code.strip().upper()
        existant = (
            await db.execute(
                select(ActeNomenclature).where(ActeNomenclature.code == code_normalise)
            )
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                f"Un acte avec le code '{code_normalise}' existe deja.",
                code="ACTE_CODE_EXISTANT",
            )

        acte = ActeNomenclature(
            code=code_normalise,
            libelle=libelle.strip(),
            categorie=categorie.strip().upper(),
            tarif_base=tarif_base,
            duree_estimee_min=duree_estimee_min,
            unitaire=unitaire,
            actif=True,
        )
        db.add(acte)
        await db.flush()

        # L'acte cree recoit aussitot son tarif de reference. Sans cette ligne, un
        # acte cree par l'interface aurait `tarif_base` mais pas de ligne dans
        # `tarifs_actes` : deux chemins de lecture pour le meme montant.
        await CategorieService.obtenir_par_code(db, CODE_CATEGORIE_STANDARD)
        db.add(
            TarifActe(acte_id=acte.id, categorie_code=CODE_CATEGORIE_STANDARD, montant=tarif_base)
        )

        await _journaliser(
            db,
            action="ACTE_NOMENCLATURE_CREATE",
            ressource="ActeNomenclature",
            ressource_id=str(acte.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={
                "code": acte.code,
                "libelle": acte.libelle,
                "tarif_base": str(acte.tarif_base),
            },
        )
        await db.commit()
        return acte

    @staticmethod
    async def modifier(
        db: AsyncSession,
        acte: ActeNomenclature,
        *,
        libelle: Optional[str] = None,
        categorie: Optional[str] = None,
        duree_estimee_min: Optional[int] = None,
        unitaire: Optional[bool] = None,
        actif: Optional[bool] = None,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> ActeNomenclature:
        """
        Met a jour l'acte **sans toucher aux lignes de facture**.

        `tarif_base` n'est volontairement pas modifiable ici : le changer
        passe par un tarif de categorie, ou par une creation d'acte. Un
        `PATCH` general qui accepte `tarif_base` finirait par etre appele par une
        edition d'ecran ordinaire, et le prix changerait sous les factures
        emises.
        """
        if libelle is not None:
            acte.libelle = libelle.strip()
        if categorie is not None:
            acte.categorie = categorie.strip().upper()
        if duree_estimee_min is not None:
            acte.duree_estimee_min = duree_estimee_min
        if unitaire is not None:
            acte.unitaire = unitaire
        if actif is not None:
            acte.actif = actif
        await db.flush()
        await _journaliser(
            db,
            action="ACTE_NOMENCLATURE_UPDATE",
            ressource="ActeNomenclature",
            ressource_id=str(acte.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={
                "libelle": acte.libelle,
                "actif": acte.actif,
                "categorie": acte.categorie,
            },
        )
        await db.commit()
        return acte


# ==============================================================================
# Tarifs
# ==============================================================================


class TarifService:
    @staticmethod
    async def definir(
        db: AsyncSession,
        *,
        acte: ActeNomenclature,
        categorie_code: str,
        montant: Decimal,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> TarifActe:
        """
        Ecrit le tarif d'un acte pour une categorie, cree s'il n'existe pas.

        Le `standard` est traite a part : il met aussi `tarif_base` a jour. C'est
        la seule ecriture de `tarif_base` hors creation, et elle correspond au
        seul tarif que la facturation lise encore.
        """
        categorie = await CategorieService.obtenir_par_code(db, categorie_code)
        tarif = (
            await db.execute(
                select(TarifActe).where(
                    TarifActe.acte_id == acte.id,
                    TarifActe.categorie_code == categorie.code,
                )
            )
        ).scalar_one_or_none()

        if tarif is None:
            tarif = TarifActe(acte_id=acte.id, categorie_code=categorie.code, montant=montant)
            db.add(tarif)
        else:
            tarif.montant = montant
            if categorie.par_defaut:
                acte.tarif_base = montant

        await db.flush()
        await _journaliser(
            db,
            action="TARIF_ACTE_ECRIT",
            ressource="TarifActe",
            ressource_id=str(tarif.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={
                "acte_id": str(acte.id),
                "acte_code": acte.code,
                "categorie_code": categorie.code,
                "montant": str(montant),
            },
        )
        await db.commit()
        return tarif

    @staticmethod
    async def supprimer(db: AsyncSession, tarif: TarifActe) -> None:
        """Retire un tarif de variante. Le tarif `standard` est protege."""
        if tarif.categorie_code == CODE_CATEGORIE_STANDARD:
            raise BusinessRuleViolationException(
                "Le tarif standard ne peut pas etre retire : c'est le tarif de "
                "reference de l'acte.",
                code="TARIF_STANDARD_PROTEGE",
            )
        await db.delete(tarif)
        await db.commit()


# ==============================================================================
# Organismes payeurs
# ==============================================================================


class OrganismeService:
    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        q: Optional[str] = None,
        type_organisme: Optional[str] = None,
        actif: Optional[bool] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[OrganismeAssurance], int]:
        conditions = []
        if actif is not None:
            conditions.append(OrganismeAssurance.actif.is_(actif))
        if type_organisme:
            conditions.append(OrganismeAssurance.type_organisme == type_organisme.upper())
        if q:
            like = f"%{q.strip()}%"
            conditions.append(
                or_(
                    OrganismeAssurance.nom.ilike(like),
                    OrganismeAssurance.code.ilike(like),
                )
            )

        count_stmt = select(func.count(OrganismeAssurance.id))
        data_stmt = select(OrganismeAssurance)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            data_stmt = data_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())
        # `nom` n'est pas unique : `id` est la clef secondaire obligatoire.
        data_stmt = (
            data_stmt.order_by(OrganismeAssurance.nom, OrganismeAssurance.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(data_stmt)).scalars().all()), total

    @staticmethod
    async def obtenir(db: AsyncSession, organisme_id: uuid.UUID) -> OrganismeAssurance:
        organisme = (
            await db.execute(
                select(OrganismeAssurance).where(OrganismeAssurance.id == organisme_id)
            )
        ).scalar_one_or_none()
        if organisme is None:
            raise EntityNotFoundException("Organisme d'assurance", organisme_id)
        return organisme

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        code: str,
        nom: str,
        type_organisme: str,
        actif: bool = True,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> OrganismeAssurance:
        code_normalise = code.strip().lower()
        existant = (
            await db.execute(
                select(OrganismeAssurance).where(OrganismeAssurance.code == code_normalise)
            )
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                f"Un organisme '{code_normalise}' existe deja.",
                code="ORGANISME_CODE_EXISTANT",
            )
        organisme = OrganismeAssurance(
            code=code_normalise,
            nom=nom.strip(),
            type_organisme=type_organisme.upper(),
            actif=actif,
        )
        db.add(organisme)
        await db.flush()
        await _journaliser(
            db,
            action="ORGANISME_CREATE",
            ressource="OrganismeAssurance",
            ressource_id=str(organisme.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={"code": organisme.code, "nom": organisme.nom},
        )
        await db.commit()
        return organisme

    @staticmethod
    async def modifier(
        db: AsyncSession,
        organisme: OrganismeAssurance,
        *,
        nom: Optional[str] = None,
        type_organisme: Optional[str] = None,
        actif: Optional[bool] = None,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> OrganismeAssurance:
        if nom is not None:
            organisme.nom = nom.strip()
        if type_organisme is not None:
            organisme.type_organisme = type_organisme.upper()
        if actif is not None:
            organisme.actif = actif
        await db.flush()
        await _journaliser(
            db,
            action="ORGANISME_UPDATE",
            ressource="OrganismeAssurance",
            ressource_id=str(organisme.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={"nom": organisme.nom, "actif": organisme.actif},
        )
        await db.commit()
        return organisme

    @staticmethod
    async def supprimer(db: AsyncSession, organisme: OrganismeAssurance) -> None:
        """
        Refuse si des droits y sont rattaches.

        Supprimer un organisme effacerait silencieusement les droits de tous les
        patients concernes. C'est la base qui bloque (`RESTRICT`) ; ce message
        est pour que l'appelant sache quoi faire : desactiver.
        """
        utilise = (
            await db.execute(
                select(func.count(DroitPriseEnCharge.id)).where(
                    DroitPriseEnCharge.organisme_id == organisme.id
                )
            )
        ).scalar_one()
        if utilise:
            raise BusinessRuleViolationException(
                f"L'organisme '{organisme.code}' porte {utilise} droit(s) de prise en "
                "charge. Desactivez-le plutot que de le supprimer.",
                code="ORGANISME_UTILISE",
            )
        await db.delete(organisme)
        await db.commit()


# ==============================================================================
# Droits de prise en charge par patient
# ==============================================================================


class DroitPriseEnChargeService:
    @staticmethod
    async def lister_par_patient(
        db: AsyncSession, patient_id: uuid.UUID
    ) -> List[Tuple[DroitPriseEnCharge, OrganismeAssurance]]:
        """
        Droits d'un patient, joints a leur organisme.

        Tri `(priorite, code organisme)`. Deux droits de meme priorite existent -
        c'est le cabinet qui tranche, pas le serveur - donc la clef secondaire
        est necessaire pour que l'ordre soit stable d'un appel a l'autre.
        """
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is None:
            raise EntityNotFoundException("Patient", patient_id)

        stmt = (
            select(DroitPriseEnCharge, OrganismeAssurance)
            .join(OrganismeAssurance, OrganismeAssurance.id == DroitPriseEnCharge.organisme_id)
            .where(DroitPriseEnCharge.patient_id == patient_id)
            .order_by(DroitPriseEnCharge.priorite, OrganismeAssurance.code, DroitPriseEnCharge.id)
        )
        return list((await db.execute(stmt)).all())

    @staticmethod
    async def obtenir(db: AsyncSession, droit_id: uuid.UUID) -> DroitPriseEnCharge:
        droit = (
            await db.execute(select(DroitPriseEnCharge).where(DroitPriseEnCharge.id == droit_id))
        ).scalar_one_or_none()
        if droit is None:
            raise EntityNotFoundException("Droit de prise en charge", droit_id)
        return droit

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        patient_id: uuid.UUID,
        organisme_id: uuid.UUID,
        numero_police: Optional[str],
        taux_prise_en_charge: Decimal,
        priorite: int,
        actif: bool,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> DroitPriseEnCharge:
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is None:
            raise EntityNotFoundException("Patient", patient_id)
        await OrganismeService.obtenir(db, organisme_id)

        droit = DroitPriseEnCharge(
            patient_id=patient_id,
            organisme_id=organisme_id,
            numero_police=numero_police.strip() if numero_police else None,
            taux_prise_en_charge=taux_prise_en_charge,
            priorite=priorite,
            actif=actif,
        )
        db.add(droit)
        await db.flush()
        await _journaliser(
            db,
            action="DROIT_PRISE_EN_CHARGE_CREATE",
            ressource="DroitPriseEnCharge",
            ressource_id=str(droit.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={
                "patient_id": str(patient_id),
                "organisme_id": str(organisme_id),
                "taux_prise_en_charge": str(taux_prise_en_charge),
                "priorite": priorite,
            },
        )
        await db.commit()
        return droit

    @staticmethod
    async def modifier(
        db: AsyncSession,
        droit: DroitPriseEnCharge,
        *,
        organisme_id: Optional[uuid.UUID] = None,
        numero_police: Optional[str] = None,
        taux_prise_en_charge: Optional[Decimal] = None,
        priorite: Optional[int] = None,
        actif: Optional[bool] = None,
        auteur: Optional[Utilisateur] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> DroitPriseEnCharge:
        if organisme_id is not None:
            await OrganismeService.obtenir(db, organisme_id)
            droit.organisme_id = organisme_id
        if numero_police is not None:
            droit.numero_police = numero_police.strip() or None
        if taux_prise_en_charge is not None:
            droit.taux_prise_en_charge = taux_prise_en_charge
        if priorite is not None:
            droit.priorite = priorite
        if actif is not None:
            droit.actif = actif
        await db.flush()
        await _journaliser(
            db,
            action="DROIT_PRISE_EN_CHARGE_UPDATE",
            ressource="DroitPriseEnCharge",
            ressource_id=str(droit.id),
            auteur=auteur,
            ip=ip,
            ua=ua,
            changements={
                "taux_prise_en_charge": str(droit.taux_prise_en_charge),
                "priorite": droit.priorite,
                "actif": droit.actif,
            },
        )
        await db.commit()
        return droit

    @staticmethod
    async def supprimer(db: AsyncSession, droit: DroitPriseEnCharge) -> None:
        await db.delete(droit)
        await db.commit()