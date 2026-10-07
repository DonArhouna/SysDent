"""
Plans, abonnements et facturation de l'éditeur (Phase C).

Trois principes :

1. **Un plan est versionné.** Modifier un plan incrémente sa `version` et archive
   un instantané dans `plan_revisions`. Un abonnement conserve sa copie figée
   (`plan_fige`) : changer un tarif ne réécrit donc jamais rétroactivement un
   contrat en cours. C'est le bug classique de la facturation par abonnement, et
   il est fermé ici par construction.
2. **Un abonnement par cabinet**, garanti par une contrainte d'unicité en base et
   non par une vérification applicative qui se contourne sous concurrence.
3. **Les quotas sont appliqués par un service central** (`QuotaService`), jamais
   par chaque appelant : voir `src/modules/platform/services/quotas.py`.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.platform.models import (
    Abonnement,
    AbonnementHistorique,
    FacturePlateforme,
    PeriodeFacturation,
    Plan,
    PlanRevision,
    StatutAbonnement,
    StatutFacturePlateforme,
)

logger = structlog.get_logger(__name__)

#: Quotas par défaut du plan de repli. Volontairement GENEREUX : le plan par
#: défaut existe pour les tenants déjà en production et ne doit pas couper qui que
#: ce soit la première nuit du déploiement.
QUOTAS_DEFAUT: Dict[str, int] = {
    "utilisateurs": 20,
    "sites": 3,
    "praticiens": 5,
    "stockage_octets": 5 * 1024**3,
    "sms_par_mois": 500,
}

FEATURES_DEFAUT: Dict[str, bool] = {
    "stock": True,
    "sms": True,
    "rapports": True,
    "export_patients": True,
    "api": False,
}


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _instantane(plan: Plan) -> Dict[str, Any]:
    return {
        "code": plan.code,
        "nom": plan.nom,
        "prix": str(plan.prix),
        "periodicite": plan.periodicite.value,
        "devise": plan.devise,
        "quotas": dict(plan.quotas or {}),
        "features": dict(plan.features or {}),
        "jours_essai": plan.jours_essai,
        "version": plan.version,
    }


class PlanService:
    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        code: str,
        nom: str,
        prix: Decimal,
        periodicite: str,
        devise: str = "XOF",
        quotas: Optional[Dict[str, int]] = None,
        features: Optional[Dict[str, bool]] = None,
        description: Optional[str] = None,
        jours_essai: int = 14,
        plan_defaut: bool = False,
        auteur: str = "système",
    ) -> Plan:
        code_normalise = code.strip().upper()
        existant = (
            await db.execute(select(Plan).where(Plan.code == code_normalise))
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                f"Le plan '{code_normalise}' existe déjà.", code="PLAN_DEJA_EXISTANT"
            )

        plan = Plan(
            code=code_normalise,
            nom=nom,
            description=description,
            prix=Decimal(prix),
            # Conversion explicite en enum : `_instantane()` est appelée AVANT
            # le flush, donc la colonne contient encore la chaîne fournie par
            # l'appelant et `.value` lèverait une AttributeError.
            periodicite=PeriodeFacturation(periodicite),
            devise=devise,
            quotas=dict(quotas or QUOTAS_DEFAUT),
            features=dict(features or FEATURES_DEFAUT),
            jours_essai=jours_essai,
            plan_defaut=plan_defaut,
            version=1,
            actif=True,
        )
        db.add(plan)
        await db.flush()
        await PlanService._archiver_revision(db, plan, "création", auteur)
        logger.info("plan_cree", code=plan.code, version=1)
        return plan

    @staticmethod
    async def modifier(
        db: AsyncSession,
        plan_id: uuid.UUID,
        *,
        nom: Optional[str] = None,
        prix: Optional[Decimal] = None,
        periodicite: Optional[str] = None,
        devise: Optional[str] = None,
        quotas: Optional[Dict[str, int]] = None,
        features: Optional[Dict[str, bool]] = None,
        jours_essai: Optional[int] = None,
        actif: Optional[bool] = None,
        motif: Optional[str] = None,
        auteur: str = "système",
    ) -> Plan:
        """
        Modifie un plan en incrémentant sa version et en archivant l'instantané
        précédent.

        Les abonnements existants ne sont PAS modifiés : chacun conserve son
        `plan_fige`. C'est le seul moyen qu'une hausse de tarif n'application
        rétroactivement aux contrats signés.
        """
        plan = await PlanService._charger(db, plan_id)
        avant = _instantane(plan)

        if nom is not None:
            plan.nom = nom
        if prix is not None:
            plan.prix = Decimal(prix)
        if periodicite is not None:
            plan.periodicite = PeriodeFacturation(periodicite)
        if devise is not None:
            plan.devise = devise
        if quotas is not None:
            plan.quotas = dict(quotas)
        if features is not None:
            plan.features = dict(features)
        if jours_essai is not None:
            plan.jours_essai = jours_essai
        if actif is not None:
            plan.actif = actif

        plan.version += 1
        await db.flush()
        await PlanService._archiver_revision(db, plan, motif or "modification", auteur, avant=avant)
        logger.info("plan_modifie", code=plan.code, version=plan.version)
        return plan

    @staticmethod
    async def _archiver_revision(
        db: AsyncSession,
        plan: Plan,
        motif: Optional[str],
        auteur: str,
        avant: Optional[Dict[str, Any]] = None,
    ) -> None:
        db.add(
            PlanRevision(
                plan_id=plan.id,
                version=plan.version,
                instantane=avant or _instantane(plan),
                motif=motif,
                auteur=auteur,
            )
        )
        await db.flush()

    @staticmethod
    async def _charger(db: AsyncSession, plan_id: uuid.UUID) -> Plan:
        plan = (await db.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
        if plan is None:
            raise EntityNotFoundException("Plan", plan_id)
        return plan

    @staticmethod
    async def par_code(db: AsyncSession, code: str) -> Optional[Plan]:
        return (
            await db.execute(select(Plan).where(Plan.code == code.strip().upper()))
        ).scalar_one_or_none()

    @staticmethod
    async def plan_defaut(db: AsyncSession) -> Plan:
        """
        Plan appliqué aux cabinets existants par le script de rattrapage.

        À défaut, on utilise un plan « ESSENTIEL » créé à la volée : mieux vaut
        un plan par défaut explicite qu'un cabinet sans abonnement, donc sans
        quota et sans feature flag.
        """
        plan = (
            await db.execute(select(Plan).where(Plan.plan_defaut.is_(True), Plan.actif.is_(True)))
        ).scalars().first()
        if plan is not None:
            return plan

        plan = Plan(
            code="ESSENTIEL",
            nom="Essentiel",
            description="Plan par défaut — quotas généreux, aucune limite contractuelle",
            prix=Decimal("0"),
            periodicite="MENSUEL",
            devise="XOF",
            quotas=dict(QUOTAS_DEFAUT),
            features=dict(FEATURES_DEFAUT),
            jours_essai=14,
            plan_defaut=True,
            version=1,
            actif=True,
        )
        db.add(plan)
        await db.flush()
        logger.info("plan_defaut_cree", code=plan.code)
        return plan

    @staticmethod
    async def lister(db: AsyncSession, actif_seulement: bool = False) -> List[Plan]:
        stmt = select(Plan).order_by(Plan.code)
        if actif_seulement:
            stmt = stmt.where(Plan.actif.is_(True))
        return list((await db.execute(stmt)).scalars().all())


class AbonnementService:
    @staticmethod
    async def souscrire(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        plan_code: Optional[str],
        statut: str = "ACTIF",
        auteur: str = "système",
        motif: Optional[str] = None,
        jours_essai: Optional[int] = None,
    ) -> Abonnement:
        """
        Crée l'abonnement d'un cabinet (un seul par cabinet).

        Le contrat est FIGÉ dans `plan_fige` : quotas, prix, fonctionnalités et
        durée d'essai au moment de la souscription.
        """
        existant = (
            await db.execute(select(Abonnement).where(Abonnement.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                "Ce cabinet possède déjà un abonnement.", code="ABONNEMENT_EXISTANT"
            )

        if plan_code:
            plan = await PlanService.par_code(db, plan_code)
            if plan is None:
                raise BusinessRuleViolationException(
                    f"Plan inconnu : '{plan_code}'.", code="PLAN_INCONNU"
                )
        else:
            plan = await PlanService.plan_defaut(db)

        essai_jours = jours_essai if jours_essai is not None else plan.jours_essai
        maintenant = _maintenant()
        abonnement = Abonnement(
            tenant_id=tenant_id,
            plan_id=plan.id,
            statut=StatutAbonnement(statut),
            plan_fige=_instantane(plan),
            date_debut=maintenant,
            numero_abonnement=f"ABO-{tenant_id.hex[:10].upper()}",
        )
        if statut == "ESSAI":
            abonnement.date_debut_essai = maintenant
            abonnement.date_fin_essai = maintenant + timedelta(days=essai_jours)
        elif plan.periodicite.value == "ANNUEL" and not plan.prix == 0:
            abonnement.date_fin = maintenant + timedelta(days=365)

        db.add(abonnement)
        await db.flush()

        db.add(
            AbonnementHistorique(
                abonnement_id=abonnement.id,
                tenant_id=tenant_id,
                action="SOUSCRIPTION",
                avant=None,
                apres=_instantane(plan),
                motif=motif,
                auteur=auteur,
            )
        )
        await db.flush()
        logger.info(
            "abonnement_souscrit", tenant_id=str(tenant_id), plan=plan.code, statut=statut
        )
        return abonnement

    @staticmethod
    async def changer_plan(
        db: AsyncSession,
        abonnement_id: uuid.UUID,
        nouveau_plan_code: str,
        motif: Optional[str],
        auteur: str,
        recalculer_quotas: bool = True,
    ) -> Abonnement:
        """
        Change le plan d'un abonnement, avec application immédiate des nouveaux
        quotas si `recalculer_quotas`.

        Le changement est journalisé dans `abonnement_historique` avec l'avant et
        l'après : « il avait 5 utilisateurs, il en a 20 » est une question à
        laquelle la base doit pouvoir répondre six mois plus tard.
        """
        abonnement = (
            await db.execute(select(Abonnement).where(Abonnement.id == abonnement_id))
        ).scalar_one_or_none()
        if abonnement is None:
            raise EntityNotFoundException("Abonnement", abonnement_id)

        plan = await PlanService.par_code(db, nouveau_plan_code)
        if plan is None:
            raise BusinessRuleViolationException(
                f"Plan inconnu : '{nouveau_plan_code}'.", code="PLAN_INCONNU"
            )

        avant = dict(abonnement.plan_fige or {})
        abonnement.plan_id = plan.id
        abonnement.plan_fige = _instantane(plan)
        await db.flush()

        db.add(
            AbonnementHistorique(
                abonnement_id=abonnement.id,
                tenant_id=abonnement.tenant_id,
                action="CHANGEMENT_PLAN",
                avant=avant,
                apres=_instantane(plan),
                motif=motif,
                auteur=auteur,
            )
        )
        await db.flush()
        logger.info(
            "abonnement_plan_change",
            tenant_id=str(abonnement.tenant_id),
            ancien=avant.get("code"),
            nouveau=plan.code,
        )
        return abonnement

    @staticmethod
    async def changer_statut(
        db: AsyncSession, abonnement_id: uuid.UUID, statut: str, motif: Optional[str], auteur: str
    ) -> Abonnement:
        abonnement = (
            await db.execute(select(Abonnement).where(Abonnement.id == abonnement_id))
        ).scalar_one_or_none()
        if abonnement is None:
            raise EntityNotFoundException("Abonnement", abonnement_id)
        avant = abonnement.statut.value
        abonnement.statut = StatutAbonnement(statut)
        await db.flush()
        db.add(
            AbonnementHistorique(
                abonnement_id=abonnement.id,
                tenant_id=abonnement.tenant_id,
                action="CHANGEMENT_STATUT",
                avant={"statut": avant},
                apres={"statut": statut},
                motif=motif,
                auteur=auteur,
            )
        )
        await db.flush()
        return abonnement

    @staticmethod
    async def pour_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Optional[Abonnement]:
        return (
            await db.execute(select(Abonnement).where(Abonnement.tenant_id == tenant_id))
        ).scalar_one_or_none()

    @staticmethod
    async def lister(db: AsyncSession, statut: Optional[str] = None) -> List[Abonnement]:
        stmt = select(Abonnement).order_by(Abonnement.created_at.desc())
        if statut:
            stmt = stmt.where(Abonnement.statut == statut)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def historique(db: AsyncSession, tenant_id: uuid.UUID) -> List[AbonnementHistorique]:
        stmt = (
            select(AbonnementHistorique)
            .where(AbonnementHistorique.tenant_id == tenant_id)
            .order_by(AbonnementHistorique.created_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())


class FacturePlateformeService:
    """
    Factures de l'éditeur — base minimale (Phase C.5).

    AUCUNE intégration de paiement automatique n'est livrée dans cette mission.
    `reference_externe` est le point d'accroche prévu pour brancher un
    prestataire plus tard : le statut sera alors réconcilié depuis une
    notification SIGNÉE du prestataire, jamais déduit d'un retour de navigateur
    (un retour navigateur, c'est le client qui décide s'il a payé).
    """

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        lignes: List[Dict[str, Any]],
        periode_debut: Optional[date] = None,
        periode_fin: Optional[date] = None,
        date_echeance: Optional[date] = None,
        statut: str = "BROUILLON",
        notes: Optional[str] = None,
        auteur: str = "système",
    ) -> FacturePlateforme:
        if not lignes:
            raise BusinessRuleViolationException(
                "Une facture doit comporter au moins une ligne.", code="FACTURE_SANS_LIGNE"
            )

        abonnement = await AbonnementService.pour_tenant(db, tenant_id)
        devise = (abonnement.plan_fige or {}).get("devise", "XOF") if abonnement else "XOF"

        total = sum(Decimal(str(ligne.get("montant", 0))) for ligne in lignes)
        numero = await FacturePlateformeService._prochain_numero(db)

        facture = FacturePlateforme(
            numero=numero,
            tenant_id=tenant_id,
            abonnement_id=abonnement.id if abonnement else None,
            lignes=lignes,
            montant=total,
            devise=devise,
            statut=StatutFacturePlateforme(statut),
            periode_debut=periode_debut,
            periode_fin=periode_fin,
            date_emission=date.today() if statut != "BROUILLON" else None,
            date_echeance=date_echeance or (date.today() + timedelta(days=30)),
            notes=notes,
        )
        db.add(facture)
        await db.flush()
        logger.info("facture_plateforme_creee", numero=numero, montant=str(total), statut=statut)
        return facture

    @staticmethod
    async def _prochain_numero(db: AsyncSession) -> str:
        annee = date.today().year
        prefixe = f"FAC-{annee}-"
        dernier = (
            await db.execute(
                select(FacturePlateforme.numero)
                .where(FacturePlateforme.numero.like(f"{prefixe}%"))
                .order_by(FacturePlateforme.numero.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        numero_suivant = int(dernier.rsplit("-", 1)[1]) + 1 if dernier else 1
        return f"{prefixe}{numero_suivant:05d}"

    @staticmethod
    async def changer_statut(
        db: AsyncSession, facture_id: uuid.UUID, statut: str, auteur: str, motif: Optional[str] = None
    ) -> FacturePlateforme:
        facture = (
            await db.execute(select(FacturePlateforme).where(FacturePlateforme.id == facture_id))
        ).scalar_one_or_none()
        if facture is None:
            raise EntityNotFoundException("Facture plateforme", facture_id)

        avant = facture.statut.value
        facture.statut = StatutFacturePlateforme(statut)
        if statut == "PAYEE":
            facture.date_paiement = date.today()
        await db.flush()
        logger.info(
            "facture_plateforme_statut",
            numero=facture.numero,
            avant=avant,
            apres=statut,
            auteur=auteur,
            motif=motif,
        )
        return facture

    @staticmethod
    async def lister(
        db: AsyncSession,
        tenant_id: Optional[uuid.UUID] = None,
        statut: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[FacturePlateforme]:
        stmt = select(FacturePlateforme).order_by(FacturePlateforme.created_at.desc())
        if tenant_id:
            stmt = stmt.where(FacturePlateforme.tenant_id == tenant_id)
        if statut:
            stmt = stmt.where(FacturePlateforme.statut == statut)
        return list((await db.execute(stmt.limit(limit).offset(offset))).scalars().all())

    @staticmethod
    async def compter(
        db: AsyncSession, tenant_id: Optional[uuid.UUID] = None, statut: Optional[str] = None
    ) -> int:
        stmt = select(func.count(FacturePlateforme.id))
        if tenant_id:
            stmt = stmt.where(FacturePlateforme.tenant_id == tenant_id)
        if statut:
            stmt = stmt.where(FacturePlateforme.statut == statut)
        return int((await db.execute(stmt)).scalar_one())

    @staticmethod
    async def marquer_en_retard(db: AsyncSession) -> int:
        """
        Bascule les factures échues non payées en `EN_RETARD`.

        Appelé par le job planifié. L'opération estENSORISÉE par le filtre SQL
        lui-même : relancer le job dix fois ne fait rien de plus.
        """
        stmt = (
            select(FacturePlateforme)
            .where(
                FacturePlateforme.statut == StatutFacturePlateforme.EMISE,
                FacturePlateforme.date_echeance < date.today(),
            )
        )
        factures = (await db.execute(stmt)).scalars().all()
        for facture in factures:
            facture.statut = StatutFacturePlateforme.EN_RETARD
        await db.flush()
        if factures:
            logger.info("factures_en_retard", nombre=len(factures))
        return len(factures)

# ==============================================================================
# CATALOGUE DE DÉPART
# ==============================================================================

#: Catalogue commercial initial, en dur ICI et nulle part ailleurs.
#:
#: Pourquoi un littéral Python alors que la Phase B.6 a mis les gabarits de semis
#: en base ? Parce que le catalogue doit exister AVANT la console : le tout premier
#: amorçage n'a pas encore de base à lire. Ensuite, l'équipe édite les plans
#: depuis la console — et le fichier n'est plus qu'un point de départ, jamais une
#: source de vérité au quotidien.
#:
#: Les quotas sont volontairement généreux : resserrer un quota actif d'un client
#: en production est une décision commerciale, pas un effet de bord technique.
CATALOGUE_DEPART: List[Dict[str, Any]] = [
    {
        "code": "ESSENTIEL",
        "nom": "Essentiel",
        "description": "Formule de démarrage — pour un cabinet naissant",
        "prix": Decimal("0"),
        "periodicite": "MENSUEL",
        "quotas": {
            "utilisateurs": 20,
            "sites": 3,
            "praticiens": 5,
            "stockage_octets": 5 * 1024**3,
            "sms_par_mois": 500,
        },
        "features": {
            "stock": True,
            "sms": True,
            "rapports": True,
            "export_patients": True,
            "api": False,
        },
        "jours_essai": 14,
        "plan_defaut": True,
    },
    {
        "code": "PRO",
        "nom": "Pro",
        "description": "Cabinet multi-praticiens avec site secondaire",
        "prix": Decimal("45000"),
        "periodicite": "MENSUEL",
        "quotas": {
            "utilisateurs": 50,
            "sites": 10,
            "praticiens": 15,
            "stockage_octets": 50 * 1024**3,
            "sms_par_mois": 5000,
        },
        "features": {
            "stock": True,
            "sms": True,
            "rapports": True,
            "export_patients": True,
            "api": True,
        },
        "jours_essai": 14,
        "plan_defaut": False,
    },
    {
        "code": "PREMIUM",
        "nom": "Premium",
        "description": "Groupe de cabinets, multi-sites, API et support prioritaire",
        "prix": Decimal("120000"),
        "periodicite": "MENSUEL",
        "quotas": {
            "utilisateurs": 200,
            "sites": 50,
            "praticiens": 60,
            "stockage_octets": 500 * 1024**3,
            "sms_par_mois": 25000,
        },
        "features": {
            "stock": True,
            "sms": True,
            "rapports": True,
            "export_patients": True,
            "api": True,
            "support_prioritaire": True,
        },
        "jours_essai": 14,
        "plan_defaut": False,
    },
]


async def bootstrap_catalogue(db: AsyncSession, auteur: str = "bootstrap") -> List[str]:
    """
    Crée les plans du catalogue de départ absents. Idempotent.

    Un plan déjà présent n'est JAMAIS écrasé : réexécuter l'amorçage après avoir
    ajusté un tarif en console ne doit pas annuler la décision commerciale.
    """
    crees: List[str] = []
    for definition in CATALOGUE_DEPART:
        code = str(definition["code"])
        if await PlanService.par_code(db, code) is not None:
            continue
        # `code` est déjà dans la definition : on ne le passe pas deux fois.
        await PlanService.creer(db, auteur=auteur, **definition)
        crees.append(code)
    if crees:
        logger.info("catalogue_plans_cree", plans=crees)
    return crees
