from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from sqlalchemy import select
from src.core.config import settings
from src.core.database import get_master_db, tenant_db_manager
from src.core.exceptions import AuthenticationException
from src.core.rate_limit import cle_login, login_tenant_limiter
from src.core.security import decrypt_secret
from src.modules.auth.dependencies import get_current_user, get_tenant_db, get_token_payload
from src.modules.auth.schemas import LoginRequest, RefreshTokenRequest, TokenResponse, UserProfileResponse
from src.modules.auth.services import AuthService
from src.modules.master.models import TenantDB
from src.modules.tenants.models import Utilisateur

router = APIRouter(prefix="/auth", tags=["Authentification"])

logger = structlog.get_logger(__name__)


async def _contrat_du_cabinet(tenant_id: Optional[str]) -> dict:
    """
    Plan, quotas et fonctionnalités du cabinet (Phase C.4).

    Une panne de la base plateforme ne doit PAS EMPêcher un praticien de
    consulter son profil : on renvoie un contrat vide, ce qui vaut
    « illimité / toutes les fonctions », et l'application se comporte comme
    avant la mission. Une coupure du backoffice ne doit pas arrêter un cabinet.
    """
    if not tenant_id:
        return {}
    from src.core.platform_database import PlatformSessionFactory
    from src.modules.platform.services.quotas import QuotaService

    session = PlatformSessionFactory()
    try:
        contexte = await QuotaService.quotas(session, tenant_id)
    except SQLAlchemyError:
        logger.warning("contrat_indisponible", tenant_id=tenant_id)
        return {}
    finally:
        await session.close()
    return {
        "plan_code": contexte.get("plan"),
        "quotas": contexte.get("quotas") or {},
        "features": contexte.get("features") or {},
    }


def _deposer_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    master_db: AsyncSession = Depends(get_master_db),
):
    """
    Connexion utilisateur.

    Le cabinet est résolu via l'index Master `utilisateur_index`, le mot de passe
    est vérifié en base argon2, et une session persistée est créée pour rendre
    le token révocable. Le cookie HttpOnly est déposé pour les navigateurs.
    """
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    # Limitation de débit AVANT tout accès base : la force brute ne doit pas
    # pouvoir consommer de connexions PostgreSQL.
    cle = cle_login(login_data.email, client_ip)
    login_tenant_limiter.tenter(cle)

    user, tenant_id, _ = await AuthService.authenticate(
        email=login_data.email,
        password=login_data.password,
        master_db=master_db,
    )

    # On rouvre la base du cabinet pour y écrire la session : la session Master
    # ne peut pas écrire dans une base tenant.
    await AuthService.marquer_connexion_index(master_db, login_data.email)

    stmt = select(TenantDB).where(TenantDB.societe_id == tenant_id, TenantDB.statut == "ACTIVE")
    tenant_config = (await master_db.execute(stmt)).scalar_one_or_none()
    if tenant_config is None:
        raise AuthenticationException("Cabinet introuvable ou inactif.", code="TENANT_NOT_FOUND")

    await tenant_db_manager.get_or_create_engine(
        tenant_id=tenant_id,
        db_name=tenant_config.db_name,
        host=tenant_config.db_host,
        port=tenant_config.db_port,
        user=tenant_config.db_user,
        password=decrypt_secret(tenant_config.db_password),
    )
    session_factory = await tenant_db_manager.get_session_factory(tenant_id)

    async with session_factory() as tenant_session:
        access_token, refresh_token = await AuthService.ouvrir_session(
            tenant_session,
            user,
            tenant_id,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await tenant_session.commit()

    login_tenant_limiter.reussite(cle)
    _deposer_cookie(response, access_token)

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
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    request: Request,
    response: Response,
    tenant_db: AsyncSession = Depends(get_tenant_db),
):
    """
    Rotation du refresh token.

    Le rôle et les permissions sont RELUS en base à chaque renouvellement.
    L'ancienne version accordait `role="ADMIN_CABINET"` et `permissions=["ALL"]`
    en dur : n'importe quel refresh token d'un compte déclassé ou désactivé
    remontait en administrateur de cabinet.
    """
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")

    user, access_token, nouveau_refresh, tenant_id = await AuthService.renouveller_session(
        tenant_db,
        refresh_data.refresh_token,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    _deposer_cookie(response, access_token)
    return APIResponse(
        message="Session renouvelée avec succès.",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=nouveau_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            tenant_id=tenant_id,
        ),
    )


@router.post("/logout", response_model=APIResponse[None])
async def logout(
    refresh_data: RefreshTokenRequest,
    response: Response,
    tenant_db: AsyncSession = Depends(get_tenant_db),
):
    """
    Déconnexion : révoque la session en base et supprime le cookie.

    Avant cette correction, le logout ne faisait que supprimer le cookie : le
    refresh token restait rejouable pendant 7 jours depuis n'importe quel client.
    """
    await AuthService.revoquer_session(tenant_db, refresh_data.refresh_token)
    await tenant_db.commit()
    response.delete_cookie("access_token")
    return APIResponse(message="Déconnexion réussie.", data=None)


@router.get("/me", response_model=APIResponse[UserProfileResponse])
async def get_me(
    user: Utilisateur = Depends(get_current_user),
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Profil de l'utilisateur connecté.

    Les données sont lues en base, pas dans le JWT : un jeton est signé mais pas
    chiffré, et il circule dans les en-têtes et les journaux. Y placer l'email
    et le nom exposerait des données personnelles à quiconque peut lire un
    access token (proxy, trace APM,support). La lecture en base a l'avantage
    secondaire de refléter immédiatement un changement de nom ou de rôle.
    """
    return APIResponse(
        data=UserProfileResponse(
            id=user.id,
            email=user.email,
            prenom=user.prenom,
            nom=user.nom,
            role=user.role.nom if user.role is not None else "INCONNU",
            permissions=payload.get("permissions", []),
            telephone=user.telephone,
            photo_url=user.photo_url,
            tenant_id=payload.get("tenant_id"),
            **await _repere_cabinet(db, user),
            **await _contrat_du_cabinet(payload.get("tenant_id")),
        )
    )


async def _repere_cabinet(db: AsyncSession, user: Utilisateur) -> dict:
    """
    Nom du cabinet et site de rattachement, lus en base.

    Un cabinet a un nom, un utilisateur a une belongance : les deux permettent
    a la barre du haut d'afficher « ou suis-je » sans un second appel, et sans
    exiger `CABINETS:READ` — que le caissier n'a pas, et ne doit pas avoir.

    Le premier cabinet actif sert de repli quand l'utilisateur n'est rattache a
    aucun site : mieux vaut un nom juste que pas de repere du tout.
    """
    from sqlalchemy import select

    from src.modules.tenants.models import Cabinet

    cabinet_id = user.cabinet_id
    nom = None
    if cabinet_id is not None:
        nom = (
            await db.execute(select(Cabinet.nom).where(Cabinet.id == cabinet_id))
        ).scalar_one_or_none()
    if nom is None:
        nom = (
            await db.execute(
                select(Cabinet.nom).where(Cabinet.actif == True).limit(1)  # noqa: E712
            )
        ).scalar_one_or_none()
        cabinet_id = None if nom is not None else cabinet_id
    return {"cabinet_nom": nom, "cabinet_id": cabinet_id}
