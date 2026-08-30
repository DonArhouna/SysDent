import math
from typing import Generic, List, Sequence, TypeVar
from fastapi import Query
from pydantic import BaseModel, Field
from .schemas import PaginatedResponse, PaginationMeta

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Numéro de la page (commence à 1)")
    limit: int = Field(default=20, ge=1, le=100, description="Nombre d'éléments par page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def paginate(items: Sequence[T], total_records: int, params: PaginationParams) -> PaginatedResponse[T]:
    total_pages = math.ceil(total_records / params.limit) if total_records > 0 else 1
    return PaginatedResponse(
        success=True,
        items=list(items),
        meta=PaginationMeta(
            page=params.page,
            limit=params.limit,
            total_records=total_records,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_previous=params.page > 1,
        ),
    )
