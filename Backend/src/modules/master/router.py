"""
Routes de la console d'administration plateforme (base Master).

Toutes les routes sont protégées par `get_current_super_admin` : avant le Sprint
0bis, `POST /master/societes` était accessible sans aucune authentification et
déclenchait un vrai `CREATE DATABASE`.
"""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from src.core.config import settings
from src.core.database import get_master_db
from src.core.exceptions import AuthenticationException
from src.core.rate_limit import cle_login, login_master_limiter
from src.modules.master.dependencies import get_current_super_admin
from src.modules.master.models import SuperAdmin
from src.modules.master.schemas import (
    MasterTokenResponse,
    SocieteCreate,
    SocieteResponse,
    SocieteUpdate,
    SocieteStatutUpdate,
    SuperAdminLogin,
    SuperAdminResponse,
    SuperAdminSessionResponse,
)
from src.modules.master.services import MasterAuthService, MasterTenantService

router = APIRouter(prefix="/master", tags=["Console Super Admin"])


def _deposer_cookie_master(response: Response, token: str) -> None:
    response.set_cookie(
        key="master_access_token",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/api/v1/master",
    )


# ==============================================================================
# AUTHENTIFICATION CONSOLE MASTER
# ==============================================================================

@router.post("/auth/login", response_model=APIResponse[MasterTokenResponse])
async def master_login(
    data: SuperAdminLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_master_db),
):
    """Connexion Super Admin à la console de plateforme (base Master)."""
    client_ip = request.client.host if request.client else "unknown"

    cle = cle_login(data.email, client_ip)
    login_master_limiter.tenter(cle)

    admin, access_token, refresh_token = await MasterAuthService.authentifier(
        db, data.email, data.password, client_ip=client_ip
    )

    login_master_limiter.reussite(cle)
    _deposer_cookie_master(response, access_token)

    return APIResponse(
        message="Authentification Super Admin réussie.",
        data=MasterTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            email=admin.email,
            nom_complet=admin.nom_complet,
        ),
    )


@router.post("/auth/refresh", response_model=APIResponse[MasterTokenResponse])
async def master_refresh(
    refresh_token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_master_db),
):
    """Renouvelle un jeton de session console Master."""
    access_token, nouveau_refresh = await MasterAuthService.renouveller(
        db, refresh_token, client_ip=request.client.host if request.client else None
    )
    _deposer_cookie_master(response, access_token)
    return APIResponse(
        message="Session renouvelée.",
        data=MasterTokenResponse(
            access_token=access_token,
            refresh_token=nouveau_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.post("/auth/logout", response_model=APIResponse[None])
async def master_logout(
    refresh_token: str,
    response: Response,
    db: AsyncSession = Depends(get_master_db),
):
    """Déconnexion : révoque la session Master en base et supprime le cookie."""
    await MasterAuthService.revoquer(db, refresh_token)
    response.delete_cookie("master_access_token", path="/api/v1/master")
    return APIResponse(message="Déconnexion Super Admin réussie.", data=None)


@router.get("/auth/me", response_model=APIResponse[SuperAdminResponse])
async def master_me(admin: SuperAdmin = Depends(get_current_super_admin)):
    """Profil du Super Admin connecté."""
    return APIResponse(
        data=SuperAdminResponse(
            id=admin.id,
            email=admin.email,
            nom_complet=admin.nom_complet,
            actif=admin.actif,
            dernier_login=admin.dernier_login,
        )
    )


# ==============================================================================
# GESTION DES SOCIÉTÉS & CABINETS HÉBERGÉS
# ==============================================================================

@router.get("/societes", response_model=APIResponse[List[SocieteResponse]])
async def list_societes(
    db: AsyncSession = Depends(get_master_db),
    _: SuperAdmin = Depends(get_current_super_admin),
):
    """Liste des sociétés et cabinets provisionnés (accès Super Admin)."""
    societes = await MasterTenantService.get_all_societes(db)
    return APIResponse(data=societes)


@router.post("/societes", response_model=APIResponse[SocieteResponse], status_code=status.HTTP_201_CREATED)
async def create_societe(
    data: SocieteCreate,
    request: Request,
    db: AsyncSession = Depends(get_master_db),
    admin: SuperAdmin = Depends(get_current_super_admin),
):
    """
    Crée une nouvelle structure/société et provisionne son dossier dédié
    (base PostgreSQL + schéma Alembic + RBAC + compte admin).

    L'auteur de l'opération est journalisé dans `audit_logs_global`.
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


@router.get("/societes/{societe_id}", response_model=APIResponse[SocieteResponse])
async def get_societe(
    societe_id: uuid.UUID,
    db: AsyncSession = Depends(get_master_db),
    _: SuperAdmin = Depends(get_current_super_admin),
):
    """Détails d'une société et statut de sa base de données."""
    societe = await MasterTenantService.get_societe_by_id(db, societe_id)
    return APIResponse(data=societe)


@router.patch("/societes/{societe_id}", response_model=APIResponse[SocieteResponse])
async def update_societe(
    societe_id: uuid.UUID,
    data: SocieteUpdate,
    db: AsyncSession = Depends(get_master_db),
    _: SuperAdmin = Depends(get_current_super_admin),
):
    """Met à jour les informations administratives d'une société."""
    societe = await MasterTenantService.get_societe_by_id(db, societe_id)
    for champ, valeur in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(societe, champ, str(valeur) if champ == "email" else valeur)
    await db.commit()
    return await MasterTenantService.get_societe_by_id(db, societe_id)


@router.post("/societes/{societe_id}/statut", response_model=APIResponse[SocieteResponse])
async def set_societe_statut(
    societe_id: uuid.UUID,
    data: SocieteStatutUpdate,
    request: Request,
    db: AsyncSession = Depends(get_master_db),
    admin: SuperAdmin = Depends(get_current_super_admin),
):
    """
    Suspend ou réactive un cabinet.

    La suspension bloque les connexions du cabinet sans supprimer aucune donnée :
    les dossiers médicaux sont conservés (obligation médico-légale).
    """
    client_ip = request.client.host if request.client else "unknown"
    societe = await MasterTenantService.basculer_statut(
        db, societe_id, data.actif, auteur=admin.email, client_ip=client_ip
    )
    etat = "réactivé" if data.actif else "suspendu"
    return APIResponse(message=f"Cabinet {etat}.", data=societe)


@router.get("/statistiques", response_model=APIResponse[dict])
async def statistiques(
    db: AsyncSession = Depends(get_master_db),
    _: SuperAdmin = Depends(get_current_super_admin),
):
    """Tableau de bord plateforme : volumes de cabinets et de sessions."""
    return APIResponse(data=await MasterTenantService.statistiques(db))
