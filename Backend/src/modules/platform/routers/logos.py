"""
Logo d'un cabinet.

- `POST/DELETE /platform/tenants/{id}/logo` : console, `platform.tenants.update` ;
- `GET /logos/{id}` : PUBLIC. Une balise `<img>` n'envoie pas de jeton, et un
  logo n'est pas une donnée sensible. La réponse est verrouillée : type imposé,
  `nosniff`, politique de contenu vide (rien ne s'exécute même si le fichier
  était piégé).
"""

import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.schemas import APIResponse
from src.core.database import get_master_db
from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import (
    client_ip,
    refuser_acces_client,
    require_platform_permissions,
)
from src.modules.platform.models import UtilisateurPlateforme
from src.modules.platform.services.journal import JournalService
from src.modules.platform.services.logos import TAILLE_MAX, LogoService

platform_logos_router = APIRouter(prefix="/platform/tenants", tags=["Platform · Tenants (cycle de vie)"])
public_logos_router = APIRouter(prefix="/logos", tags=["Logos"])

MODIFIER = require_platform_permissions("platform.tenants.update")


@platform_logos_router.post(
    "/{tenant_id}/logo",
    response_model=APIResponse[dict],
    summary="Envoyer le logo d'un cabinet (PNG, JPEG ou WebP, 512 Ko max)",
    responses={422: {"description": "Format non accepté, fichier vide ou trop lourd"}},
)
async def envoyer_logo(
    tenant_id: uuid.UUID,
    request: Request,
    fichier: UploadFile = File(..., description="PNG, JPEG ou WebP, 512 Ko au plus"),
    master_db: AsyncSession = Depends(get_master_db),
    platform_db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(MODIFIER),
):
    refuser_acces_client(request)
    # Lecture bornée : un fichier énorme n'est jamais chargé en entier en mémoire.
    contenu = await fichier.read(TAILLE_MAX + 1)
    if len(contenu) > TAILLE_MAX:
        raise BusinessRuleViolationException("Logo trop lourd : 512 Ko maximum.", code="LOGO_TROP_LOURD")
    url = await LogoService.enregistrer(master_db, tenant_id, contenu)
    await JournalService.journaliser(
        platform_db, action="PLATFORM_LOGO_MODIFIE", type_cible="TENANT", cible_id=str(tenant_id),
        tenant_id=tenant_id, acteur_email=auteur.email, acteur_id=auteur.id,
        apres={"taille_octets": len(contenu)}, ip_address=client_ip(request),
    )
    await platform_db.commit()
    return APIResponse(message="Logo enregistré.", data={"logo_url": url})


@platform_logos_router.delete("/{tenant_id}/logo", response_model=APIResponse[None], summary="Retirer le logo")
async def supprimer_logo(
    tenant_id: uuid.UUID,
    request: Request,
    master_db: AsyncSession = Depends(get_master_db),
    platform_db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(MODIFIER),
):
    refuser_acces_client(request)
    await LogoService.supprimer(master_db, tenant_id)
    await JournalService.journaliser(
        platform_db, action="PLATFORM_LOGO_RETIRE", type_cible="TENANT", cible_id=str(tenant_id),
        tenant_id=tenant_id, acteur_email=auteur.email, acteur_id=auteur.id, ip_address=client_ip(request),
    )
    await platform_db.commit()
    return APIResponse(message="Logo retiré.", data=None)


@public_logos_router.get("/{societe_id}", summary="Logo d'un cabinet (public)", response_class=Response)
async def lire_logo(societe_id: uuid.UUID, master_db: AsyncSession = Depends(get_master_db)):
    logo = await LogoService.lire(master_db, societe_id)
    if logo is None:
        raise EntityNotFoundException("Logo", str(societe_id))
    contenu, mime = logo
    return Response(
        content=contenu,
        media_type=mime,
        headers={
            # L'adresse change à chaque envoi (`?v=`) : on peut cacher longtemps.
            "Cache-Control": "public, max-age=604800, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )
