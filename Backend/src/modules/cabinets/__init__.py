from .router import router as cabinets_router
from .services import (
    CabinetService,
    DisponibiliteService,
    FauteuilService,
    PraticienService,
    SalleService,
)

__all__ = [
    "cabinets_router",
    "CabinetService",
    "SalleService",
    "FauteuilService",
    "PraticienService",
    "DisponibiliteService",
]
