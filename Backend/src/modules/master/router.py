from typing import List
import uuid
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from src.core.database import get_master_db
from src.modules.master.models import Societe
from src.modules.master.schemas import SocieteCreate, SocieteResponse, SocieteUpdate
from src.modules.master.services import MasterTenantService

router = APIRouter(prefix="/master/societes", tags=["Super Admin / Sociétés & Dossiers"])


@router.get("", response_model=APIResponse[List[SocieteResponse]])
async def list_societes(db: AsyncSession = Depends(get_master_db)):
    """Liste l'ensemble des sociétés et cabinets provisionnés (Accès Super Admin)."""
    societes = await MasterTenantService.get_all_societes(db)
    return APIResponse(data=societes)


@router.post("", response_model=APIResponse[SocieteResponse], status_code=status.HTTP_201_CREATED)
async def create_societe(
    data: SocieteCreate,
    request: Request,
    db: AsyncSession = Depends(get_master_db),
):
    """
    Crée une nouvelle structure/société et provisionne automatiquement son dossier dédié (DB PostgreSQL).
    """
    client_ip = request.client.host if request.client else "unknown"
    societe = await MasterTenantService.create_societe_and_provision_tenant(
        session=db,
        data=data,
        client_ip=client_ip,
    )
    return APIResponse(
        message=f"La société '{societe.nom}' et son dossier DB ont été créés avec succès.",
        data=societe,
    )


@router.get("/{societe_id}", response_model=APIResponse[SocieteResponse])
async def get_societe(societe_id: uuid.UUID, db: AsyncSession = Depends(get_master_db)):
    """Récupère les détails d'une société et son statut de base de données."""
    societe = await MasterTenantService.get_societe_by_id(db, societe_id)
    return APIResponse(data=societe)
