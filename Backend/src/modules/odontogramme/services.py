"""
Services métier de l'Odontogramme (D1C).

Règles couvertes :
  RG10 — chaque modification de dent est horodatée avec le praticien et la consultation
  RG11 — un odontogramme adulte comprend 32 dents, un enfant 20 dents

Principe central : **l'odontogramme n'est jamais créé implicitement par une
écriture**. Il est généré à la première lecture ou par appel explicite, et toute
modification d'une dent écrit une ligne d'historique. `Dent.etat_actuel` n'est
qu'un cache de lecture rapide ; l'historique fait foi.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.common.dentaire import (
    DENTS_LAIT_ENFANT,
    DENTS_PERMANENTES_ADULTE,
    ETAT_SAINE,
    ETATS_ATTENTION,
    ETATS_DENT,
    ETATS_SOIGNES,
    FACES_COURTES,
    FACES_DENT,
    valider_etat_dent,
    valider_face,
    valider_numero_dent,
    vers_universal,
)
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.odontogramme.schemas import (
    ChartingParodontalCreate,
    DentMiseAJour,
    DentsMiseAJourLot,
    FaceMiseAJour,
    OdontogrammeCreer,
    TYPE_ADULTE,
    TYPE_ENFANT,
    TYPE_MIXTE,
)
from src.modules.tenants.models import (
    ChartingParodontal,
    Consultation,
    Dent,
    DossierMedical,
    EtatDentHistorique,
    FaceDent,
    Odontogramme,
    Praticien,
    Utilisateur,
)

logger = structlog.get_logger(__name__)

#: Étiquettes lisibles par le praticien, par état. Le code reste la référence.
LIBELLES_ETATS = {
    "SAINE": "Saine",
    "A_TRAITER": "À traiter",
    "ABSENTE_EXTRACTEE": "Absente (extraite)",
    "ABSENTE_CONGENITALE": "Absente (congénitale)",
    "INCLUSE": "Dent incluse",
    "SUPERNUMERAIRE": "Dent surnuméraire",
    "CARIE_DEBUTANTE": "Carie débutante",
    "CARIE_AVANCEE": "Carie avancée",
    "CARIE_PROFONDE": "Carie profonde",
    "CARIE_SOUS_PLOMBAGE": "Carie sous plombage",
    "OBTURATION_AMALGAME": "Obturation amalgame",
    "OBTURATION_COMPOSITE": "Obturation composite",
    "OBTURATION_CVI": "Obturation CVI",
    "INLAY": "Inlay",
    "ONLAY": "Onlay",
    "COURONNE": "Couronne",
    "TCR": "TCR",
    "REPRISE_TCR": "Reprise de TCR",
    "APEXIFICATION": "Apexification",
    "COURONNE_METAL": "Couronne métal",
    "COURONNE_CERAMIQUE": "Couronne céramique",
    "BRIDGE_PILIER": "Bridge (pilier)",
    "BRIDGE_INTERMEDIAIRE": "Bridge (intermédiaire)",
    "PROTHESE_PARTIELLE": "Prothèse partielle",
    "PROTHESE_TOTALE": "Prothèse totale",
    "STELLITE": "Stellite",
    "IMPLANT_POSE": "Implant posé",
    "COURONNE_SUR_IMPLANT": "Couronne sur implant",
    "ATTENTE_OSTEOINTEGRATION": "Attente d'ostéointégration",
    "EXTRACTION_PLANIFIEE": "Extraction planifiée",
    "EXTRACTION_REALISEE": "Extraction réalisée",
    "RESECTION_APICALE": "Résection apicale",
    "BAGUE": "Bague orthodontique",
    "BRACKET": "Bracket",
    "CONTENTION": "Contention",
    "FACETTE": "Facette",
    "BLANCHIMENT": "Blanchiment",
}


class OdontogrammeService:
    # ---------------------------------------------------------------- helpers
    @staticmethod
    async def _obtenir_dossier(db: AsyncSession, patient_id: uuid.UUID) -> Tuple[Any, DossierMedical]:
        from src.modules.tenants.models import Patient

        stmt = (
            select(Patient, DossierMedical)
            .join(DossierMedical, DossierMedical.patient_id == Patient.id)
            .where(Patient.id == patient_id)
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            raise EntityNotFoundException("Patient", patient_id)
        return row[0], row[1]

    @staticmethod
    async def _charger(
        db: AsyncSession, odontogramme_id: uuid.UUID, *, avec_historique: bool = False
    ) -> Odontogramme:
        # `dossier_medical` est chargé explicitement : le routeur et le journal
        # d'audit lisent `dossier_medical.patient_id`. Un accès paresseux ici
        # échouerait en contexte async (MissingGreenlet).
        options = [
            selectinload(Odontogramme.dossier_medical),
            selectinload(Odontogramme.dents).selectinload(Dent.faces),
        ]
        if avec_historique:
            options.append(selectinload(Odontogramme.dents).selectinload(Dent.historique))

        stmt = (
            select(Odontogramme)
            .options(*options)
            # `expire_on_commit=False` (réglage applicatif) laisse les
            # collections déjà chargées en cache dans l'identity map : la
            # requête ne les rafraîchirait pas, et une face ou une dent ajoutée
            # par le traitement courant resterait invisible. `populate_existing`
            # force la recharge.
            .execution_options(populate_existing=True)
            .where(Odontogramme.id == odontogramme_id)
        )
        odontogramme = (await db.execute(stmt)).scalar_one_or_none()
        if odontogramme is None:
            raise EntityNotFoundException("Odontogramme", odontogramme_id)
        return odontogramme

    @staticmethod
    async def _resoudre_praticien(
        db: AsyncSession, auteur: Optional[Utilisateur], praticien_id: Optional[uuid.UUID]
    ) -> Optional[uuid.UUID]:
        """
        Profil `Praticien` de l'auteur d'un constat, s'il en a un (RG10).

        Renvoie `None` quand le compte connecté n'a pas de profil : le compte
        reste l'auteur du constat, seul le numéro d'Ordre manque. Exiger un
        profil pour consigner un constat revenait à créer une entité
        réglementaire pour la seule raison de savoir qui a regardé.
        """
        if auteur is not None:
            stmt = select(Praticien.id).where(Praticien.utilisateur_id == auteur.id)
            profil = (await db.execute(stmt)).scalar_one_or_none()
            if profil is not None:
                return profil

        if praticien_id is not None:
            existe = (
                await db.execute(select(Praticien.id).where(Praticien.id == praticien_id))
            ).scalar_one_or_none()
            if existe is None:
                raise EntityNotFoundException("Praticien", praticien_id)
            return praticien_id

        # Découplage : le compte connecté EST l'auteur du constat. L'absence de
        # profil praticien n'empêche pas de consigner ce qu'on a vu : elle
        # empêche seulement d'attribuer un numéro d'Ordre, ce qui n'est pas la
        # même chose.
        return None

    @staticmethod
    async def _verifier_consultation(
        db: AsyncSession, consultation_id: Optional[uuid.UUID], dossier_id: uuid.UUID
    ) -> None:
        """
        Vérifie que la consultation appartient bien au dossier du patient.

        Sans cette vérification, rattacher le constat d'un odontogramme à une
        consultation d'un autre patient produirait un dossier médical faux.
        """
        if consultation_id is None:
            return
        stmt = select(Consultation.id).where(
            Consultation.id == consultation_id,
            Consultation.dossier_medical_id == dossier_id,
        )
        existe = (await db.execute(stmt)).scalar_one_or_none()
        if existe is None:
            raise BusinessRuleViolationException(
                "La consultation indiquée n'appartient pas à ce dossier patient.",
                code="CONSULTATION_AUTRE_DOSSIER",
            )

    # ----------------------------------------------------------------- création
    @staticmethod
    async def creer_ou_obtenir(
        db: AsyncSession,
        patient_id: uuid.UUID,
        *,
        type_odontogramme: str = TYPE_ADULTE,
        systeme_notation: str = "FDI",
        auteur: Optional[Utilisateur] = None,
        creer_si_absent: bool = True,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Odontogramme:
        """
        Retourne l'odontogramme du patient, en le générant si nécessaire.

        La génération applique RG11 : 32 dents pour un adulte, 20 pour un
        enfant. Le type MIXTE (dentition de transition) est traité comme l'adulte
        côté pré-remplissage ; le praticien peut ensuite retirer ou ajouter les
        dents de lait au fil des consultations.
        """
        patient, dossier = await OdontogrammeService._obtenir_dossier(db, patient_id)

        stmt = select(Odontogramme).where(Odontogramme.dossier_medical_id == dossier.id)
        existant = (await db.execute(stmt)).scalar_one_or_none()
        if existant is not None:
            return await OdontogrammeService._charger(db, existant.id)

        if not creer_si_absent:
            raise EntityNotFoundException("Odontogramme", f"patient {patient_id}")

        if patient.archive:
            raise BusinessRuleViolationException(
                f"Le dossier {patient.numero_dossier} est archivé.",
                code="PATIENT_ARCHIVE",
            )

        type_normalise = (type_odontogramme or TYPE_ADULTE).strip().upper()
        if type_normalise not in (TYPE_ADULTE, TYPE_ENFANT, TYPE_MIXTE):
            raise BusinessRuleViolationException(
                f"Type d'odontogramme inconnu : {type_odontogramme}."
            )

        if type_normalise == TYPE_ENFANT:
            numeros = list(DENTS_LAIT_ENFANT)
        else:
            numeros = list(DENTS_PERMANENTES_ADULTE)

        odontogramme = Odontogramme(
            dossier_medical_id=dossier.id,
            type=type_normalise,
            systeme_notation=(systeme_notation or "FDI").strip().upper(),
        )
        db.add(odontogramme)
        await db.flush()

        for numero in numeros:
            db.add(
                Dent(
                    odontogramme_id=odontogramme.id,
                    numero_fdi=numero,
                    numero_universal=vers_universal(numero),
                    etat_actuel=ETAT_SAINE,
                )
            )
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="ODONTOGRAMME_CREATE",
            resource_type="Odontogramme",
            resource_id=str(odontogramme.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(patient.id),
                "numero_dossier": patient.numero_dossier,
                "type": type_normalise,
                "nb_dents": len(numeros),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info(
            "odontogramme_genere",
            patient_id=str(patient.id),
            type=type_normalise,
            nb_dents=len(numeros),
        )
        return await OdontogrammeService._charger(db, odontogramme.id)

    # ------------------------------------------------------------------- lecture
    @staticmethod
    async def obtenir_ou_creer(
        db: AsyncSession,
        patient_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Odontogramme:
        """Lecture d'un odontogramme, avec génération paresseuse si absent."""
        return await OdontogrammeService.creer_ou_obtenir(
            db,
            patient_id,
            auteur=auteur,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    @staticmethod
    def synthese(odontogramme: Odontogramme) -> Dict[str, Any]:
        """Compteurs d'aide à la décision, calculés à la volée."""
        dents = odontogramme.dents
        soignees = [d for d in dents if d.etat_actuel in ETATS_SOIGNES]
        a_traiter = [d for d in dents if d.etat_actuel in ETATS_ATTENTION or d.etat_actuel == "A_TRAITER"]
        absentes = [
            d for d in dents if d.etat_actuel in ("ABSENTE_EXTRACTEE", "ABSENTE_CONGENITALE")
        ]
        return {
            "nb_dents": len(dents),
            "nb_dents_soignees": len(soignees),
            "nb_dents_a_traiter": len(a_traiter),
            "nb_dents_absentes": len(absentes),
            "resume": (
                f"{len(soignees)} dent(s) soignée(s), "
                f"{len(a_traiter)} à traiter, "
                f"{len(absentes)} absente(s)"
            ),
        }

    # ------------------------------------------------------------------ écriture
    @staticmethod
    async def _appliquer_mise_a_jour(
        db: AsyncSession,
        odontogramme: Odontogramme,
        dossier_id: uuid.UUID,
        mise_a_jour: DentMiseAJour,
        auteur: Optional[Utilisateur],
        praticien_id_resolu: uuid.UUID,
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> Dent:
        """Applique un changement d'état et écrit la ligne d'historique (RG10)."""
        numero = valider_numero_dent(mise_a_jour.numero_fdi)
        nouvel_etat = valider_etat_dent(mise_a_jour.etat)
        face = valider_face(mise_a_jour.face)

        await OdontogrammeService._verifier_consultation(
            db, mise_a_jour.consultation_id, dossier_id
        )

        dent = next((d for d in odontogramme.dents if d.numero_fdi == numero), None)
        if dent is None:
            raise EntityNotFoundException(
                "Dent",
                numero,
                details={
                    "message": (
                        f"La dent {numero} ne fait pas partie de cet odontogramme "
                        f"(type {odontogramme.type}). Créez la dent avant de la modifier."
                    )
                },
            )

        etat_precedent = dent.etat_actuel
        dent.etat_actuel = nouvel_etat
        if mise_a_jour.mobilite is not None:
            dent.mobilite = mise_a_jour.mobilite
        if mise_a_jour.notes is not None:
            dent.notes = mise_a_jour.notes
        dent.updated_at = datetime.now(timezone.utc)

        # RG10 : la ligne d'historique porte la date, l'état, l'état antérieur,
        # la face, la consultation et le praticien.
        historique = EtatDentHistorique(
            date_constat=mise_a_jour.date_constat or datetime.now(timezone.utc),
            dent_id=dent.id,
            etat=nouvel_etat,
            etat_precedent=etat_precedent,
            face=face,
            consultation_id=mise_a_jour.consultation_id,
            praticien_id=praticien_id_resolu,
            notes=mise_a_jour.notes,
        )
        db.add(historique)
        await db.flush()

        # Si une face est précisée, on la met à jour : c'est la localisation de
        # la lésion, pas une information séparée.
        if face:
            face_existante = next((f for f in dent.faces if f.face == face), None)
            if face_existante is None:
                db.add(FaceDent(dent_id=dent.id, face=face, etat=nouvel_etat))
            else:
                face_existante.etat = nouvel_etat
            await db.flush()

        await AuditService.log_action(
            db=db,
            action="DENT_ETAT_UPDATE",
            resource_type="Dent",
            resource_id=str(dent.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(odontogramme.dossier_medical.patient_id)
                if odontogramme.dossier_medical
                else None,
                "numero_fdi": numero,
                "etat_precedent": etat_precedent,
                "etat_nouveau": nouvel_etat,
                "face": face,
                "consultation_id": str(mise_a_jour.consultation_id)
                if mise_a_jour.consultation_id
                else None,
                "praticien_id": str(praticien_id_resolu),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        return dent

    @staticmethod
    async def mettre_a_jour_dent(
        db: AsyncSession,
        patient_id: uuid.UUID,
        mise_a_jour: DentMiseAJour,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Odontogramme:
        """Met à jour une seule dent (UC5 du CDC)."""
        odontogramme = await OdontogrammeService.obtenir_ou_creer(
            db, patient_id, auteur, client_ip=client_ip, user_agent=user_agent
        )
        _, dossier = await OdontogrammeService._obtenir_dossier(db, patient_id)

        praticien_id = await OdontogrammeService._resoudre_praticien(
            db, auteur, mise_a_jour.praticien_id
        )

        await OdontogrammeService._appliquer_mise_a_jour(
            db,
            odontogramme,
            dossier.id,
            mise_a_jour,
            auteur,
            praticien_id,
            client_ip,
            user_agent,
        )

        await db.commit()
        logger.info(
            "dent_mise_a_jour",
            patient_id=str(patient_id),
            numero_fdi=mise_a_jour.numero_fdi,
            etat=mise_a_jour.etat,
        )
        return await OdontogrammeService._charger(db, odontogramme.id)

    @staticmethod
    async def mettre_a_jour_dents(
        db: AsyncSession,
        patient_id: uuid.UUID,
        lot: DentsMiseAJourLot,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Odontogramme:
        """
        Met à jour plusieurs dents en une transaction.

        Une seule écriture d'audit par dent, mais un seul commit : soit toutes
        les dents sont modifiées, soit aucune. Un lot partiellement appliqué
        laisserait un odontogramme incohérent avec la consultation qui l'a
        produit.
        """
        odontogramme = await OdontogrammeService.obtenir_ou_creer(
            db, patient_id, auteur, client_ip=client_ip, user_agent=user_agent
        )
        _, dossier = await OdontogrammeService._obtenir_dossier(db, patient_id)

        # Les overridden communs s'appliquent à chaque dent du lot.
        praticien_id = await OdontogrammeService._resoudre_praticien(
            db, auteur, lot.praticien_id
        )

        for item in lot.dents:
            enrichi = item.model_copy(
                update={
                    "consultation_id": item.consultation_id or lot.consultation_id,
                    "praticien_id": item.praticien_id or lot.praticien_id,
                }
            )
            await OdontogrammeService._appliquer_mise_a_jour(
                db,
                odontogramme,
                dossier.id,
                enrichi,
                auteur,
                praticien_id,
                client_ip,
                user_agent,
            )

        await db.commit()
        logger.info(
            "dents_misees_a_jour_lot",
            patient_id=str(patient_id),
            nb_dents=len(lot.dents),
        )
        return await OdontogrammeService._charger(db, odontogramme.id)

    # ------------------------------------------------------------------- faces
    @staticmethod
    async def mettre_a_jour_faces(
        db: AsyncSession,
        patient_id: uuid.UUID,
        numero_fdi: int,
        faces: List[FaceMiseAJour],
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Odontogramme:
        """
        Met à jour les faces d'une dent.

        Les faces sont enregistrées telles quelles : une face revenue à l'état
        sain garde sa ligne, ce qui évite de perdre l'information « cette face a
        été traitée » sans quoi l'historique du soin disparaîtrait du rendu.
        """
        numero = valider_numero_dent(numero_fdi)
        odontogramme = await OdontogrammeService.obtenir_ou_creer(
            db, patient_id, auteur, client_ip=client_ip, user_agent=user_agent
        )

        dent = next((d for d in odontogramme.dents if d.numero_fdi == numero), None)
        if dent is None:
            raise EntityNotFoundException("Dent", numero)

        praticien_id = await OdontogrammeService._resoudre_praticien(db, auteur, None)

        for item in faces:
            face = valider_face(item.face)
            etat = valider_etat_dent(item.etat)
            existante = next((f for f in dent.faces if f.face == face), None)

            if existante is None:
                db.add(FaceDent(dent_id=dent.id, face=face, etat=etat, notes=item.notes))
            else:
                existante.etat = etat
                existante.notes = item.notes
                existante.updated_at = datetime.now(timezone.utc)

            db.add(
                EtatDentHistorique(
                    date_constat=datetime.now(timezone.utc),
                    dent_id=dent.id,
                    etat=etat,
                    etat_precedent=dent.etat_actuel,
                    face=face,
                    praticien_id=praticien_id,
                    notes=item.notes,
                )
            )

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="DENT_FACES_UPDATE",
            resource_type="Dent",
            resource_id=str(dent.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "numero_fdi": numero,
                "faces": [{"face": f.face, "etat": f.etat} for f in faces],
                "praticien_id": str(praticien_id),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return await OdontogrammeService._charger(db, odontogramme.id)

    # -------------------------------------------------------------- historique
    @staticmethod
    async def historique_dent(
        db: AsyncSession, patient_id: uuid.UUID, numero_fdi: int
    ) -> Dict[str, Any]:
        """Historique complet d'une dent (RG10) : le praticien peut justifier chaque état."""
        numero = valider_numero_dent(numero_fdi)
        odontogramme = await OdontogrammeService.obtenir_ou_creer(db, patient_id)
        dent = next((d for d in odontogramme.dents if d.numero_fdi == numero), None)
        if dent is None:
            raise EntityNotFoundException("Dent", numero)

        stmt = (
            select(EtatDentHistorique)
            .where(EtatDentHistorique.dent_id == dent.id)
            .order_by(EtatDentHistorique.date_constat.desc())
        )
        historique = list((await db.execute(stmt)).scalars().all())
        return {"dent": dent, "historique": historique}

    @staticmethod
    async def historique_global(
        db: AsyncSession, patient_id: uuid.UUID, limite: int = 100
    ) -> List[EtatDentHistorique]:
        """Historique du patient, toutes dents confondues, du plus récent au plus ancien."""
        odontogramme = await OdontogrammeService.obtenir_ou_creer(db, patient_id)
        ids_dents = [d.id for d in odontogramme.dents]
        if not ids_dents:
            return []

        stmt = (
            select(EtatDentHistorique)
            .where(EtatDentHistorique.dent_id.in_(ids_dents))
            .order_by(EtatDentHistorique.date_constat.desc())
            .limit(limite)
        )
        return list((await db.execute(stmt)).scalars().all())

    # ----------------------------------------------------------- charting
    @staticmethod
    async def enregistrer_charting(
        db: AsyncSession,
        patient_id: uuid.UUID,
        charting: ChartingParodontalCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ChartingParodontal:
        """Enregistre un relevé parodental (sondage 6 points + indices)."""
        odontogramme = await OdontogrammeService.obtenir_ou_creer(db, patient_id, auteur)
        _, dossier = await OdontogrammeService._obtenir_dossier(db, patient_id)

        dent = next((d for d in odontogramme.dents if d.id == charting.dent_id), None)
        if dent is None:
            raise EntityNotFoundException("Dent", charting.dent_id)

        await OdontogrammeService._verifier_consultation(
            db, charting.consultation_id, dossier.id
        )
        praticien_id = await OdontogrammeService._resoudre_praticien(db, auteur, None)

        releve = ChartingParodontal(
            dent_id=dent.id,
            consultation_id=charting.consultation_id,
            sondages=[s.model_dump() for s in charting.sondages] if charting.sondages else None,
            nac=charting.nac,
            recession=charting.recession,
            saignement_bop=charting.saignement_bop,
            suppuration=charting.suppuration,
            mobilite=charting.mobilite,
            furcation=charting.furcation,
            plaque_ipv=charting.plaque_ipv,
            notes=charting.notes,
        )
        db.add(releve)
        await db.flush()

        if charting.mobilite is not None:
            dent.mobilite = charting.mobilite
            await db.flush()

        await AuditService.log_action(
            db=db,
            action="CHARTING_PARODONTAL_CREATE",
            resource_type="ChartingParodontal",
            resource_id=str(releve.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(patient_id),
                "numero_fdi": dent.numero_fdi,
                "nb_sites": len(charting.sondages or []),
                "consultation_id": str(charting.consultation_id) if charting.consultation_id else None,
                "praticien_id": str(praticien_id),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info(
            "charting_parodontal_enregistre",
            patient_id=str(patient_id),
            numero_fdi=dent.numero_fdi,
        )
        return releve

    @staticmethod
    async def lister_chartings(
        db: AsyncSession, patient_id: uuid.UUID, dent_id: Optional[uuid.UUID] = None
    ) -> List[ChartingParodontal]:
        """Relevés parodontaux d'un patient, ou d'une dent si `dent_id` est fourni."""
        odontogramme = await OdontogrammeService.obtenir_ou_creer(db, patient_id)
        ids_dents = [d.id for d in odontogramme.dents]

        stmt = select(ChartingParodontal).where(ChartingParodontal.dent_id.in_(ids_dents))
        if dent_id is not None:
            if dent_id not in ids_dents:
                raise EntityNotFoundException("Dent", dent_id)
            stmt = stmt.where(ChartingParodontal.dent_id == dent_id)

        stmt = stmt.order_by(ChartingParodontal.date_examen.desc())
        return list((await db.execute(stmt)).scalars().all())
