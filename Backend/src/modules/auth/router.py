from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.schemas import APIResponse
from sqlalchemy import select
from src.core.config import settings
from src.core.database import get_master_db
from src.core.exceptions import AuthenticationException
from src.core.rate_limit import cle_login, login_tenant_limiter
from src.modules.auth.dependencies import get_current_user, get_tenant_db, get_token_payload
from src.modules.auth.schemas import (
    ActivationDeuxFacteursRequest,
    ActivationInfoResponse,
    ActivationRequest,
    CodesSecoursResponse,
    EnvoiCodeResponse,
    EtapeCodeRequest,
    EtapeJetonRequest,
    EtapeMotDePasseRequest,
    JetonActivationRequest,
    LoginEtapeResponse,
    LoginRequest,
    PreparationTotpResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserProfileResponse,
)
from src.modules.auth.securite import (
    ACTIVATION,
    ETAPE_2FA,
    ETAPE_ENROLEMENT,
    SecuriteCompte,
    decouper_jeton,
    deux_facteurs_obligatoire,
    methodes_2fa,
    session_cabinet,
)
from src.modules.auth.services import AuthService
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


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _charger(db: AsyncSession, user_id) -> Utilisateur:
    from sqlalchemy.orm import selectinload

    return (
        await db.execute(
            select(Utilisateur).options(selectinload(Utilisateur.role)).where(Utilisateur.id == user_id)
        )
    ).scalar_one()


async def _ouvrir(
    db: AsyncSession,
    user: Utilisateur,
    tenant_id: str,
    request: Request,
    response: Response,
    **extra,
) -> APIResponse[LoginEtapeResponse]:
    """Ouvre la session : seule issue qui émet des jetons de session."""
    access_token, refresh_token = await AuthService.ouvrir_session(
        db, user, tenant_id, ip_address=_ip(request), user_agent=request.headers.get("user-agent")
    )
    await db.commit()
    _deposer_cookie(response, access_token)
    return APIResponse(
        message="Authentification réussie.",
        data=LoginEtapeResponse(
            etape="session",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            tenant_id=tenant_id,
            **extra,
        ),
    )


async def _suite(
    db: AsyncSession, user: Utilisateur, tenant_id: str, request: Request, response: Response
) -> APIResponse[LoginEtapeResponse]:
    """Après une étape franchie : l'étape suivante, ou la session."""
    etape = await SecuriteCompte.etape_suivante(db, user, tenant_id)
    if etape["etape"] == "session":
        return await _ouvrir(
            db, user, tenant_id, request, response, deux_facteurs_recommande=not user.deux_facteurs
        )
    await db.commit()
    return APIResponse(message="Étape suivante requise.", data=LoginEtapeResponse(**etape))


def _limiter(prefixe: str, cle: str, request: Request) -> str:
    """Même limiteur que le login : 5 essais, puis blocage. Un code à 6 chiffres ne se devine pas en 5."""
    complete = f"{prefixe}|{cle_login(cle, _ip(request))}"
    login_tenant_limiter.tenter(complete)
    return complete


@router.post("/login", response_model=APIResponse[LoginEtapeResponse])
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    master_db: AsyncSession = Depends(get_master_db),
):
    """
    Connexion utilisateur, **en étapes**.

    Le cabinet est résolu via l'index Master, le mot de passe vérifié en argon2.
    Ensuite, selon le compte : session directe, changement du mot de passe
    temporaire, code de double authentification, ou configuration de la 2FA
    (obligatoire pour l'administrateur du cabinet). Voir `LoginEtapeResponse`.
    """
    cle = cle_login(login_data.email, _ip(request))
    login_tenant_limiter.tenter(cle)

    user, tenant_id, _ = await AuthService.authenticate(
        email=login_data.email,
        password=login_data.password,
        master_db=master_db,
    )
    await AuthService.marquer_connexion_index(master_db, login_data.email)
    login_tenant_limiter.reussite(cle)

    async with await session_cabinet(tenant_id) as db:
        return await _suite(db, await _charger(db, user.id), tenant_id, request, response)


# ── Activation du compte (lien reçu par e-mail) ──────────────────────────────


@router.post("/activation/verification", response_model=APIResponse[ActivationInfoResponse])
async def verifier_activation(data: JetonActivationRequest, request: Request):
    """Dit à qui appartient le lien, avant de choisir le mot de passe. Ne consomme rien."""
    tenant_id, secret = decouper_jeton(data.jeton)
    _limiter("tenant_activation", secret[:16], request)
    async with await session_cabinet(tenant_id) as db:
        _, user = await SecuriteCompte.lire(db, secret, (ACTIVATION,))
    cabinet_nom, logo = await _identite_cabinet(tenant_id)
    return APIResponse(
        data=ActivationInfoResponse(
            email=user.email, prenom=user.prenom, nom=user.nom, cabinet_nom=cabinet_nom, cabinet_logo_url=logo
        )
    )


@router.post("/activation", response_model=APIResponse[None])
async def activer_compte(data: ActivationRequest, request: Request):
    """Le titulaire choisit son mot de passe ; le lien ne sert plus ensuite."""
    tenant_id, secret = decouper_jeton(data.jeton)
    _limiter("tenant_activation", secret[:16], request)
    async with await session_cabinet(tenant_id) as db:
        user = await SecuriteCompte.activer(db, secret, data.mot_de_passe)
        await AuthService.revoquer_toutes_sessions(db, user.id)
        await db.commit()
    return APIResponse(message="Compte activé. Vous pouvez vous connecter.", data=None)


# ── Étapes de connexion ───────────────────────────────────────────────────────


@router.post("/etape/mot-de-passe", response_model=APIResponse[LoginEtapeResponse])
async def etape_mot_de_passe(data: EtapeMotDePasseRequest, request: Request, response: Response):
    """Remplace le mot de passe temporaire, puis enchaîne sur l'étape suivante."""
    tenant_id, secret = decouper_jeton(data.jeton_etape)
    _limiter("tenant_etape", secret[:16], request)
    async with await session_cabinet(tenant_id) as db:
        user, _ = await SecuriteCompte.changer_mot_de_passe_initial(db, secret, data.nouveau)
        await AuthService.revoquer_toutes_sessions(db, user.id)
        return await _suite(db, user, tenant_id, request, response)


@router.post("/etape/code-email", response_model=APIResponse[EnvoiCodeResponse])
async def etape_code_email(data: EtapeJetonRequest, request: Request):
    """Envoie un code à l'adresse du compte. Il ne vaut que pour cette étape."""
    tenant_id, secret = decouper_jeton(data.jeton_etape)
    async with await session_cabinet(tenant_id) as db:
        jeton, user = await SecuriteCompte.lire(db, secret, (ETAPE_2FA, ETAPE_ENROLEMENT))
        # Chaque envoi compte, sans remise à zéro : pas d'inondation de boîte mail.
        _limiter("tenant_code_email", user.email, request)
        envoi = await SecuriteCompte.envoyer_code_email(db, user, jeton.hash_jeton)
    return APIResponse(message="Code envoyé.", data=EnvoiCodeResponse(**envoi))


@router.post("/etape/2fa", response_model=APIResponse[LoginEtapeResponse])
async def etape_2fa(data: EtapeCodeRequest, request: Request, response: Response):
    """Code de l'application, code e-mail de cette étape, ou code de secours."""
    tenant_id, secret = decouper_jeton(data.jeton_etape)
    cle = _limiter("tenant_etape", secret[:16], request)
    async with await session_cabinet(tenant_id) as db:
        user, _ = await SecuriteCompte.verifier_defi(db, secret, data.code)
        login_tenant_limiter.reussite(cle)
        return await _ouvrir(db, user, tenant_id, request, response)


@router.post("/etape/2fa/preparation", response_model=APIResponse[PreparationTotpResponse])
async def etape_preparation_totp(data: EtapeJetonRequest, request: Request):
    """Secret à scanner (QR code), pendant la configuration obligatoire."""
    tenant_id, secret = decouper_jeton(data.jeton_etape)
    async with await session_cabinet(tenant_id) as db:
        _, user = await SecuriteCompte.lire(db, secret, (ETAPE_ENROLEMENT,))
        preparation = SecuriteCompte.preparer_totp(user)
        await db.commit()
    return APIResponse(data=PreparationTotpResponse(**preparation))


@router.post("/etape/2fa/activation", response_model=APIResponse[LoginEtapeResponse])
async def etape_activation_2fa(data: ActivationDeuxFacteursRequest, request: Request, response: Response):
    """Active la 2FA (application ou e-mail), rend les codes de secours une fois, ouvre la session."""
    if not data.jeton_etape:
        raise AuthenticationException("Étape de connexion manquante.", code="JETON_ETAPE_REQUIS")
    tenant_id, secret = decouper_jeton(data.jeton_etape)
    cle = _limiter("tenant_etape", secret[:16], request)
    async with await session_cabinet(tenant_id) as db:
        jeton, user = await SecuriteCompte.lire(db, secret, (ETAPE_ENROLEMENT,))
        codes = await SecuriteCompte.activer_2fa(db, user, data.methode, data.code, jeton.hash_jeton)
        SecuriteCompte.consommer(jeton)
        login_tenant_limiter.reussite(cle)
        return await _ouvrir(db, user, tenant_id, request, response, codes_secours=codes)


# ── 2FA volontaire, depuis « Mon compte » (session ouverte) ──────────────────


def _contexte_session(user: Utilisateur) -> str:
    import hashlib

    return hashlib.sha256(f"session:{user.id}".encode()).hexdigest()


@router.post("/2fa/preparation", response_model=APIResponse[PreparationTotpResponse])
async def preparation_totp(
    user: Utilisateur = Depends(get_current_user), db: AsyncSession = Depends(get_tenant_db)
):
    preparation = SecuriteCompte.preparer_totp(user)
    await db.commit()
    return APIResponse(data=PreparationTotpResponse(**preparation))


@router.post("/2fa/code-email", response_model=APIResponse[EnvoiCodeResponse])
async def code_email_session(
    request: Request, user: Utilisateur = Depends(get_current_user), db: AsyncSession = Depends(get_tenant_db)
):
    _limiter("tenant_code_email", user.email, request)
    envoi = await SecuriteCompte.envoyer_code_email(db, user, _contexte_session(user))
    return APIResponse(message="Code envoyé.", data=EnvoiCodeResponse(**envoi))


@router.post("/2fa/activation", response_model=APIResponse[CodesSecoursResponse])
async def activation_2fa_session(
    data: ActivationDeuxFacteursRequest,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    cle = _limiter("tenant_activation_2fa", user.email, request)
    codes = await SecuriteCompte.activer_2fa(db, user, data.methode, data.code, _contexte_session(user))
    await db.commit()
    login_tenant_limiter.reussite(cle)
    return APIResponse(message="Double authentification activée.", data=CodesSecoursResponse(codes_secours=codes))


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
    societe_nom, logo = await _identite_cabinet(payload.get("tenant_id"))
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
            deux_facteurs=user.deux_facteurs,
            methodes_2fa=methodes_2fa(user) if user.deux_facteurs else [],
            deux_facteurs_obligatoire=deux_facteurs_obligatoire(user),
            cabinet_logo_url=logo,
            societe_nom=societe_nom,
            **await _repere_cabinet(db, user),
            **await _contrat_du_cabinet(payload.get("tenant_id")),
        )
    )


async def _identite_cabinet(tenant_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """(nom, adresse du logo) de la société, en base master. Une panne ne casse rien."""
    if not tenant_id:
        return None, None
    import uuid as _uuid

    from src.core.database import MasterAsyncSessionFactory
    from src.modules.master.models import Societe

    try:
        async with MasterAsyncSessionFactory() as master:
            ligne = (
                await master.execute(
                    select(Societe.nom, Societe.logo_url).where(Societe.id == _uuid.UUID(str(tenant_id)))
                )
            ).first()
            return (ligne[0], ligne[1]) if ligne else (None, None)
    except (SQLAlchemyError, ValueError):
        return None, None


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
