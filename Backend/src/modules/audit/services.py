from typing import Any, Dict, Optional
import uuid
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.pagination import PaginationParams, paginate
from src.modules.audit.schemas import AuditLogResponse
from src.modules.tenants.models import AuditLogTenant

logger = structlog.get_logger(__name__)


class AuditService:
    @staticmethod
    async def log_action(
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLogTenant:
        """Enregistre un événement médico-légal immuable dans la base du cabinet."""
        log_entry = AuditLogTenant(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log_entry)
        await db.flush()

        logger.info(
            "audit_trail_recorded",
            action=action,
            resource=resource_type,
            resource_id=resource_id,
            user_email=user_email,
        )
        return log_entry
