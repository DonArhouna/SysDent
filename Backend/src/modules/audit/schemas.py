from datetime import datetime
from typing import Any, Dict, Optional
import uuid
from pydantic import Field
from src.common.schemas import BaseSchema


class AuditLogCreate(BaseSchema):
    action: str = Field(..., description="Action réalisée (ex: CONSULTATION_UPDATE, INVOICE_VOID)")
    resource_type: str = Field(..., description="Type d'entité (ex: Patient, Odontogram, Facture)")
    resource_id: str = Field(..., description="Identifiant unique de la ressource")
    changes: Optional[Dict[str, Any]] = Field(None, description="Diff json {before: ..., after: ...}")


class AuditLogResponse(BaseSchema):
    id: uuid.UUID
    timestamp: datetime
    user_id: Optional[uuid.UUID] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
