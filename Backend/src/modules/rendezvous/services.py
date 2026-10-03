"""
Services métier du module Rendez-vous (D2B).

Ce module installe l'agenda : qui vient, quand, chez qui, dans quel fauteuil, et
ce qui empêche qu'on ne double-booke.

Quatre décisions structurantes, qui ne se déduisent pas du code :

1. **La base est l'arbitre des conflits, pas le code.** Une contrainte
   d'exclusion PostgreSQL interdit deux rendez-vous qui se chevauchent pour un
   même praticien, et deux occupations qui se chevauchent pour un même fauteuil.
   Une vérification applicative ne peut pas empêcher deux secrétaires de valider
   au même instant : entre son test et son INSERT, l'autre passe.

   Le service fait *malgré tout* une vérification préalable, non pour protéger la
   base mais pour produire un message exploitable : une violation de contrainte
   ne dit pas « Mme Diop, détartrage ». Une fois le contrôle passé, la
   contrainte reste la garantie.

2. **L'occupation d'un fauteuil tient dans UNE seule table** (`creneaux_fauteuil`),
   qu'elle vienne d'un rendez-vous ou d'une panne. Répartir les deux cas entre
   deux tables obligerait à revérifier en croisant, et rouvrirait la fenêtre de
   course qu'on vient de fermer.

3. **Hors disponibilités déclarées, on permet — mais on le signale.** Un cabinet
   qui n'a pas encore saisi ses horaires ne doit pas pouvoir prendre un
   rendez-vous, et une urgence ne peut pas attendre que l'administrateur ait
   fini sa saisie. Le rendez-vous est donc accepté, et la réponse porte
   `hors_disponibilites: true` pour que l'interface le montre. Les CONFLITS, en
   revanche, restent bloquants : ceux-là sont physiques.

4. **Le cycle de vie est fermé.** Un rendez-vous annulé ne se rouvre pas ; on en
   crée un autre. Les transitions vivent dans `src/common/rendezvous.py`.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.disponibilite import (
    DUREE_CRENEAU_MINUTES,
    creneaux_proposables,
    minutes_de,
)
from src.common.rendezvous import (
    ABSENT,
    ANNULE,
    BLOCAGE_RENDEZ_VOUS,
    CONFIRME,
    EN_CONSULTATION,
    EN_SALLE_ATTENTE,
    LIBELLES_MOTIF_BLOCAGE,
    LIBELLES_STATUT,
    MOTIFS_BLOCAGE,
    MOTIFS_INDISPONIBILITE,
    PLANIFIE,
    STATUTS_ACTIFS,
    STATUTS_EXCLUS_DU_CONFLIT,
    TERMINEE,
    TransitionInterdite,
    chevauchent,
    duree_minutes,
    formater_creneau,
    transitions_possibles,
    verifier_transition,
)
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.rendezvous.schemas import (
    AgendaResponse,
    BlocageFauteuilCreate,
    CreneauLibre,
    RendezVousCreate,
    RendezVousUpdate,
)
from src.modules.tenants.models import (
    Cabinet,
    CabinetPraticien,
    Consultation,
    CreneauFauteuil,
    Disponibilite,
    Fauteuil,
    Patient,
    Praticien,
    MotifBlocageFauteuilEnum,
    RendezVous,
    Salle,
    Utilisateur,
)

logger = structlog.get_logger(__name__)

class ConflitRendezVousException(BusinessRuleViolationException):
    """
    Un créneau demandé est déjà occupé.

    Distinguée des autres violations métier parce que le frontend doit pouvoir
    réagir différemment : ici, il propose d'autres horaires au patient au lieu
    d'afficher une erreur de saisie.
    """

    def __init__(self, conflits: List[Dict[str, Any]], message: Optional[str] = None):
        if message is None:
            message = _formater_message_conflits(conflits)
        super().__init__(
            message=message,
            code="CRENEAU_DEJA_OCCUPE",
            details={"conflits": conflits},
        )
        self.conflits = conflits


def _formater_message_conflits(conflits: Sequence[Dict[str, Any]]) -> str:
    """Un message qui nomme l'obstacle, pas seulement son existence."""
    if not conflits:
        return "Créneau déjà occupé."

    lignes = []
    for conflit in conflits:
        ressource = "praticien" if conflit["ressource"] == "PRATICIEN" else "fauteuil"
        qui = conflit.get("patient_nom") or "un autre patient"
        motif = f" — {conflit['motif']}" if conflit.get("motif") else ""
        lignes.append(
            f"{ressource.capitalize()} occupé {conflit['debut']:%H:%M}-{conflit['fin']:%H:%M} "
            f"par {qui}{motif}"
        )
    return " ; ".join(lignes) + "."


class RendezVousService:
    # ======================================================================
    # Aides
    # ======================================================================
    @staticmethod
    def _vers_reponse(
        rendez_vous: RendezVous, *, hors_disponibilites: bool = False
    ) -> Dict[str, Any]:
        """
        Sérialise un rendez-vous avec son identité pré-jointe.

        Toutes les relations lues ici doivent être chargées par `_charger` ou
        `lister` : le module ne fait aucune requête par rendez-vous.
        """
        patient = rendez_vous.patient
        praticien = rendez_vous.praticien
        fauteuil = (
            rendez_vous.creneaux_fauteuil[0].fauteuil if rendez_vous.creneaux_fauteuil else None
        )
        consultation = rendez_vous.consultation

        return {
            "id": rendez_vous.id,
            "patient_id": rendez_vous.patient_id,
            "cabinet_id": rendez_vous.cabinet_id,
            "praticien_id": rendez_vous.praticien_id,
            "debut": rendez_vous.debut,
            "fin": rendez_vous.fin,
            "duree_minutes": duree_minutes(rendez_vous.debut, rendez_vous.fin),
            "motif": rendez_vous.motif,
            "type_motif": rendez_vous.type_motif.value,
            "statut": rendez_vous.statut.value,
            "statut_libelle": LIBELLES_STATUT[rendez_vous.statut.value],
            "notes": rendez_vous.notes,
            "motif_annulation": rendez_vous.motif_annulation,
            "date_statut": rendez_vous.date_statut,
            "fauteuil_id": fauteuil.id if fauteuil else None,
            "consultation_id": consultation.id if consultation else None,
            "patient_nom": patient.nom if patient else None,
            "patient_prenom": patient.prenom if patient else None,
            "numero_dossier": patient.numero_dossier if patient else None,
            "patient_telephone": patient.telephone_1 if patient else None,
            "praticien_nom": praticien.utilisateur.nom if praticien and praticien.utilisateur else None,
            "praticien_titre": praticien.titre if praticien else None,
            "cabinet_nom": rendez_vous.cabinet.nom if rendez_vous.cabinet else None,
            "fauteuil_numero": fauteuil.numero if fauteuil else None,
            "hors_disponibilites": hors_disponibilites,
            "transitions_possibles": sorted(transitions_possibles(rendez_vous.statut.value)),
        }

    @staticmethod
    async def _charger(db: AsyncSession, rendez_vous_id: uuid.UUID) -> RendezVous:
        stmt = (
            select(RendezVous)
            .options(
                selectinload(RendezVous.patient),
                selectinload(RendezVous.praticien).selectinload(Praticien.utilisateur),
                selectinload(RendezVous.cabinet),
                selectinload(RendezVous.creneaux_fauteuil).selectinload(
                    CreneauFauteuil.fauteuil
                ),
                selectinload(RendezVous.consultation),
            )
            # `expire_on_commit=False` laisse les collections en cache dans
            # l'identity map : sans `populate_existing`, un fauteuil retiré
            # par le traitement courant resterait visible.
            .execution_options(populate_existing=True)
            .where(RendezVous.id == rendez_vous_id)
        )
        rendez_vous = (await db.execute(stmt)).scalar_one_or_none()
        if rendez_vous is None:
            raise EntityNotFoundException("Rendez-vous", rendez_vous_id)
        return rendez_vous

    # ======================================================================
    # VÉRIFICATIONS PRÉALABLES
    # ======================================================================
    @staticmethod
    async def _verifier_patient(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is None:
            raise EntityNotFoundException("Patient", patient_id)
        if patient.archive:
            raise BusinessRuleViolationException(
                f"Le dossier {patient.numero_dossier} est archivé : pas de nouveau "
                "rendez-vous. Réactivez le dossier si le patient revient.",
                code="PATIENT_ARCHIVE",
            )
        return patient

    @staticmethod
    async def _resoudre_cabinet(
        db: AsyncSession, praticien_id: uuid.UUID, cabinet_id: Optional[uuid.UUID]
    ) -> Tuple[Cabinet, Praticien]:
        """
        Détermine le site, et vérifie que le praticien y travaille.

        Un praticien rattaché à un seul site n'a pas à être désigné à chaque
        rendez-vous ; à plusieurs sites, l'ambiguïté est refusée plutôt que
        devinée, comme le fait déjà `ConsultationService`.
        """
        praticien = (
            await db.execute(
                select(Praticien)
                .options(selectinload(Praticien.utilisateur))
                .where(Praticien.id == praticien_id)
            )
        ).scalar_one_or_none()
        if praticien is None:
            raise EntityNotFoundException("Praticien", praticien_id)

        if cabinet_id is not None:
            cabinet = (
                await db.execute(
                    select(Cabinet).where(Cabinet.id == cabinet_id, Cabinet.actif.is_(True))
                )
            ).scalar_one_or_none()
            if cabinet is None:
                raise EntityNotFoundException("Cabinet", cabinet_id)
            return cabinet, praticien

        cabinets = list(
            (
                await db.execute(
                    select(Cabinet)
                    .join(CabinetPraticien, CabinetPraticien.cabinet_id == Cabinet.id)
                    .where(
                        CabinetPraticien.praticien_id == praticien_id,
                        CabinetPraticien.actif.is_(True),
                        Cabinet.actif.is_(True),
                    )
                )
            ).scalars().all()
        )
        if not cabinets:
            raise BusinessRuleViolationException(
                "Ce praticien n'est rattaché à aucun site actif : impossible de lui "
                "attribuer un rendez-vous. Rattachez-le d'abord à un cabinet.",
                code="PRATICIEN_NON_RATTACHE",
            )
        if len(cabinets) > 1:
            raise BusinessRuleViolationException(
                f"{praticien.utilisateur.nom} travaille sur {len(cabinets)} sites : "
                "précisez `cabinet_id`.",
                code="CABINET_AMBIGU",
            )
        return cabinets[0], praticien

    @staticmethod
    async def _verifier_fauteuil(
        db: AsyncSession, fauteuil_id: uuid.UUID, cabinet_id: uuid.UUID
    ) -> Fauteuil:
        """
        Vérifie qu'un fauteuil est actif ET situé dans le site du rendez-vous.

        Réserver un fauteuil d'un autre site produirait un rendez-vous impossible
        à honorer.

        La salle est lue depuis la jointure, pas paresseusement : `fauteuil.salle`
        n'est pas chargée, et y accéder hors d'un `greenlet` lèverait
        `MissingGreenlet`.
        """
        row = (
            await db.execute(
                select(Fauteuil, Salle.cabinet_id)
                .join(Salle, Salle.id == Fauteuil.salle_id)
                .where(Fauteuil.id == fauteuil_id)
            )
        ).one_or_none()
        if row is None:
            raise EntityNotFoundException("Fauteuil", fauteuil_id)
        fauteuil, cabinet_du_fauteuil = row

        if not fauteuil.actif:
            raise BusinessRuleViolationException(
                f"Le fauteuil « {fauteuil.numero} » est désactivé : il n'accepte plus "
                "de rendez-vous.",
                code="FAUTEUIL_INACTIF",
            )
        if cabinet_du_fauteuil != cabinet_id:
            raise BusinessRuleViolationException(
                f"Le fauteuil « {fauteuil.numero} » n'appartient pas au site du "
                "rendez-vous.",
                code="FAUTEUIL_AUTRE_CABINET",
            )
        return fauteuil

    # ======================================================================
    # DÉTECTION DE CONFLITS
    # ======================================================================
    @staticmethod
    async def _conflits(
        db: AsyncSession,
        *,
        praticien_id: uuid.UUID,
        debut: datetime,
        fin: datetime,
        fauteuil_id: Optional[uuid.UUID] = None,
        exclure_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Cherche les occupations qui se chevauchent, praticien ET fauteuil.

        Sert à produire un message exploitable. La garantie, elle, vient de la
        contrainte d'exclusion : si un conflit passe d'ici, c'est que la base
        l'avait déjà vu.
        """
        conflits: List[Dict[str, Any]] = []

        stmt = (
            select(RendezVous, Patient)
            .join(Patient, Patient.id == RendezVous.patient_id)
            .where(
                RendezVous.praticien_id == praticien_id,
                RendezVous.statut.notin_(STATUTS_EXCLUS_DU_CONFLIT),
                RendezVous.debut < fin,
                debut < RendezVous.fin,
            )
        )
        if exclure_id:
            stmt = stmt.where(RendezVous.id != exclure_id)

        for rendez_vous, patient in (await db.execute(stmt)).all():
            conflits.append(
                {
                    "ressource": "PRATICIEN",
                    "id": str(rendez_vous.id),
                    "motif": rendez_vous.motif,
                    "patient_nom": patient.nom,
                    "patient_prenom": patient.prenom,
                    "numero_dossier": patient.numero_dossier,
                    "debut": rendez_vous.debut.isoformat(),
                    "fin": rendez_vous.fin.isoformat(),
                    "statut": rendez_vous.statut.value,
                }
            )

        if fauteuil_id is not None:
            stmt_f = (
                select(CreneauFauteuil, Patient, RendezVous)
                .outerjoin(
                    RendezVous, RendezVous.id == CreneauFauteuil.rendez_vous_id
                )
                .outerjoin(Patient, Patient.id == RendezVous.patient_id)
                .where(
                    CreneauFauteuil.fauteuil_id == fauteuil_id,
                    CreneauFauteuil.debut < fin,
                    debut < CreneauFauteuil.fin,
                )
            )
            if exclure_id:
                # L'occupation du rendez-vous qu'on déplace ne doit pas se
                # conflicter avec lui-même.
                stmt_f = stmt_f.where(
                    (CreneauFauteuil.rendez_vous_id.is_(None))
                    | (CreneauFauteuil.rendez_vous_id != exclure_id)
                )

            for occupation, patient, rendez_vous in (await db.execute(stmt_f)).all():
                if rendez_vous is not None:
                    motif = rendez_vous.motif
                elif occupation.motif.value in MOTIFS_INDISPONIBILITE:
                    motif = occupation.motif_detail or LIBELLES_MOTIF_BLOCAGE[
                        occupation.motif.value
                    ]
                else:
                    motif = occupation.motif.value
                conflits.append(
                    {
                        "ressource": "FAUTEUIL",
                        "id": str(occupation.id),
                        "motif": motif,
                        "patient_nom": patient.nom if patient else None,
                        "patient_prenom": patient.prenom if patient else None,
                        "numero_dossier": patient.numero_dossier if patient else None,
                        "debut": occupation.debut.isoformat(),
                        "fin": occupation.fin.isoformat(),
                        "statut": occupation.motif.value,
                    }
                )

        return conflits

    @staticmethod
    async def _detecter_conflits(
        db: AsyncSession,
        *,
        praticien_id: uuid.UUID,
        debut: datetime,
        fin: datetime,
        fauteuil_id: Optional[uuid.UUID] = None,
        exclure_id: Optional[uuid.UUID] = None,
    ) -> None:
        conflits = await RendezVousService._conflits(
            db,
            praticien_id=praticien_id,
            debut=debut,
            fin=fin,
            fauteuil_id=fauteuil_id,
            exclure_id=exclure_id,
        )
        if conflits:
            raise ConflitRendezVousException(conflits)

    # ======================================================================
    # HORS DISPONIBILITÉS DÉCLARÉES
    # ======================================================================
    @staticmethod
    async def _hors_disponibilites(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        debut: datetime,
        fin: datetime,
        cabinet_id: uuid.UUID,
    ) -> bool:
        """
        Le créneau sort-il des disponibilités déclarées du praticien ?

        Simple, et volontairement approximatif : on vérifie l'appartenance du
        créneau à l'union des créneaux proposables, pas un découpage au pas de
        30 minutes. Une disponibilité de 09:00-12:00 découpée donne des
        créneaux de 30 min ; un rendez-vous de 45 minutes à 11:30-12:15 déborde
        réellement, et doit être signalé.
        """
        jour = debut.date()
        stmt = select(Disponibilite).where(
            Disponibilite.praticien_id == praticien_id,
            Disponibilite.actif.is_(True),
            (Disponibilite.cabinet_id == cabinet_id) | (Disponibilite.cabinet_id.is_(None)),
        )
        disponibilites = list((await db.execute(stmt)).scalars().all())

        if not disponibilites:
            return True

        # On demande un créneau unique couvrant tout le rendez-vous : s'il
        # existe, le rendez-vous tient dans une plage déclarée.
        debut_m = minutes_de(debut.time())
        fin_m = minutes_de(fin.time()) or 24 * 60

        for dispo in disponibilites:
            if dispo.date_specifique is not None and dispo.date_specifique != jour:
                continue
            if dispo.date_specifique is None and dispo.jour_semaine != jour.weekday():
                continue
            # `Disponibilite.type` est une colonne String (D2A), pas un enum
            # PostgreSQL : on compare la chaîne, pas un `.value`.
            if dispo.type in MOTIFS_INDISPONIBILITE:
                continue
            d = minutes_de(dispo.heure_debut)
            f = minutes_de(dispo.heure_fin)
            if d <= debut_m and fin_m <= f:
                return False
        return True

    # ======================================================================
    # CRÉATION
    # ======================================================================
    @staticmethod
    async def creer(
        db: AsyncSession,
        data: RendezVousCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[RendezVous, bool]:
        """
        Prend un rendez-vous (UC9).

        Renvoie le rendez-vous et un booléen « hors disponibilités déclarées » :
        l'appelant doit propager l'avertissement, sinon une prise de rendez-vous
        hors horaire resterait invisible.
        """
        await RendezVousService._verifier_patient(db, data.patient_id)
        cabinet, _ = await RendezVousService._resoudre_cabinet(
            db, data.praticien_id, data.cabinet_id
        )

        fin = data.fin
        if data.fauteuil_id:
            await RendezVousService._verifier_fauteuil(db, data.fauteuil_id, cabinet.id)

        # Contrôle préalable, pour le message. La base reste l'arbitre.
        await RendezVousService._detecter_conflits(
            db,
            praticien_id=data.praticien_id,
            debut=data.debut,
            fin=fin,
            fauteuil_id=data.fauteuil_id,
        )

        hors_disponibilites = await RendezVousService._hors_disponibilites(
            db, data.praticien_id, data.debut, fin, cabinet.id
        )

        rendez_vous = RendezVous(
            patient_id=data.patient_id,
            cabinet_id=cabinet.id,
            praticien_id=data.praticien_id,
            debut=data.debut,
            fin=fin,
            motif=data.motif.strip(),
            type_motif=data.type_motif,
            statut=data.statut,
            notes=data.notes,
        )
        db.add(rendez_vous)

        try:
            await db.flush()
            if data.fauteuil_id:
                db.add(
                    CreneauFauteuil(
                        fauteuil_id=data.fauteuil_id,
                        rendez_vous_id=rendez_vous.id,
                        debut=data.debut,
                        fin=fin,
                        motif=BLOCAGE_RENDEZ_VOUS,
                        motif_detail=data.motif.strip()[:255],
                    )
                )
                await db.flush()
        except IntegrityError:
            # La contrainte d'exclusion a parlé : deux requêtes se sont
            # croisées. On revient au contrôle applicatif, qui sait nommer
            # l'obstacle.
            await db.rollback()
            conflits = await RendezVousService._conflits(
                db,
                praticien_id=data.praticien_id,
                debut=data.debut,
                fin=fin,
                fauteuil_id=data.fauteuil_id,
            )
            if conflits:
                raise ConflitRendezVousException(conflits) from None
            raise

        await AuditService.log_action(
            db=db,
            action="RENDEZ_VOUS_CREATE",
            resource_type="RendezVous",
            resource_id=str(rendez_vous.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(data.patient_id),
                "praticien_id": str(data.praticien_id),
                "debut": data.debut.isoformat(),
                "duree_minutes": data.duree_minutes,
                "fauteuil_id": str(data.fauteuil_id) if data.fauteuil_id else None,
                "hors_disponibilites": hors_disponibilites,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()

        logger.info(
            "rendez_vous_cree",
            rendez_vous_id=str(rendez_vous.id),
            hors_disponibilites=hors_disponibilites,
        )
        return await RendezVousService._charger(db, rendez_vous.id), hors_disponibilites

    # ======================================================================
    # REPORT
    # ======================================================================
    @staticmethod
    async def planifier(
        db: AsyncSession,
        rendez_vous_id: uuid.UUID,
        debut: datetime,
        duree_minutes_: int,
        auteur: Optional[Utilisateur] = None,
        *,
        fauteuil_id: Optional[uuid.UUID] = None,
        motif_report: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RendezVous:
        """
        Déplace un rendez-vous.

        Refuse un rendez-vous déjà commencé ou terminé : un patient passé dans
        la salle d'attente ne se reprogramme pas, il se chasede... se rappelle.
        """
        rendez_vous = await RendezVousService._charger(db, rendez_vous_id)

        if rendez_vous.statut.value not in (PLANIFIE, CONFIRME):
            raise BusinessRuleViolationException(
                f"Seul un rendez-vous planifié ou confirmé peut être reporté "
                f"(statut actuel : {LIBELLES_STATUT[rendez_vous.statut.value]}).",
                code="REPORT_NON_AUTORISE",
            )

        fin = debut + timedelta(minutes=duree_minutes_)

        # Le fauteuil est soit celui demandé, soit celui déjà réservé.
        fauteuil_arbitre = fauteuil_id
        if fauteuil_arbitre is None:
            fauteuil_arbitre = (
                rendez_vous.creneaux_fauteuil[0].fauteuil_id
                if rendez_vous.creneaux_fauteuil
                else None
            )
        if fauteuil_arbitre:
            await RendezVousService._verifier_fauteuil(
                db, fauteuil_arbitre, rendez_vous.cabinet_id
            )

        await RendezVousService._detecter_conflits(
            db,
            praticien_id=rendez_vous.praticien_id,
            debut=debut,
            fin=fin,
            fauteuil_id=fauteuil_arbitre,
            exclure_id=rendez_vous.id,
        )

        ancien = formater_creneau(rendez_vous.debut, rendez_vous.fin)

        rendez_vous.debut = debut
        rendez_vous.fin = fin

        for occupation in list(rendez_vous.creneaux_fauteuil):
            await db.delete(occupation)
        await db.flush()

        if fauteuil_arbitre:
            db.add(
                CreneauFauteuil(
                    fauteuil_id=fauteuil_arbitre,
                    rendez_vous_id=rendez_vous.id,
                    debut=debut,
                    fin=fin,
                    motif=BLOCAGE_RENDEZ_VOUS,
                    motif_detail=rendez_vous.motif[:255],
                )
            )

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            conflits = await RendezVousService._conflits(
                db,
                praticien_id=rendez_vous.praticien_id,
                debut=debut,
                fin=fin,
                fauteuil_id=fauteuil_arbitre,
                exclure_id=rendez_vous.id,
            )
            if conflits:
                raise ConflitRendezVousException(conflits) from None
            raise

        await AuditService.log_action(
            db=db,
            action="RENDEZ_VOUS_REPLANIFIE",
            resource_type="RendezVous",
            resource_id=str(rendez_vous.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "ancien_creneau": ancien,
                "nouveau_creneau": formater_creneau(debut, fin),
                "motif": motif_report,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return await RendezVousService._charger(db, rendez_vous.id)

    # ======================================================================
    # CYCLE DE VIE
    # ======================================================================
    @staticmethod
    async def changer_statut(
        db: AsyncSession,
        rendez_vous_id: uuid.UUID,
        nouveau_statut: str,
        auteur: Optional[Utilisateur] = None,
        *,
        motif: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RendezVous:
        """
        Fait avancer le rendez-vous dans son cycle de vie.

        Un rendez-vous annulé ou manqué libère son créneau **sans rien faire** :
        la contrainte d'exclusion ignore ces statuts. C'est le comportement
        attendu et il ne doit pas être contourné par une suppression.
        """
        rendez_vous = await RendezVousService._charger(db, rendez_vous_id)
        actuel = rendez_vous.statut.value

        try:
            verifier_transition(actuel, nouveau_statut)
        except TransitionInterdite as exc:
            raise BusinessRuleViolationException(
                exc.message, code=exc.code, details={"depuis": actuel, "vers": nouveau_statut}
            ) from None

        if nouveau_statut == ANNULE and not (motif or "").strip():
            raise BusinessRuleViolationException(
                "Indiquez la raison de l'annulation.",
                code="MOTIF_ANNULATION_REQUIS",
            )

        rendez_vous.statut = nouveau_statut
        rendez_vous.date_statut = datetime.now(timezone.utc)
        if nouveau_statut == ANNULE:
            rendez_vous.motif_annulation = (motif or "").strip()

        await db.flush()

        await AuditService.log_action(
            db=db,
            action=f"RENDEZ_VOUS_{nouveau_statut}",
            resource_type="RendezVous",
            resource_id=str(rendez_vous.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"depuis": actuel, "vers": nouveau_statut, "motif": motif},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        logger.info("rendez_vous_statut", rendez_vous_id=str(rendez_vous.id), vers=nouveau_statut)
        return await RendezVousService._charger(db, rendez_vous_id)

    # ======================================================================
    # OUVERTURE DE CONSULTATION
    # ======================================================================
    @staticmethod
    async def demarrer_consultation(
        db: AsyncSession,
        rendez_vous_id: uuid.UUID,
        auteur: Optional[Utilisateur],
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Consultation:
        """
        Ouvre la consultation à partir du rendez-vous (le patient est en salle).

        C'est le seul endroit où `consultations.rendez_vous_id` et
        `consultations.fauteuil_id` sont posés : le fauteuil est repris de
        l'occupation du rendez-vous, donc l'Agenda et le Dossier ne peuvent pas
        diverger sur le lieu du soin.

        Le rendez-vous passe à EN_CONSULTATION et **sera terminé par le module
        Consultations** quand la consultation sera close : un rendez-vous ne se
        termine pas tout seul.
        """
        from src.modules.consultations.services import ConsultationService
        from src.modules.consultations.schemas import ConsultationCreate

        rendez_vous = await RendezVousService._charger(db, rendez_vous_id)
        statut = rendez_vous.statut.value

        if statut in (EN_CONSULTATION, TERMINEE):
            raise BusinessRuleViolationException(
                "Ce rendez-vous a déjà donné lieu à une consultation.",
                code="CONSULTATION_DEJA_OUVERTE",
            )
        if statut in (ANNULE, ABSENT):
            raise BusinessRuleViolationException(
                f"Un rendez-vous « {LIBELLES_STATUT[statut].lower()} » ne peut pas "
                "ouvrir de consultation.",
                code="RENDEZ_VOUS_NON_JOIGNABLE",
            )
        if statut == PLANIFIE:
            raise BusinessRuleViolationException(
                "Confirmez d'abord le rendez-vous : un patient qui n'a pas confirmé "
                "peut ne pas venir, et on n'ouvre pas une consultation dans le vide.",
                code="RENDEZ_VOUS_NON_CONFIRME",
            )

        consultation_existante = (
            await db.execute(
                select(Consultation).where(Consultation.rendez_vous_id == rendez_vous_id)
            )
        ).scalar_one_or_none()
        if consultation_existante is not None:
            raise BusinessRuleViolationException(
                "Une consultation est déjà rattachée à ce rendez-vous.",
                code="CONSULTATION_DEJA_OUVERTE",
                details={"consultation_id": str(consultation_existante.id)},
            )

        # Le statut passe à EN_CONSULTATION AVANT l'ouverture : `demarrer`
        # valide lui-même son propre `commit`, qui emporte donc ce changement
        # avec lui. Les deux écritures restent cohérents même si la ligne suivante
        # échoue : le rendez-vous sera « en consultation » sans lien, ce que le
        # module Consultations sait détecter.
        rendez_vous.statut = EN_CONSULTATION
        rendez_vous.date_statut = datetime.now(timezone.utc)
        await db.flush()

        consultation = await ConsultationService.demarrer(
            db,
            ConsultationCreate(
                patient_id=rendez_vous.patient_id,
                cabinet_id=rendez_vous.cabinet_id,
                motif=rendez_vous.motif,
                type_motif=rendez_vous.type_motif.value,
            ),
            auteur,
            praticien_id=rendez_vous.praticien_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        fauteuil_id = (
            rendez_vous.creneaux_fauteuil[0].fauteuil_id
            if rendez_vous.creneaux_fauteuil
            else None
        )
        consultation.fauteuil_id = fauteuil_id
        consultation.rendez_vous_id = rendez_vous.id

        await AuditService.log_action(
            db=db,
            action="RENDEZ_VOUS_CONSULTATION_OUVERTE",
            resource_type="RendezVous",
            resource_id=str(rendez_vous.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "consultation_id": str(consultation.id),
                "fauteuil_id": str(fauteuil_id) if fauteuil_id else None,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        logger.info(
            "consultation_ouverte_depuis_rdv",
            rendez_vous_id=str(rendez_vous.id),
            consultation_id=str(consultation.id),
        )
        return consultation

    # ======================================================================
    # MODIFICATIONS
    # ======================================================================
    @staticmethod
    async def modifier(
        db: AsyncSession,
        rendez_vous_id: uuid.UUID,
        data: RendezVousUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RendezVous:
        """Corrige le motif, les notes, ou change le fauteuil tant que rien n'a commencé."""
        rendez_vous = await RendezVousService._charger(db, rendez_vous_id)

        if rendez_vous.statut.value not in (PLANIFIE, CONFIRME):
            raise BusinessRuleViolationException(
                f"Un rendez-vous « {LIBELLES_STATUT[rendez_vous.statut.value].lower()} » "
                "n'est plus modifiable. Le dossier médical fait foi.",
                code="RENDEZ_VOUS_FIGE",
            )

        champs = data.model_dump(exclude_unset=True, exclude_none=True)

        if "fauteuil_id" in champs:
            nouveau = champs.pop("fauteuil_id")
            if nouveau is not None:
                await RendezVousService._verifier_fauteuil(
                    db, nouveau, rendez_vous.cabinet_id
                )
            for occupation in list(rendez_vous.creneaux_fauteuil):
                await db.delete(occupation)
            await db.flush()
            if nouveau is not None:
                db.add(
                    CreneauFauteuil(
                        fauteuil_id=nouveau,
                        rendez_vous_id=rendez_vous.id,
                        debut=rendez_vous.debut,
                        fin=rendez_vous.fin,
                        motif=BLOCAGE_RENDEZ_VOUS,
                        motif_detail=rendez_vous.motif[:255],
                    )
                )

        for champ, valeur in champs.items():
            setattr(rendez_vous, champ, valeur)

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise ConflitRendezVousException(
                await RendezVousService._conflits(
                    db,
                    praticien_id=rendez_vous.praticien_id,
                    debut=rendez_vous.debut,
                    fin=rendez_vous.fin,
                    fauteuil_id=data.fauteuil_id,
                    exclure_id=rendez_vous.id,
                )
            ) from None

        await AuditService.log_action(
            db=db,
            action="RENDEZ_VOUS_UPDATE",
            resource_type="RendezVous",
            resource_id=str(rendez_vous.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes=champs,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return await RendezVousService._charger(db, rendez_vous_id)

    # ======================================================================
    # LECTURE
    # ======================================================================
    @staticmethod
    async def obtenir(db: AsyncSession, rendez_vous_id: uuid.UUID) -> RendezVous:
        return await RendezVousService._charger(db, rendez_vous_id)

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        patient_id: Optional[uuid.UUID] = None,
        praticien_id: Optional[uuid.UUID] = None,
        cabinet_id: Optional[uuid.UUID] = None,
        fauteuil_id: Optional[uuid.UUID] = None,
        du: Optional[datetime] = None,
        au: Optional[datetime] = None,
        statuts: Optional[Sequence[str]] = None,
        limite: int = 100,
    ) -> List[RendezVous]:
        stmt = (
            select(RendezVous)
            .options(
                selectinload(RendezVous.patient),
                selectinload(RendezVous.praticien).selectinload(Praticien.utilisateur),
                selectinload(RendezVous.cabinet),
                selectinload(RendezVous.creneaux_fauteuil).selectinload(
                    CreneauFauteuil.fauteuil
                ),
                selectinload(RendezVous.consultation),
            )
            .order_by(RendezVous.debut)
        )
        if patient_id:
            stmt = stmt.where(RendezVous.patient_id == patient_id)
        if praticien_id:
            stmt = stmt.where(RendezVous.praticien_id == praticien_id)
        if cabinet_id:
            stmt = stmt.where(RendezVous.cabinet_id == cabinet_id)
        if du:
            stmt = stmt.where(RendezVous.fin > du)
        if au:
            stmt = stmt.where(RendezVous.debut < au)
        if statuts:
            stmt = stmt.where(RendezVous.statut.in_([s.upper() for s in statuts]))
        if fauteuil_id:
            stmt = stmt.where(
                RendezVous.id.in_(
                    select(CreneauFauteuil.rendez_vous_id).where(
                        CreneauFauteuil.fauteuil_id == fauteuil_id
                    )
                )
            )
        return list((await db.execute(stmt.limit(limite))).scalars().all())

    @staticmethod
    async def agenda(
        db: AsyncSession,
        jour: date,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
        praticien_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Journée d'agenda, rendez-vous ET indisponibilités de fauteuil.

        Les deux dans la même réponse parce qu'un planning qui ignore un fauteuil
        en réparation propose un créneau qu'on ne pourra pas honorer.
        """
        debut_jour = datetime.combine(jour, datetime.min.time(), tzinfo=timezone.utc)
        fin_jour = debut_jour + timedelta(days=1)

        rendez_vous = await RendezVousService.lister(
            db,
            cabinet_id=cabinet_id,
            praticien_id=praticien_id,
            du=debut_jour,
            au=fin_jour,
            limite=500,
        )

        stmt = (
            select(CreneauFauteuil, Fauteuil, Salle)
            .join(Fauteuil, Fauteuil.id == CreneauFauteuil.fauteuil_id)
            .join(Salle, Salle.id == Fauteuil.salle_id)
            .where(
                CreneauFauteuil.rendez_vous_id.is_(None),
                CreneauFauteuil.debut < fin_jour,
                debut_jour < CreneauFauteuil.fin,
            )
            .order_by(CreneauFauteuil.debut)
        )
        if cabinet_id:
            stmt = stmt.where(Salle.cabinet_id == cabinet_id)

        indisponibilites = []
        for occupation, fauteuil, salle in (await db.execute(stmt)).all():
            indisponibilites.append(
                {
                    "fauteuil_id": str(fauteuil.id),
                    "fauteuil_numero": fauteuil.numero,
                    "salle": salle.nom,
                    "debut": occupation.debut,
                    "fin": occupation.fin,
                    "motif": occupation.motif.value,
                    "motif_libelle": LIBELLES_MOTIF_BLOCAGE[occupation.motif.value],
                    "motif_detail": occupation.motif_detail,
                }
            )

        return {
            "date": debut_jour,
            "cabinet_id": cabinet_id,
            "rendez_vous": [RendezVousService._vers_reponse(r) for r in rendez_vous],
            "indisponibilites": indisponibilites,
            "nb_rendez_vous": sum(
                1 for r in rendez_vous if r.statut.value in STATUTS_ACTIFS
            ),
            "nb_annules": sum(
                1 for r in rendez_vous if r.statut.value in (ANNULE, ABSENT)
            ),
        }


class CreneauFauteuilService:
    """Immobilisations de fauteuil sans rendez-vous (panne, entretien)."""

    @staticmethod
    async def creer(
        db: AsyncSession,
        data: BlocageFauteuilCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CreneauFauteuil:
        fauteuil = (
            await db.execute(
                select(Fauteuil).where(Fauteuil.id == data.fauteuil_id)
            )
        ).scalar_one_or_none()
        if fauteuil is None:
            raise EntityNotFoundException("Fauteuil", data.fauteuil_id)

        fin = data.debut + timedelta(minutes=data.duree_minutes)
        occupation = CreneauFauteuil(
            fauteuil_id=data.fauteuil_id,
            debut=data.debut,
            fin=fin,
            # Le schéma expose une chaîne ; la colonne est un ENUM. Sans
            # conversion explicite, l'attribut ORM reste une chaîne tant que la
            # ligne n'a pas été rechargée, et `.motif.value` échoue ensuite.
            motif=MotifBlocageFauteuilEnum(data.motif),
            motif_detail=data.motif_detail,
        )
        db.add(occupation)

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            conflits = await CreneauFauteuilService._conflits(
                db, data.fauteuil_id, data.debut, fin
            )
            if conflits:
                raise ConflitRendezVousException(conflits) from None
            raise

        await AuditService.log_action(
            db=db,
            action="FAUTEUIL_BLOQUE",
            resource_type="CreneauFauteuil",
            resource_id=str(occupation.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "fauteuil": fauteuil.numero,
                "motif": data.motif,
                "plage": formater_creneau(data.debut, fin),
                "motif_detail": data.motif_detail,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        logger.info("fauteuil_bloque", fauteuil_id=str(data.fauteuil_id), motif=data.motif)
        return occupation

    @staticmethod
    async def _conflits(
        db: AsyncSession, fauteuil_id: uuid.UUID, debut: datetime, fin: datetime
    ) -> List[Dict[str, Any]]:
        stmt = select(CreneauFauteuil, RendezVous).where(
            CreneauFauteuil.fauteuil_id == fauteuil_id,
            CreneauFauteuil.debut < fin,
            debut < CreneauFauteuil.fin,
        ).outerjoin(RendezVous, RendezVous.id == CreneauFauteuil.rendez_vous_id)
        conflits = []
        for occupation, rendez_vous in (await db.execute(stmt)).all():
            conflits.append(
                {
                    "ressource": "FAUTEUIL",
                    "id": str(occupation.id),
                    "motif": (
                        occupation.motif.value
                        if rendez_vous is None
                        else rendez_vous.motif
                    ),
                    "debut": occupation.debut.isoformat(),
                    "fin": occupation.fin.isoformat(),
                    "statut": occupation.motif.value,
                }
            )
        return conflits

    @staticmethod
    async def supprimer(
        db: AsyncSession,
        creneau_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
    ) -> None:
        occupation = (
            await db.execute(
                select(CreneauFauteuil).where(CreneauFauteuil.id == creneau_id)
            )
        ).scalar_one_or_none()
        if occupation is None:
            raise EntityNotFoundException("Blocage de fauteuil", creneau_id)
        if occupation.rendez_vous_id is not None:
            raise BusinessRuleViolationException(
                "Ce créneau appartient à un rendez-vous : annulez le rendez-vous "
                "plutôt que de supprimer son occupation.",
                code="OCCUPATION_LIEE_A_UN_RDV",
            )

        await AuditService.log_action(
            db=db,
            action="FAUTEUIL_DEBLOQUE",
            resource_type="CreneauFauteuil",
            resource_id=str(creneau_id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"motif": occupation.motif.value},
        )
        await db.delete(occupation)
        await db.commit()


# ==============================================================================
# CRÉNEAUX LIBRES
# ==============================================================================

class CreneauService:
    """
    Créneaux réellement disponibles pour un praticien un jour donné.

    Complète le calcul de D2A (`DisponibiliteService.creneaux`), qui ne
    connaît que les heures déclarées : ici on retranche ce qui est DÉJÀ pris —
    rendez-vous du praticien, et indisponibilités des fauteuils.
    """

    @staticmethod
    async def libres(
        db: AsyncSession,
        praticien_id: uuid.UUID,
        jour: date,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
        duree_minutes_: int = DUREE_CRENEAU_MINUTES,
        exclure_id: Optional[uuid.UUID] = None,
    ) -> List[CreneauLibre]:
        from src.modules.cabinets.services import DisponibiliteService

        base = await DisponibiliteService.creneaux(
            db,
            praticien_id,
            jour,
            cabinet_id=cabinet_id,
            duree_minutes=duree_minutes_,
        )
        if not base["creneaux"]:
            return []

        debut_jour = datetime.combine(jour, datetime.min.time(), tzinfo=timezone.utc)
        fin_jour = debut_jour + timedelta(days=1)

        # Rendez-vous du praticien ce jour-là : ils rendent ses créneaux pris,
        # même sans fauteuil.
        stmt = select(RendezVous).where(
            RendezVous.praticien_id == praticien_id,
            RendezVous.statut.notin_(STATUTS_EXCLUS_DU_CONFLIT),
            RendezVous.debut < fin_jour,
            debut_jour < RendezVous.fin,
        )
        if cabinet_id:
            stmt = stmt.where(RendezVous.cabinet_id == cabinet_id)
        if exclure_id:
            stmt = stmt.where(RendezVous.id != exclure_id)
        rendez_vous = list((await db.execute(stmt)).scalars().all())

        # Fauteuils immobilisés dans ce site : sans fauteuil libre, le créneau
        # n'est pas proposable.
        fauteuils_libres = await CreneauService._fauteuils_libres(
            db, debut_jour, fin_jour, cabinet_id=cabinet_id
        )

        resultat: List[CreneauLibre] = []
        for debut_str, fin_str in base["creneaux"]:
            h, m = (int(x) for x in debut_str.split(":"))
            debut = debut_jour + timedelta(hours=h, minutes=m)
            h2, m2 = (int(x) for x in fin_str.split(":"))
            fin = debut_jour + timedelta(hours=h2, minutes=m2)

            pris = any(
                chevauchent(debut, fin, r.debut, r.fin) for r in rendez_vous
            )
            if pris:
                continue
            if fauteuils_libres == 0:
                continue
            resultat.append(CreneauLibre(debut=debut, fin=fin))

        return resultat

    @staticmethod
    async def _fauteuils_libres(
        db: AsyncSession,
        debut_jour: datetime,
        fin_jour: datetime,
        *,
        cabinet_id: Optional[uuid.UUID] = None,
    ) -> int:
        stmt = (
            select(func.count(func.distinct(Fauteuil.id)))
            .join(Salle, Salle.id == Fauteuil.salle_id)
            .outerjoin(
                CreneauFauteuil,
                (CreneauFauteuil.fauteuil_id == Fauteuil.id)
                & (CreneauFauteuil.debut < fin_jour)
                & (debut_jour < CreneauFauteuil.fin),
            )
            .where(Fauteuil.actif.is_(True), CreneauFauteuil.id.is_(None))
        )
        if cabinet_id:
            stmt = stmt.where(Salle.cabinet_id == cabinet_id)
        return int((await db.execute(stmt)).scalar_one())
