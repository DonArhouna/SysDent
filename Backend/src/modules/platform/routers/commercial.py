"""
Plans, abonnements, quotas et facturation — console PLATEFORME (Phase C).

Préfixe `/platform`, groupe OpenAPI « Platform · Plans & Facturation ».
"""

from decimal import Decimal
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.core.exceptions import AppException
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import require_platform_permissions
from src.modules.platform.models import PlanRevision, UtilisateurPlateforme
from src.modules.platform.schemas import (
    AbonnementResponse,
    ChangementPlan,
    FacturePlateformeCreate,
    FacturePlateformeResponse,
    PlanCreate,
    PlanResponse,
    PlanRevisionResponse,
    PlanUpdate,
    QuotaResumeResponse,
)
from src.modules.platform.services.journal import JournalService
from src.modules.platform.services.plans import (
    AbonnementService,
    FacturePlateformeService,
    PlanService,
)
from src.modules.platform.services.quotas import QuotaService

platform_commercial_router = APIRouter(
    prefix="/platform", tags=["Platform · Plans, abonnements & facturation"]
)


def _vers_plan(plan) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        code=plan.code,
        nom=plan.nom,
        description=plan.description,
        prix=str(plan.prix),
        periodicite=plan.periodicite.value,
        devise=plan.devise,
        quotas=dict(plan.quotas or {}),
        features=dict(plan.features or {}),
        version=plan.version,
        actif=plan.actif,
        plan_defaut=plan.plan_defaut,
        jours_essai=plan.jours_essai,
    )


def _vers_abonnement(abonnement) -> AbonnementResponse:
    fige = abonnement.plan_fige or {}
    return AbonnementResponse(
        id=abonnement.id,
        tenant_id=abonnement.tenant_id,
        numero=abonnement.numero_abonnement,
        plan_id=abonnement.plan_id,
        plan=fige.get("code"),
        plan_nom=fige.get("nom"),
        statut=abonnement.statut.value,
        plan_fige=fige,
        date_debut=abonnement.date_debut,
        date_fin=abonnement.date_fin,
        date_debut_essai=abonnement.date_debut_essai,
        date_fin_essai=abonnement.date_fin_essai,
        renouvellement_auto=abonnement.renouvellement_auto,
    )


def _vers_facture(facture) -> FacturePlateformeResponse:
    return FacturePlateformeResponse(
        id=facture.id,
        numero=facture.numero,
        tenant_id=facture.tenant_id,
        lignes=facture.lignes,
        montant=str(facture.montant),
        devise=facture.devise,
        statut=facture.statut.value,
        periode_debut=facture.periode_debut,
        periode_fin=facture.periode_fin,
        date_emission=facture.date_emission,
        date_echeance=facture.date_echeance,
        date_paiement=facture.date_paiement,
        reference_externe=facture.reference_externe,
        notes=facture.notes,
    )


# ==============================================================================
# PLANS
# ==============================================================================


@platform_commercial_router.get(
    "/plans",
    response_model=APIResponse[List[PlanResponse]],
    summary="Lister les plans",
)
async def lister_plans(
    actif_seulement: bool = Query(False),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.plans.read")),
):
    """Catalogue des formules : prix, périodicité, quotas et fonctionnalités."""
    plans = await PlanService.lister(db, actif_seulement=actif_seulement)
    return APIResponse(data=[_vers_plan(p) for p in plans])


@platform_commercial_router.post(
    "/plans",
    response_model=APIResponse[PlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un plan",
    responses={409: {"description": "Code de plan déjà utilisé"}},
)
async def creer_plan(
    data: PlanCreate,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.plans.write")),
):
    """
    Crée une formule commerciale.

    Les quotas sont stockés en JSONB : ce sont des données de configuration dont
    la forme évolue avec le produit, pas une structure figée. Le service
    d'application des quotas reste, lui, strictement typé.
    """
    plan = await PlanService.creer(
        db,
        code=data.code,
        nom=data.nom,
        prix=Decimal(str(data.prix)),
        periodicite=data.periodicite,
        devise=data.devise,
        quotas=data.quotas,
        features=data.features,
        description=data.description,
        jours_essai=data.jours_essai,
        plan_defaut=data.plan_defaut,
        auteur=auteur.email,
    )
    await JournalService.journaliser(
        db,
        action="PLATFORM_PLAN_CREE",
        type_cible="PLAN",
        cible_id=str(plan.id),
        acteur_email=auteur.email,
        apres={"code_plan": plan.code, "version": plan.version},
    )
    return APIResponse(message=f"Plan '{plan.code}' créé.", data=_vers_plan(plan))


@platform_commercial_router.patch(
    "/plans/{plan_id}",
    response_model=APIResponse[PlanResponse],
    summary="Modifier un plan (crée une nouvelle version)",
    responses={404: {"description": "Plan introuvable"}},
)
async def modifier_plan(
    plan_id: uuid.UUID,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.plans.write")),
):
    """
    Modifie un plan : sa `version` est incrémentée et l'instantané précédent est
    archivé.

    **Les abonnements existants ne sont PAS modifiés.** Chacun conserve la copie
    figée de son contrat (`plan_fige`) : augmenter un tarif ne réécrit jamais un
    contrat en cours.
    """
    plan = await PlanService.modifier(
        db,
        plan_id,
        nom=data.nom,
        prix=Decimal(str(data.prix)) if data.prix is not None else None,
        periodicite=data.periodicite,
        devise=data.devise,
        quotas=data.quotas,
        features=data.features,
        jours_essai=data.jours_essai,
        actif=data.actif,
        motif=data.motif,
        auteur=auteur.email,
    )
    await JournalService.journaliser(
        db,
        action="PLATFORM_PLAN_MODIFIE",
        type_cible="PLAN",
        cible_id=str(plan.id),
        acteur_email=auteur.email,
        apres={"code_plan": plan.code, "version": plan.version},
        motif=data.motif,
    )
    return APIResponse(
        message=f"Plan '{plan.code}' mis à jour (version {plan.version}).",
        data=_vers_plan(plan),
    )


@platform_commercial_router.get(
    "/plans/{plan_id}/revisions",
    response_model=APIResponse[List[PlanRevisionResponse]],
    summary="Historique des versions d'un plan",
)
async def historique_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.plans.read")),
):
    """Toutes les versions archivées du plan : ce que chaque contrat a réellement signé."""
    from sqlalchemy import select

    revisions = (
        await db.execute(
            select(PlanRevision)
            .where(PlanRevision.plan_id == plan_id)
            .order_by(PlanRevision.version.desc())
        )
    ).scalars().all()
    return APIResponse(
        data=[
            PlanRevisionResponse(
                version=r.version,
                instantane=r.instantane,
                motif=r.motif,
                auteur=r.auteur,
                created_at=r.created_at,
            )
            for r in revisions
        ]
    )


# ==============================================================================
# ABONNEMENTS
# ==============================================================================


@platform_commercial_router.get(
    "/subscriptions",
    response_model=APIResponse[List[AbonnementResponse]],
    summary="Lister les abonnements",
)
async def lister_abonnements(
    statut: Optional[str] = Query(None, description="ESSAI | ACTIF | SUSPENDU | EXPIRE | RESILIE"),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.subscriptions.read")),
):
    """Tous les abonnements, avec le plan FIGÉ au moment de la souscription."""
    abonnements = await AbonnementService.lister(db, statut=statut)
    return APIResponse(data=[_vers_abonnement(a) for a in abonnements])


@platform_commercial_router.get(
    "/subscriptions/{abonnement_id}",
    response_model=APIResponse[AbonnementResponse],
    summary="Détail d'un abonnement",
)
async def detail_abonnement(
    abonnement_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.subscriptions.read")),
):
    from sqlalchemy import select

    from src.modules.platform.models import Abonnement

    abonnement = (
        await db.execute(select(Abonnement).where(Abonnement.id == abonnement_id))
    ).scalar_one_or_none()
    if abonnement is None:
        from src.core.exceptions import EntityNotFoundException

        raise EntityNotFoundException("Abonnement", abonnement_id)
    return APIResponse(data=_vers_abonnement(abonnement))


@platform_commercial_router.post(
    "/subscriptions/{abonnement_id}/plan",
    response_model=APIResponse[AbonnementResponse],
    summary="Changer le plan d'un abonnement",
    responses={404: {"description": "Abonnement ou plan introuvable"}},
)
async def changer_plan(
    abonnement_id: uuid.UUID,
    data: ChangementPlan,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.subscriptions.write")
    ),
):
    """
    Change la formule d'un cabinet. Les nouveaux quotas s'appliquent
    immédiatement, et le passage est journalisé avec l'avant et l'après.
    """
    abonnement = await AbonnementService.changer_plan(
        db, abonnement_id, data.plan_code, data.motif, auteur.email
    )
    return APIResponse(
        message=f"Plan de l'abonnement remplacé par '{data.plan_code}'.",
        data=_vers_abonnement(abonnement),
    )


@platform_commercial_router.get(
    "/subscriptions/tenant/{tenant_id}/historique",
    response_model=APIResponse[List[dict]],
    summary="Historique des changements d'un abonnement",
)
async def historique_abonnement(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.subscriptions.read")),
):
    """Chronologie des souscriptions et changements de plan, avec le motif de chacun."""
    entrees = await AbonnementService.historique(db, tenant_id)
    return APIResponse(
        data=[
            {
                "horodatage": e.created_at.isoformat(),
                "action": e.action,
                "avant": e.avant,
                "apres": e.apres,
                "motif": e.motif,
                "auteur": e.auteur,
            }
            for e in entrees
        ]
    )


# ==============================================================================
# QUOTAS
# ==============================================================================


@platform_commercial_router.get(
    "/tenants/{tenant_id}/quotas",
    response_model=APIResponse[QuotaResumeResponse],
    summary="Consommation et limites d'un cabinet",
    responses={404: {"description": "Cabinet sans dossier plateforme"}},
)
async def quotas_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.plans.read")),
):
    """
    Quota par quota : consommation, limite et taux d'usage.

    La consommation vient du dernier relevé d'agrégats journalier, pas d'une
    requête dans la base du cabinet : cet écran reste donc instantané même avec
    plusieurs centaines de clients.
    """
    resume = await QuotaService.resume_quotas(db, tenant_id)
    return APIResponse(data=QuotaResumeResponse(**resume))


@platform_commercial_router.get(
    "/tenants/{tenant_id}/quotas/simulation",
    response_model=APIResponse[dict],
    summary="Simuler l'effet d'un quota",
)
async def simuler_quota(
    tenant_id: uuid.UUID,
    ressource: str = Query(..., description="utilisateurs | sites | praticiens | …"),
    consommation: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.plans.read")),
):
    """
    « Avec 6 utilisateurs, le plan ESSENTIEL autorise-t-il encore ? »

    Utile avant une intervention : l'opérateur voit le refus avant de le
    provoquer chez le client. Ne lève jamais — une simulation qui échoue
    n'apprend rien.
    """
    return APIResponse(data=await QuotaService.simuler(db, tenant_id, ressource, consommation))


# ==============================================================================
# FACTURES
# ==============================================================================


@platform_commercial_router.get(
    "/invoices",
    response_model=PaginatedResponse[FacturePlateformeResponse],
    summary="Lister les factures de l'éditeur",
)
async def lister_factures(
    tenant_id: Optional[uuid.UUID] = Query(None),
    statut: Optional[str] = Query(None, description="BROUILLON | EMISE | PAYEE | EN_RETARD | ANNULEE"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.billing.read")),
):
    """Factures paginées, filtrables par cabinet et par statut."""
    params = PaginationParams(page=page, limit=limit)
    items = await FacturePlateformeService.lister(
        db, tenant_id=tenant_id, statut=statut, limit=params.limit, offset=params.offset
    )
    total = await FacturePlateformeService.compter(db, tenant_id=tenant_id, statut=statut)
    return paginate(
        items=[_vers_facture(f) for f in items], total_records=total, params=params
    )


@platform_commercial_router.post(
    "/invoices",
    response_model=APIResponse[FacturePlateformeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer une facture manuellement",
    responses={422: {"description": "Aucune ligne fournie"}},
)
async def creer_facture(
    data: FacturePlateformeCreate,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.billing.write")),
):
    """
    Émet une facture pour un cabinet.

    **Aucun paiement automatique n'est branché** : le champ `reference_externe`
    est le point d'accroche prévu pour un prestataire, qui réconciliera le statut
    depuis une notification signée. Le statut ne doit JAMAIS être déduit d'un
    retour de navigateur — c'est le client qui déciderait s'il a payé.
    """
    facture = await FacturePlateformeService.creer(
        db,
        tenant_id=_tenant_id_de_facture(data, request),
        lignes=data.lignes,
        periode_debut=data.periode_debut,
        periode_fin=data.periode_fin,
        date_echeance=data.date_echeance,
        statut=data.statut,
        notes=data.notes,
        auteur=auteur.email,
    )
    await JournalService.journaliser(
        db,
        action="PLATFORM_FACTURE_CREEE",
        type_cible="FACTURE",
        cible_id=str(facture.id),
        tenant_id=facture.tenant_id,
        acteur_email=auteur.email,
        apres={"numero": facture.numero, "montant": str(facture.montant)},
    )
    return APIResponse(message=f"Facture {facture.numero} créée.", data=_vers_facture(facture))


def _tenant_id_de_facture(data: FacturePlateformeCreate, request: Request) -> uuid.UUID:
    """
    Lit `tenant_id` : corps JSON d'abord, query string en repli.

    Le corps reste la source principale (l'interface travaille en POST + JSON) ;
    la query string permet au support d'émettre une facture depuis un simple
    lien d'exploitation, sans écrire de JSON.
    """
    brut = data.model_extra.get("tenant_id") if data.model_extra else None
    brut = brut or request.query_params.get("tenant_id")
    if not brut:
        raise AppException(
            "Le champ 'tenant_id' est obligatoire.", code="VALIDATION_ERROR", status_code=422
        )
    return uuid.UUID(str(brut))


@platform_commercial_router.post(
    "/invoices/{facture_id}/statut",
    response_model=APIResponse[FacturePlateformeResponse],
    summary="Changer le statut d'une facture",
)
async def changer_statut_facture(
    facture_id: uuid.UUID,
    statut: str = Query(..., description="BROUILLON | EMISE | PAYEE | EN_RETARD | ANNULEE"),
    motif: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(require_platform_permissions("platform.billing.write")),
):
    """Fait évoluer le statut d'une facture (marquage manuel du paiement en attendant le prestataire)."""
    facture = await FacturePlateformeService.changer_statut(db, facture_id, statut, auteur.email, motif)
    return APIResponse(message=f"Facture {facture.numero} : {statut}.", data=_vers_facture(facture))