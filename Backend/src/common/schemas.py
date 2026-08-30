from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class APIResponse(BaseModel, Generic[T]):
    """Enveloppe standardisée pour toutes les réponses HTTP positives."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None

    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total_records: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Enveloppe pour les réponses de listes paginées."""
    success: bool = True
    items: List[T]
    meta: PaginationMeta

    model_config = ConfigDict(from_attributes=True)


class BaseSchema(BaseModel):
    """Schéma Pydantic de base avec configuration standardisée."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        validate_assignment=True,
        ser_json_timedelta="iso8601",
    )
