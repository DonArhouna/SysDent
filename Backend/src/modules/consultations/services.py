"""
Services métier du module Consultations & Actes (D1B).

Workflow implémenté (Étape 4 à 6 du diagramme de séquence du CDC) :
  PLANIFIEE -> EN_COURS -> TERMINEE, avec sortie ANNULEE possible avant clôture.

Garde-fous métier :
  - On ne clôt pas une consultation sans diagnostic (pas de facture sans motif).
  - Le total des actes est toujours recalculé (RG07) et jamais reçu du client.
  - Le tarif est figé à la saisie : une révision de la nomenclature ne réécrit pas
    l'historique comptable.
  - Toute écriture clinique est journalisée (traçabilité médico-légale).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.consultations.schemas import (
    ActeRealiseCreate,
    ActeRealiseResponse,
    ActeRealiseUpdate,
    ConsultationAnnuler,
    ConsultationCreate,
    ConsultationTerminer,
    ConsultationUpdate,
    RechercheConsultations,
)
from src.modules.patients.services import AlertService, EtatGeneralService
from src.modules.tenants.models import (
    ActeNomenclature,
    ActeRealise,
    Cabinet,
    Consultation,
    DossierMedical,
    EtatGeneral,
    Patient,
    Praticien,
    StatutConsultationEnum,
    Utilisateur,
)

logger = structlog.get_logger(__name__)

STATUTS_OUVERTS = {"PLANIFIEE", "EN_ATTENTE", "EN_COURS"}
STATUTS_CLOS = {"TERMINEE", "ANNULEE"}

# Champs cliniques modifiables et journalisés lors d'une mise à jour.
CHAMPS_CLINIQUES = [
    "motif",
    "type_motif",
    "motif_detail",
    "anamnese",
    "examen_exobuccal",
    "examen_endobuccal",
    "diagnostic_principal",
    "diagnostics_differentiels",
    "codes_cim10",
    "plan_traitement",
    "recommandations",
    "prochain_rdv_prevu",
    "duree_minutes",
]


class NomenclatureService:
    """Nomenclature des actes : recherche et résolution de tarif."""

    @staticmethod
    async def lister(
        db: AsyncSession,
        q: Optional[str] = None,
        categorie: Optional[str] = None,
        inclure_inactifs: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ActeNomenclature], int]:
        conditions = []
        if not inclure_inactifs:
            conditions.append(ActeNomenclature.actif.is_(True))
        if categorie:
            conditions.append(ActeNomenclature.categorie == categorie.upper())
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
        data_stmt = data_stmt.order_by(ActeNomenclature.categorie, ActeNomenclature.code).offset(offset).limit(limit)
        rows = await db.execute(data_stmt)
        return list(rows.scalars().all()), total

    @staticmethod
    async def obtenir(db: AsyncSession, acte_id: uuid.UUID) -> ActeNomenclature:
        acte = (await db.execute(select(ActeNomenclature).where(ActeNomenclature.id == acte_id))).scalar_one_or_none()
        if acte is None:
            raise EntityNotFoundException("Acte de nomenclature", acte_id)
        return acte

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
        actif: bool = True,
        auteur: Optional[Utilisateur] = None,
    ) -> ActeNomenclature:
        code_normalise = code.strip().upper()
        existant = (
            await db.execute(select(ActeNomenclature).where(ActeNomenclature.code == code_normalise))
        ).scalar_one_or_none()
        if existant:
            raise BusinessRuleViolationException(
                f"Un acte avec le code '{code_normalise}' existe déjà.", code="ACTE_CODE_EXISTANT"
            )

        acte = ActeNomenclature(
            code=code_normalise,
            libelle=libelle.strip(),
            categorie=categorie.strip().upper(),
            tarif_base=tarif_base,
            duree_estimee_min=duree_estimee_min,
            unitaire=unitaire,
            actif=actif,
        )
        db.add(acte)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="ACTE_NOMENCLATURE_CREATE",
            resource_type="ActeNomenclature",
            resource_id=str(acte.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"code": acte.code, "libelle": acte.libelle, "tarif_base": str(acte.tarif_base)},
        )
        await db.commit()
        return acte


class ConsultationService:
    # ------------------------------------------------------------------ helpers
    @staticmethod
    async def _resoudre_patient_et_dossier(
        db: AsyncSession, patient_id: uuid.UUID
    ) -> Tuple[Patient, DossierMedical]:
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
    async def _resoudre_cabinet(db: AsyncSession, cabinet_id: Optional[uuid.UUID]) -> Cabinet:
        """
        Détermine le cabinet de réalisation. Un tenant peut gérer plusieurs sites :
        si aucun n'est fourni, on prend le seul cabinet actif du dossier.
        """
        if cabinet_id is not None:
            cabinet = (
                await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id, Cabinet.actif.is_(True)))
            ).scalar_one_or_none()
            if cabinet is None:
                raise EntityNotFoundException("Cabinet", cabinet_id)
            return cabinet

        cabinets = list((await db.execute(select(Cabinet).where(Cabinet.actif.is_(True)))).scalars().all())
        if not cabinets:
            raise BusinessRuleViolationException(
                "Aucun cabinet actif dans ce dossier. Créez un cabinet avant d'enregistrer une consultation.",
                code="AUCUN_CABINET_ACTIF",
            )
        if len(cabinets) > 1:
            raise BusinessRuleViolationException(
                "Plusieurs cabinets actifs dans ce dossier : précisez `cabinet_id`.",
                code="CABINET_AMBIGU",
            )
        return cabinets[0]

    @staticmethod
    async def _charger(
        db: AsyncSession, consultation_id: uuid.UUID
    ) -> Consultation:
        # Toutes les relations lues ensuite par `detail()` ou par le routeur sont
        # chargées ici : un accès paresseux en contexte async lèverait
        # MissingGreenlet (le lazy-load s'exécute hors du greenlet await).
        stmt = (
            select(Consultation)
            .options(
                selectinload(Consultation.actes_realises).selectinload(ActeRealise.acte),
                selectinload(Consultation.dossier_medical).selectinload(DossierMedical.patient),
                selectinload(Consultation.dossier_medical).selectinload(DossierMedical.antecedents),
                selectinload(Consultation.dossier_medical).selectinload(DossierMedical.etat_general),
            )
            .where(Consultation.id == consultation_id)
        )
        consultation = (await db.execute(stmt)).scalar_one_or_none()
        if consultation is None:
            raise EntityNotFoundException("Consultation", consultation_id)
        return consultation

    @staticmethod
    async def _praticien_du_user(
        db: AsyncSession, auteur: Optional[Utilisateur], praticien_id: Optional[uuid.UUID]
    ) -> Praticien:
        """
        Détermine le praticien responsable de la consultation.

        Un compte non-praticien (secrétaire, comptable) ne peut pas porter une
        consultation : le praticien est l'auteur clinique du acte, la traçabilité
        médico-légale l'exige. On tente d'abord le praticien rattaché au compte.
        """
        if auteur is not None:
            stmt = select(Praticien).where(Praticien.utilisateur_id == auteur.id)
            profil = (await db.execute(stmt)).scalar_one_or_none()
            if profil is not None:
                return profil

        if praticien_id is None:
            raise BusinessRuleViolationException(
                "Votre compte n'est rattaché à aucun profil praticien : impossible d'attribuer la consultation.",
                code="PRATICIEN_NON_IDENTIFIE",
            )

        profil = (await db.execute(select(Praticien).where(Praticien.id == praticien_id))).scalar_one_or_none()
        if profil is None:
            raise EntityNotFoundException("Praticien", praticien_id)
        return profil

    @staticmethod
    async def _total_actes(actes: List[ActeRealise]) -> Decimal:
        """RG07 : le total est recalculé à partir des lignes, jamais fourni en entrée."""
        total = Decimal("0.00")
        for acte in actes:
            total += (acte.tarif_applique or Decimal("0.00")) * acte.quantite
        return total.quantize(Decimal("0.01"))

    @staticmethod
    def _verifier_modifiable(consultation: Consultation) -> None:
        statut = consultation.statut.value if hasattr(consultation.statut, "value") else str(consultation.statut)
        if statut in STATUTS_CLOS:
            raise BusinessRuleViolationException(
                f"Une consultation {statut.lower()} n'est plus modifiable. Créez une nouvelle consultation.",
                code="CONSULTATION_CLOSED",
            )

    @staticmethod
    def _marquer_etat_general_a_verifier(dossier: Optional[DossierMedical]) -> bool:
        """
        RG02 : l'état général doit être vérifié à chaque nouvelle consultation.

        On ne bloque pas — un praticien peut légitimement consulter sans mise à
        jour — mais on signale une saisie absente ou vieille de plus d'un an.

        Lecture directe sur la relation déjà chargée par `_charger()` : aucune
        requête, aucun lazy-load (qui échouerait en contexte async).
        """
        if dossier is None or dossier.etat_general is None:
            return True
        derniere_maj = dossier.etat_general.updated_at
        if derniere_maj is None:
            return True
        return (datetime.now(timezone.utc) - derniere_maj).days > 365

    # ------------------------------------------------------------------- create
    @staticmethod
    async def demarrer(
        db: AsyncSession,
        data: ConsultationCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        praticien_id: Optional[uuid.UUID] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Consultation:
        """Démarre une consultation (Étape 4 du CDC) et la bascule en EN_COURS."""
        patient, dossier = await ConsultationService._resoudre_patient_et_dossier(db, data.patient_id)

        if patient.archive:
            raise BusinessRuleViolationException(
                f"Le dossier {patient.numero_dossier} est archivé : une consultation n'est pas possible.",
                code="PATIENT_ARCHIVE",
            )

        praticien = await ConsultationService._praticien_du_user(db, auteur, praticien_id)
        cabinet = await ConsultationService._resoudre_cabinet(db, data.cabinet_id)

        consultation = Consultation(
            dossier_medical_id=dossier.id,
            praticien_id=praticien.id,
            cabinet_id=cabinet.id,
            motif=data.motif.strip(),
            type_motif=data.type_motif,
            motif_detail=data.motif_detail,
            anamnese=data.anamnese,
            # ENUM, pas chaîne : SQLAlchemy ne convertit la valeur qu'à la
            # LECTURE. Écrire la chaîne laissait l'attribut ORM dans cet état
            # jusqu'au rechargement suivant, et le module Rendez-vous — qui
            # sérialise cette consultation sans la recharger — lisait
            # `.statut.value` et plantait.
            statut=StatutConsultationEnum.EN_COURS,
            date_consultation=data.date_consultation or datetime.now(timezone.utc),
            duree_minutes=data.duree_minutes,
        )
        db.add(consultation)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="CONSULTATION_START",
            resource_type="Consultation",
            resource_id=str(consultation.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "patient_id": str(patient.id),
                "numero_dossier": patient.numero_dossier,
                "motif": consultation.motif,
                "type_motif": consultation.type_motif.value,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info(
            "consultation_demarree",
            consultation_id=str(consultation.id),
            patient_id=str(patient.id),
        )
        return await ConsultationService._charger(db, consultation.id)

    # ------------------------------------------------------------------- update
    @staticmethod
    async def mettre_a_jour(
        db: AsyncSession,
        consultation_id: uuid.UUID,
        data: ConsultationUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Consultation:
        """Met à jour les champs cliniques (Étape 5 du CDC : examen et diagnostic)."""
        consultation = await ConsultationService._charger(db, consultation_id)
        ConsultationService._verifier_modifiable(consultation)

        champs = data.model_dump(exclude_unset=True, exclude_none=True)
        if not champs:
            return consultation

        avant = {champ: getattr(consultation, champ, None) for champ in champs}
        for champ, valeur in champs.items():
            setattr(consultation, champ, valeur)

        # Une consultation passe en cours dès qu'on la renseigne cliniquement.
        statut_actuel = consultation.statut.value if hasattr(consultation.statut, "value") else consultation.statut
        if statut_actuel == "PLANIFIEE":
            consultation.statut = "EN_COURS"

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="CONSULTATION_UPDATE",
            resource_type="Consultation",
            resource_id=str(consultation.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                champ: {
                    "ancien": _serialiser(avant.get(champ)),
                    "nouveau": _serialiser(getattr(consultation, champ)),
                }
                for champ in champs
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return await ConsultationService._charger(db, consultation_id)

    # ----------------------------------------------------------------- terminer
    @staticmethod
    async def terminer(
        db: AsyncSession,
        consultation_id: uuid.UUID,
        data: ConsultationTerminer,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Consultation:
        """
        Clôture de la consultation (Étape 6 du CDC).

        Un diagnostic principal est exigé : sans lui, la facture qui en découle
        n'a aucune base clinique, et la règle RG02 impose que l'état général ait
        été vu. Les modifications post-clôture sont impossibles.
        """
        consultation = await ConsultationService._charger(db, consultation_id)
        ConsultationService._verifier_modifiable(consultation)

        if data.diagnostic_principal is not None:
            consultation.diagnostic_principal = data.diagnostic_principal.strip()
        elif not (consultation.diagnostic_principal or "").strip():
            raise BusinessRuleViolationException(
                "Impossible de terminer une consultation sans diagnostic principal.",
                code="DIAGNOSTIC_OBLIGATOIRE",
            )

        if data.codes_cim10 is not None:
            consultation.codes_cim10 = data.codes_cim10
        if data.plan_traitement is not None:
            consultation.plan_traitement = data.plan_traitement
        if data.recommandations is not None:
            consultation.recommandations = data.recommandations
        if data.prochain_rdv_prevu is not None:
            consultation.prochain_rdv_prevu = data.prochain_rdv_prevu

        consultation.statut = "TERMINEE"
        consultation.updated_at = datetime.now(timezone.utc)

        await db.flush()

        total = await ConsultationService._total_actes(consultation.actes_realises)

        await AuditService.log_action(
            db=db,
            action="CONSULTATION_TERMINATE",
            resource_type="Consultation",
            resource_id=str(consultation.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "diagnostic_principal": consultation.diagnostic_principal,
                "nb_actes": len(consultation.actes_realises),
                "total_actes": str(total),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        logger.info("consultation_terminee", consultation_id=str(consultation.id), total=str(total))
        return await ConsultationService._charger(db, consultation_id)

    # ------------------------------------------------------------------ annuler
    @staticmethod
    async def annuler(
        db: AsyncSession,
        consultation_id: uuid.UUID,
        data: ConsultationAnnuler,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Consultation:
        """
        Annulation. Refusée si des actes ont déjà été saisis : un acte réalisé est
        un acte physique, il se facture ou se corrige, il ne s'efface pas.
        """
        consultation = await ConsultationService._charger(db, consultation_id)
        ConsultationService._verifier_modifiable(consultation)

        if consultation.actes_realises:
            raise BusinessRuleViolationException(
                f"Cette consultation comporte {len(consultation.actes_realises)} acte(s) : "
                "supprimez-les d'abord, ou laissez la consultation se terminer.",
                code="CONSULTATION_HAS_ACTES",
            )

        consultation.statut = "ANNULEE"
        consultation.updated_at = datetime.now(timezone.utc)

        await db.flush()
        await AuditService.log_action(
            db=db,
            action="CONSULTATION_CANCEL",
            resource_type="Consultation",
            resource_id=str(consultation.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"motif_annulation": data.motif_annulation},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        logger.info("consultation_annulee", consultation_id=str(consultation.id))
        return await ConsultationService._charger(db, consultation_id)

    # ---------------------------------------------------------------- recherche
    @staticmethod
    async def rechercher(
        db: AsyncSession, filtres: RechercheConsultations, offset: int, limit: int
    ) -> Tuple[List[Consultation], int]:
        conditions = []

        if filtres.patient_id:
            conditions.append(DossierMedical.patient_id == filtres.patient_id)
        if filtres.praticien_id:
            conditions.append(Consultation.praticien_id == filtres.praticien_id)
        if filtres.statut:
            conditions.append(Consultation.statut == filtres.statut)
        if filtres.date_debut:
            conditions.append(Consultation.date_consultation >= filtres.date_debut)
        if filtres.date_fin:
            conditions.append(Consultation.date_consultation <= filtres.date_fin)

        base = select(Consultation)
        if filtres.patient_id:
            base = base.join(DossierMedical, DossierMedical.id == Consultation.dossier_medical_id)
        if conditions:
            base = base.where(*conditions)

        count_stmt = select(func.count(func.distinct(Consultation.id)))
        if filtres.patient_id:
            count_stmt = count_stmt.join(DossierMedical, DossierMedical.id == Consultation.dossier_medical_id)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())

        data_stmt = (
            base.options(
                selectinload(Consultation.dossier_medical).selectinload(DossierMedical.patient),
                selectinload(Consultation.dossier_medical).selectinload(DossierMedical.antecedents),
                selectinload(Consultation.dossier_medical).selectinload(DossierMedical.etat_general),
            )
            .order_by(Consultation.date_consultation.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = await db.execute(data_stmt)
        return list(rows.scalars().unique().all()), total

    @staticmethod
    async def detail(
        db: AsyncSession,
        consultation_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Consultation complète : actes, total, durée réelle, alertes du patient."""
        consultation = await ConsultationService._charger(db, consultation_id)
        dossier = consultation.dossier_medical

        # L'état général et les antécédents sont déjà chargés par `_charger` :
        # on les lit sans requête supplémentaire et sans lazy-load.
        etat_general = dossier.etat_general if dossier else None
        antecedents: List[Any] = list(dossier.antecedents) if dossier else []

        total = await ConsultationService._total_actes(consultation.actes_realises)

        duree_reelle = None
        if consultation.statut in ("TERMINEE", "ANNULEE") and consultation.created_at and consultation.updated_at:
            ecoule = consultation.updated_at - consultation.created_at
            minutes = int(ecoule.total_seconds() // 60)
            # La durée saisie reste la référence : le delta technique (durée de la
            # requête HTTP incluse) ne reflète pas le temps passé au fauteuil.
            if minutes > 0:
                duree_reelle = minutes

        return {
            "consultation": consultation,
            "total": total,
            "duree_reelle_minutes": duree_reelle,
            "etat_general_a_verifier": ConsultationService._marquer_etat_general_a_verifier(dossier),
            "alertes": AlertService.calculer(etat_general, antecedents),
        }


class ActeRealiseService:
    """Saisie et correction des actes réalisés (Étape 6 du CDC)."""

    @staticmethod
    async def lister(db: AsyncSession, consultation_id: uuid.UUID) -> List[ActeRealise]:
        await ConsultationService._charger(db, consultation_id)  # 404 si consultation absente
        stmt = (
            select(ActeRealise)
            .options(selectinload(ActeRealise.acte))
            .where(ActeRealise.consultation_id == consultation_id)
            .order_by(ActeRealise.created_at)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def ajouter(
        db: AsyncSession,
        consultation_id: uuid.UUID,
        data: ActeRealiseCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActeRealise:
        consultation = await ConsultationService._charger(db, consultation_id)
        ConsultationService._verifier_modifiable(consultation)

        acte_nomenclature = await NomenclatureService.obtenir(db, data.acte_id)
        if not acte_nomenclature.actif:
            raise BusinessRuleViolationException(
                f"L'acte '{acte_nomenclature.code}' n'est plus actif et ne peut pas être facturé.",
                code="ACTE_INACTIF",
            )

        # Un soin unitaire porte nécessairement sur une dent identifiée.
        if acte_nomenclature.unitaire and data.dent_numero is None:
            raise BusinessRuleViolationException(
                f"L'acte '{acte_nomenclature.code}' est un soin unitaire : le numéro de dent est obligatoire.",
                code="DENT_NUMERO_OBLIGATOIRE",
            )
        if data.face and data.dent_numero is None:
            raise BusinessRuleViolationException(
                "Une face ne peut être précisée sans numéro de dent.",
                code="DENT_NUMERO_OBLIGATOIRE",
            )

        # Tarif : forfait saisi (accord commercial) sinon tarif de la nomenclature.
        # Figé ici : une révision ultérieure de la nomenclature ne réécrit pas l'historique.
        tarif = data.tarif_applique if data.tarif_applique is not None else acte_nomenclature.tarif_base
        tarif = Decimal(tarif).quantize(Decimal("0.01"))

        acte = ActeRealise(
            consultation_id=consultation.id,
            acte_id=acte_nomenclature.id,
            dent_numero=data.dent_numero,
            face=data.face,
            description=data.description,
            tarif_applique=tarif,
            quantite=data.quantite,
            notes=data.notes,
        )
        db.add(acte)
        await db.flush()
        # La relation `acte` est posée explicitement : le routeur la lit pour
        # renvoyer code et libellé, et un accès paresseux après commit échouerait
        # en contexte async (MissingGreenlet).
        acte.acte = acte_nomenclature

        await AuditService.log_action(
            db=db,
            action="ACTE_REALISE_CREATE",
            resource_type="ActeRealise",
            resource_id=str(acte.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "consultation_id": str(consultation.id),
                "code": acte_nomenclature.code,
                "libelle": acte_nomenclature.libelle,
                "tarif_applique": str(tarif),
                "quantite": acte.quantite,
                "dent_numero": acte.dent_numero,
                "face": acte.face,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        # Après commit, la session expire les attributs : on ré-exécute une requête
        # avec les relations chargées plutôt que de laisser le routeur lazy-loader.
        return (
            await db.execute(
                select(ActeRealise)
                .options(selectinload(ActeRealise.acte))
                .where(ActeRealise.id == acte.id)
            )
        ).scalar_one()

    @staticmethod
    async def modifier(
        db: AsyncSession,
        acte_id: uuid.UUID,
        data: ActeRealiseUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ActeRealise:
        stmt = (
            select(ActeRealise)
            .options(selectinload(ActeRealise.acte), selectinload(ActeRealise.consultation))
            .where(ActeRealise.id == acte_id)
        )
        acte = (await db.execute(stmt)).scalar_one_or_none()
        if acte is None:
            raise EntityNotFoundException("Acte réalisé", acte_id)

        ConsultationService._verifier_modifiable(acte.consultation)

        champs = data.model_dump(exclude_unset=True, exclude_none=True)
        if not champs:
            return acte

        # Cohérence dent/face après fusion des champs modifiés avec l'existant.
        dent = champs.get("dent_numero", acte.dent_numero)
        face = champs.get("face", acte.face)
        if face and dent is None:
            raise BusinessRuleViolationException(
                "Une face ne peut être précisée sans numéro de dent.",
                code="DENT_NUMERO_OBLIGATOIRE",
            )
        if acte.acte.unitaire and dent is None:
            raise BusinessRuleViolationException(
                f"L'acte '{acte.acte.code}' est un soin unitaire : le numéro de dent est obligatoire.",
                code="DENT_NUMERO_OBLIGATOIRE",
            )

        avant = {champ: getattr(acte, champ, None) for champ in champs}
        for champ, valeur in champs.items():
            setattr(acte, champ, valeur)

        await db.flush()

        await AuditService.log_action(
            db=db,
            action="ACTE_REALISE_UPDATE",
            resource_type="ActeRealise",
            resource_id=str(acte.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                champ: {
                    "ancien": _serialiser(avant.get(champ)),
                    "nouveau": _serialiser(getattr(acte, champ)),
                }
                for champ in champs
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.commit()
        return (
            await db.execute(
                select(ActeRealise)
                .options(selectinload(ActeRealise.acte))
                .where(ActeRealise.id == acte.id)
            )
        ).scalar_one()

    @staticmethod
    async def supprimer(
        db: AsyncSession,
        acte_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        motif: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Suppression d'un acte saisi par erreur. La trace d'audit conserve le code,
        le libellé et le montant : le journal reste la source de vérité.
        """
        stmt = (
            select(ActeRealise)
            .options(selectinload(ActeRealise.acte), selectinload(ActeRealise.consultation))
            .where(ActeRealise.id == acte_id)
        )
        acte = (await db.execute(stmt)).scalar_one_or_none()
        if acte is None:
            raise EntityNotFoundException("Acte réalisé", acte_id)

        ConsultationService._verifier_modifiable(acte.consultation)

        await AuditService.log_action(
            db=db,
            action="ACTE_REALISE_DELETE",
            resource_type="ActeRealise",
            resource_id=str(acte.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "consultation_id": str(acte.consultation_id),
                "code": acte.acte.code,
                "libelle": acte.acte.libelle,
                "tarif_applique": str(acte.tarif_applique),
                "quantite": acte.quantite,
                "motif_suppression": motif,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

        await db.delete(acte)
        await db.commit()
        logger.info("acte_realise_supprime", acte_id=str(acte_id))

    @staticmethod
    async def total_consultation(db: AsyncSession, consultation_id: uuid.UUID) -> Decimal:
        """Total facturable d'une consultation (RG07). Point d'entrée du pôle facturation."""
        stmt = select(ActeRealise).where(ActeRealise.consultation_id == consultation_id)
        actes = list((await db.execute(stmt)).scalars().all())
        return await ConsultationService._total_actes(actes)


def _serialiser(valeur: Any) -> Any:
    """Rend une valeur ORM lisible dans le JSONB d'audit."""
    if valeur is None or isinstance(valeur, (str, int, float, bool)):
        return valeur
    if isinstance(valeur, Decimal):
        return str(valeur)
    if isinstance(valeur, (datetime,)):
        return valeur.isoformat()
    if isinstance(valeur, (list, tuple)):
        return [_serialiser(v) for v in valeur]
    return str(valeur)
