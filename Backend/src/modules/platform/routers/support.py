"""
Accès support encadré — console PLATEFORME (Phase D).

Trois endpoints, tous sous `/platform` :

- `POST /platform/tenants/{tenant_id}/acces-support`  : ouvre un accès (30 min)
- `GET  /platform/acces-support`                       : accès en cours
- `POST /platform/acces-support/{id}/revocation`       : coupe immédiatement

Le jeton retourné n'ouvre QUE des routes de lecture de l'espace du cabinet, et
seulement tant que la ligne `acces_support` est active : la révocation est
revalidée à chaque requête, pas déduite de l'expiration du jeton.
"""

import uuid
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.schemas import APIResponse
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import require_platform_permissions
from src.modules.platform.models import AccesSupport, UtilisateurPlateforme
from src.modules.platform.schemas import (
    AccesSupportCreate,
    AccesSupportResponse,
    SupportTokenResponse,
)
from src.modules.platform.services.journal import JournalService
from src.modules.platform.services.support import SupportAccessService

platform_support_router = APIRouter(
    prefix="/platform", tags=["Platform · Accès support"]
)

logger = structlog.get_logger(__name__)


def _vers_reponse(acces: AccesSupport) -> AccesSupportResponse:
    return AccesSupportResponse(
        id=acces.id,
        tenant_id=acces.tenant_id,
        agent_email=acces.agent_email,
        motif=acces.motif,
        ticket=acces.ticket,
        lecture_seule=acces.lecture_seule,
        statut=acces.statut.value,
        expire_le=acces.expire_le,
        revoque_at=acces.revoque_at,
        motif_revoque=acces.motif_revoque,
        administrateur_notifie=acces.admin_notifie,
        cree_le=acces.created_at,
    )


@platform_support_router.post(
    "/tenants/{tenant_id}/acces-support",
    response_model=APIResponse[SupportTokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Ouvrir un accès support encadré",
    responses={
        400: {"description": "Motif manquant ou trop court pour une élévation"},
        403: {"description": "Permission `platform.support.grant` manquante"},
        404: {"description": "Cabinet introuvable"},
        409: {"description": "Cabinet résilié : dossier inaccessible"},
    },
)
async def ouvrir_acces_support(
    tenant_id: uuid.UUID,
    data: AccesSupportCreate,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    agent: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.support.grant")
    ),
):
    """
    Émet un jeton d'accès à l'espace du cabinet, valable 30 minutes.

    **Lecture seule par défaut.** Passer `lecture_seule=false` exige la
    permission `platform.support.grant_elevated` ET un motif d'au moins 40
    caractères justifiant pourquoi la lecture ne suffit pas — et le drapeau
    `PLATFORM_SUPPORT_ELEVATION_ABILITEE` doit être activé sur l'installation.

    Le jeton returned porte `impersonated_by`, `support_reason`, `support_ticket`
    et `scope=support` : chaque action faite avec est attribuable à un agent et à
    un motif, sans que l'agent ait jamais eu accès au mot de passe du cabinet.

    L'ouverture est écrite dans le journal immuable de la plateforme **et** dans
    le journal d'audit du cabinet.
    """
    resultat = await SupportAccessService.demander(
        db,
        tenant_id=tenant_id,
        agent_id=agent.id,
        agent_email=agent.email,
        motif=data.motif,
        ticket=data.ticket,
        lecture_seule=data.lecture_seule,
        eleve=not data.lecture_seule,
        ip_address=request.client.host if request.client else None,
    )
    # Le journal du cabinet reçoit la mention lisible par le client.
    await _journaliser_chez_le_cabinet(
        db, tenant_id, agent.email, data.motif, data.ticket, data.lecture_seule
    )
    return APIResponse(
        message=(
            "Accès support ouvert. Le jeton est valable "
            f"{resultat['duree_minutes']} minutes et n'est pas renouvelable."
        ),
        data=SupportTokenResponse(
            id=resultat["id"],
            jeton=resultat["jeton"],
            expire_le=resultat["expire_le"],
            duree_minutes=resultat["duree_minutes"],
            lecture_seule=resultat["lecture_seule"],
            administrateur_notifie=resultat["administrateur_notifie"],
        ),
    )


async def _journaliser_chez_le_cabinet(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    agent_email: str,
    motif: str,
    ticket: Optional[str],
    lecture_seule: bool,
) -> None:
    """
    Trace l'accès dans le journal d'audit DU CABINET (Phase D.3).

    C'est la contrepartie non négociable : l'éditeur trace dans son journal,
    le cabinet trace dans le sien. Un client qui lit son journal voit « Accès
    support par X le …, motif : … ».

    L'écriture est volontairement tolérante aux pannes — une base tenant
    indisponible ne doit pas faire perdre l'accès côté plateforme, qui est déjà
    journalisé.
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from src.core.database import MasterAsyncSessionFactory, tenant_db_manager
    from src.modules.master.models import TenantDB
    from src.modules.tenants.models import AuditLogTenant

    try:
        async with MasterAsyncSessionFactory() as master:
            config = (
                await master.execute(
                    select(TenantDB).where(
                        TenantDB.societe_id == tenant_id, TenantDB.statut == "ACTIVE"
                    )
                )
            ).scalar_one_or_none()
        if config is None:
            return

        factory = await tenant_db_manager.get_session_factory(str(config.societe_id))
        async with factory() as tenant_session:
            entree = AuditLogTenant(
                action="SUPPORT_ACCESS",
                user_id=None,
                user_email=agent_email,
                resource_type="tenant",
                resource_id=str(tenant_id),
                changes={
                    "agent": agent_email,
                    "motif": motif,
                    "ticket": ticket,
                    "lecture_seule": lecture_seule,
                    "libelle": f"Accès support par {agent_email}, motif : {motif}",
                },
                ip_address=None,
                user_agent="plateforme-sysdent",
                timestamp=datetime.now(timezone.utc),
            )
            tenant_session.add(entree)
            await tenant_session.commit()
    except Exception as exc:  # noqa: BLE001 - la trace client ne bloque pas l'accès
        logger.warning(
            "journal_cabinet_acces_support_indisponible",
            tenant_id=str(tenant_id),
            erreur=str(exc),
        )


@platform_support_router.get(
    "/acces-support",
    response_model=APIResponse[List[AccesSupportResponse]],
    summary="Lister les accès support",
)
async def lister_acces_support(
    tenant_id: Optional[uuid.UUID] = Query(None, description="Filtrer par cabinet"),
    seulement_actifs: bool = Query(True),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.support.read")),
):
    """
    Accès ouverts, du plus récent au plus ancien.

    « Actif » = non révoqué et non expiré. C'est la réponse à « qui a accès à
    ce cabinet, là, maintenant ? » sans analyser un journal.
    """
    acces = await SupportAccessService.lister(
        db, tenant_id=tenant_id, seulement_actifs=seulement_actifs
    )
    return APIResponse(data=[_vers_reponse(a) for a in acces])


@platform_support_router.post(
    "/acces-support/{acces_id}/revocation",
    response_model=APIResponse[AccesSupportResponse],
    summary="Révoquer un accès support",
)
async def revoquer_acces_support(
    acces_id: uuid.UUID,
    request: Request,
    motif: str = Query(..., min_length=5, description="Motif de la révocation"),
    db: AsyncSession = Depends(get_platform_db),
    agent: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.support.revoke")
    ),
):
    """
    Coupe un accès. L'effet est immédiat : le jeton reste cryptographiquement
    valide jusqu'à son expiration, mais chaque requête faite avec est revalidée
    contre la base et refusée.

    Révoquer un accès déjà révoqué n'est pas une erreur : l'opérateur doit pouvoir
    confirmer l'absence d'accès sans apprendre qu'il avait déjà coupé.
    """
    acces = await SupportAccessService.revoquer(db, acces_id, agent.email, motif)
    await JournalService.journaliser(
        db,
        action="PLATFORM_ACCES_SUPPORT_REVOQUE",
        type_cible="TENANT",
        cible_id=str(acces.tenant_id),
        tenant_id=acces.tenant_id,
        acteur_email=agent.email,
        apres={"access_id": str(acces.id)},
        motif=motif,
        ip_address=request.client.host if request.client else None,
    )
    return APIResponse(message="Accès support révoqué.", data=_vers_reponse(acces))