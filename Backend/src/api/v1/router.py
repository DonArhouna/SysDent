from fastapi import APIRouter
from src.modules.audit import audit_router
from src.modules.auth import auth_router
from src.modules.cabinets import cabinets_router
from src.modules.caisse import caisse_router
from src.modules.consultations import consultations_router, nomenclature_router
from src.modules.facturation import devis_router, facturation_router
from src.modules.master import master_router
from src.modules.odontogramme import odontogramme_router
from src.modules.ordonnances import medicaments_router, ordonnances_router
from src.modules.patients import patients_router
from src.modules.platform.routers.auth import platform_auth_router
from src.modules.platform.routers.commercial import platform_commercial_router
from src.modules.platform.routers.onboarding import onboarding_router
from src.modules.platform.routers.support import platform_support_router
from src.modules.platform.routers.supervision import platform_supervision_router
from src.modules.platform.routers.tenants import platform_tenants_router
from src.modules.platform.routers.users import platform_users_router
from src.modules.rbac import rbac_router
from src.modules.rendezvous import rendezvous_router
from src.modules.stock import stock_router
from src.modules.utilisateurs import utilisateurs_router

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

# Pôle 2 : facturation. `/factures/journal-caisse` est déclaré dans le même
# routeur AVANT `/factures/{facture_id}` : l'ordre interne suffit, aucun
# problème d'absorption ici.
api_v1_router.include_router(caisse_router)
api_v1_router.include_router(facturation_router)
api_v1_router.include_router(devis_router)

api_v1_router.include_router(rbac_router)
api_v1_router.include_router(stock_router)
api_v1_router.include_router(utilisateurs_router)

# ─────────────────────────────────────────────────────────────────────────────
# CONSOLE PLATEFORME (backoffice éditeur)
# ─────────────────────────────────────────────────────────────────────────────
# Les routes `/platform/*` sont un MONDE SEPARE : clé de signature dédiée,
# audience dédiée, catalogue de permissions `platform.*`, base de données
# dédiée. Elles sont enregistrées en fin de liste pour que l'ajout de la console
# ne puisse pas modifier l'ordre de résolution des routes client (les absorption
# de type `/ordonnances/{id}` vs `/ordonnances/medicaments` documentées plus haut
# sont sensibles à cet ordre).
api_v1_router.include_router(platform_auth_router)
api_v1_router.include_router(platform_users_router)
api_v1_router.include_router(platform_tenants_router)
api_v1_router.include_router(platform_commercial_router)
api_v1_router.include_router(platform_support_router)
api_v1_router.include_router(platform_supervision_router)

# Onboarding PUBLIC : hors du groupe « Platform » et sans jeton. Enregistré en
# fin de liste, comme la console, pour ne pas modifier l'ordre de résolution des
# routes client.
api_v1_router.include_router(onboarding_router)
