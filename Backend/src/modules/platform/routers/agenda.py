"""
Agenda de l'équipe éditrice : `/platform/rendez-vous`.

Lecture : `platform.agenda.read`. Écriture : `platform.agenda.write`.
Aucune donnée patient : voir `services/agenda.py`.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import LIMITE_PAGE_MAX, PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.core.database import get_master_db
from src.core.platform_database import get_platform_db
from src.modules.master.models import Societe
from src.modules.platform.dependencies import refuser_acces_client, require_platform_permissions
from src.modules.platform.models import RendezVousPlateforme, UtilisateurPlateforme
from src.modules.platform.schemas import (
    RendezVousPlateformeCreate,
    RendezVousPlateformeResponse,
    RendezVousPlateformeUpdate,
    StatutRendezVousPlateformeRequest,
)
from src.modules.platform.services.agenda import AgendaService

platform_agenda_router = APIRouter(prefix="/platform/rendez-vous", tags=["Platform · Agenda"])

LECTURE = require_platform_permissions("platform.agenda.read")
ECRITURE = require_platform_permissions("platform.agenda.write")


async def _noms(
    master_db: AsyncSession, platform_db: AsyncSession, rdvs: Iterable[RendezVousPlateforme]
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Noms des cabinets (base master) et des agents (console), en deux requêtes."""
    rdvs = list(rdvs)
    tenants = {r.tenant_id for r in rdvs if r.tenant_id}
    agents = {r.agent_id for r in rdvs if r.agent_id}
    noms_t: Dict[str, str] = {}
    noms_a: Dict[str, str] = {}
    if tenants:
        lignes = await master_db.execute(select(Societe.id, Societe.nom).where(Societe.id.in_(tenants)))
        for sid, nom in lignes.all():
            noms_t[str(sid)] = nom
    if agents:
        lignes = await platform_db.execute(
            select(UtilisateurPlateforme.id, UtilisateurPlateforme.prenom, UtilisateurPlateforme.nom).where(
                UtilisateurPlateforme.id.in_(agents)
            )
        )
        for uid, prenom, nom in lignes.all():
            noms_a[str(uid)] = f"{prenom} {nom}".strip()
    return noms_t, noms_a


def _vue(
    r: RendezVousPlateforme, noms_t: Dict[str, str], noms_a: Dict[str, str], prevenu: bool = False
) -> RendezVousPlateformeResponse:
    return RendezVousPlateformeResponse(
        id=r.id,
        titre=r.titre,
        type_rdv=r.type_rdv,
        statut=r.statut,
        debut=r.debut,
        duree_minutes=r.duree_minutes,
        fin=r.debut + timedelta(minutes=r.duree_minutes),
        tenant_id=r.tenant_id,
        tenant_nom=noms_t.get(str(r.tenant_id)) if r.tenant_id else None,
        prospect_nom=r.prospect_nom,
        contact_nom=r.contact_nom,
        contact_email=r.contact_email,
        contact_telephone=r.contact_telephone,
        lieu=r.lieu,
        lien_visio=r.lien_visio,
        agent_id=r.agent_id,
        agent_nom=noms_a.get(str(r.agent_id)) if r.agent_id else None,
        notes=r.notes,
        motif_annulation=r.motif_annulation,
        cree_par=r.cree_par,
        contact_prevenu=prevenu,
    )


async def _nom_cible(
    master_db: AsyncSession, tenant_id: Optional[uuid.UUID], prospect: Optional[str]
) -> Optional[str]:
    if tenant_id:
        return (await master_db.execute(select(Societe.nom).where(Societe.id == tenant_id))).scalar_one_or_none()
    return prospect


@platform_agenda_router.get(
    "", response_model=PaginatedResponse[RendezVousPlateformeResponse], summary="Rendez-vous de l'équipe"
)
async def lister(
    request: Request,
    du: Optional[datetime] = Query(None, description="Début de période (inclus)"),
    au: Optional[datetime] = Query(None, description="Fin de période (exclue)"),
    agent_id: Optional[uuid.UUID] = Query(None),
    tenant_id: Optional[uuid.UUID] = Query(None),
    statut: Optional[str] = Query(None),
    type_rdv: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    _: UtilisateurPlateforme = Depends(LECTURE),
):
    refuser_acces_client(request)
    rdvs, total = await AgendaService.lister(
        db, du=du, au=au, agent_id=agent_id, tenant_id=tenant_id, statut=statut, type_rdv=type_rdv,
        limit=limit, offset=(page - 1) * limit,
    )
    noms_t, noms_a = await _noms(master_db, db, rdvs)
    return paginate(
        items=[_vue(r, noms_t, noms_a) for r in rdvs],
        total_records=total,
        params=PaginationParams(page=page, limit=limit),
    )


@platform_agenda_router.post(
    "", response_model=APIResponse[RendezVousPlateformeResponse], status_code=201, summary="Planifier un rendez-vous"
)
async def creer(
    data: RendezVousPlateformeCreate,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(ECRITURE),
):
    """Refusé si l'agent a déjà un rendez-vous actif sur ce créneau (`RDV_CONFLIT_AGENT`)."""
    refuser_acces_client(request)
    donnees = data.model_dump(exclude={"notifier_contact"})
    if donnees.get("contact_email"):
        donnees["contact_email"] = str(donnees["contact_email"]).lower()
    nom = await _nom_cible(master_db, data.tenant_id, data.prospect_nom)
    rdv, prevenu = await AgendaService.creer(db, donnees, auteur, nom, data.notifier_contact)
    noms_t, noms_a = await _noms(master_db, db, [rdv])
    return APIResponse(message="Rendez-vous planifié.", data=_vue(rdv, noms_t, noms_a, prevenu))


@platform_agenda_router.get(
    "/{rdv_id}", response_model=APIResponse[RendezVousPlateformeResponse], summary="Détail d'un rendez-vous"
)
async def obtenir(
    rdv_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    _: UtilisateurPlateforme = Depends(LECTURE),
):
    refuser_acces_client(request)
    rdv = await AgendaService.obtenir(db, rdv_id)
    noms_t, noms_a = await _noms(master_db, db, [rdv])
    return APIResponse(data=_vue(rdv, noms_t, noms_a))


@platform_agenda_router.patch(
    "/{rdv_id}", response_model=APIResponse[RendezVousPlateformeResponse], summary="Modifier un rendez-vous"
)
async def modifier(
    rdv_id: uuid.UUID,
    data: RendezVousPlateformeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(ECRITURE),
):
    """Le contact est prévenu si l'horaire, la durée ou le lieu changent."""
    refuser_acces_client(request)
    changements = data.model_dump(exclude_unset=True, exclude={"notifier_contact"})
    if changements.get("contact_email"):
        changements["contact_email"] = str(changements["contact_email"]).lower()
    actuel = await AgendaService.obtenir(db, rdv_id)
    nom = await _nom_cible(
        master_db,
        changements.get("tenant_id", actuel.tenant_id),
        changements.get("prospect_nom", actuel.prospect_nom),
    )
    rdv, prevenu = await AgendaService.modifier(db, rdv_id, changements, auteur, nom, data.notifier_contact)
    noms_t, noms_a = await _noms(master_db, db, [rdv])
    return APIResponse(message="Rendez-vous modifié.", data=_vue(rdv, noms_t, noms_a, prevenu))


@platform_agenda_router.post(
    "/{rdv_id}/statut",
    response_model=APIResponse[RendezVousPlateformeResponse],
    summary="Confirmer, marquer effectué ou annuler",
)
async def changer_statut(
    rdv_id: uuid.UUID,
    data: StatutRendezVousPlateformeRequest,
    request: Request,
    db: AsyncSession = Depends(get_platform_db),
    master_db: AsyncSession = Depends(get_master_db),
    auteur: UtilisateurPlateforme = Depends(ECRITURE),
):
    """L'annulation exige un motif ; le contact en est prévenu."""
    refuser_acces_client(request)
    actuel = await AgendaService.obtenir(db, rdv_id)
    nom = await _nom_cible(master_db, actuel.tenant_id, actuel.prospect_nom)
    rdv, prevenu = await AgendaService.changer_statut(
        db, rdv_id, data.statut, data.motif, auteur, nom, data.notifier_contact
    )
    noms_t, noms_a = await _noms(master_db, db, [rdv])
    return APIResponse(message="Statut mis à jour.", data=_vue(rdv, noms_t, noms_a, prevenu))
