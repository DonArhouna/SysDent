"""
Onboarding public (Phase F) — routes PUBLIQUES, hors `/platform`.

Volontairement hors du préfixe `/platform` et du groupe « Platform » : ces
routes n'acceptent aucun jeton et n'exposent aucune donnée de gestion. Les
regrouper avec la console ferait croire qu'un jeton plateforme est nécessaire.

Groupes OpenAPI : « Onboarding public ». Séparé de « Platform » pour que la
console puisse être déployée avec un périmètre réseau différent.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.schemas import APIResponse
from src.core.database import get_master_db
from src.core.platform_database import get_platform_db
from src.core.rate_limit import RateLimiter
from src.modules.platform.schemas import (
    InscriptionCreate,
    InscriptionResponse,
    OnboardingEtatResponse,
    VerificationEmailRequest,
)
from src.modules.platform.services.onboarding import OnboardingService

onboarding_router = APIRouter(prefix="/onboarding", tags=["Onboarding public"])

#: Limitation de débit de l'inscription. Un robot qui tente 1000 adresses doit
#: être ralenti bien avant que le provisionnement (création d'une base
#: PostgreSQL par demande) ne devienne un déni de service.
limiteur_inscription = RateLimiter(max_tentatives=5, fenetre_secondes=3600)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@onboarding_router.post(
    "/inscription",
    response_model=APIResponse[InscriptionResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer un cabinet en essai",
    responses={
        409: {
            "description": (
                "Inscription refusée. Message volontairement identique que "
                "l'adresse existe déjà ou non — ni de fuite d'information."
            )
        },
        429: {"description": "Trop de tentatives depuis cette adresse"},
        503: {"description": "Inscriptions temporairement désactivées"},
    },
)
async def inscrire(
    data: InscriptionCreate,
    request: Request,
    master_db: AsyncSession = Depends(get_master_db),
    platform_db: AsyncSession = Depends(get_platform_db),
):
    """
    Auto-inscription : crée un cabinet **en essai** et son administrateur, par le
    service de provisionnement de la console.

    Le cabinet est réellement provisionné (base, schéma, rôles, nomenclature,
    abonnement) — seule la connexion est verrouillée tant que l'e-mail n'est pas
    vérifié. Un e-mail de vérification est envoyé ; en développement, il est
    écrit sur la console par l'implémentation « log » de l'envoi de messages.

    **Aucune information sur l'existence d'un cabinet ou d'un compte n'est
    renvoyée** : un e-mail déjà utilisé, un nom déjà pris et une erreur de
    provisionnement produisent le même statut et le même texte.
    """
    limiteur_inscription.tenter(_ip(request) or "inconnu")

    resultat = await OnboardingService.inscrire(
        master_db,
        platform_db,
        nom_cabinet=data.nom_cabinet,
        email=data.email,
        mot_de_passe=data.mot_de_passe,
        prenom=data.admin_prenom,
        nom=data.admin_nom,
        telephone=data.telephone,
        ville=data.ville,
        pays=data.pays,
        plan_code=data.plan_code,
        jours_essai=data.jours_essai,
        honeypot=data.site_web_trap,
        ip_address=_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await master_db.commit()
    await platform_db.commit()

    return APIResponse(
        message=(
            "Inscription enregistrée. Consultez votre boîte mail pour vérifier "
            "votre adresse et activer votre espace."
        ),
        data=InscriptionResponse(**resultat),
    )


@onboarding_router.post(
    "/verification-email",
    response_model=APIResponse[dict],
    summary="Vérifier l'adresse e-mail",
    responses={400: {"description": "Jeton invalide, expiré ou déjà utilisé"}},
)
async def verifier_email(
    data: VerificationEmailRequest,
    platform_db: AsyncSession = Depends(get_platform_db),
):
    """
    Valide le jeton reçu par e-mail et déverrouille la connexion du cabinet.

    Le jeton est à **usage unique** et stocké haché : une fuite de la base ne
    permet ni de vérifier une adresse ni de prendre la main sur un cabinet. Un
    jeton déjà utilisé répond exactement comme un jeton inexistant.
    """
    resultat = await OnboardingService.verifier_email(platform_db, data.jeton)
    await platform_db.commit()
    return APIResponse(
        message="Adresse vérifiée. Votre espace est actif.", data=resultat
    )


@onboarding_router.get(
    "/etat",
    response_model=APIResponse[OnboardingEtatResponse],
    summary="État de démarrage d'un cabinet (checklist)",
)
async def etat(
    tenant_id: str = Query(..., description="Identifiant du cabinet"),
    platform_db: AsyncSession = Depends(get_platform_db),
):
    """
    Checklist de démarrage : sept étapes, celles qui sont faites et celles qui
    restent, chacune avec une consigne exploitable.

    Alimentée par des **compteurs** (`sites`, `praticiens`, `actes`…), jamais par
    une lecture nominative : cet endpoint ne doit pas devenir un chemin de
    contournement vers les données d'un cabinet.

    Le `tenant_id` est demandé en paramètre explicite : cette route est publique
    et n'a pas de jeton. Les valeurs qu'elle renvoie sont déjà agrégées et
    non sensibles ; elle est à protéger par un contrôle d'accès réseau (VOD /
    IP) si l'exposition publique n'est pas souhaitable.
    """
    import uuid as _uuid

    try:
        identifiant = _uuid.UUID(tenant_id)
    except ValueError:
        from src.core.exceptions import AppException

        raise AppException("Identifiant de cabinet invalide.", code="TENANT_ID_INVALIDE", status_code=422)

    return APIResponse(data=OnboardingEtatResponse(**await OnboardingService.etat_onboarding(platform_db, identifiant)))