from .router import router as patients_router
from .services import AlertService, AntecedentService, EtatGeneralService, PatientService

__all__ = [
    "patients_router",
    "PatientService",
    "EtatGeneralService",
    "AntecedentService",
    "AlertService",
]

# `router` est volontairement exporté sous ce nom pour éviter toute collision avec
# `fastapi.router` lors des imports en chaîne (comme pour les autres modules).
