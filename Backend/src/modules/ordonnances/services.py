"""
Services métier des ordonnances (D1D).

Règles couvertes :
  RG07 — les allergies déclenchent des alertes automatiques
  RG08 — les contre-indications bloquent certains médicaments
  RG12 — traçabilité médico-légale de l'acte de prescription

Deux principes qui gouvernent tout le module :

1. **Distinguer « interdit » de « précaution ».** Un AINS chez une patiente
   enceinte est formellement interdit ; l'amoxicilline au premier trimestre est
   une précaution qui se discute. Traiter les deux de la même façon rendrait
   l'outil soit bloquant à l'excès, soit inerte.

2. **L'alerte ne bloque que ce qu'elle doit.** Le praticien garde la main :
   une contre-indication formelle interdit la ligne, une précaution exige une
   justification écrite qui devient une pièce du dossier.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.common.numerotation import generer_numero_ordonnance
from src.common.ordonnance import (
    INTERDIT,
    PRECAUTION,
    conditions_pour_contre_indications,
    detecter_interactions,
    evaluer_contre_indications,
    interactions_speciales,
    libelle_condition,
)
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.ordonnances.referentiel import FORMULAIRE_DENTAIRE
from src.modules.ordonnances.schemas import (
    AlertePrescription,
    LignePrescriptionCreate,
    MedicamentCreate,
    OrdonnanceCreate,
    OrdonnanceUpdate,
)
from src.modules.tenants.models import (
    AntecedentMedical,
    Consultation,
    DossierMedical,
    EtatGeneral,
    LignePrescription,
    MedicamentReferentiel,
    Patient,
    Prescription,
    Praticien,
    Utilisateur,
)

logger = structlog.get_logger(__name__)


class MedicamentService:
    """Référentiel médicamenteux du cabinet."""

    @staticmethod
    async def semer_formulaire(db: AsyncSession) -> int:
        """
        Insère le formulaire de départ (idempotent).

        L'identité d'une entrée est son DCI **tel qu'écrit**, pas sa molécule
        porteuse : `normaliser_dci` sert à comparer des interactions
        (« amoxicilline + acide clavulanique » se comporte comme
        « amoxicilline »), mais pas à identifier un produit. Utiliser la clé
        normalisée ici ferait perdre les règles propres à une association, qui
        ne seraient alors jamais semées.
        """
        existantes = {
            d.dci.strip().lower(): d
            for d in (await db.execute(select(MedicamentReferentiel))).scalars().all()
        }

        creations = 0
        for entree in FORMULAIRE_DENTAIRE:
            cle = entree["dci"].strip().lower()
            if cle in existantes:
                # Le formulaire fait autorité : on met à jour les règles.
                # Une règle retirée doit disparaître, sinon elle bloquerait à tort.
                existantes[cle].contre_indications = entree["contre_indications"]
                existantes[cle].precautions = entree["precautions"]
                existantes[cle].posologie_adulte = entree["posologie_adulte"]
                existantes[cle].classe_therapeutique = entree["classe_therapeutique"]
                continue
            db.add(MedicamentReferentiel(**entree))
            creations += 1

        await db.flush()
        if creations:
            logger.info("formulaire_medicamenteux_semere", ajouts=creations)
        return creations

    @staticmethod
    async def rechercher(
        db: AsyncSession,
        q: Optional[str] = None,
        forme: Optional[str] = None,
        classe: Optional[str] = None,
        inclure_inactifs: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[MedicamentReferentiel], int]:
        conditions = []
        if not inclure_inactifs:
            conditions.append(MedicamentReferentiel.actif.is_(True))
        if forme:
            conditions.append(MedicamentReferentiel.forme == forme.upper())
        if classe:
            conditions.append(MedicamentReferentiel.classe_therapeutique == classe.upper())
        if q:
            like = f"%{q.strip()}%"
            conditions.append(
                MedicamentReferentiel.nom_commercial.ilike(like)
                | MedicamentReferentiel.dci.ilike(like)
            )

        count_stmt = select(func.count(MedicamentReferentiel.id))
        data_stmt = select(MedicamentReferentiel)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            data_stmt = data_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())
        data_stmt = (
            data_stmt.order_by(MedicamentReferentiel.classe_therapeutique, MedicamentReferentiel.nom_commercial)
            .offset(offset)
            .limit(limit)
        )
        return list((await db.execute(data_stmt)).scalars().all()), total

    @staticmethod
    async def creer(db: AsyncSession, data: MedicamentCreate) -> MedicamentReferentiel:
        from src.common.ordonnance import normaliser_dci

        dci_normalise = data.dci.strip()
        if (
            await db.execute(
                select(MedicamentReferentiel).where(
                    func.lower(MedicamentReferentiel.dci) == dci_normalise.lower()
                )
            )
        ).scalar_one_or_none() is not None:
            raise BusinessRuleViolationException(
                f"Le médicament '{dci_normalise}' est déjà au référentiel.",
                code="MEDICAMENT_DEJA_EXISTANT",
            )

        medicament = MedicamentReferentiel(
            nom_commercial=data.nom_commercial.strip(),
            dci=dci_normalise,
            forme=data.forme.upper(),
            dosage=data.dosage,
            classe_therapeutique=(data.classe_therapeutique or "").upper() or None,
            posologie_adulte=data.posologie_adulte,
            precautions=data.precautions,
            contre_indications=[r.model_dump() for r in data.contre_indications],
            actif=True,
        )
        db.add(medicament)
        await db.flush()
        return medicament


class OrdonnanceService:
    # ---------------------------------------------------------------- helpers
    @staticmethod
    async def _contexte_patient(
        db: AsyncSession, patient_id: uuid.UUID
    ) -> Tuple[Patient, DossierMedical, Dict[str, str]]:
        """
        Charge l'état clinique du patient et en déduit les conditions actives.

        Les conditions sont dérivées de l'état général ET des antécédents : un
        antécédent « cardiovasculaire » jamais recopié dans l'état général ne
        doit pas pouvoir laisser passer une prescription dangereuse.
        """
        stmt = (
            select(Patient, DossierMedical)
            .join(DossierMedical, DossierMedical.patient_id == Patient.id)
            .where(Patient.id == patient_id)
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            raise EntityNotFoundException("Patient", patient_id)
        patient, dossier = row[0], row[1]

        stmt_etat = select(EtatGeneral).where(EtatGeneral.dossier_medical_id == dossier.id)
        etat = (await db.execute(stmt_etat)).scalar_one_or_none()

        stmt_ant = select(AntecedentMedical).where(
            AntecedentMedical.dossier_medical_id == dossier.id
        )
        antecedents = list((await db.execute(stmt_ant)).scalars().all())

        conditions = conditions_pour_contre_indications(
            grossesse=bool(etat and etat.grossesse),
            grossesse_terme=etat.grossesse_terme if etat else None,
            allaitement=bool(etat and etat.allaitement),
            diabete=bool(etat and etat.diabete),
            hta=bool(etat and etat.hta),
            allergies=list(etat.allergies) if etat and etat.allergies else [],
            antecedents=antecedents,
        )
        return patient, dossier, conditions

    @staticmethod
    async def _verifier_consultation(
        db: AsyncSession, consultation_id: uuid.UUID, dossier_id: uuid.UUID
    ) -> Consultation:
        stmt = (
            select(Consultation)
            .options(selectinload(Consultation.dossier_medical))
            .where(Consultation.id == consultation_id)
        )
        consultation = (await db.execute(stmt)).scalar_one_or_none()
        if consultation is None:
            raise EntityNotFoundException("Consultation", consultation_id)
        if consultation.dossier_medical_id != dossier_id:
            raise BusinessRuleViolationException(
                "La consultation indiquée n'appartient pas à ce dossier patient.",
                code="CONSULTATION_AUTRE_DOSSIER",
            )
        return consultation

    @staticmethod
    async def _resoudre_praticien(
        db: AsyncSession, auteur: Optional[Utilisateur]
    ) -> uuid.UUID:
        """Identifiant du praticien prescripteur : obligatoire (acte médical signé)."""
        if auteur is None:
            raise BusinessRuleViolationException(
                "Identité du prescripteur inconnue.", code="PRATICIEN_NON_IDENTIFIE"
            )
        stmt = select(Praticien.id).where(Praticien.utilisateur_id == auteur.id)
        profil = (await db.execute(stmt)).scalar_one_or_none()
        if profil is None:
            raise BusinessRuleViolationException(
                "Votre compte n'est rattaché à aucun profil praticien : impossible "
                "d'établir une ordonnance signée.",
                code="PRATICIEN_NON_IDENTIFIE",
            )
        return profil

    @staticmethod
    async def _controler_ligne(
        db: AsyncSession,
        ligne: LignePrescriptionCreate,
        conditions: Dict[str, str],
        *,
        auteur: Optional[Utilisateur],
    ) -> Tuple[MedicamentReferentiel, Optional[Any], List[AlertePrescription]]:
        """
        Contrôle une ligne avant enregistrement (RG07, RG08).

        Retourne : (médicament, alerte_interdite, alertes_précaution).

        Une contre-indication formelle lève une exception : on ne « laisse pas
        passer avec un avertissement », ce serait un contre-sens médical.
        """
        if ligne.medicament_id is None:
            # Médicament hors référentiel : aucune règle automatique applicable.
            # On le signale explicitement plutôt que de laisser croire à un contrôle.
            return (
                None,
                None,
                [
                    AlertePrescription(
                        code="MEDICAMENT_HORS_REFERENTIEL",
                        gravite=PRECAUTION,
                        message=(
                            "Médicament hors référentiel : aucune contre-indication "
                            "automatique n'a pu être évaluée. Vérifiez manuellement."
                        ),
                        condition="",
                    )
                ],
            )

        medicament = (
            await db.execute(
                select(MedicamentReferentiel).where(MedicamentReferentiel.id == ligne.medicament_id)
            )
        ).scalar_one_or_none()
        if medicament is None:
            raise EntityNotFoundException("Médicament", ligne.medicament_id)
        if not medicament.actif:
            raise BusinessRuleViolationException(
                f"Le médicament '{medicament.nom_commercial}' est retiré du référentiel.",
                code="MEDICAMENT_INACTIF",
            )

        alertes = evaluer_contre_indications(
            dci=medicament.dci,
            contre_indications=medicament.contre_indications,
            conditions_actives=conditions,
        )

        interdites = [a for a in alertes if a.gravite == INTERDIT]
        precautions = [a for a in alertes if a.gravite == PRECAUTION]

        if interdites:
            details = " ; ".join(a.message for a in interdites)

            # La tentative est journalisée via structlog, PAS via AuditService.
            # L'audit en base vit dans la transaction métier : lever une
            # exception ici la ferait annuler, et l'événement le plus important
            # du module disparaîtrait. structlog est hors transaction, il survit.
            # Le gestionnaire d'exceptions trace ensuite le refus avec le code
            # CONTRE_INDICATION_ABSOLUE : la tentative reste donc traçable dans
            # les journaux du serveur.
            logger.warning(
                "prescription_refusee_contre_indication",
                dci=medicament.dci,
                conditions_actives=sorted(conditions.keys()),
                conditions=[a.condition for a in interdites],
                motifs=[a.message for a in interdites],
                prescripteur=auteur.email if auteur else None,
            )

            raise BusinessRuleViolationException(
                f"Prescription impossible : {details}",
                code="CONTRE_INDICATION_ABSOLUE",
                details={"alertes": [a.model_dump() for a in interdites]},
            )

        if precautions and not (ligne.justification_precaution or "").strip():
            raise BusinessRuleViolationException(
                "Précaution : la prescription exige une justification écrite.",
                code="JUSTIFICATION_PRECAUTION_REQUISE",
                details={"alertes": [a.model_dump() for a in precautions]},
            )

        return medicament, None, [
            AlertePrescription(
                code=a.code,
                gravite=a.gravite,
                message=a.message,
                condition=a.condition,
            )
            for a in precautions
        ]

    # ------------------------------------------------------------------- création
    @staticmethod
    async def creer(
        db: AsyncSession,
        data: OrdonnanceCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Prescription:
        """Émet une ordonnance pour une consultation (UC7 du CDC)."""
        patient, dossier, conditions = await OrdonnanceService._contexte_patient(
            db, data.patient_id
        )

        if patient.archive:
            raise BusinessRuleViolationException(
                f"Le dossier {patient.numero_dossier} est archivé.",
                code="PATIENT_ARCHIVE",
            )

        consultation = await OrdonnanceService._verifier_consultation(
            db, data.consultation_id, dossier.id
        )
        praticien_id = await OrdonnanceService._resoudre_praticien(db, auteur)

        if not data.lignes:
            raise BusinessRuleViolationException(
                "Une ordonnance sans ligne n'a pas de sens.", code="ORDONNANCE_VIDE"
            )

        toutes_alertes: List[AlertePrescription] = []
        medicaments: List[Optional[MedicamentReferentiel]] = []

        for ligne in data.lignes:
            medicament, _, alertes = await OrdonnanceService._controler_ligne(
                db, ligne, conditions, auteur=auteur
            )
            medicaments.append(medicament)
            toutes_alertes.extend(alertes)

        # Interactions médicamenteuses, contrôlées sur l'ensemble de l'ordonnance :
        # une interaction n'existe qu'entre deux lignes.
        dcis = [m.dci for m in medicaments if m is not None]
        for alerte in detecter_interactions(dcis) + interactions_speciales(dcis):
            toutes_alertes.append(
                AlertePrescription(
                    code=alerte["code"],
                    gravite=alerte["gravite"],
                    message=alerte["message"],
                    condition="INTERACTION",
                )
            )

        numero = await generer_numero_ordonnance(db)
        prescription = Prescription(
            numero=numero,
            consultation_id=consultation.id,
            praticien_id=praticien_id,
            patient_id=patient.id,
            notes_generales=data.notes_generales,
            signe=False,
            alertes=[a.model_dump() for a in toutes_alertes],
        )
        db.add(prescription)
        await db.flush()

        for ligne, medicament in zip(data.lignes, medicaments):
            db.add(
                LignePrescription(
                    prescription_id=prescription.id,
                    medicament_id=medicament.id if medicament else None,
                    medicament_texte=(
                        ligne.medicament_texte
                        or (medicament.nom_commercial if medicament else None)
                    ),
                    posologie=ligne.posologie,
                    duree=ligne.duree,
                    instructions=ligne.instructions,
                    quantite=ligne.quantite,
                    justification_precaution=ligne.justification_precaution,
                )
            )

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PRESCRIPTION_CREATE",
            resource_type="Prescription",
            resource_id=str(prescription.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "numero": numero,
                "patient_id": str(patient.id),
                "numero_dossier": patient.numero_dossier,
                "consultation_id": str(consultation.id),
                "nb_lignes": len(data.lignes),
                "alertes": [a.model_dump() for a in toutes_alertes],
                "conditions_actives": list(conditions.keys()),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info(
            "ordonnance_creee",
            numero=numero,
            patient_id=str(patient.id),
            nb_lignes=len(data.lignes),
            nb_alertes=len(toutes_alertes),
        )
        return await OrdonnanceService._charger(db, prescription.id)

    # ------------------------------------------------------------------ écriture
    @staticmethod
    async def signer(
        db: AsyncSession,
        prescription_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Prescription:
        """
        Signe l'ordonnance.

        La signature la rend non modifiable : une ordonnance signée est un acte
        médical opposable. On ne la « dé-signe » pas, on en émet une autre.
        """
        prescription = await OrdonnanceService._charger(db, prescription_id)

        if prescription.signe:
            return prescription

        if not prescription.lignes:
            raise BusinessRuleViolationException(
                "Impossible de signer une ordonnance vide.", code="ORDONNANCE_VIDE"
            )

        prescription.signe = True
        prescription.date_signature = datetime.now(timezone.utc)

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PRESCRIPTION_SIGN",
            resource_type="Prescription",
            resource_id=str(prescription.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero": prescription.numero, "date_signature": str(prescription.date_signature)},
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info("ordonnance_signee", numero=prescription.numero)
        return await OrdonnanceService._charger(db, prescription_id)

    @staticmethod
    async def modifier(
        db: AsyncSession,
        prescription_id: uuid.UUID,
        data: OrdonnanceUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Prescription:
        """Modifie les notes d'une ordonnance **non signée**."""
        prescription = await OrdonnanceService._charger(db, prescription_id)

        if prescription.signe:
            raise BusinessRuleViolationException(
                "Cette ordonnance est signée : elle n'est plus modifiable. "
                "Émettez une nouvelle ordonnance.",
                code="PRESCRIPTION_SIGNEE",
            )

        champs = data.model_dump(exclude_unset=True, exclude_none=True)
        for champ, valeur in champs.items():
            setattr(prescription, champ, valeur)

        await db.flush()
        await db.commit()
        return await OrdonnanceService._charger(db, prescription_id)

    @staticmethod
    async def ajouter_ligne(
        db: AsyncSession,
        prescription_id: uuid.UUID,
        ligne: LignePrescriptionCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Prescription:
        """
        Ajoute une ligne à une ordonnance existante non signée.

        Le contrôle de contre-indication est refait intégralement : l'état du
        patient a pu changer depuis l'émission.
        """
        prescription = await OrdonnanceService._charger(db, prescription_id)

        if prescription.signe:
            raise BusinessRuleViolationException(
                "Cette ordonnance est signée : elle n'est plus modifiable.",
                code="PRESCRIPTION_SIGNEE",
            )

        _, dossier, conditions = await OrdonnanceService._contexte_patient(
            db, prescription.patient_id
        )
        await OrdonnanceService._controler_ligne(db, ligne, conditions, auteur=auteur)

        db.add(
            LignePrescription(
                prescription_id=prescription.id,
                medicament_id=ligne.medicament_id,
                medicament_texte=ligne.medicament_texte,
                posologie=ligne.posologie,
                duree=ligne.duree,
                instructions=ligne.instructions,
                quantite=ligne.quantite,
                justification_precaution=ligne.justification_precaution,
            )
        )
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PRESCRIPTION_LIGNE_ADD",
            resource_type="Prescription",
            resource_id=str(prescription.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"medicament_texte": ligne.medicament_texte},
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return await OrdonnanceService._charger(db, prescription_id)

    @staticmethod
    async def supprimer_ligne(
        db: AsyncSession,
        prescription_id: uuid.UUID,
        ligne_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        motif: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Prescription:
        """Supprime une ligne d'une ordonnance non signée, avec trace en audit."""
        prescription = await OrdonnanceService._charger(db, prescription_id)

        if prescription.signe:
            raise BusinessRuleViolationException(
                "Cette ordonnance est signée : elle n'est plus modifiable.",
                code="PRESCRIPTION_SIGNEE",
            )

        ligne = next((l for l in prescription.lignes if l.id == ligne_id), None)
        if ligne is None:
            raise EntityNotFoundException("Ligne d'ordonnance", ligne_id)

        await AuditService.log_action(
            db=db,
            action="PRESCRIPTION_LIGNE_DELETE",
            resource_type="Prescription",
            resource_id=str(prescription.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"medicament_texte": ligne.medicament_texte, "motif": motif},
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.delete(ligne)
        await db.flush()
        await db.commit()
        return await OrdonnanceService._charger(db, prescription_id)

    # ------------------------------------------------------------------ lecture
    @staticmethod
    async def _charger(db: AsyncSession, prescription_id: uuid.UUID) -> Prescription:
        stmt = (
            select(Prescription)
            .options(
                selectinload(Prescription.lignes).selectinload(LignePrescription.medicament),
                selectinload(Prescription.consultation),
            )
            # `expire_on_commit=False` (réglage applicatif) laisse les
            # collections déjà chargées dans l'identity map : la requête ne les
            # rafraîchirait pas, et une ligne ajoutée ou supprimée par le
            # traitement courant resterait invisible. `populate_existing` force
            # la recharge.
            .execution_options(populate_existing=True)
            .where(Prescription.id == prescription_id)
        )
        prescription = (await db.execute(stmt)).scalar_one_or_none()
        if prescription is None:
            raise EntityNotFoundException("Ordonnance", prescription_id)
        return prescription

    @staticmethod
    async def obtenir(db: AsyncSession, prescription_id: uuid.UUID) -> Prescription:
        return await OrdonnanceService._charger(db, prescription_id)

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        patient_id: Optional[uuid.UUID] = None,
        consultation_id: Optional[uuid.UUID] = None,
        limite: int = 50,
    ) -> List[Prescription]:
        stmt = select(Prescription).options(
            selectinload(Prescription.lignes).selectinload(LignePrescription.medicament)
        )
        if patient_id:
            stmt = stmt.where(Prescription.patient_id == patient_id)
        if consultation_id:
            stmt = stmt.where(Prescription.consultation_id == consultation_id)
        stmt = stmt.order_by(Prescription.date_ordonnance.desc()).limit(limite)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def controler_possibilite(
        db: AsyncSession,
        patient_id: uuid.UUID,
        ligne: LignePrescriptionCreate,
    ) -> Dict[str, Any]:
        """
        Contrôle à blanc, sans rien enregistrer (UC8 « Vérifier contre-indications »).

        Le cas d'usage réel : le praticien hésite avant de taper la posologie. On
        veut répondre sans risquer d'écrire une ordonnance qu'il va devoir
        corriger. Retourne aussi l'état du patient, qui explique le refus.
        """
        _, _, conditions = await OrdonnanceService._contexte_patient(db, patient_id)

        medicament = None
        if ligne.medicament_id is not None:
            medicament = (
                await db.execute(
                    select(MedicamentReferentiel).where(
                        MedicamentReferentiel.id == ligne.medicament_id
                    )
                )
            ).scalar_one_or_none()

        alertes: List[AlertePrescription] = []
        if medicament is None:
            alertes.append(
                AlertePrescription(
                    code="MEDICAMENT_HORS_REFERENTIEL",
                    gravite=PRECAUTION,
                    message="Médicament hors référentiel : contrôle automatique impossible.",
                    condition="",
                )
            )
        else:
            for alerte in evaluer_contre_indications(
                dci=medicament.dci,
                contre_indications=medicament.contre_indications,
                conditions_actives=conditions,
            ):
                alertes.append(
                    AlertePrescription(
                        code=alerte.code,
                        gravite=alerte.gravite,
                        message=alerte.message,
                        condition=alerte.condition,
                    )
                )

        return {
            "prescription_possible": not any(a.gravite == INTERDIT for a in alertes),
            "justification_requise": any(a.gravite == PRECAUTION for a in alertes),
            "alertes": alertes,
            "conditions_actives": [
                {"condition": code, "libelle": libelle_condition(code), "detail": detail}
                for code, detail in sorted(conditions.items())
            ],
        }
