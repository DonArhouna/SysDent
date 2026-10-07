"""Routes de la session de caisse : ouverture, encaissement, clôture, journal."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import LIMITE_PAGE_MAX, PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.modules.auth.dependencies import (
    get_current_user,
    get_tenant_db,
    require_permissions,
)
from src.modules.caisse.schemas import (
    ClotureCaisseCreate,
    OuvertureCaisseCreate,
    PaiementCaisseResponse,
    SessionCaisseResponse,
)
from src.modules.caisse.services import CaisseService
from src.modules.tenants.models import (
    ModePaiementEnum,
    SessionCaisse,
    StatutSessionCaisseEnum,
    Utilisateur,
)

router = APIRouter(prefix="/caisse", tags=["Caisse & Clôture"])


def _serialiser(session: SessionCaisse) -> SessionCaisseResponse:
    return SessionCaisseResponse(
        id=session.id,
        numero=session.numero,
        cabinet_id=session.cabinet_id,
        statut=session.statut,
        ouverte_le=session.ouverte_le,
        ouverte_par=session.ouverte_par_email,
        ouverture_especes=session.ouverture_especes,
        close_le=session.close_le,
        close_par=session.close_par_email,
        especes_comptees=session.especes_comptees,
        especes_attendues=session.especes_attendues,
        ecart_especes=session.ecart_especes,
        total_especes=session.total_especes,
        total_carte=session.total_carte,
        total_virement=session.total_virement,
        total_mobile_money=session.total_mobile_money,
        total_cheque=session.total_cheque,
        total_assurance=session.total_assurance,
        total_encaisse=session.total_encaisse,
        nb_paiements=session.nb_paiements,
        motif_ecart=session.motif_ecart,
        notes=session.notes,
    )


@router.get("/sessions", response_model=APIResponse[list[SessionCaisseResponse]])
async def lister_sessions(
    cabinet_id: uuid.UUID = Query(..., description="Site dont on veut les sessions"),
    statut: StatutSessionCaisseEnum | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Historique des sessions de caisse, de la plus récente à la plus ancienne."""
    sessions = await CaisseService.lister(
        db, cabinet_id=cabinet_id, statut=statut, limit=limit
    )
    return APIResponse(data=[_serialiser(s) for s in sessions])


@router.get("/session-courante", response_model=APIResponse[SessionCaisseResponse | None])
async def session_courante(
    cabinet_id: uuid.UUID = Query(..., description="Site concerné"),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """
    Session ouverte, ou `null` s'il n'y en a pas.

    L'écran d'accueil du caissier s'appuie dessus : il affiche « caisse
    fermée » et le montant du dernier dépôt tant qu'aucune session n'est ouverte.
    """
    session = await CaisseService.session_ouverte(db, cabinet_id)
    return APIResponse(data=_serialiser(session) if session else None)


@router.post(
    "/sessions", response_model=APIResponse[SessionCaisseResponse], status_code=201
)
async def ouvrir_session(
    data: OuvertureCaisseCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """
    Ouvre la session de caisse avec le dépôt d'espèces du tiroir.

    Le dépôt déclaré par le caissier est sa responsabilité personnelle : ce n'est
    pas de l'argent du cabinet. C'est pour cela qu'il est memorandum du début et
    de la fin, et non compté dans les recettes.
    """
    session = await CaisseService.ouvrir(
        db,
        cabinet_id=data.cabinet_id,
        ouverture_especes=data.ouverture_especes,
        auteur=current_user,
        notes=data.notes,
    )
    return APIResponse(
        message=f"Session {session.numero} ouverte.", data=_serialiser(session)
    )


@router.post(
    "/sessions/{session_id}/cloture",
    response_model=APIResponse[SessionCaisseResponse],
)
async def cloturer_session(
    session_id: uuid.UUID,
    data: ClotureCaisseCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """
    Clôture la session et fige ses totaux.

    Les totaux par mode sont recopiés dans la session à cet instant : un
    encaissement ultérieur ne réécrira pas cette journée. L'écart d'espèces est
    calculé et conservé, avec son motif s'il y en a un.
    """
    session = await CaisseService.cloturer(
        db,
        session_id,
        especes_comptees=data.especes_comptees,
        auteur=current_user,
        motif_ecart=data.motif_ecart,
        notes=data.notes,
    )
    return APIResponse(
        message=(
            f"Session {session.numero} close : "
            f"{session.nb_paiements} encaissement(s), "
            f"écart {session.ecart_especes} FCFA."
        ),
        data=_serialiser(session),
    )


@router.get(
    "/sessions/{session_id}/paiements",
    response_model=PaginatedResponse[PaiementCaisseResponse],
)
async def paiements_de_la_session(
    session_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Détail des encaissements d'une session, avec l'auteur de chacun."""
    paiements = await CaisseService.paiements(db, session_id, limit=limit)
    items = [
        PaiementCaisseResponse(
            id=p.id,
            facture_id=p.facture_id,
            recu_numero=p.recu_numero,
            montant=p.montant,
            mode=p.mode,
            reference=p.reference,
            auteur=p.enregistre_par_email,
            date_paiement=p.date_paiement,
        )
        for p in paiements
    ]
    return paginate(items, len(items), PaginationParams(page=page, limit=limit))


@router.get(
    "/paiements-hors-session", response_model=PaginatedResponse[PaiementCaisseResponse]
)
async def paiements_hors_session(
    cabinet_id: uuid.UUID = Query(..., description="Site concerné"),
    limit: int = Query(100, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """
    Encaissements qui n'appartiennent à aucune session de caisse.

    Ce sont les paiements antérieurs au déploiement des sessions. Les lister
    n'est pas les dissimuler : une somme qui n'entre dans aucune clôture est une
    somme dont personne ne répond, et c'est exactement le genre d'écart qu'une
    clôture doit faire apparaître.
    """
    paiements = await CaisseService.paiements_hors_session(
        db, cabinet_id=cabinet_id, limit=limit
    )
    items = [
        PaiementCaisseResponse(
            id=p.id,
            facture_id=p.facture_id,
            recu_numero=p.recu_numero,
            montant=p.montant,
            mode=p.mode,
            reference=p.reference,
            auteur=p.enregistre_par_email,
            date_paiement=p.date_paiement,
        )
        for p in paiements
    ]
    return paginate(items, len(items), PaginationParams(page=1, limit=limit))
