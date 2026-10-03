"""
Services métier du module Cabinets & Ressources (D2A).

Ce module installe le **décor physique et organisationnel** du cabinet : sites,
salles, fauteuils, praticiens, et les plages horaires auxquelles ils travaillent.
Le module Agenda (D2B) consommera ces données sans les redéfinir.

Trois décisions structurantes, qui méritent d'être explicitées parce qu'elles
ne sont pas déductibles du code :

1. **Un fauteuil utilisé ne se supprime pas, il se désactive.**
   `consultations.fauteuil_id` porte l'historique du lieu où le soin a eu lieu.
   Supprimer le fauteuil mettrait `SET NULL` sur ces lignes et effacerait une
   information médico-légale. On ne permet donc la suppression que d'un
   fauteuil jamais utilisé ; sinon on le désactive.

2. **Une disponibilité appartient au praticien, pas au rôle.**
   Un praticien modifie les siennes ; l'administrateur peut modifier celles de
   tous. Ce n'est pas une permission mais une règle métier : un praticien n'a
   rien à dire de l'agenda d'un confrère.

3. **Les horaires d'ouverture et les disponibilités sont deux notions
   distinctes** (voir `src/common/disponibilite.py`). Ce module expose les
   deux sans les confondre, et fournit déjà `creneaux_proposables`, calcul dont
   le module Agenda aura besoin.
"""

import uuid
from datetime import date, time
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.disponibilite import (
    BLOCKING,
    CONSULTATION,
    DUREE_CRENEAU_MINUTES,
    JOURS_COURTS,
    JOURS_SEMAINE,
    LIBELLES_TYPE_PLAGE,
    TYPES_PLAGE,
    PlageInvalide,
    compacter,
    creneaux_proposables,
    est_bloquante,
    minutes_de,
)
from src.core.exceptions import (
    BusinessRuleViolationException,

    EntityNotFoundException,
)
from src.modules.audit.services import AuditService
from src.modules.cabinets.schemas import (
    CabinetUpdate,
    DisponibiliteCreate,
    FauteuilCreate,
    FauteuilUpdate,
    PraticienCreate,
    PraticienUpdate,
    RattachementCreate,
    SalleCreate,
    SalleUpdate,
)
from src.modules.tenants.models import (
    Cabinet,
    CabinetPraticien,
    Consultation,
    Disponibilite,
    Fauteuil,
    Praticien,
    Salle,
    Utilisateur,
)

logger = structlog.get_logger(__name__)


# ==============================================================================
# CABINETS (SITES)
# ==============================================================================

class CabinetService:
    """
    Les sites d'une société.

    Un tenant peut en exploiter plusieurs : `ConsultationService._resoudre_cabinet`
    refuse alors de deviner et exige un `cabinet_id` explicite. Ce module est
    donc multi-site par conception, pas par accident.
    """

    @staticmethod
    async def lister(db: AsyncSession, inclure_inactifs: bool = False) -> List[Cabinet]:
        stmt = select(Cabinet).order_by(Cabinet.nom)
        if not inclure_inactifs:
            stmt = stmt.where(Cabinet.actif.is_(True))
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def obtenir(db: AsyncSession, cabinet_id: uuid.UUID) -> Cabinet:
        cabinet = (
            await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
        ).scalar_one_or_none()
        if cabinet is None:
            raise EntityNotFoundException("Cabinet", cabinet_id)
        return cabinet

    @staticmethod
    async def _compteurs(db: AsyncSession, cabinet_id: uuid.UUID) -> Dict[str, int]:
        """Compteurs de la fiche cabinet, en trois requêtes plutôt qu'en cascade."""
        nb_salles = int(
            (
                await db.execute(
                    select(func.count(Salle.id)).where(Salle.cabinet_id == cabinet_id)
                )
            ).scalar_one()
        )
        nb_fauteuils = int(
            (
                await db.execute(
                    select(func.count(Fauteuil.id))
                    .join(Salle, Salle.id == Fauteuil.salle_id)
                    .where(Salle.cabinet_id == cabinet_id, Fauteuil.actif.is_(True))
                )
            ).scalar_one()
        )
        nb_praticiens = int(
            (
                await db.execute(
                    select(func.count(CabinetPraticien.id)).where(
                        CabinetPraticien.cabinet_id == cabinet_id,
                        CabinetPraticien.actif.is_(True),
                    )
                )
            ).scalar_one()
        )
        return {
            "nb_salles": nb_salles,
            "nb_fauteuils_actifs": nb_fauteuils,
            "nb_praticiens_actifs": nb_praticiens,
        }

    @staticmethod
    async def modifier(
        db: AsyncSession,
        cabinet_id: uuid.UUID,
        data: CabinetUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Cabinet:
        cabinet = await CabinetService.obtenir(db, cabinet_id)

        # Désactiver le dernier cabinet actif laisserait le tenant sans aucune
        # possibilité d'enregistrer une consultation : blocage silencieux.
        if data.actif is False and cabinet.actif:
            restants = int(
                (
                    await db.execute(
                        select(func.count(Cabinet.id)).where(
                            Cabinet.actif.is_(True), Cabinet.id != cabinet_id
                        )
                    )
                ).scalar_one()
            )
            if restants == 0:
                raise BusinessRuleViolationException(
                    "Impossible de désactiver le dernier cabinet actif : le cabinet "
                    "n'enregistre plus aucune consultation sans site de référence.",
                    code="DERNIER_CABINET_ACTIF",
                )

        champs = data.model_dump(exclude_unset=True, exclude_none=True)
        for champ, valeur in champs.items():
            setattr(cabinet, champ, valeur)

        await db.flush()
        await AuditService.log_action(
            db=db,
            action="CABINET_UPDATE",
            resource_type="Cabinet",
            resource_id=str(cabinet.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes=champs,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return cabinet


# ==============================================================================
# SALLES
# ==============================================================================

class SalleService:
    @staticmethod
    async def lister(
        db: AsyncSession, cabinet_id: uuid.UUID
    ) -> List[Tuple[Salle, int, int]]:
        """Salles d'un site, avec le nombre de fauteuils (total et actifs)."""
        stmt = (
            select(Salle, func.count(Fauteuil.id), func.count(Fauteuil.id).filter(Fauteuil.actif.is_(True)))
            .outerjoin(Fauteuil, Fauteuil.salle_id == Salle.id)
            .where(Salle.cabinet_id == cabinet_id)
            .group_by(Salle.id)
            .order_by(Salle.nom)
        )
        return list((await db.execute(stmt)).all())

    @staticmethod
    async def obtenir(db: AsyncSession, salle_id: uuid.UUID) -> Salle:
        salle = (
            await db.execute(select(Salle).where(Salle.id == salle_id))
        ).scalar_one_or_none()
        if salle is None:
            raise EntityNotFoundException("Salle", salle_id)
        return salle

    @staticmethod
    async def creer(
        db: AsyncSession,
        cabinet_id: uuid.UUID,
        data: SalleCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Salle:
        cabinet = await CabinetService.obtenir(db, cabinet_id)
        if not cabinet.actif:
            raise BusinessRuleViolationException(
                f"Le cabinet « {cabinet.nom} » est désactivé : on n'y crée plus de salle.",
                code="CABINET_INACTIF",
            )

        doublon = (
            await db.execute(
                select(Salle).where(
                    func.lower(Salle.nom) == data.nom.lower(),
                    Salle.cabinet_id == cabinet_id,
                )
            )
        ).scalar_one_or_none()
        if doublon is not None:
            raise BusinessRuleViolationException(
                f"La salle « {data.nom} » existe déjà dans ce cabinet.",
                code="SALLE_DUPLIQUEE",
            )

        salle = Salle(cabinet_id=cabinet_id, nom=data.nom, etage=data.etage)
        db.add(salle)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="SALLE_CREATE",
            resource_type="Salle",
            resource_id=str(salle.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"nom": salle.nom, "cabinet_id": str(cabinet_id)},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return salle

    @staticmethod
    async def modifier(
        db: AsyncSession,
        salle_id: uuid.UUID,
        data: SalleUpdate,
        auteur: Optional[Utilisateur] = None,
    ) -> Salle:
        salle = await SalleService.obtenir(db, salle_id)
        for champ, valeur in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(salle, champ, valeur)
        await db.flush()
        await db.commit()
        return salle

    @staticmethod
    async def supprimer(
        db: AsyncSession,
        salle_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Supprime une salle — uniquement si elle est vide.

        Une salle qui contient encore des fauteuils actifs n'est pas supprimée :
        il faut d'abord les désactiver un par un. Supprimer la salle en cascade
        effacerait des fauteuils, donc potentiellement des références de
        consultations.
        """
        salle = await SalleService.obtenir(db, salle_id)

        fauteuils = int(
            (
                await db.execute(
                    select(func.count(Fauteuil.id)).where(Fauteuil.salle_id == salle_id)
                )
            ).scalar_one()
        )
        if fauteuils:
            raise BusinessRuleViolationException(
                f"La salle « {salle.nom} » contient encore {fauteuils} fauteuil(s). "
                "Désactivez-les avant de supprimer la salle.",
                code="SALLE_NON_VIDE",
            )

        nom_salle = salle.nom
        await AuditService.log_action(
            db=db,
            action="SALLE_DELETE",
            resource_type="Salle",
            resource_id=str(salle_id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"nom": nom_salle},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.delete(salle)
        await db.commit()


# ==============================================================================
# FAUTEUILS
# ==============================================================================

class FauteuilService:
    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
        salle_id: Optional[uuid.UUID] = None,
        inclure_inactifs: bool = False,
    ) -> List[Tuple[Fauteuil, str, str]]:
        """Fauteuils (toutes salles d'un site, ou une salle), avec salle et cabinet."""
        stmt = (
            select(Fauteuil, Salle.nom, Cabinet.nom)
            .join(Salle, Salle.id == Fauteuil.salle_id)
            .join(Cabinet, Cabinet.id == Salle.cabinet_id)
            .order_by(Salle.nom, Fauteuil.numero)
        )
        if cabinet_id:
            stmt = stmt.where(Salle.cabinet_id == cabinet_id)
        if salle_id:
            stmt = stmt.where(Fauteuil.salle_id == salle_id)
        if not inclure_inactifs:
            stmt = stmt.where(Fauteuil.actif.is_(True))
        return list((await db.execute(stmt)).all())

    @staticmethod
    async def obtenir(db: AsyncSession, fauteuil_id: uuid.UUID) -> Fauteuil:
        fauteuil = (
            await db.execute(select(Fauteuil).where(Fauteuil.id == fauteuil_id))
        ).scalar_one_or_none()
        if fauteuil is None:
            raise EntityNotFoundException("Fauteuil", fauteuil_id)
        return fauteuil

    @staticmethod
    async def creer(
        db: AsyncSession,
        salle_id: uuid.UUID,
        data: FauteuilCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Fauteuil:
        salle = await SalleService.obtenir(db, salle_id)

        doublon = (
            await db.execute(
                select(Fauteuil).where(
                    func.lower(Fauteuil.numero) == data.numero.lower(),
                    Fauteuil.salle_id == salle_id,
                )
            )
        ).scalar_one_or_none()
        if doublon is not None:
            raise BusinessRuleViolationException(
                f"Le fauteuil « {data.numero} » existe déjà dans la salle « {salle.nom} ».",
                code="FAUTEUIL_DUPLIQUE",
            )

        fauteuil = Fauteuil(
            salle_id=salle_id,
            numero=data.numero,
            equipements=data.equipements,
            actif=True,
        )
        db.add(fauteuil)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="FAUTEUIL_CREATE",
            resource_type="Fauteuil",
            resource_id=str(fauteuil.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero": fauteuil.numero, "salle": salle.nom},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return fauteuil

    @staticmethod
    async def modifier(
        db: AsyncSession,
        fauteuil_id: uuid.UUID,
        data: FauteuilUpdate,
        auteur: Optional[Utilisateur] = None,
    ) -> Fauteuil:
        fauteuil = await FauteuilService.obtenir(db, fauteuil_id)
        for champ, valeur in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(fauteuil, champ, valeur)
        await db.flush()
        await db.commit()
        return fauteuil

    @staticmethod
    async def supprimer(
        db: AsyncSession,
        fauteuil_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Supprime un fauteuil **jamais utilisé**, le désactive sinon.

        Règle 1 du module. `consultations.fauteuil_id` est en `ON DELETE SET
        NULL` : supprimer un fauteuil qui a servi effacerait de la trace le lieu
        du soin. On renvoie donc vers la désactivation, qui préserve l'historique
        tout en retirant le fauteuil des propositions de planning.
        """
        fauteuil = await FauteuilService.obtenir(db, fauteuil_id)

        nb_consultations = int(
            (
                await db.execute(
                    select(func.count(Consultation.id)).where(
                        Consultation.fauteuil_id == fauteuil_id
                    )
                )
            ).scalar_one()
        )
        if nb_consultations:
            raise BusinessRuleViolationException(
                f"Le fauteuil « {fauteuil.numero} » a servi à {nb_consultations} "
                "consultation(s) : il ne peut pas être supprimé, seulement désactivé. "
                "L'historique médico-légal doit garder le lieu du soin.",
                code="FAUTEUIL_UTILISE",
                details={"nb_consultations": nb_consultations},
            )

        await AuditService.log_action(
            db=db,
            action="FAUTEUIL_DELETE",
            resource_type="Fauteuil",
            resource_id=str(fauteuil_id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero": fauteuil.numero},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.delete(fauteuil)
        await db.commit()

    @staticmethod
    async def reactiver(
        db: AsyncSession,
        fauteuil_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
    ) -> Fauteuil:
        fauteuil = await FauteuilService.obtenir(db, fauteuil_id)
        fauteuil.actif = True
        await db.flush()
        await db.commit()
        return fauteuil


# ==============================================================================
# PRATICIENS & RATTACHEMENTS
# ==============================================================================

class PraticienService:
    @staticmethod
    async def lister(
        db: AsyncSession, *, cabinet_id: Optional[uuid.UUID] = None
    ) -> List[Praticien]:
        # Le tri se fait sur le nom du compte porteur : `Praticien` n'a pas de
        # colonne `nom`, il ne connaît que son `utilisateur_id`.
        #
        # `disponibilites` est chargée ici comme les deux autres relations :
        # `vers_reponse_praticien` compte les plages, et un `getattr(p,
        # "disponibilites", [])` NE l'empêche pas — l'attribut existe sur la
        # classe, donc l'accès déclenche un lazy-load, qui lève MissingGreenlet
        # hors contexte greenlet.
        stmt = (
            select(Praticien)
            .join(Utilisateur, Utilisateur.id == Praticien.utilisateur_id)
            .options(
                selectinload(Praticien.utilisateur),
                selectinload(Praticien.rattachements),
                selectinload(Praticien.disponibilites),
            )
            .order_by(Utilisateur.nom, Utilisateur.prenom)
        )
        if cabinet_id:
            stmt = stmt.where(
                Praticien.id.in_(
                    select(CabinetPraticien.praticien_id).where(
                        CabinetPraticien.cabinet_id == cabinet_id,
                        CabinetPraticien.actif.is_(True),
                    )
                )
            )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def obtenir(db: AsyncSession, praticien_id: uuid.UUID) -> Praticien:
        praticien = (
            await db.execute(
                select(Praticien)
                .options(
                    selectinload(Praticien.utilisateur),
                    selectinload(Praticien.rattachements),
                    selectinload(Praticien.disponibilites),
                )
                .where(Praticien.id == praticien_id)
            )
        ).scalar_one_or_none()
        if praticien is None:
            raise EntityNotFoundException("Praticien", praticien_id)
        return praticien

    @staticmethod
    async def creer(
        db: AsyncSession,
        data: PraticienCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Praticien:
        """
        Rattache un compte existant au métier de praticien.

        Exiger un `utilisateur_id` plutôt que créer l'identité ici est
        délibéré : un praticien sans compte ne pourrait rien signer, et c'est la
        signature qui rend un acte opposable.
        """
        utilisateur = (
            await db.execute(
                select(Utilisateur).where(Utilisateur.id == data.utilisateur_id)
            )
        ).scalar_one_or_none()
        if utilisateur is None:
            raise EntityNotFoundException("Utilisateur", data.utilisateur_id)
        if not utilisateur.actif:
            raise BusinessRuleViolationException(
                f"Le compte {utilisateur.email} est désactivé : on ne peut pas en faire "
                "un praticien actif.",
                code="COMPTE_INACTIF",
            )

        deja = (
            await db.execute(
                select(Praticien).where(Praticien.utilisateur_id == data.utilisateur_id)
            )
        ).scalar_one_or_none()
        if deja is not None:
            raise BusinessRuleViolationException(
                f"Le compte {utilisateur.email} est déjà rattaché à un profil praticien.",
                code="PRATICIEN_EXISTANT",
            )

        if data.numero_ordre:
            collision = (
                await db.execute(
                    select(Praticien).where(
                        func.lower(Praticien.numero_ordre) == data.numero_ordre.lower()
                    )
                )
            ).scalar_one_or_none()
            if collision is not None:
                raise BusinessRuleViolationException(
                    f"Le numéro d'ordre {data.numero_ordre} est déjà attribué à un "
                    "autre praticien.",
                    code="NUMERO_ORDRE_DUPLIQUE",
                )

        cabinet_id = None
        if data.cabinet_id:
            cabinet = await CabinetService.obtenir(db, data.cabinet_id)
            if not cabinet.actif:
                raise BusinessRuleViolationException(
                    f"Le cabinet « {cabinet.nom} » est désactivé.",
                    code="CABINET_INACTIF",
                )
            cabinet_id = cabinet.id

        praticien = Praticien(
            utilisateur_id=utilisateur.id,
            titre=data.titre,
            specialite=data.specialite,
            numero_ordre=data.numero_ordre,
            signature_url=data.signature_url,
            bio=data.bio,
        )
        db.add(praticien)
        await db.flush()

        if cabinet_id:
            db.add(
                CabinetPraticien(
                    cabinet_id=cabinet_id, praticien_id=praticien.id, actif=True
                )
            )
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PRATICIEN_CREATE",
            resource_type="Praticien",
            resource_id=str(praticien.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "email": utilisateur.email,
                "specialite": praticien.specialite,
                "numero_ordre": praticien.numero_ordre,
                "cabinet_id": str(cabinet_id) if cabinet_id else None,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        logger.info("praticien_cree", praticien_id=str(praticien.id))
        return await PraticienService.obtenir(db, praticien.id)

    @staticmethod
    async def modifier(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        data: PraticienUpdate,
        auteur: Optional[Utilisateur] = None,
    ) -> Praticien:
        praticien = await PraticienService.obtenir(db, praticien_id)

        if data.numero_ordre:
            collision = (
                await db.execute(
                    select(Praticien).where(
                        func.lower(Praticien.numero_ordre) == data.numero_ordre.lower(),
                        Praticien.id != praticien_id,
                    )
                )
            ).scalar_one_or_none()
            if collision is not None:
                raise BusinessRuleViolationException(
                    f"Le numéro d'ordre {data.numero_ordre} est déjà attribué à un "
                    "autre praticien.",
                    code="NUMERO_ORDRE_DUPLIQUE",
                )

        for champ, valeur in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(praticien, champ, valeur)
        await db.flush()
        await db.commit()
        return await PraticienService.obtenir(db, praticien_id)

    # -------------------------------------------------------------- rattachement
    @staticmethod
    async def rattacher(
        db: AsyncSession,
        cabinet_id: uuid.UUID,
        praticien_id: uuid.UUID,
        data: RattachementCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CabinetPraticien:
        """Rattache un praticien à un site, ou réactive un rattachement clos."""
        await CabinetService.obtenir(db, cabinet_id)
        await PraticienService.obtenir(db, praticien_id)

        existant = (
            await db.execute(
                select(CabinetPraticien).where(
                    CabinetPraticien.cabinet_id == cabinet_id,
                    CabinetPraticien.praticien_id == praticien_id,
                )
            )
        ).scalar_one_or_none()

        if existant is not None:
            if existant.actif:
                raise BusinessRuleViolationException(
                    "Ce praticien est déjà rattaché à ce cabinet.",
                    code="RATTACHEMENT_EXISTANT",
                )
            # Rattachement clôturé : on le rouvre en conservant l'historique des
            # dates, on n'en crée pas un second qui ferait doublon.
            existant.date_debut = data.date_debut or date.today()
            existant.date_fin = data.date_fin
            existant.actif = True
            await db.flush()
            await db.commit()
            return existant

        rattachement = CabinetPraticien(
            cabinet_id=cabinet_id,
            praticien_id=praticien_id,
            date_debut=data.date_debut or date.today(),
            date_fin=data.date_fin,
            actif=True,
        )
        db.add(rattachement)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PRATICIEN_RATTACHEMENT",
            resource_type="CabinetPraticien",
            resource_id=str(rattachement.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"cabinet_id": str(cabinet_id), "praticien_id": str(praticien_id)},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return rattachement

    @staticmethod
    async def detacher(
        db: AsyncSession,
        cabinet_id: uuid.UUID,
        praticien_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
    ) -> CabinetPraticien:
        """
        Clôt le rattachement d'un praticien à un site.

        On NE SUPPRIME PAS la ligne : `date_fin` est renseignée et le
        rattachement devient inactif. Les consultations passées restent
        attribuables à ce praticien dans ce site.
        """
        rattachement = (
            await db.execute(
                select(CabinetPraticien).where(
                    CabinetPraticien.cabinet_id == cabinet_id,
                    CabinetPraticien.praticien_id == praticien_id,
                    CabinetPraticien.actif.is_(True),
                )
            )
        ).scalar_one_or_none()
        if rattachement is None:
            raise EntityNotFoundException("Rattachement", praticien_id)

        rattachement.actif = False
        rattachement.date_fin = date.today()
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PRATICIEN_DETACHEMENT",
            resource_type="CabinetPraticien",
            resource_id=str(rattachement.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"cabinet_id": str(cabinet_id), "praticien_id": str(praticien_id)},
        )
        await db.commit()
        return rattachement

    @staticmethod
    async def lister_rattachements(
        db: AsyncSession, cabinet_id: uuid.UUID
    ) -> List[CabinetPraticien]:
        stmt = (
            select(CabinetPraticien)
            .join(Praticien, Praticien.id == CabinetPraticien.praticien_id)
            .join(Utilisateur, Utilisateur.id == Praticien.utilisateur_id)
            .options(
                selectinload(CabinetPraticien.praticien).selectinload(Praticien.utilisateur)
            )
            .where(CabinetPraticien.cabinet_id == cabinet_id)
            .order_by(CabinetPraticien.actif.desc(), Utilisateur.nom)
        )
        return list((await db.execute(stmt)).scalars().all())


# ==============================================================================
# DISPONIBILITÉS
# ==============================================================================

class DisponibiliteService:
    @staticmethod
    async def lister(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
    ) -> List[Disponibilite]:
        stmt = select(Disponibilite).where(Disponibilite.praticien_id == praticien_id)
        if cabinet_id:
            stmt = stmt.where(
                (Disponibilite.cabinet_id == cabinet_id)
                | (Disponibilite.cabinet_id.is_(None))  # valable pour tous les sites
            )
        stmt = stmt.order_by(
            Disponibilite.date_specifique.isnot(None),
            Disponibilite.jour_semaine,
            Disponibilite.heure_debut,
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def creer(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        data: DisponibiliteCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Disponibilite:
        praticien = await PraticienService.obtenir(db, praticien_id)

        if data.cabinet_id:
            await CabinetService.obtenir(db, data.cabinet_id)

        # Deux plages exactement identiques n'apportent rien et肆无忌惮 le
        # calcul de créneaux (fusionnées sans que personne ne s'en aperçoive).
        chevauchant = await DisponibiliteService._chevauchement_exact(
            db,
            praticien_id,
            data.jour_semaine,
            data.date_specifique,
            data.heure_debut,
            data.heure_fin,
            data.type,
            data.cabinet_id,
        )
        if chevauchant is not None:
            raise BusinessRuleViolationException(
                f"Ce créneau est déjà déclaré en {data.type.lower()} "
                f"({chevauchant.heure_debut:%H:%M} - {chevauchant.heure_fin:%H:%M}).",
                code="DISPONIBILITE_DUPLIQUEE",
            )

        disponibilite = Disponibilite(
            praticien_id=praticien_id,
            cabinet_id=data.cabinet_id,
            jour_semaine=data.jour_semaine,
            date_specifique=data.date_specifique,
            heure_debut=data.heure_debut,
            heure_fin=data.heure_fin,
            type=data.type,
            actif=data.actif,
        )
        db.add(disponibilite)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="DISPONIBILITE_CREATE",
            resource_type="Disponibilite",
            resource_id=str(disponibilite.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "jour_semaine": data.jour_semaine,
                "date_specifique": str(data.date_specifique) if data.date_specifique else None,
                "plage": f"{data.heure_debut:%H:%M}-{data.heure_fin:%H:%M}",
                "type": data.type,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        logger.info(
            "disponibilite_creee",
            praticien_id=str(praticien.id),
            type=data.type,
        )
        return disponibilite

    @staticmethod
    async def _chevauchement_exact(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        jour_semaine: Optional[int],
        date_specifique: Optional[date],
        heure_debut: time,
        heure_fin: time,
        type_plage: str,
        cabinet_id: Optional[uuid.UUID],
    ) -> Optional[Disponibilite]:
        """
        Recherche une plage strictement identique.

        « Strictement identique » inclut les HEURES **et le type** :

        - comparer seulement jour et site ferait rejeter toute seconde plage du
          même jour ;
        - omettre le type ferait rejeter la superposition d'une formation
          (`BLOCKING`) sur une plage de consultation de mêmes horaires — alors
          que c'est exactement ainsi qu'on déclare « je travaille l'après-midi,
          sauf formation ce jour-là ».

        L'égalité sur une colonne NULL doit signifier « les deux absents », ce
        que `IS NULL` exprime et que `== None` ne ferait pas en SQL.
        """
        conditions = [
            Disponibilite.praticien_id == praticien_id,
            Disponibilite.actif.is_(True),
            Disponibilite.heure_debut == heure_debut,
            Disponibilite.heure_fin == heure_fin,
            Disponibilite.type == type_plage,
            Disponibilite.jour_semaine == jour_semaine
            if jour_semaine is not None
            else Disponibilite.jour_semaine.is_(None),
            Disponibilite.date_specifique == date_specifique
            if date_specifique is not None
            else Disponibilite.date_specifique.is_(None),
            Disponibilite.cabinet_id == cabinet_id
            if cabinet_id is not None
            else Disponibilite.cabinet_id.is_(None),
        ]
        return (await db.execute(select(Disponibilite).where(*conditions))).scalars().first()

    @staticmethod
    async def supprimer(
        db: AsyncSession,
        disponibilite_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Disponibilite:
        disponibilite = (
            await db.execute(
                select(Disponibilite).where(Disponibilite.id == disponibilite_id)
            )
        ).scalar_one_or_none()
        if disponibilite is None:
            raise EntityNotFoundException("Disponibilité", disponibilite_id)

        await AuditService.log_action(
            db=db,
            action="DISPONIBILITE_DELETE",
            resource_type="Disponibilite",
            resource_id=str(disponibilite.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "plage": f"{disponibilite.heure_debut:%H:%M}-{disponibilite.heure_fin:%H:%M}",
                "type": disponibilite.type,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.delete(disponibilite)
        await db.commit()
        return disponibilite

    # ------------------------------------------------------------- créneaux
    @staticmethod
    async def creneaux(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        jour: date,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
        duree_minutes: int = DUREE_CRENEAU_MINUTES,
    ) -> Dict[str, Any]:
        """
        Créneaux proposables au patient pour une date.

        Renvoie aussi les compteurs et un avertissement : un praticien sans
        disponibilité ne doit pas laisser croire qu'il n'est pas joignable, il
        faut que la panne soit visible.
        """
        await PraticienService.obtenir(db, praticien_id)

        stmt = select(Disponibilite).where(
            Disponibilite.praticien_id == praticien_id,
            Disponibilite.actif.is_(True),
        )
        if cabinet_id:
            stmt = stmt.where(
                (Disponibilite.cabinet_id == cabinet_id)
                | (Disponibilite.cabinet_id.is_(None))
            )
        toutes = list((await db.execute(stmt)).scalars().all())

        # Une plage d'exception ne concerne qu'un jour : la filter ici évite au
        # calcul de créneaux inutiles, et rend les compteurs exacts.
        jour_cible = jour.weekday()
        pertinent = [
            d
            for d in toutes
            if d.date_specifique is None
            or d.date_specifique == jour
        ]

        creneaux = creneaux_proposables(pertinent, jour, duree_minutes)

        nb_consultation = sum(1 for d in pertinent if not est_bloquante(d.type))
        nb_bloquantes = sum(1 for d in pertinent if est_bloquante(d.type))

        avertissement = None
        if not pertinent:
            avertissement = (
                "Aucune disponibilité déclarée pour ce praticien à cette date : "
                "rien ne peut être proposé au patient. Vérifiez ses disponibilités "
                "(et ses absences)."
            )
        elif not creneaux:
            # Trois cas distincts, et tous doivent être expliqués : sinon une
            # liste vide passe pour « agenda complet » alors qu'il s'agit d'une
            # panne de configuration ou d'un jour d'absence.
            if nb_consultation:
                avertissement = (
                    "Le praticien travaille ce jour-là, mais toutes ses plages sont "
                    "bloquées (congé, remplacement). Aucun créneau n'est proposable."
                )
            else:
                avertissement = (
                    "Ce jour n'est déclaré qu'en indisponibilité : le praticien a "
                    "signé une absence, aucune plage de consultation n'est ouverte."
                )

        return {
            "date": jour,
            "praticien_id": praticien_id,
            "cabinet_id": cabinet_id,
            "creneaux": [list(p) for p in compacter(creneaux)],
            "duree_minutes": duree_minutes,
            "nb_plages_consultation": nb_consultation,
            "nb_plages_bloquantes": nb_bloquantes,
            "avertissement": avertissement,
        }


# ==============================================================================
# RÉFÉRENTIEL (contrat de formulaires)
# ==============================================================================

def referentiel_jours() -> Dict[str, Any]:
    """
    Jours et types de plage exposés au frontend.

    Publier la convention (0 = lundi) évite que chaque écran la redécouvre, et
    donc qu'un frontend et un backend divergent sur le jour de la semaine.
    """
    return {
        "jours": [
            {
                "index": i,
                "code": JOURS_COURTS[i],
                "libelle": JOURS_SEMAINE[i],
            }
            for i in range(7)
        ],
        "types_plage": [
            {"code": code, "libelle": LIBELLES_TYPE_PLAGE[code]}
            for code in TYPES_PLAGE
        ],
        "duree_creneau_minutes": DUREE_CRENEAU_MINUTES,
    }


def vers_reponse_disponibilite(d: Disponibilite) -> Dict[str, Any]:
    """Sérialise une disponibilité en précalculant ce que l'UI doit afficher."""
    from src.common.disponibilite import libelle_jour

    if d.jour_semaine is not None:
        libelle = libelle_jour(d.jour_semaine)
    elif d.date_specifique is not None:
        libelle = d.date_specifique.strftime("%d/%m/%Y")
    else:
        libelle = None

    return {
        "id": d.id,
        "praticien_id": d.praticien_id,
        "cabinet_id": d.cabinet_id,
        "jour_semaine": d.jour_semaine,
        "date_specifique": d.date_specifique,
        "heure_debut": d.heure_debut,
        "heure_fin": d.heure_fin,
        "type": d.type,
        "actif": d.actif,
        "duree_minutes": minutes_de(d.heure_fin) - minutes_de(d.heure_debut),
        "libelle_jour": libelle,
        "plage": f"{d.heure_debut:%H:%M} - {d.heure_fin:%H:%M}",
    }


def vers_reponse_praticien(p: Praticien) -> Dict[str, Any]:
    """
    Sérialise un praticien.

    Les trois relations lues ici (`utilisateur`, `rattachements`,
    `disponibilites`) doivent être chargées en amont par `selectinload`. Un
    `getattr(p, "disponibilites", [])` de secours ne protège pas : l'attribut
    existe sur la classe, donc l'accès part quand même en lazy-load.
    """
    utilisateur = p.utilisateur
    return {
        "id": p.id,
        "utilisateur_id": p.utilisateur_id,
        "titre": p.titre,
        "specialite": p.specialite,
        "numero_ordre": p.numero_ordre,
        "signature_url": p.signature_url,
        "bio": p.bio,
        "prenom": utilisateur.prenom if utilisateur else None,
        "nom": utilisateur.nom if utilisateur else None,
        "email": utilisateur.email if utilisateur else None,
        "compte_actif": bool(utilisateur.actif) if utilisateur else False,
        "cabinets": [r.cabinet_id for r in p.rattachements if r.actif],
        "nb_disponibilites": len(p.disponibilites),
    }
