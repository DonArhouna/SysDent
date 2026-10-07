from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.pagination import PaginationParams, paginate
from src.common.schemas import PaginatedResponse
from src.modules.audit.schemas import AuditLogResponse
from src.modules.auth.dependencies import (
    get_actor,
    get_current_user,
    get_tenant_db,
)
from src.core.exceptions import BusinessRuleViolationException
from src.modules.tenants.models import AuditLogTenant, Utilisateur

router = APIRouter(prefix="/audit", tags=["Audit & Traçabilité"])


async def refuser_actor_tenant(
    actor: Utilisateur = Depends(get_actor),
) -> Utilisateur:
    """
    Refuse l'accès au journal d'audit pour tout acteur du tenant.

    Une interdiction explicite est nécessaire, et non une permission absente :
    `ADMIN_CABINET` **court-circuite** le contrôle des permissions (c'est le rôle
    de secours du cabinet), donc retirer `AUDIT:READ` de la matrice n'aurait rien
    changé pour lui.

    Le journal d'audit est une **traçabilité de plateforme**. L'application du
    cabinet n'a rien à y chercher, et y montrer l'historique complet de toutes les
    actions du personnel n'apporte rien à un utilisateur du cabinet.

    L'**écriture**, elle, reste en place partout : c'est une obligation de
    traçabilité. Seule la lecture est retirée d'ici. Le support plateforme et le
    backoffice continuent d'y accéder par leur propre chemin.
    """
    if actor is not None and getattr(actor, "role_id", None) is not None:
        raise BusinessRuleViolationException(
            "Le journal d'audit est réservé à la plateforme.",
            code="HORS_PERIMETRE_TENANT",
        )
    return actor


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    resource_type: Optional[str] = Query(None, description="Filtrer par ressource (ex: Patient)"),
    resource_id: Optional[str] = Query(None, description="Filtrer par ID d'entité"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Utilisateur = Depends(refuser_actor_tenant),
    db: AsyncSession = Depends(get_tenant_db),
    # Format "MODULE:ACTION" : c'est le format que produit `AuthService.authenticate`
    # (module + action de la table `permissions`). Le former "AUDIT_READ" ne pouvait
    # jamais correspondre et bloquait l'accès pour tout rôle non-administrateur.
):
    """
    Consulte le journal d'audit légal du cabinet (Réservé aux profils autorisés).

    Accepte un jeton support en lecture seule : diagnostiquer « qui a touché à ce
    dossier, et quand ? » est précisément le besoin du support, et le journal ne
    contient pas de contenu clinique — uniquement qui a fait quoi.
    """
    params = PaginationParams(page=page, limit=limit)
    
    query = select(AuditLogTenant)
    count_query = select(func.count(AuditLogTenant.id))

    if resource_type:
        query = query.where(AuditLogTenant.resource_type == resource_type)
        count_query = count_query.where(AuditLogTenant.resource_type == resource_type)

    if resource_id:
        query = query.where(AuditLogTenant.resource_id == resource_id)
        count_query = count_query.where(AuditLogTenant.resource_id == resource_id)

    total_count_res = await db.execute(count_query)
    total_records = total_count_res.scalar_one()

    query = query.order_by(AuditLogTenant.timestamp.desc()).offset(params.offset).limit(params.limit)
    items_res = await db.execute(query)
    items = items_res.scalars().all()

    return paginate(items=items, total_records=total_records, params=params)
