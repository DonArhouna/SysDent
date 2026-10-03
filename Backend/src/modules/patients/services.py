"""
Services métier du pôle Patients & Dossier Médical (Étape 1 à 3 du CDC).

Règles de gestion couvertes :
  RG01 — numéro de dossier unique auto-généré
  RG02 — état général vérifié / mis à jour à chaque consultation
  RG12 — traçabilité médico-légale de toute action sensible
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.common.numerotation import generer_numero_dossier_patient
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.patients.schemas import (
    AlerteMedicale,
    AntecedentMedicalCreate,
    AntecedentMedicalUpdate,
    EtatGeneralCreate,
    EtatGeneralResponse,
    EtatGeneralUpdate,
    PatientCreate,
    PatientUpdate,
    RecherchePatients,
)
from src.modules.tenants.models import (
    AntecedentMedical,
    Consultation,
    DossierMedical,
    EtatGeneral,
    Patient,
    Utilisateur,
)

logger = structlog.get_logger(__name__)


class AlertService:
    """
    Calcule les alertes cliniques affichées au praticien (RG03, RG04).

    Volontairement fail-safe : une allergie grave ou une grossesse remonte toujours,
    même si le reste de l'état général est vide. Ces alertes alimenteront le
    contrôle de contre-indications du module Ordonnances.
    """

    @staticmethod
    def calculer(
        etat_general: Optional[EtatGeneral],
        antecedents: List[AntecedentMedical],
    ) -> List[AlerteMedicale]:
        alertes: List[AlerteMedicale] = []

        if etat_general:
            # Allergies : la gravité est portée par l'entrée elle-même.
            for allergie in etat_general.allergies or []:
                if not isinstance(allergie, dict):
                    continue
                substance = allergie.get("substance", "substance inconnue")
                severite = (allergie.get("severite") or "legere").lower()
                reaction = allergie.get("reaction")
                niveau = "GRAVE" if severite == "grave" else ("MODERE" if severite == "moderee" else "INFO")
                message = f"Allergie {allergie.get('severite', severite)} : {substance}"
                if reaction:
                    message += f" — réaction : {reaction}"
                alertes.append(
                    AlerteMedicale(code="ALLERGIE", niveau=niveau, message=message, source="ETAT_GENERAL")
                )

            if etat_general.grossesse:
                terme = etat_general.grossesse_terme
                message = "Patiente enceinte."
                if terme:
                    message += f" Terme : {terme}."
                message += " Prescriptions à valider contre les contre-indications (RG04)."
                alertes.append(
                    AlerteMedicale(code="GROSSESSE", niveau="GRAVE", message=message, source="ETAT_GENERAL")
                )

            if etat_general.allaitement:
                alertes.append(
                    AlerteMedicale(
                        code="ALLAITEMENT",
                        niveau="MODERE",
                        message="Allaitement en cours : vérifier la sécurité des prescriptions (RG04).",
                        source="ETAT_GENERAL",
                    )
                )

            if etat_general.diabete:
                type_diabete = f" ({etat_general.diabete_type})" if etat_general.diabete_type else ""
                alertes.append(
                    AlerteMedicale(
                        code="DIABETE",
                        niveau="MODERE",
                        message=f"Diabète connu{type_diabete} : precautions anesthésiques et retards de cicatrisation.",
                        source="ETAT_GENERAL",
                    )
                )

            if etat_general.hta:
                alertes.append(
                    AlerteMedicale(
                        code="HTA",
                        niveau="MODERE",
                        message="Hypertension artérielle : vérifier la tension avant toute anesthésie.",
                        source="ETAT_GENERAL",
                    )
                )

        # Antécédents : un antécédent en cours reste un signal même si l'état
        # général n'a pas été mis à jour (situation fréquente en pratique).
        for antecedent in antecedents:
            if not antecedent.en_cours:
                continue
            type_norm = (antecedent.type_antecedent or "").upper()
            if type_norm == "ALLERGIE":
                alertes.append(
                    AlerteMedicale(
                        code="ALLERGIE",
                        niveau="GRAVE",
                        message=f"Antécédent allergique en cours : {antecedent.description}",
                        source="ANTECEDENT",
                    )
                )
            elif type_norm in {"CARDIO", "CARDIAQUE"}:
                alertes.append(
                    AlerteMedicale(
                        code="ANTECEDENT_CARDIAQUE",
                        niveau="GRAVE",
                        message=f"Antécédent cardiovasculaire en cours : {antecedent.description}",
                        source="ANTECEDENT",
                    )
                )
            elif type_norm in {"RESPIRATOIRE", "ANESTHESIE"}:
                alertes.append(
                    AlerteMedicale(
                        code="ANTECEDENT_ACTIF",
                        niveau="MODERE",
                        message=f"Antécédent respiratoire en cours : {antecedent.description}",
                        source="ANTECEDENT",
                    )
                )
            else:
                alertes.append(
                    AlerteMedicale(
                        code="ANTECEDENT_ACTIF",
                        niveau="INFO",
                        message=f"Antécédent en cours ({type_norm or 'non précisé'}) : {antecedent.description}",
                        source="ANTECEDENT",
                    )
                )

        return alertes


class PatientService:
    @staticmethod
    async def _charger_patient_avec_dossier(
        db: AsyncSession, patient_id: uuid.UUID, *, with_antecedents: bool = True
    ) -> Patient:
        stmt = (
            select(Patient)
            .options(
                selectinload(Patient.dossier_medical)
                .selectinload(DossierMedical.etat_general),
                selectinload(Patient.dossier_medical)
                .selectinload(DossierMedical.antecedents)
                if with_antecedents
                else selectinload(Patient.dossier_medical),
            )
            .where(Patient.id == patient_id)
        )
        result = await db.execute(stmt)
        patient = result.scalar_one_or_none()
        if not patient:
            raise EntityNotFoundException("Patient", patient_id)
        return patient

    @staticmethod
    async def _detecter_doublons(
        db: AsyncSession,
        nom: str,
        prenom: str,
        telephone_1: str,
        date_naissance: Optional[Any] = None,
        exclure_id: Optional[uuid.UUID] = None,
    ) -> List[Patient]:
        """
        Recherche de dossiers potentiellement identiques (UC11 « Fusionner doublons »).

        Heuristique volontairement prudente : on ne signale que des correspondances
        sur nom + prénom, optionally strengthenées par la date de naissance ou le
        téléphone. Une correspondance téléphone seule est trop fréquente au Sénégal
        (numéros familiaux) pour être traitée comme un doublon.
        """
        conditions = [
            func.lower(func.trim(Patient.nom)) == nom.strip().lower(),
            func.lower(func.trim(Patient.prenom)) == prenom.strip().lower(),
            Patient.archive == False,  # noqa: E712
        ]
        if date_naissance is not None:
            conditions.append(Patient.date_naissance == date_naissance)
        elif telephone_1:
            conditions.append(Patient.telephone_1 == telephone_1)
        if exclure_id is not None:
            conditions.append(Patient.id != exclure_id)

        stmt = select(Patient).where(*conditions).limit(5)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def creer_patient(
        db: AsyncSession,
        data: PatientCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Patient:
        """
        Crée un dossier patient complet (RG01) : identité + dossier médical +
        état général + antécédents + odontogramme initialisé (32 dents).

        Le numéro de dossier est généré par le service et non reçu du client
        (RG01 : « numéro de dossier unique auto-généré »).
        """
        # Détection de doublons : on n'empêche pas la création (le praticien a
        # toujours raison sur un homonyme réel), mais on trace l'alerte et on
        # remonte la liste au client pour arbitrage.
        doublons = await PatientService._detecter_doublons(
            db,
            nom=data.nom,
            prenom=data.prenom,
            telephone_1=data.telephone_1,
            date_naissance=data.date_naissance,
        )
        if doublons:
            logger.warning(
                "creation_patient_doublon_detecte",
                candidat_nom=data.nom,
                candidat_prenom=data.prenom,
                nb_doublons=len(doublons),
            )

        numero_dossier = await generer_numero_dossier_patient(db)

        patient = Patient(
            numero_dossier=numero_dossier,
            prenom=data.prenom,
            nom=data.nom,
            date_naissance=data.date_naissance,
            sexe=data.sexe,
            type_piece_identite=data.type_piece_identite,
            numero_piece_identite=data.numero_piece_identite,
            adresse=data.adresse,
            ville=data.ville,
            telephone_1=data.telephone_1,
            telephone_2=data.telephone_2,
            email=str(data.email) if data.email else None,
            profession=data.profession,
            employeur=data.employeur,
            groupe_sanguin=data.groupe_sanguin,
            source=data.source,
            notes=data.notes,
            actif=True,
            archive=False,
        )
        db.add(patient)
        await db.flush()

        dossier = DossierMedical(
            patient_id=patient.id,
            notes_confidentielles=None,
        )
        db.add(dossier)
        await db.flush()

        # RG02 : l'état_general est matérialisé dès la création pour qu'il existe
        # un point de comparaison à chaque consultation. Si l'appelant a transmis
        # un état général (création en une seule requête, étapes 1 à 3 du CDC), on
        # l'applique immédiatement plutôt que d'insérer un état vide à écraser ensuite.
        etat_general = EtatGeneral(dossier_medical_id=dossier.id)
        if data.etat_general is not None:
            for champ, valeur in data.etat_general.model_dump(exclude_unset=True).items():
                if hasattr(etat_general, champ):
                    setattr(etat_general, champ, valeur)
        db.add(etat_general)
        await db.flush()

        for antecedent in data.antecedents or []:
            db.add(
                AntecedentMedical(
                    dossier_medical_id=dossier.id,
                    type_antecedent=antecedent.type_antecedent,
                    description=antecedent.description,
                    date_survenue=antecedent.date_survenue,
                    en_cours=antecedent.en_cours,
                    traitement_associe=antecedent.traitement_associe,
                    notes=antecedent.notes,
                )
            )

        await db.flush()

        # Traçabilité médico-légale (RG12). L'ID de la ressource est celui du
        # patient : c'est la clé que le praticien recherche dans le journal.
        # Le numéro de dossier généré est ajouté à l'audit juste après, quand il
        # est disponible (avant le flush du patient il ne l'est pas encore).
        await AuditService.log_action(
            db=db,
            action="PATIENT_CREATE",
            resource_type="Patient",
            resource_id=str(patient.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "numero_dossier": numero_dossier,
                "nom": data.nom,
                "prenom": data.prenom,
                "date_naissance": data.date_naissance.isoformat(),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info("patient_cree", patient_id=str(patient.id), numero_dossier=numero_dossier)
        return await PatientService._charger_patient_avec_dossier(db, patient.id)

    @staticmethod
    async def obtenir_patient(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
        return await PatientService._charger_patient_avec_dossier(db, patient_id)

    @staticmethod
    async def obtenir_dossier_complet(
        db: AsyncSession,
        patient_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fiche patient complète (UC5 « Consulter dossier médical ») avec alertes
        cliniques calculées et compteurs de consultations.
        """
        patient = await PatientService._charger_patient_avec_dossier(db, patient_id)

        dossier = patient.dossier_medical
        etat_general = dossier.etat_general if dossier else None
        antecedents = list(dossier.antecedents) if dossier else []

        # RG02 : l'état général doit être vérifié à chaque nouvelle consultation.
        # On signale une saisie ancienne plutôt que de la bloquer.
        a_jour_le = etat_general.updated_at if etat_general else None
        if etat_general is None or a_jour_le is None:
            etat_general_a_verifier = True
        else:
            delai_jours = (datetime.now(timezone.utc) - a_jour_le).days
            etat_general_a_verifier = delai_jours > 365

        nb_consultations = 0
        derniere_consultation = None
        if dossier:
            count_stmt = select(func.count(Consultation.id)).where(
                Consultation.dossier_medical_id == dossier.id
            )
            nb_consultations = int((await db.execute(count_stmt)).scalar_one())
            last_stmt = (
                select(func.max(Consultation.date_consultation))
                .where(Consultation.dossier_medical_id == dossier.id)
            )
            derniere_consultation = (await db.execute(last_stmt)).scalar_one_or_none()

        # Consultation du dossier = événement tracé (RG12), comme dans un dossier
        # médico-légal réel : qui a ouvert le dossier et quand.
        await AuditService.log_action(
            db=db,
            action="PATIENT_VIEW",
            resource_type="Patient",
            resource_id=str(patient.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return {
            "patient": patient,
            "etat_general": etat_general,
            "antecedents": antecedents,
            "alertes": AlertService.calculer(etat_general, antecedents),
            "nb_consultations": nb_consultations,
            "derniere_consultation": derniere_consultation,
            "etat_general_a_verifier": etat_general_a_verifier,
        }

    @staticmethod
    async def rechercher(
        db: AsyncSession, filtres: RecherchePatients, offset: int, limit: int
    ) -> Tuple[List[Patient], int]:
        """Recherche multicritère paginée (nom, prénom, N° dossier, tél., date naissance)."""
        conditions = []

        if filtres.uniquement_archives:
            conditions.append(Patient.archive == True)  # noqa: E712
        elif not filtres.include_archives:
            conditions.append(Patient.archive == False)  # noqa: E712

        if filtres.q:
            terme = filtres.q.strip()
            if terme:
                # Numéro de dossier : recherche exacte si le motif ressemble à un PAT-...
                like = f"%{terme}%"
                conditions.append(
                    or_(
                        Patient.nom.ilike(like),
                        Patient.prenom.ilike(like),
                        Patient.numero_dossier.ilike(like),
                        Patient.telephone_1.ilike(like),
                        Patient.telephone_2.ilike(like),
                    )
                )

        if filtres.nom:
            conditions.append(Patient.nom.ilike(f"%{filtres.nom.strip()}%"))
        if filtres.telephone:
            compact = filtres.telephone.strip()
            conditions.append(
                or_(
                    Patient.telephone_1.ilike(f"%{compact}%"),
                    Patient.telephone_2.ilike(f"%{compact}%"),
                )
            )
        if filtres.numero_dossier:
            conditions.append(Patient.numero_dossier == filtres.numero_dossier.strip().upper())
        if filtres.date_naissance:
            conditions.append(Patient.date_naissance == filtres.date_naissance)

        where_clause = conditions[0] if len(conditions) == 1 else (and_(*conditions) if conditions else None)

        count_stmt = select(func.count(Patient.id))
        data_stmt = select(Patient)
        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)
            data_stmt = data_stmt.where(where_clause)

        total = int((await db.execute(count_stmt)).scalar_one())
        data_stmt = data_stmt.order_by(Patient.nom.asc(), Patient.prenom.asc()).offset(offset).limit(limit)
        rows = await db.execute(data_stmt)
        return list(rows.scalars().all()), total

    @staticmethod
    async def modifier_patient(
        db: AsyncSession,
        patient_id: uuid.UUID,
        data: PatientUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Patient:
        """Mise à jour administrative (UC3). Ne touche pas aux données cliniques."""
        patient = await PatientService._charger_patient_avec_dossier(db, patient_id, with_antecedents=False)

        if patient.archive:
            raise BusinessRuleViolationException(
                "Ce dossier est archivé. Réactivez-le avant toute modification."
            )

        champs_modifiables = data.model_dump(exclude_unset=True, exclude_none=True)
        if not champs_modifiables:
            return patient

        # Détection de changement d'identité -> contrôle de doublon.
        nouveau_nom = champs_modifiables.get("nom", patient.nom)
        nouveau_prenom = champs_modifiables.get("prenom", patient.prenom)
        if "nom" in champs_modifiables or "prenom" in champs_modifiables:
            doublons = await PatientService._detecter_doublons(
                db,
                nom=nouveau_nom,
                prenom=nouveau_prenom,
                telephone_1=champs_modifiables.get("telephone_1", patient.telephone_1),
                date_naissance=champs_modifiables.get("date_naissance", patient.date_naissance),
                exclure_id=patient.id,
            )
            if doublons:
                logger.warning(
                    "modification_patient_doublon_detecte",
                    patient_id=str(patient.id),
                    nb_doublons=len(doublons),
                )

        avant = {champ: getattr(patient, champ, None) for champ in champs_modifiables}

        for champ, valeur in champs_modifiables.items():
            setattr(patient, champ, str(valeur) if champ == "email" else valeur)

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PATIENT_UPDATE",
            resource_type="Patient",
            resource_id=str(patient.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                champ: {
                    "ancien": str(avant.get(champ)) if avant.get(champ) is not None else None,
                    "nouveau": str(getattr(patient, champ)) if getattr(patient, champ) is not None else None,
                }
                for champ in champs_modifiables
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info("patient_modifie", patient_id=str(patient.id), champs=list(champs_modifiables))
        return await PatientService._charger_patient_avec_dossier(db, patient.id, with_antecedents=False)

    @staticmethod
    async def archiver_patient(
        db: AsyncSession,
        patient_id: uuid.UUID,
        motif: Optional[str] = None,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Patient:
        """
        Archivage (UC12). Le dossier n'est jamais supprimé : les données
        의료 remain accessibles pour la traçabilité. Un dossier avec consultations
        ne peut être archivé que s'il n'a aucune consultation en cours.
        """
        patient = await PatientService._charger_patient_avec_dossier(db, patient_id, with_antecedents=False)

        if patient.archive:
            return patient

        dossier = patient.dossier_medical
        if dossier:
            en_cours_stmt = select(func.count(Consultation.id)).where(
                Consultation.dossier_medical_id == dossier.id,
                Consultation.statut.in_(["EN_ATTENTE", "EN_COURS"]),
            )
            en_cours = int((await db.execute(en_cours_stmt)).scalar_one())
            if en_cours > 0:
                raise BusinessRuleViolationException(
                    f"Impossible d'archiver : {en_cours} consultation(s) en cours sur ce dossier.",
                    code="PATIENT_HAS_ACTIVE_CONSULTATIONS",
                )

        patient.archive = True
        patient.actif = False
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PATIENT_ARCHIVE",
            resource_type="Patient",
            resource_id=str(patient.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero_dossier": patient.numero_dossier, "motif": motif},
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info("patient_archived", patient_id=str(patient.id), motif=motif)
        return patient

    @staticmethod
    async def reactiver_patient(
        db: AsyncSession,
        patient_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Patient:
        """Réactivation d'un dossier archivé (opération inverse de l'archivage)."""
        patient = await PatientService._charger_patient_avec_dossier(db, patient_id, with_antecedents=False)
        if not patient.archive:
            return patient

        patient.archive = False
        patient.actif = True
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PATIENT_REACTIVATE",
            resource_type="Patient",
            resource_id=str(patient.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero_dossier": patient.numero_dossier},
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info("patient_reactivated", patient_id=str(patient.id))
        return patient


class EtatGeneralService:
    """État général (Étape 2 du CDC, RG02)."""

    @staticmethod
    async def _obtenir_dossier(db: AsyncSession, patient_id: uuid.UUID) -> Tuple[Patient, DossierMedical]:
        stmt = (
            select(Patient, DossierMedical)
            .join(DossierMedical, DossierMedical.patient_id == Patient.id)
            .where(Patient.id == patient_id)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise EntityNotFoundException("Patient", patient_id)
        return row[0], row[1]

    @staticmethod
    async def obtenir(db: AsyncSession, patient_id: uuid.UUID) -> Optional[EtatGeneral]:
        _, dossier = await EtatGeneralService._obtenir_dossier(db, patient_id)
        if dossier.etat_general:
            return dossier.etat_general
        stmt = select(EtatGeneral).where(EtatGeneral.dossier_medical_id == dossier.id)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def enregistrer(
        db: AsyncSession,
        patient_id: uuid.UUID,
        data: EtatGeneralCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> EtatGeneral:
        """Crée l'état général s'il est absent, sinon le met à jour (upsert)."""
        patient, dossier = await EtatGeneralService._obtenir_dossier(db, patient_id)

        if patient.archive:
            raise BusinessRuleViolationException(
                "Ce dossier est archivé. Réactivez-le avant toute saisie clinique."
            )

        stmt = select(EtatGeneral).where(EtatGeneral.dossier_medical_id == dossier.id)
        etat = (await db.execute(stmt)).scalar_one_or_none()

        if etat is None:
            etat = EtatGeneral(dossier_medical_id=dossier.id)
            db.add(etat)

        avant = {
            "allergies": list(etat.allergies or []),
            "grossesse": etat.grossesse,
            "diabete": etat.diabete,
            "hta": etat.hta,
        }

        for champ, valeur in data.model_dump(exclude_unset=True).items():
            if hasattr(etat, champ):
                setattr(etat, champ, valeur)

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="ETAT_GENERAL_UPDATE",
            resource_type="EtatGeneral",
            resource_id=str(etat.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(patient.id),
                "numero_dossier": patient.numero_dossier,
                "avant": {
                    "allergies": avant["allergies"],
                    "grossesse": avant["grossesse"],
                    "diabete": avant["diabete"],
                    "hta": avant["hta"],
                },
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return etat

    @staticmethod
    async def modifier(
        db: AsyncSession,
        patient_id: uuid.UUID,
        data: EtatGeneralUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> EtatGeneral:
        """Mise à jour partielle de l'état général (vérification à la consultation)."""
        return await EtatGeneralService.enregistrer(
            db,
            patient_id,
            EtatGeneralCreate(**data.model_dump(exclude_unset=True, exclude_none=True)),
            auteur,
            client_ip=client_ip,
            user_agent=user_agent,
        )


class AntecedentService:
    """Antécédents médicaux (Étape 3 du CDC)."""

    @staticmethod
    async def lister(db: AsyncSession, patient_id: uuid.UUID) -> List[AntecedentMedical]:
        _, dossier = await EtatGeneralService._obtenir_dossier(db, patient_id)
        stmt = (
            select(AntecedentMedical)
            .where(AntecedentMedical.dossier_medical_id == dossier.id)
            .order_by(AntecedentMedical.en_cours.desc(), AntecedentMedical.date_survenue.desc().nullslast())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def ajouter(
        db: AsyncSession,
        patient_id: uuid.UUID,
        data: AntecedentMedicalCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AntecedentMedical:
        patient, dossier = await EtatGeneralService._obtenir_dossier(db, patient_id)

        if patient.archive:
            raise BusinessRuleViolationException(
                "Ce dossier est archivé. Réactivez-le avant toute saisie clinique."
            )

        antecedent = AntecedentMedical(
            dossier_medical_id=dossier.id,
            type_antecedent=data.type_antecedent,
            description=data.description,
            date_survenue=data.date_survenue,
            en_cours=data.en_cours,
            traitement_associe=data.traitement_associe,
            notes=data.notes,
        )
        db.add(antecedent)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="ANTECEDENT_CREATE",
            resource_type="AntecedentMedical",
            resource_id=str(antecedent.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(patient.id),
                "numero_dossier": patient.numero_dossier,
                "type": antecedent.type_antecedent,
                "description": antecedent.description,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return antecedent

    @staticmethod
    async def modifier(
        db: AsyncSession,
        antecedent_id: uuid.UUID,
        data: AntecedentMedicalUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AntecedentMedical:
        stmt = select(AntecedentMedical).where(AntecedentMedical.id == antecedent_id)
        antecedent = (await db.execute(stmt)).scalar_one_or_none()
        if antecedent is None:
            raise EntityNotFoundException("Antécédent", antecedent_id)

        champs = data.model_dump(exclude_unset=True, exclude_none=True)
        if not champs:
            return antecedent

        avant = {champ: getattr(antecedent, champ, None) for champ in champs}
        for champ, valeur in champs.items():
            setattr(antecedent, champ, valeur)

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="ANTECEDENT_UPDATE",
            resource_type="AntecedentMedical",
            resource_id=str(antecedent.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                champ: {
                    "ancien": str(avant.get(champ)) if avant.get(champ) is not None else None,
                    "nouveau": str(getattr(antecedent, champ)) if getattr(antecedent, champ) is not None else None,
                }
                for champ in champs
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return antecedent
