from .router import medicaments_router, router as ordonnances_router
from .services import MedicamentService, OrdonnanceService

__all__ = [
    "ordonnances_router",
    "medicaments_router",
    "OrdonnanceService",
    "MedicamentService",
]
