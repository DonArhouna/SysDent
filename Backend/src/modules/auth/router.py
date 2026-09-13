from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from src.core.config import settings
from src.core.database import get_master_db
from src.core.exceptions import AuthenticationException
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.modules.auth.dependencies import get_current_user, get_token_payload
from src.modules.auth.schemas import LoginRequest, RefreshTokenRequest, TokenResponse, UserProfileResponse
from src.modules.auth.services import AuthService
from src.modules.tenants.models import SessionUser, Utilisateur

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    master_db: AsyncSession = Depends(get_master_db),
):
    """
    Connexion utilisateur : résout le cabinet rattaché à l'email, vérifie le mot de passe
    dans sa base tenant, puis génère un Access Token court et un Refresh Token de session.
    Dépose optionnellement le cookie HttpOnly pour une sécurité maximale contre les failles XSS.
    """
    user, tenant_id, permissions = await AuthService.authenticate(
        email=login_data.email,
        password=login_data.password,
        master_db=master_db,
    )

    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=tenant_id,
        role=user.role.nom,
        permissions=permissions,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id),
        tenant_id=tenant_id,
    )

    # Déposer le cookie HttpOnly sécurisé
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return APIResponse(
        message="Authentification réussie.",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            tenant_id=tenant_id,
        ),
    )


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh_token(refresh_data: RefreshTokenRequest, response: Response):
    """Effectue la rotation du refresh token et délivre un nouvel access token."""
    payload = decode_token(refresh_data.refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationException("Jeton de rafraîchissement invalide.", code="INVALID_REFRESH_TOKEN")

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    new_access_token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="ADMIN_CABINET",
        permissions=["ALL"],
    )
    new_refresh_token = create_refresh_token(user_id=user_id, tenant_id=tenant_id)

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return APIResponse(
        message="Session renouvelée avec succès.",
        data=TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            tenant_id=tenant_id,
        ),
    )


@router.post("/logout", response_model=APIResponse[None])
async def logout(response: Response):
    """Déconnexion de l'utilisateur et suppression du cookie sécurisé."""
    response.delete_cookie("access_token")
    return APIResponse(message="Déconnexion réussie.", data=None)


@router.get("/me", response_model=APIResponse[dict])
async def get_me(payload: dict = Depends(get_token_payload)):
    """Récupère les informations de l'utilisateur connecté."""
    return APIResponse(
        data={
            "user_id": payload.get("sub"),
            "tenant_id": payload.get("tenant_id"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
        }
    )
