import math
from typing import Generic, List, Sequence, TypeVar
from fastapi import Query
from pydantic import BaseModel, Field
from .schemas import PaginatedResponse, PaginationMeta

T = TypeVar("T")


#: Plafond unique de pagination, reutilise par les routes qui annoncent
#: leur `limit`. Une route qui annonce un plafond different du modele
#: accepte en query une valeur que la construction de page refuse ensuite.
LIMITE_PAGE_MAX: int = 100


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Numéro de la page (commence à 1)")
    limit: int = Field(
        default=20, ge=1, le=LIMITE_PAGE_MAX, description="Nombre d'éléments par page"
    )

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
