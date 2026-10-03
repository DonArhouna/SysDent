from fastapi import APIRouter
from src.modules.audit import audit_router
from src.modules.auth import auth_router
from src.modules.cabinets import cabinets_router
from src.modules.consultations import consultations_router, nomenclature_router
from src.modules.master import master_router
from src.modules.odontogramme import odontogramme_router
from src.modules.ordonnances import medicaments_router, ordonnances_router
from src.modules.patients import patients_router
from src.modules.rbac import rbac_router
from src.modules.rendezvous import rendezvous_router

api_v1_router = APIRouter()

# Enregistrement des sous-routeurs
api_v1_router.include_router(auth_router)
api_v1_router.include_router(master_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(consultations_router)
api_v1_router.include_router(nomenclature_router)
api_v1_router.include_router(odontogramme_router)

# ⚠️ ORDRE IMPORTANT : le sous-routeur des médicaments est enregistré AVANT le
# routeur des ordonnances. FastAPI teste les routes dans l'ordre de
# déclaration, et `/ordonnances/{prescription_id}` (GET) absorberait sinon
# `/ordonnances/medicaments`, qui n'existe qu'au niveau du sous-routeur.
# Inverser cet ordre casse silencieusement le référentiel médicamenteux.
api_v1_router.include_router(medicaments_router)
api_v1_router.include_router(ordonnances_router)

# Pôle 2 : décor physique puis agenda.
api_v1_router.include_router(cabinets_router)
api_v1_router.include_router(rendezvous_router)

api_v1_router.include_router(rbac_router)
