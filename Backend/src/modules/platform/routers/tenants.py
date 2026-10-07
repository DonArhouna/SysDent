"""
Cycle de vie des cabinets — console PLATEFORME (Phase B).

Préfixe `/platform/tenants`, groupe OpenAPI « Platform · Tenants ».

Toutes les routes d'écriture exigent un motif : une action sur un contrat
client sans raison écrite est indéfendable six mois plus tard, devant le client
comme devant un contrôleur.
"""

from datetime import date
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.core.database import get_master_db
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import (
    client_ip,
    get_current_platform_user,
    require_platform_permissions,
)
from src.modules.platform.models import StatutTenant, UtilisateurPlateforme
from src.modules.platform.schemas import (
    Archivage,
    HistoriqueStatutEntry,
    TenantCreate,
    TenantCreationResponse,
    TenantDetailResponse,
    TenantResponse,
    TenantUpdate,
    TransitionStatut,
)
from src.modules.platform.services.provisioning import ProvisioningService
from src.modules.platform.services.tenants import TenantService, transitions_possibles

platform_tenants_router = APIRouter(
    prefix="/platform/tenants", tags=["Platform · Tenants (cycle de vie)"]
)


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


@platform_tenants_router.get(
    "",
    response_model=PaginatedResponse[TenantResponse],
    summary="Registre paginé des cabinets",
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Permission insuffisante"},
    },
)
async def lister_tenants(
    q: Optional[str] = Query(None, description="Recherche sur nom, ville, téléphone, e-mail"),
    statut: Optional[str] = Query(
        None, description="ESSAI | ACTIF | SUSPENDU | RESILIE"
    ),
    plan: Optional[str] = Query(None, description="Filtrer par code de plan"),
    pays: Optional[str] = Query(None),
    archive: Optional[bool] = Query(None, description="true = archivés uniquement"),
    created_from: Optional[date] = Query(None, description="Date de création minimale"),
    created_to: Optional[date] = Query(None, description="Date de création maximale"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.read")),
):
    """
    Registre des cabinets : recherche, filtres statut/plan/pays/période, pagination.

    Le filtre `plan` parcourt les abonnements du tenant : le plan vit dans la
    base plateforme, pas dans `societes`, où il n'a pas sa place.
    """
    params = PaginationParams(page=page, limit=limit)
    items = await TenantService.lister(
        platform_db,
        master_db,
        recherche=q,
        statut=statut,
        plan_code=plan,
        pays=pays,
        archive=archive,
        created_from=created_from,
        created_to=created_to,
        limit=params.limit,
        offset=params.offset,
    )
    total = await TenantService.compter(
        platform_db, master_db, recherche=q, statut=statut, archive=archive
    )
    return paginate(items=[TenantResponse(**i) for i in items], total_records=total, params=params)


@platform_tenants_router.post(
    "",
    response_model=APIResponse[TenantCreationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer et provisionner un cabinet",
    responses={
        401: {"description": "Non authentifié"},
        403: {"description": "Permission insuffisante"},
        409: {"description": "NINEA ou e-mail administrateur déjà utilisé"},
        500: {"description": "Échec du provisionnement — entièrement annulé (aucun tenant à moitié créé)"},
    },
)
async def creer_tenant(
    data: TenantCreate,
    request: Request,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.tenants.create")
    ),
):
    """
    Provisionne un cabinet de bout en bout : base dédiée, schéma, semis depuis les
    gabarits, dossier plateforme, abonnement, index de routage, invitation de
    l'administrateur.

    **Tout ou rien.** En cas d'échec, chaque étape déjà effectuée est annulée
    (base supprimée, société supprimée) : il ne reste jamais de tenant à moitié
    créé, contrairement à l'outillage `/master/societes` d'origine qui laissait
    un état `PROVISIONING` orphelin.
    """
    resultat = await ProvisioningService.provisionner(
        master_db=master_db,
        platform_db=platform_db,
        nom=data.nom,
        admin_email=data.admin_email,
        admin_prenom=data.admin_prenom,
        admin_nom=data.admin_nom,
        statut_initial=data.statut_initial,
        ninea=data.ninea,
        adresse_siege=data.adresse_siege,
        ville=data.ville,
        pays=data.pays,
        telephone=data.telephone,
        site_web=data.site_web,
        logo_url=data.logo_url,
        langue=data.langue,
        fuseau_horaire=data.fuseau_horaire,
        devise=data.devise,
        plan_code=data.plan_code,
        jours_essai=data.jours_essai,
        auteur=auteur.email,
        motif=data.motif,
        client_ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    detail = await TenantService.detail(platform_db, master_db, resultat.tenant_id)
    return APIResponse(
        message=f"Le cabinet '{data.nom}' a été provisionné.",
        data=TenantCreationResponse(
            tenant=TenantDetailResponse(**detail),
            etapes=resultat.etapes,
            gabarits_appliques=resultat.gabarits_appliques,
            invitation_admin_envoyee=resultat.invitation_envoyee,
        ),
    )


@platform_tenants_router.get(
    "/transitions",
    response_model=APIResponse[dict],
    summary="Matrice des transitions de statut",
)
async def matrice_transitions(
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.read")),
):
    """
    Table des transitions autorisées.

    Exposée pour que le frontend puisse griser un bouton plutôt que d'attendre un
    422 : la règle est une donnée, pas une/devinette côté client.
    """
    return APIResponse(
        data={statut.value: transitions_possibles(statut) for statut in StatutTenant}
    )


@platform_tenants_router.get(
    "/{tenant_id}",
    response_model=APIResponse[TenantDetailResponse],
    summary="Détail d'un cabinet",
    responses={404: {"description": "Cabinet introuvable"}},
)
async def detail_tenant(
    tenant_id: uuid.UUID,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.read")),
):
    """Fiche complète : identité, statut, préférences, abonnement et transitions possibles."""
    detail = await TenantService.detail(platform_db, master_db, tenant_id)
    return APIResponse(data=TenantDetailResponse(**detail))


@platform_tenants_router.patch(
    "/{tenant_id}",
    response_model=APIResponse[TenantDetailResponse],
    summary="Modifier les informations d'un cabinet",
)
async def modifier_tenant(
    tenant_id: uuid.UUID,
    data: TenantUpdate,
    request: Request,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.tenants.update")
    ),
):
    """Met à jour l'identité (nom, contacts) ou les préférences (pays, langue, fuseau, devise)."""
    detail = await TenantService.modifier(
        platform_db,
        master_db,
        tenant_id,
        nom=data.nom,
        ninea=data.ninea,
        adresse_siege=data.adresse_siege,
        ville=data.ville,
        telephone=data.telephone,
        email=data.email,
        site_web=data.site_web,
        pays=data.pays,
        langue=data.langue,
        fuseau_horaire=data.fuseau_horaire,
        devise=data.devise,
        logo_url=data.logo_url,
        auteur=auteur.email,
        motif=data.motif,
        client_ip=client_ip(request),
    )
    return APIResponse(message="Cabinet modifié.", data=TenantDetailResponse(**detail))


@platform_tenants_router.post(
    "/{tenant_id}/suspension",
    response_model=APIResponse[TenantDetailResponse],
    summary="Suspendre un cabinet",
    responses={
        403: {"description": "Permission insuffisante"},
        422: {"description": "Transition non autorisée depuis l'état courant"},
    },
)
async def suspendre_tenant(
    tenant_id: uuid.UUID,
    data: TransitionStatut,
    request: Request,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.tenants.suspend")
    ),
):
    """
    Suspend l'accès du cabinet.

    Effets immédiats : le login du cabinet est refusé, l'API du cabinet renvoie
    `TENANT_NOT_FOUND`, et **toutes les sessions ouvertes sont révoquées** — sans
    cela un utilisateur resterait connecté jusqu'à l'expiration de son jeton, sur
    un compte qu'on vient de suspendre.

    Aucune donnée n'est supprimée : la suspension est réversible.
    """
    detail = await TenantService.changer_statut(
        platform_db,
        master_db,
        tenant_id,
        cible=StatutTenant.SUSPENDU,
        motif=data.motif,
        auteur=auteur.email,
        client_ip=client_ip(request),
        request_id=_request_id(request),
    )
    return APIResponse(message="Cabinet suspendu.", data=TenantDetailResponse(**detail))


@platform_tenants_router.post(
    "/{tenant_id}/reactivation",
    response_model=APIResponse[TenantDetailResponse],
    summary="Réactiver un cabinet",
)
async def reactiver_tenant(
    tenant_id: uuid.UUID,
    data: TransitionStatut,
    request: Request,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.tenants.activate")
    ),
):
    """Rétablit l'accès d'un cabinet suspendu, ou confirme le passage en production d'un essai."""
    detail = await TenantService.changer_statut(
        platform_db,
        master_db,
        tenant_id,
        cible=StatutTenant.ACTIF,
        motif=data.motif,
        auteur=auteur.email,
        client_ip=client_ip(request),
        request_id=_request_id(request),
    )
    return APIResponse(message="Cabinet réactivé.", data=TenantDetailResponse(**detail))


@platform_tenants_router.post(
    "/{tenant_id}/resiliation",
    response_model=APIResponse[TenantDetailResponse],
    summary="Résilier un cabinet",
)
async def resilier_tenant(
    tenant_id: uuid.UUID,
    data: TransitionStatut,
    request: Request,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.tenants.terminate")
    ),
):
    """
    Fait passer le cabinet en `RESILIE` — état terminal : aucune transition sortante.

    Aucune donnée n'est supprimée à ce stade. La suppression définitive est une
    opération distincte, avec ses propres verrous (double confirmation, droit
    spécifique, rétention).
    """
    detail = await TenantService.changer_statut(
        platform_db,
        master_db,
        tenant_id,
        cible=StatutTenant.RESILIE,
        motif=data.motif,
        auteur=auteur.email,
        client_ip=client_ip(request),
        request_id=_request_id(request),
    )
    return APIResponse(message="Cabinet résilié.", data=TenantDetailResponse(**detail))


@platform_tenants_router.post(
    "/{tenant_id}/archivage",
    response_model=APIResponse[TenantDetailResponse],
    summary="Archiver / désarchiver logiquement",
)
async def archiver_tenant(
    tenant_id: uuid.UUID,
    data: Archivage,
    request: Request,
    platform_db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.tenants.archive")
    ),
):
    """
    Retire le cabinet du registre actif sans rien supprimer.

    L'archivage est RÉVERSIBLE ; c'est ce qui en fait l'outil du quotidien. La
    suppression définitive, elle, est irréversible et exige trois verrous.
    """
    detail = await TenantService.archiver(
        platform_db,
        master_db,
        tenant_id,
        archiver=data.archiver,
        motif=data.motif,
        auteur=auteur.email,
        client_ip=client_ip(request),
    )
    return APIResponse(
        message="Cabinet archivé." if data.archiver else "Cabinet désarchivé.",
        data=TenantDetailResponse(**detail),
    )


@platform_tenants_router.get(
    "/{tenant_id}/historique",
    response_model=APIResponse[List[HistoriqueStatutEntry]],
    summary="Historique horodaté des transitions",
)
async def historique_tenant(
    tenant_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    platform_db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.tenants.read")),
):
    """
    Journal des changements de statut : horodatage, avant, après, motif, auteur, IP.

    Alimente l'écran « pourquoi ce cabinet est-il suspendu ? », question à laquelle
    la console doit pouvoir répondre sans fouiller dans les logs.
    """
    entrees = await TenantService.historique(platform_db, tenant_id, limit=limit)
    return APIResponse(
        data=[
            HistoriqueStatutEntry(
                horodatage=e.timestamp,
                statut_precedent=e.statut_precedent,
                statut_nouveau=e.statut_nouveau,
                motif=e.motif,
                auteur_email=e.auteur_email,
                ip_address=e.ip_address,
            )
            for e in entrees
        ]
    )