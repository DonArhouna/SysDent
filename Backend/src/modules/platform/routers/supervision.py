"""
Supervision, journal d'audit, santé et annonces — console PLATEFORME (Phase E).

Cinq groupes d'endpoints, tous en lecture ou en écriture d'administration :

- `/platform/stats/*`     : agrégats d'usage (jamais de contenu clinique)
- `/platform/audit`       : journal immuable, consultation + export CSV
- `/platform/sante`       : diagnostic réel des composants
- `/platform/annonces`    : messages affichés en bannière par l'app cliente
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.core.database import get_master_db
from src.core.platform_database import get_platform_db
from src.modules.platform.dependencies import require_platform_permissions
from src.modules.platform.models import Annonce, UtilisateurPlateforme
from src.modules.platform.schemas import (
    AnnonceCreate,
    AnnonceResponse,
    AuditEntryResponse,
    StatsGlobalesResponse,
    StatsTenantResponse,
)
from src.modules.platform.services.announcements import AnnouncementService
from src.modules.platform.services.health import HealthService
from src.modules.platform.services.journal import JournalService
from src.modules.platform.services.stats import StatsService

platform_supervision_router = APIRouter(
    prefix="/platform", tags=["Platform · Supervision & journal"]
)


def _vers_audit(entree) -> AuditEntryResponse:
    return AuditEntryResponse(
        id=entree.id,
        horodatage=entree.horodatage,
        acteur_email=entree.acteur_email,
        acteur_id=entree.acteur_id,
        action=entree.action,
        type_cible=entree.type_cible,
        cible_id=entree.cible_id,
        tenant_id=entree.tenant_id,
        ip_address=entree.ip_address,
        user_agent=entree.user_agent,
        motif=entree.motif,
        avant=entree.avant,
        apres=entree.apres,
    )


def _vers_annonce(annonce: Annonce) -> AnnonceResponse:
    return AnnonceResponse(
        id=annonce.id,
        titre=annonce.titre,
        message=annonce.message,
        type_annonce=annonce.type_annonce.value,
        debut=annonce.debut,
        fin=annonce.fin,
        active=annonce.active,
        plans_cibles=annonce.plans_cibles or [],
        tenants_cibles=annonce.tenants_cibles or [],
        cree_par=annonce.cree_par,
        cree_le=annonce.created_at,
    )


# ==============================================================================
# STATISTIQUES D'USAGE
# ==============================================================================


@platform_supervision_router.get(
    "/stats/globales",
    response_model=APIResponse[StatsGlobalesResponse],
    summary="Vue d'ensemble de la base installée",
)
async def stats_globales(
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.stats.read")),
):
    """
    Répartition par statut et par formule, croissance, cabinets inactifs, cabinets
    proches de leur quota.

    **Aucun contenu clinique** : uniquement des compteurs agrégés, lus dans
    `stats_tenant` (une ligne par cabinet et par jour). Aucun accès aux bases
    clients n'a lieu ici — le coût est borné par le nombre de cabinets.
    """
    vue = await StatsService.vue_globale(db)
    return APIResponse(data=StatsGlobalesResponse(**vue))


@platform_supervision_router.get(
    "/stats/tenants/{tenant_id}",
    response_model=APIResponse[StatsTenantResponse],
    summary="Statistiques d'un cabinet",
    responses={404: {"description": "Cabinet sans dossier plateforme"}},
)
async def stats_tenant(
    tenant_id: uuid.UUID,
    jours: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.stats.read")),
):
    """
    Compteurs du cabinet et série temporelle.

    Un cabinet sans relevé est renvoyé avec des compteurs à zéro et
    `releve=null` — pas d'erreur : un cabinet provisionné ce matin n'a pas encore
    eu son relevé nocturne, et « pas encore de données » n'est pas une panne.
    """
    from src.modules.platform.services.tenants import TenantService

    await TenantService.exiger_dossier(db, tenant_id)
    releve = await StatsService.dernier_releve(db, tenant_id)
    serie = await StatsService.serie(db, tenant_id, jours)

    return APIResponse(
        data=StatsTenantResponse(
            tenant_id=tenant_id,
            releve=None
            if releve is None
            else {
                "jour": releve.jour.isoformat(),
                "utilisateurs_actifs": releve.utilisateurs_actifs,
                "sites": releve.sites,
                "praticiens": releve.praticiens,
                "patients": releve.patients,
                "rendez_vous_periode": releve.rendez_vous_periode,
                "stockage_octets": releve.stockage_octets,
                "sms_envoyes": releve.sms_envoyes,
                "factures_creees": releve.factures_creees,
                "derniere_activite": releve.derniere_activite.isoformat()
                if releve.derniere_activite
                else None,
            },
            serie=[{"jour": s.jour.isoformat(), "patients": s.patients, "praticiens": s.praticiens} for s in serie],
        )
    )


# ==============================================================================
# JOURNAL D'AUDIT PLATEFORME
# ==============================================================================


@platform_supervision_router.get(
    "/audit",
    response_model=PaginatedResponse[AuditEntryResponse],
    summary="Consulter le journal d'audit plateforme",
)
async def lister_audit(
    acteur_email: Optional[str] = Query(None),
    tenant_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    type_cible: Optional[str] = Query(None),
    debut: Optional[datetime] = Query(None),
    fin: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.audit.read")),
):
    """
    Journal immuable, filtrable.

    **Aucune modification ni suppression n'est possible**, y compris par le code
    applicatif : la table porte des déclencheurs PostgreSQL qui refusent UPDATE,
    DELETE et TRUNCATE. Il n'existe donc volontairement aucun `PATCH` ni `DELETE`
    sur cette ressource — l'absence n'est pas un oubli, c'est la garantie.
    """
    filtres = {
        "acteur_email": acteur_email,
        "tenant_id": tenant_id,
        "action": action,
        "type_cible": type_cible,
        "debut": debut,
        "fin": fin,
    }
    params = PaginationParams(page=page, limit=limit)
    entrees = await JournalService.lister(
        db, filtres, limit=params.limit, offset=params.offset
    )
    total = await JournalService.compter(db, filtres)
    return paginate(
        items=[_vers_audit(e) for e in entrees], total_records=total, params=params
    )


@platform_supervision_router.get(
    "/audit/export",
    summary="Exporter le journal d'audit en CSV",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "Fichier CSV"}},
)
async def exporter_audit(
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.audit.export")
    ),
    acteur_email: Optional[str] = Query(None),
    tenant_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    debut: Optional[datetime] = Query(None),
    fin: Optional[datetime] = Query(None),
):
    """
    Export CSV (séparateur `;`, tout cité) — ouvrable directement dans un tableur
    francophone.

    Réservé à l'Auditeur et au Super Admin : l'export permet d'extraire le journal
    hors du système, ce qui est un acte de sortie de données, pas une simple
    consultation.
    """
    contenu = await JournalService.export_csv(
        db,
        {
            "acteur_email": acteur_email,
            "tenant_id": tenant_id,
            "action": action,
            "debut": debut,
            "fin": fin,
        },
    )
    await JournalService.journaliser(
        db,
        action="PLATFORM_AUDIT_EXPORTE",
        type_cible="JOURNAL",
        cible_id="journal_audit",
        acteur_email=auteur.email,
        apres={"filtres": "appliques"},
    )
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response(
        content=contenu,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="audit-plateforme-{horodatage}.csv"'
        },
    )


# ==============================================================================
# SANTÉ
# ==============================================================================


@platform_supervision_router.get(
    "/sante",
    response_model=APIResponse[dict],
    summary="État de santé de la plateforme",
)
async def sante(
    db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.health.read")),
):
    """
    Diagnostic RÉELLEMENT exécuté : base plateforme, base master, bases clients,
    divergence de schéma, catalogue commercial, jobs.

    Le statut global est `ok` ou `degrade` — jamais de 500 justifiant le statut :
    une page de santé qui renvoie une erreur ne dit pas *quel* composant est en
    panne. Les messages techniques sont tronqués : une trace SQL complète peut
    contenir la chaîne de connexion, donc un mot de passe.
    """
    return APIResponse(data=await HealthService.global_(db, master_db))


# ==============================================================================
# ANNONCES
# ==============================================================================


@platform_supervision_router.get(
    "/annonces",
    response_model=APIResponse[List[AnnonceResponse]],
    summary="Lister les annonces",
)
async def lister_annonces(
    actives_seulement: bool = Query(False),
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(require_platform_permissions("platform.announcements.read")),
):
    """Toutes les annonces publiées, pour l'écran d'administration."""
    annonces = await AnnouncementService.lister(db, actives_seulement)
    return APIResponse(data=[_vers_annonce(a) for a in annonces])


@platform_supervision_router.post(
    "/annonces",
    response_model=APIResponse[AnnonceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Publier une annonce",
)
async def publier_annonce(
    data: AnnonceCreate,
    db: AsyncSession = Depends(get_platform_db),
    auteur: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.announcements.write")
    ),
):
    """
    Publie une bannière affichée par l'application cliente.

    Ciblage : `plans_cibles` (codes de formules) et/ou `tenants_cibles` (UUID) ;
    les deux vides = tous les cabinets. Une annonce peut viser une formule
    entière (« maintenance dimanche 02:00 ») ou un client précis
    (« incident de facturation cabinet X »).
    """
    annonce = await AnnouncementService.publier(
        db,
        titre=data.titre,
        message=data.message,
        type_annonce=data.type_annonce,
        debut=data.debut,
        fin=data.fin,
        plans_cibles=data.plans_cibles,
        tenants_cibles=data.tenants_cibles,
        auteur=auteur.email,
    )
    await JournalService.journaliser(
        db,
        action="PLATFORM_ANNONCE_PUBLIEE",
        type_cible="ANNONCE",
        cible_id=str(annonce.id),
        acteur_email=auteur.email,
        apres={
            "type_annonce": data.type_annonce,
            "plans_cibles": data.plans_cibles,
            "nb_tenants_cibles": len(data.tenants_cibles or []),
        },
    )
    return APIResponse(message="Annonce publiée.", data=_vers_annonce(annonce))


@platform_supervision_router.delete(
    "/annonces/{annonce_id}",
    response_model=APIResponse[AnnonceResponse],
    summary="Désactiver une annonce",
)
async def desactiver_annonce(
    annonce_id: uuid.UUID,
    db: AsyncSession = Depends(get_platform_db),
    _: UtilisateurPlateforme = Depends(
        require_platform_permissions("platform.announcements.write")
    ),
):
    """
    Arrête l'affichage de la bannière.

    **Désactivation, pas suppression** : une maintenance passée doit rester
    consultable (« qui avait été prévenu, et depuis quand ? »), et une annonce
    supprimée serait absente du journal alors qu'elle a été affichée.
    """
    annonce = await AnnouncementService.desactiver(db, annonce_id)
    return APIResponse(message="Annonce désactivée.", data=_vers_annonce(annonce))