"""
Services métier du module Facturation & Caisse (D2C).

Contrat inter-pôles (voir COMMANDS.md) :
  - une facture issue d'une consultation est générée depuis les ACTES RÉALISÉS,
    le total est recalculé côté serveur (RG07) et jamais reçu du client ;
  - les générateurs de numéros (`FAC-`, `RECU-`, `DEV-`) viennent de
    `src/common/numerotation.py` : la caisse ne compose jamais un numéro à la main.

Garde-fous financiers :
  - on n'encaisse pas plus que le reste à payer : un trop-perçu relève du
    remboursement, pas d'une caisse qui laisserait un solde négatif ;
  - une facture annulée est figée : plus aucun paiement n'y entre ;
  - une facture avec encaissements ne s'annule pas : il faut d'abord rembourser
    (module à venir) — sinon la caisse du jour ne rapprocherait plus ;
  - un devis accepté se convertit en facture une seule fois (RG14).

Toute écriture passe par l'audit trail (RG12) : émission, encaissement,
annulation, conversion.
"""

import calendar
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from typing import List, Optional, Sequence, Tuple

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.common.numerotation import (
    generer_numero_devis,
    generer_numero_facture,
    generer_numero_recu_paiement,
)
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.audit.services import AuditService
from src.modules.facturation.schemas import (
    DevisCreate,
    DevisStatutUpdate,
    FactureConsultationCreate,
    FactureLibreCreate,
    PaiementCreate,
    PlanEchelonnementCreate,
    VALIDITE_DEVIS_JOURS,
)
from src.modules.tenants.models import (
    ActeNomenclature,
    ActeRealise,
    Cabinet,
    Consultation,
    Devis,
    DossierMedical,
    Echeance,
    Facture,
    LigneDevis,
    LigneFacture,
    ModePaiementEnum,
    Paiement,
    Patient,
    PlanEchelonnement,
    Praticien,
    StatutConsultationEnum,
    StatutDevisEnum,
    StatutEcheanceEnum,
    StatutFactureEnum,
    Utilisateur,
)

logger = structlog.get_logger(__name__)

_CENT = Decimal("0.01")

# Transitions autorisées du cycle de vie d'un devis (même philosophie que les
# rendez-vous : le cycle est fermé, un devis refusé ne se rouvre pas).
TRANSITIONS_DEVIS = {
    StatutDevisEnum.BROUILLON: {StatutDevisEnum.ENVOYE},
    StatutDevisEnum.ENVOYE: {StatutDevisEnum.ACCEPTE, StatutDevisEnum.REFUSE},
    StatutDevisEnum.ACCEPTE: set(),
    StatutDevisEnum.REFUSE: set(),
    StatutDevisEnum.EXPIRE: set(),
}

# Pas en jours des fréquences courtes. MENSUEL est traité par avancement
# calendaire (le 31 janvier + 1 mois = 28/29 février, pas le 3 mars).
_PAS_FREQUENCE_JOURS = {
    "HEBDO": 7,
    "BIMENSUEL": 14,
}


def _quantize(valeur: Decimal) -> Decimal:
    return Decimal(valeur).quantize(_CENT)


def _statut_lisible(statut) -> str:
    """`ENUM.value` si disponible, sinon la chaîne (le piège SQLAlchemy documenté)."""
    return statut.value if hasattr(statut, "value") else str(statut)


def _fin_de_journee(jour: date) -> datetime:
    """Borne exclusive `< fin_de_journee(j)` attrape tous les paiements du jour `j`."""
    return datetime.combine(jour + timedelta(days=1), time.min, tzinfo=timezone.utc)


def _avancer(jour: date, frequence: str, pas: int) -> date:
    """Ajoute `pas` périodes à `jour` selon la fréquence du plan."""
    if frequence == "MENSUEL":
        mois = jour.month - 1 + pas
        annee = jour.year + mois // 12
        mois = mois % 12 + 1
        dernier_jour = calendar.monthrange(annee, mois)[1]
        return jour.replace(year=annee, month=mois, day=min(jour.day, dernier_jour))
    return jour + timedelta(days=_PAS_FREQUENCE_JOURS[frequence] * pas)


# ==============================================================================
# FACTURES
# ==============================================================================

class FactureService:
    """Émission, consultation et annulation des factures (RG07)."""

    # ------------------------------------------------------------- résolutions
    @staticmethod
    async def _charger(db: AsyncSession, facture_id: uuid.UUID) -> Facture:
        """
        Charge la facture avec ses lignes, paiements et plan d'échelonnement.

        `populate_existing=True` : sans lui, une relation déjà lue (notamment
        `plan_echelonnement`, mis en cache à None au premier `_charger`) ne serait
        pas rafraîchie après une écriture de la même session — le plan qu'on vient
        de créer resterait invisible. Même correction que
        `OdontogrammeService._charger` (voir pièges documentés dans COMMANDS.md).
        """
        stmt = (
            select(Facture)
            .where(Facture.id == facture_id)
            .options(
                selectinload(Facture.lignes),
                selectinload(Facture.paiements).selectinload(Paiement.echeance),
                selectinload(Facture.plan_echelonnement).selectinload(PlanEchelonnement.echeances),
            )
            .execution_options(populate_existing=True)
        )
        facture = (await db.execute(stmt)).scalar_one_or_none()
        if facture is None:
            raise EntityNotFoundException("Facture", facture_id)
        return facture

    @staticmethod
    async def _resoudre_cabinet(db: AsyncSession, cabinet_id: Optional[uuid.UUID]) -> Cabinet:
        """
        Même règle que le module Consultations : un tenant est multi-site, on ne
        devine pas. Un seul cabinet actif = résolution implicite, sinon 422.
        """
        if cabinet_id is not None:
            cabinet = (
                await db.execute(select(Cabinet).where(Cabinet.id == cabinet_id))
            ).scalar_one_or_none()
            if cabinet is None:
                raise EntityNotFoundException("Cabinet", cabinet_id)
            return cabinet

        actifs = (
            await db.execute(select(Cabinet).where(Cabinet.actif.is_(True)).order_by(Cabinet.nom))
        ).scalars().all()
        if len(actifs) == 1:
            return actifs[0]
        if not actifs:
            raise BusinessRuleViolationException(
                "Aucun cabinet actif sur ce dossier : créez d'abord un site.",
                code="CABINET_ABSENT",
            )
        raise BusinessRuleViolationException(
            "Plusieurs cabinets sont actifs : précisez `cabinet_id`.",
            code="CABINET_AMBIGU",
            details={"cabinets": [str(c.id) for c in actifs]},
        )

    @staticmethod
    async def _resoudre_patient(db: AsyncSession, patient_id: uuid.UUID) -> Patient:
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is None:
            raise EntityNotFoundException("Patient", patient_id)
        if patient.archive:
            raise BusinessRuleViolationException(
                f"Le dossier {patient.numero_dossier} est archivé : aucune facturation possible.",
                code="PATIENT_ARCHIVE",
            )
        return patient

    @staticmethod
    def _recalculer_statut(facture: Facture) -> StatutFactureEnum:
        """RG07 : le statut dérive du montant payé, il n'est jamais déclaré par le client."""
        if facture.statut == StatutFactureEnum.ANNULEE:
            return StatutFactureEnum.ANNULEE
        if facture.montant_paye >= facture.montant_total:
            return StatutFactureEnum.PAYEE
        if facture.montant_paye > Decimal("0.00"):
            return StatutFactureEnum.PARTIELLEMENT_PAYEE
        return StatutFactureEnum.EMISE

    @staticmethod
    def _rafraichir_apres_paiement(facture: Facture) -> None:
        """Met à jour `montant_paye` / `montant_restant` / `statut` depuis les paiements."""
        facture.montant_paye = _quantize(
            sum((p.montant for p in facture.paiements), Decimal("0.00"))
        )
        facture.montant_restant = _quantize(facture.montant_total - facture.montant_paye)
        facture.statut = FactureService._recalculer_statut(facture)

    # ------------------------------------------------------------------ émission
    @staticmethod
    async def emettre_depuis_consultation(
        db: AsyncSession,
        consultation_id: uuid.UUID,
        data: FactureConsultationCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Facture:
        """
        Émet la facture d'une consultation TERMINÉE depuis ses actes réalisés.

        Le total est recalculé depuis `actes_realises` (RG07) : jamais reçu du
        client, jamais ressaisi par le secrétariat. Une consultation déjà
        facturée ne l'est pas deux fois : c'est le garde-fou anti-doublon, la
        facture de la consultation est unique tant qu'elle n'est pas annulée.
        """
        consultation = (
            await db.execute(
                select(Consultation)
                .where(Consultation.id == consultation_id)
                .options(selectinload(Consultation.actes_realises))
            )
        ).scalar_one_or_none()
        if consultation is None:
            raise EntityNotFoundException("Consultation", consultation_id)

        if consultation.statut != StatutConsultationEnum.TERMINEE:
            raise BusinessRuleViolationException(
                "Seule une consultation terminée peut être facturée : les actes ne sont pas figés avant la clôture.",
                code="CONSULTATION_NON_TERMINEE",
                details={"statut": _statut_lisible(consultation.statut)},
            )

        deja_facturee = (
            await db.execute(
                select(func.count(Facture.id)).where(
                    Facture.consultation_id == consultation_id,
                    Facture.statut != StatutFactureEnum.ANNULEE,
                )
            )
        ).scalar_one()
        if deja_facturee:
            raise BusinessRuleViolationException(
                "Cette consultation a déjà une facture en cours : annulez-la d'abord pour réémettre.",
                code="CONSULTATION_DEJA_FACTUREE",
            )

        actes: Sequence[ActeRealise] = consultation.actes_realises
        if not actes:
            raise BusinessRuleViolationException(
                "Aucun acte enregistré sur cette consultation : rien à facturer.",
                code="CONSULTATION_SANS_ACTES",
            )

        # Libellés résolus depuis la nomenclature (jamais du client).
        lignes: List[LigneFacture] = []
        total = Decimal("0.00")
        for acte in actes:
            designation = acte.description
            if not designation and acte.acte_id:
                designation = (
                    await db.execute(
                        select(ActeNomenclature.libelle).where(ActeNomenclature.id == acte.acte_id)
                    )
                ).scalar_one_or_none()
            designation = designation or "Acte dentaire"
            montant = _quantize(acte.tarif_applique * acte.quantite)
            total += montant
            lignes.append(
                LigneFacture(
                    acte_realise_id=acte.id,
                    designation=designation,
                    quantite=acte.quantite,
                    prix_unitaire=_quantize(acte.tarif_applique),
                    montant=montant,
                )
            )

        # La consultation porte un `dossier_medical_id`, pas un `patient_id` :
        # le patient est celui du dossier médical d'origine.
        patient_id = (
            await db.execute(
                select(DossierMedical.patient_id).where(
                    DossierMedical.id == consultation.dossier_medical_id
                )
            )
        ).scalar_one()

        facture = Facture(
            numero=await generer_numero_facture(db),
            patient_id=patient_id,
            cabinet_id=consultation.cabinet_id,
            consultation_id=consultation.id,
            praticien_id=consultation.praticien_id,
            montant_total=_quantize(total),
            montant_tva=Decimal("0.00"),
            montant_paye=Decimal("0.00"),
            montant_restant=_quantize(total),
            statut=StatutFactureEnum.EMISE,
            date_emission=date.today(),
            date_echeance=data.date_echeance,
            emis_par_id=auteur.id if auteur else None,
        )
        facture.lignes = lignes
        db.add(facture)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="FACTURE_EMISSION",
            resource_type="Facture",
            resource_id=str(facture.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "numero": facture.numero,
                "montant_total": float(facture.montant_total),
                "consultation_id": str(consultation.id),
                "nb_lignes": len(lignes),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        logger.info(
            "facture_emise",
            numero=facture.numero,
            consultation_id=str(consultation.id),
            montant_total=float(facture.montant_total),
        )
        return facture

    @staticmethod
    async def emettre_libre(
        db: AsyncSession,
        data: FactureLibreCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Facture:
        """Émet une facture hors consultation (produit, forfait). Totaux calculés serveur."""
        patient = await FactureService._resoudre_patient(db, data.patient_id)
        cabinet = await FactureService._resoudre_cabinet(db, data.cabinet_id)
        if data.praticien_id is not None:
            praticien_existe = (
                await db.execute(select(Praticien.id).where(Praticien.id == data.praticien_id))
            ).scalar_one_or_none()
            if praticien_existe is None:
                raise EntityNotFoundException("Praticien", data.praticien_id)

        lignes: List[LigneFacture] = []
        total = Decimal("0.00")
        for entree in data.lignes:
            montant = _quantize(entree.prix_unitaire * entree.quantite)
            total += montant
            lignes.append(
                LigneFacture(
                    designation=entree.designation,
                    quantite=entree.quantite,
                    prix_unitaire=_quantize(entree.prix_unitaire),
                    montant=montant,
                )
            )

        facture = Facture(
            numero=await generer_numero_facture(db),
            patient_id=patient.id,
            cabinet_id=cabinet.id,
            praticien_id=data.praticien_id,
            montant_total=_quantize(total),
            montant_tva=Decimal("0.00"),
            montant_paye=Decimal("0.00"),
            montant_restant=_quantize(total),
            statut=StatutFactureEnum.EMISE,
            date_emission=date.today(),
            date_echeance=data.date_echeance,
            emis_par_id=auteur.id if auteur else None,
        )
        facture.lignes = lignes
        db.add(facture)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="FACTURE_EMISSION",
            resource_type="Facture",
            resource_id=str(facture.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "numero": facture.numero,
                "montant_total": float(facture.montant_total),
                "nb_lignes": len(lignes),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return facture

    # ------------------------------------------------------------------ lecture
    @staticmethod
    async def obtenir(db: AsyncSession, facture_id: uuid.UUID) -> Facture:
        return await FactureService._charger(db, facture_id)

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        patient_id: Optional[uuid.UUID] = None,
        statut: Optional[str] = None,
        q: Optional[str] = None,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Facture], int]:
        conditions = []
        if patient_id is not None:
            conditions.append(Facture.patient_id == patient_id)
        if statut:
            try:
                conditions.append(Facture.statut == StatutFactureEnum(statut.upper()))
            except ValueError:
                raise BusinessRuleViolationException(
                    f"Statut inconnu : {statut}.",
                    code="STATUT_FACTURE_INCONNU",
                    details={"statuts": [s.value for s in StatutFactureEnum]},
                )
        if q:
            conditions.append(Facture.numero.ilike(f"%{q.strip()}%"))
        if date_debut:
            conditions.append(Facture.date_emission >= date_debut)
        if date_fin:
            conditions.append(Facture.date_emission <= date_fin)

        count_stmt = select(func.count(Facture.id))
        data_stmt = (
            select(Facture).options(selectinload(Facture.lignes), selectinload(Facture.paiements))
        )
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            data_stmt = data_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())
        data_stmt = (
            data_stmt.order_by(Facture.date_emission.desc(), Facture.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = await db.execute(data_stmt)
        return list(rows.scalars().unique().all()), total

    # ----------------------------------------------------------------- annulation
    @staticmethod
    async def annuler(
        db: AsyncSession,
        facture_id: uuid.UUID,
        motif: str,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Facture:
        """
        Annule une facture. Interdite dès qu'un paiement existe : la caisse du
        jour doit rester rapprochable — le remboursement est l'autre voie.
        Les échéances non réglées du plan éventuel sont annulées en cascade.
        """
        facture = await FactureService._charger(db, facture_id)
        if facture.statut == StatutFactureEnum.ANNULEE:
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} est déjà annulée.",
                code="FACTURE_DEJA_ANNULEE",
            )
        if facture.paiements:
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} a des encaissements ({facture.montant_paye} FCFA) : "
                "passez par un remboursement avant annulation.",
                code="FACTURE_AVEC_PAIEMENTS",
                details={
                    "montant_paye": float(facture.montant_paye),
                    "nb_paiements": len(facture.paiements),
                },
            )

        facture.statut = StatutFactureEnum.ANNULEE
        facture.montant_restant = Decimal("0.00")
        if facture.plan_echelonnement is not None:
            facture.plan_echelonnement.actif = False
            for echeance in facture.plan_echelonnement.echeances:
                if echeance.statut != StatutEcheanceEnum.PAYEE:
                    echeance.statut = StatutEcheanceEnum.ANNULEE

        await db.flush()
        await AuditService.log_action(
            db=db,
            action="FACTURE_ANNULATION",
            resource_type="Facture",
            resource_id=str(facture.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero": facture.numero, "motif": motif.strip()},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return facture


# ==============================================================================
# PAIEMENTS (caisse)
# ==============================================================================

class PaiementService:
    """Encaissements multi-moyens et journal de caisse."""

    @staticmethod
    async def encaisser(
        db: AsyncSession,
        facture_id: uuid.UUID,
        data: PaiementCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Paiement:
        """
        Encaisse un paiement sur une facture.

        Sans `echeance_id` : paiement libre dans la limite du reste à payer.
        Avec `echeance_id` : le paiement règle EXACTEMENT le reste dû de
        l'échéance — la caisse ne fait pas d'allocation partielle, le reçu et
        l'échéance doivent se correspondre au centime (RG08).
        """
        facture = await FactureService._charger(db, facture_id)

        if facture.statut == StatutFactureEnum.ANNULEE:
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} est annulée : aucun encaissement possible.",
                code="FACTURE_ANNULEE",
            )
        if facture.montant_restant <= Decimal("0.00"):
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} est déjà soldée ({facture.montant_total} FCFA).",
                code="FACTURE_DEJA_PAYEE",
            )
        montant = _quantize(data.montant)
        if montant > facture.montant_restant:
            raise BusinessRuleViolationException(
                f"Encaissement refusé : {montant} FCFA dépasse le reste à payer "
                f"({facture.montant_restant} FCFA). Un trop-perçu relève du remboursement.",
                code="PAIEMENT_TROP_ELEVE",
                details={"montant_restant": float(facture.montant_restant)},
            )

        echeance: Optional[Echeance] = None
        if data.echeance_id is not None:
            echeance = await PaiementService._resoudre_echeance(db, facture, data.echeance_id)
            reste_echeance = _quantize(echeance.montant_prevu - echeance.montant_paye)
            if reste_echeance <= Decimal("0.00"):
                raise BusinessRuleViolationException(
                    f"L'échéance {echeance.numero} est déjà payée.",
                    code="ECHEANCE_DEJA_PAYEE",
                )
            if montant != reste_echeance:
                raise BusinessRuleViolationException(
                    f"L'échéance {echeance.numero} attend exactement {reste_echeance} FCFA "
                    f"(montant fourni : {montant} FCFA).",
                    code="ECHEANCE_MONTANT_INCOHERENT",
                    details={"attendu": float(reste_echeance), "fourni": float(montant)},
                )

        paiement = Paiement(
            facture_id=facture.id,
            patient_id=facture.patient_id,
            montant=montant,
            mode=data.mode,
            reference=(data.reference or "").strip() or None,
            recu_numero=await generer_numero_recu_paiement(db),
            enregistre_par_id=auteur.id if auteur else None,
        )
        db.add(paiement)
        await db.flush()

        if echeance is not None:
            echeance.montant_paye = _quantize(echeance.montant_paye + montant)
            echeance.date_paiement = datetime.now(timezone.utc)
            echeance.paiement_id = paiement.id
            echeance.statut = StatutEcheanceEnum.PAYEE
            # Assignation par la relation : l'objet reste lisible en session
            # (pas de lazy-load en contexte async, cf. pièges documentés).
            paiement.echeance = echeance

        facture.paiements.append(paiement)
        FactureService._rafraichir_apres_paiement(facture)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PAIEMENT_ENCAISSE",
            resource_type="Paiement",
            resource_id=str(paiement.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "recu_numero": paiement.recu_numero,
                "facture_numero": facture.numero,
                "montant": float(paiement.montant),
                "mode": _statut_lisible(paiement.mode),
                "echeance": echeance.numero if echeance else None,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        logger.info(
            "paiement_encaisse",
            recu=paiement.recu_numero,
            facture=facture.numero,
            montant=float(paiement.montant),
        )
        return paiement

    @staticmethod
    async def _resoudre_echeance(
        db: AsyncSession, facture: Facture, echeance_id: uuid.UUID
    ) -> Echeance:
        echeance = (
            await db.execute(select(Echeance).where(Echeance.id == echeance_id))
        ).scalar_one_or_none()
        if echeance is None:
            raise EntityNotFoundException("Echeance", echeance_id)
        plan = (
            await db.execute(
                select(PlanEchelonnement).where(PlanEchelonnement.id == echeance.plan_id)
            )
        ).scalar_one_or_none()
        if plan is None or plan.facture_id != facture.id:
            raise BusinessRuleViolationException(
                "Cette échéance n'appartient pas à la facture indiquée.",
                code="ECHEANCE_FACTURE_INCOHERENTE",
            )
        return echeance

    @staticmethod
    async def journal_caisse(
        db: AsyncSession,
        *,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
        mode: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        Journal de caisse : tous les encaissements, avec la facture et le patient.
        C'est le point d'entrée du « rapport caisse » du comptable (UC6).
        """
        conditions = []
        if date_debut:
            conditions.append(Paiement.date_paiement >= datetime.combine(date_debut, time.min, tzinfo=timezone.utc))
        if date_fin:
            conditions.append(Paiement.date_paiement < _fin_de_journee(date_fin))
        if mode:
            try:
                conditions.append(Paiement.mode == ModePaiementEnum(mode.upper()))
            except ValueError:
                raise BusinessRuleViolationException(
                    f"Mode de paiement inconnu : {mode}.",
                    code="MODE_PAIEMENT_INCONNU",
                    details={"modes": [m.value for m in ModePaiementEnum]},
                )

        base = (
            select(
                Paiement,
                Facture.numero.label("facture_numero"),
                Patient.prenom.label("patient_prenom"),
                Patient.nom.label("patient_nom"),
            )
            .join(Facture, Paiement.facture_id == Facture.id)
            .join(Patient, Paiement.patient_id == Patient.id)
        )
        count_stmt = select(func.count(Paiement.id))
        if conditions:
            base = base.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())
        stmt = base.order_by(Paiement.date_paiement.desc()).offset(offset).limit(limit)
        rows = (await db.execute(stmt)).all()

        items = [
            {
                "id": str(paiement.id),
                "recu_numero": paiement.recu_numero,
                "facture_id": str(paiement.facture_id),
                "facture_numero": facture_numero,
                "patient": f"{patient_prenom} {patient_nom}".strip(),
                "montant": paiement.montant,
                "mode": _statut_lisible(paiement.mode),
                "reference": paiement.reference,
                "date_paiement": paiement.date_paiement,
            }
            for paiement, facture_numero, patient_prenom, patient_nom in rows
        ]
        return items, total


# ==============================================================================
# ÉCHELONNEMENT (RG08)
# ==============================================================================

class EchelonnementService:
    """Plans de paiement et génération des échéances (RG08)."""

    @staticmethod
    async def creer(
        db: AsyncSession,
        facture_id: uuid.UUID,
        data: PlanEchelonnementCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PlanEchelonnement:
        """
        Crée le plan d'échelonnement d'une facture et génère ses échéances.

        Le plan couvre le RESTE À PAYER du jour de sa création : les
        encaissements déjà faits ne sont pas redécoupés. Le reliquat de division
        centime est reporté sur la PREMIÈRE échéance : les suivantes restent
        toutes identiques, ce qui se communique mieux au patient.
        """
        facture = await FactureService._charger(db, facture_id)

        if facture.statut == StatutFactureEnum.ANNULEE:
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} est annulée.",
                code="FACTURE_ANNULEE",
            )
        if facture.plan_echelonnement is not None and facture.plan_echelonnement.actif:
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} a déjà un plan d'échelonnement actif.",
                code="PLAN_DEJA_EXISTANT",
            )
        reste = facture.montant_restant
        if reste <= Decimal("0.00"):
            raise BusinessRuleViolationException(
                f"La facture {facture.numero} est soldée : rien à échelonner.",
                code="FACTURE_DEJA_PAYEE",
            )

        nombre = data.nombre_echeances
        base = (reste / nombre).quantize(_CENT, rounding=ROUND_DOWN)
        reliquat = _quantize(reste - base * nombre)

        echeances: List[Echeance] = []
        jour = data.date_debut
        for numero in range(1, nombre + 1):
            montant_prevu = base + (reliquat if numero == 1 else Decimal("0.00"))
            echeances.append(
                Echeance(
                    numero=numero,
                    montant_prevu=_quantize(montant_prevu),
                    montant_paye=Decimal("0.00"),
                    date_prevue=jour,
                    statut=StatutEcheanceEnum.A_PAYER,
                )
            )
            jour = _avancer(jour, data.frequence.value, 1)

        plan = PlanEchelonnement(
            facture_id=facture.id,
            patient_id=facture.patient_id,
            montant_total=reste,
            nombre_echeances=nombre,
            date_debut=data.date_debut,
            frequence=data.frequence,
            notes=data.notes,
            actif=True,
        )
        plan.echeances = echeances
        db.add(plan)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="PLAN_ECHELONNEMENT_CREATION",
            resource_type="PlanEchelonnement",
            resource_id=str(plan.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "facture_numero": facture.numero,
                "montant_total": float(reste),
                "nombre_echeances": nombre,
                "frequence": data.frequence.value,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return plan

    @staticmethod
    async def obtenir(db: AsyncSession, facture_id: uuid.UUID) -> Optional[PlanEchelonnement]:
        facture = await FactureService._charger(db, facture_id)
        return facture.plan_echelonnement


# ==============================================================================
# DEVIS (RG14)
# ==============================================================================

class DevisService:
    """Devis : cycle de vie fermé et conversion en facture sans ressaisie."""

    @staticmethod
    async def _charger(db: AsyncSession, devis_id: uuid.UUID) -> Devis:
        stmt = select(Devis).where(Devis.id == devis_id).options(selectinload(Devis.lignes))
        devis = (await db.execute(stmt)).scalar_one_or_none()
        if devis is None:
            raise EntityNotFoundException("Devis", devis_id)
        return devis

    @staticmethod
    async def creer(
        db: AsyncSession,
        data: DevisCreate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Devis:
        patient = await FactureService._resoudre_patient(db, data.patient_id)
        cabinet = await FactureService._resoudre_cabinet(db, data.cabinet_id)

        lignes: List[LigneDevis] = []
        total = Decimal("0.00")
        for entree in data.lignes:
            montant = _quantize(entree.prix_unitaire * entree.quantite)
            total += montant
            lignes.append(
                LigneDevis(
                    acte_id=entree.acte_id,
                    designation=entree.designation,
                    dent_numero=entree.dent_numero,
                    quantite=entree.quantite,
                    prix_unitaire=_quantize(entree.prix_unitaire),
                    montant=montant,
                )
            )

        date_validite = data.date_validite or (date.today() + timedelta(days=VALIDITE_DEVIS_JOURS))
        if date_validite < date.today():
            raise BusinessRuleViolationException(
                "La date de validité d'un devis ne peut pas être dans le passé.",
                code="DEVIS_VALIDITE_PASSEE",
            )

        devis = Devis(
            numero=await generer_numero_devis(db),
            patient_id=patient.id,
            cabinet_id=cabinet.id,
            montant_total=_quantize(total),
            statut=StatutDevisEnum.BROUILLON,
            date_validite=date_validite,
            notes=data.notes,
            emis_par_id=auteur.id if auteur else None,
        )
        devis.lignes = lignes
        db.add(devis)
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="DEVIS_EMISSION",
            resource_type="Devis",
            resource_id=str(devis.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero": devis.numero, "montant_total": float(devis.montant_total)},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return devis

    @staticmethod
    async def obtenir(db: AsyncSession, devis_id: uuid.UUID) -> Devis:
        return await DevisService._charger(db, devis_id)

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        patient_id: Optional[uuid.UUID] = None,
        statut: Optional[str] = None,
        q: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Devis], int]:
        conditions = []
        if patient_id is not None:
            conditions.append(Devis.patient_id == patient_id)
        if statut:
            try:
                conditions.append(Devis.statut == StatutDevisEnum(statut.upper()))
            except ValueError:
                raise BusinessRuleViolationException(
                    f"Statut inconnu : {statut}.",
                    code="STATUT_DEVIS_INCONNU",
                    details={"statuts": [s.value for s in StatutDevisEnum]},
                )
        if q:
            conditions.append(Devis.numero.ilike(f"%{q.strip()}%"))

        count_stmt = select(func.count(Devis.id))
        data_stmt = select(Devis).options(selectinload(Devis.lignes))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            data_stmt = data_stmt.where(*conditions)

        total = int((await db.execute(count_stmt)).scalar_one())
        data_stmt = data_stmt.order_by(Devis.created_at.desc()).offset(offset).limit(limit)
        rows = await db.execute(data_stmt)
        return list(rows.scalars().unique().all()), total

    @staticmethod
    async def changer_statut(
        db: AsyncSession,
        devis_id: uuid.UUID,
        data: DevisStatutUpdate,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Devis:
        devis = await DevisService._charger(db, devis_id)
        nouveau = StatutDevisEnum(data.statut)
        actuel = StatutDevisEnum(_statut_lisible(devis.statut))

        if nouveau == actuel:
            return devis
        if nouveau not in TRANSITIONS_DEVIS.get(actuel, set()):
            raise BusinessRuleViolationException(
                f"Transition impossible : un devis {actuel.value} ne peut pas devenir {nouveau.value}.",
                code="DEVIS_TRANSITION_INVALIDE",
                details={
                    "depuis": actuel.value,
                    "vers": [s.value for s in TRANSITIONS_DEVIS.get(actuel, set())],
                },
            )
        if nouveau == StatutDevisEnum.ACCEPTE:
            if not data.signature_patient:
                raise BusinessRuleViolationException(
                    "Un devis n'est accepté qu'avec la signature du patient.",
                    code="SIGNATURE_PATIENT_REQUISE",
                )
            if devis.date_validite is not None and devis.date_validite < date.today():
                raise BusinessRuleViolationException(
                    f"Le devis {devis.numero} a expiré le {devis.date_validite} : émettez un nouveau devis.",
                    code="DEVIS_EXPIRE",
                )
            devis.signature_patient = True
            devis.date_signature = datetime.now(timezone.utc)

        devis.statut = nouveau
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="DEVIS_STATUT",
            resource_type="Devis",
            resource_id=str(devis.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={"numero": devis.numero, "statut": nouveau.value},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return devis

    @staticmethod
    async def convertir_en_facture(
        db: AsyncSession,
        devis_id: uuid.UUID,
        auteur: Optional[Utilisateur] = None,
        *,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Facture:
        """
        RG14 : convertit un devis ACCEPTE en facture, lignes comprises.

        Une seule conversion par devis (`facture_id` UNIQUE) : le même plan de
        traitement ne doit jamais être facturé deux fois.
        """
        devis = await DevisService._charger(db, devis_id)
        actuel = StatutDevisEnum(_statut_lisible(devis.statut))

        if actuel != StatutDevisEnum.ACCEPTE:
            raise BusinessRuleViolationException(
                f"Seul un devis accepté se convertit en facture (statut actuel : {actuel.value}).",
                code="DEVIS_NON_ACCEPTE",
            )
        if devis.facture_id is not None:
            raise BusinessRuleViolationException(
                f"Le devis {devis.numero} a déjà été converti en facture.",
                code="DEVIS_DEJA_CONVERTI",
                details={"facture_id": str(devis.facture_id)},
            )

        patient = await FactureService._resoudre_patient(db, devis.patient_id)

        facture = Facture(
            numero=await generer_numero_facture(db),
            patient_id=patient.id,
            cabinet_id=devis.cabinet_id,
            praticien_id=devis.praticien_id,
            montant_total=devis.montant_total,
            montant_tva=Decimal("0.00"),
            montant_paye=Decimal("0.00"),
            montant_restant=devis.montant_total,
            statut=StatutFactureEnum.EMISE,
            date_emission=date.today(),
            emis_par_id=auteur.id if auteur else None,
        )
        facture.lignes = [
            LigneFacture(
                designation=l.designation,
                quantite=l.quantite,
                prix_unitaire=l.prix_unitaire,
                montant=l.montant,
            )
            for l in devis.lignes
        ]
        db.add(facture)
        await db.flush()

        devis.facture_id = facture.id
        await db.flush()

        await AuditService.log_action(
            db=db,
            action="DEVIS_CONVERSION",
            resource_type="Devis",
            resource_id=str(devis.id),
            user_id=auteur.id if auteur else None,
            user_email=auteur.email if auteur else None,
            changes={
                "numero": devis.numero,
                "facture_numero": facture.numero,
                "montant": float(facture.montant_total),
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        return facture
