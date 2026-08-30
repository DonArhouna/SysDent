from fastapi import APIRouter
from src.modules.audit import audit_router
from src.modules.auth import auth_router
from src.modules.master import master_router

api_v1_router = APIRouter()

# Enregistrement des sous-routeurs
api_v1_router.include_router(auth_router)
api_v1_router.include_router(master_router)
api_v1_router.include_router(audit_router)
