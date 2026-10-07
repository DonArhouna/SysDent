"""Routes du module Utilisateurs — l'administration des comptes du cabinet."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import LIMITE_PAGE_MAX, PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.modules.auth.dependencies import (
    get_current_tenant_id,
    get_current_user,
    get_master_db,
    get_tenant_db,
    require_permissions,
)
from src.modules.tenants.models import Utilisateur
from src.modules.utilisateurs.schemas import (
    MotDePasseTemporaireResponse,
    SessionUtilisateurResponse,
    UtilisateurCreate,
    UtilisateurDetailResponse,
    UtilisateurResponse,
    UtilisateurUpdate,
)
from src.modules.utilisateurs.services import UtilisateurService

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs & rôles"])


def _serialiser(u: Utilisateur, noms_cabinet: dict | None = None) -> UtilisateurResponse:
    profil = u.praticien_profil
    return UtilisateurResponse(
        id=u.id,
        email=u.email,
        prenom=u.prenom,
        nom=u.nom,
        role=u.role.nom if u.role else "—",
        actif=u.actif,
        telephone=u.telephone,
        cabinet_id=u.cabinet_id,
        cabinet_nom=(noms_cabinet or {}).get(str(u.cabinet_id)) if u.cabinet_id else None,
        deux_facteurs=bool(u.deux_facteurs),
        dernier_login=u.dernier_login,
        a_profil_professionnel=profil is not None,
        numero_ordre=profil.numero_ordre if profil else None,
        created_at=u.created_at if hasattr(u, "created_at") else None,
    )


@router.get("", response_model=PaginatedResponse[UtilisateurResponse])
async def lister_utilisateurs(
    request: Request,
    q: str | None = Query(None, description="Recherche sur nom, prénom, email"),
    role: str | None = Query(None, description="Filtrer par nom de rôle"),
    actif: bool | None = Query(None, description="Filtrer par état du compte"),
    cabinet_id: uuid.UUID | None = Query(None, description="Filtrer par site"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("ADMIN:READ")),
):
    """
    Comptes du cabinet.

    Le nom du site est résolu en une requête pour l'ensemble de la page : le
    frontend affiche «/site» dans la liste, et le faire ligne par ligne
    reviendrait à doubler le nombre d'allers-retours.
    """
    lignes, total = await UtilisateurService.lister(
        db,
        q=q,
        role=role,
        actif=actif,
        cabinet_id=cabinet_id,
        offset=(page - 1) * limit,
        limit=limit,
    )
    noms = await _noms_cabinet(db, {u.cabinet_id for u in lignes if u.cabinet_id})
    return paginate(
        [_serialiser(u, noms) for u in lignes],
        total,
        PaginationParams(page=page, limit=limit),
    )


async def _noms_cabinet(db: AsyncSession, ids: set) -> dict:
    if not ids:
        return {}
    from sqlalchemy import select

    from src.modules.tenants.models import Cabinet

    lignes = (
        await db.execute(select(Cabinet.id, Cabinet.nom).where(Cabinet.id.in_(ids)))
    ).all()
    return {str(cid): nom for cid, nom in lignes}


@router.post("", response_model=APIResponse[UtilisateurResponse], status_code=status.HTTP_201_CREATED)
async def creer_utilisateur(
    data: UtilisateurCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    master_db: AsyncSession = Depends(get_master_db),
    tenant_id: str = Depends(get_current_tenant_id),
    auteur: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ADMIN:CREATE")),
):
    """
    Crée un compte **et le rend connectable**.

    L'écriture de la ligne de routage en base master est indissociable de la
    création : un compte sans elle existe mais ne peut jamais se connecter. Si
    elle échoue, la création échoue — on ne laisse pas d'adresse brûlée en base.
    """
    # L'identifiant du cabinet vient de la session authentifiee, jamais du
    # corps de la requete : un client ne doit pas pouvoir creer de compte dans
    # un autre cabinet.
    societe_id = uuid.UUID(str(tenant_id))
    u = await UtilisateurService.creer(
        db,
        master_db=master_db,
        societe_id=societe_id,
        email=data.email,
        mot_de_passe=data.mot_de_passe,
        prenom=data.prenom,
        nom=data.nom,
        role=data.role,
        telephone=data.telephone,
        cabinet_id=data.cabinet_id,
        auteur=auteur,
    )
    noms = await _noms_cabinet(db, {u.cabinet_id} if u.cabinet_id else set())
    return APIResponse(
        message=f"Compte créé pour {u.prenom} {u.nom}.", data=_serialiser(u, noms)
    )



@router.get("/{utilisateur_id}", response_model=APIResponse[UtilisateurDetailResponse])
async def obtenir_utilisateur(
    utilisateur_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("ADMIN:READ")),
):
    """Fiche d'un compte, avec ses sessions ouvertes."""
    u = await UtilisateurService._charger(db, utilisateur_id)
    noms = await _noms_cabinet(db, {u.cabinet_id} if u.cabinet_id else set())
    sessions = await UtilisateurService.lister_sessions(db, utilisateur_id)
    maintenant = datetime.now(timezone.utc)
    detail = UtilisateurDetailResponse(
        **_serialiser(u, noms).model_dump(),
        sessions=[
            SessionUtilisateurResponse(
                id=s.id,
                ip_address=s.ip_address,
                user_agent=s.user_agent,
                est_revoque=s.est_revoque,
                expire_at=s.expire_at,
                derniere_activite=s.derniere_activite,
                expiree=s.expire_at < maintenant,
            )
            for s in sessions
        ],
    )
    return APIResponse(data=detail)


@router.patch("/{utilisateur_id}", response_model=APIResponse[UtilisateurResponse])
async def modifier_utilisateur(
    utilisateur_id: uuid.UUID,
    data: UtilisateurUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    auteur: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ADMIN:UPDATE")),
):
    """
    Modifie profil, rôle, site ou état.

    Trois refus sont non négociables : se désactiver soi-même, retirer le rôle
    d'administration au dernier administrateur, et désactiver le dernier
    administrateur. Un cabinet qui se verrouille n'a personne pour le rouvrir.
    """
    u = await UtilisateurService.modifier(
        db,
        utilisateur_id,
        prenom=data.prenom,
        nom=data.nom,
        telephone=data.telephone,
        role=data.role,
        actif=data.actif,
        cabinet_id=data.cabinet_id,
        auteur=auteur,
    )
    noms = await _noms_cabinet(db, {u.cabinet_id} if u.cabinet_id else set())
    return APIResponse(data=_serialiser(u, noms))


@router.post(
    "/{utilisateur_id}/mot-de-passe",
    response_model=APIResponse[MotDePasseTemporaireResponse],
)
async def reinitialiser_mot_de_passe(
    utilisateur_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("ADMIN:UPDATE")),
):
    """
    Réinitialise le mot de passe et rend un mot de passe temporaire, une fois.

    Les sessions ouvertes sont révoquées : quelqu'un pouvait être connecté avec
    l'ancien mot de passe, et le changer ne doit pas laisser cette session
    valide.
    """
    temporaire = await UtilisateurService.reinitialiser_mot_de_passe(db, utilisateur_id)
    return APIResponse(data=MotDePasseTemporaireResponse(temporaire=temporaire))


@router.delete(
    "/{utilisateur_id}",
    response_model=APIResponse[UtilisateurResponse],
    status_code=status.HTTP_200_OK,
)
async def desactiver_utilisateur(
    utilisateur_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    auteur: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ADMIN:DELETE")),
):
    """
    **Désactive** un compte — ne le supprime jamais.

    Une consultation, un acte, une clôture de caisse le référencent : supprimer
    la ligne effacerait l'auteur d'un acte médical. Désactiver ferme l'accès,
    révoque les sessions, et conserve la preuve.
    """
    u = await UtilisateurService.modifier(db, utilisateur_id, actif=False, auteur=auteur)
    noms = await _noms_cabinet(db, {u.cabinet_id} if u.cabinet_id else set())
    return APIResponse(
        message="Compte désactivé. Les données qu'il a produites sont conservées.",
        data=_serialiser(u, noms),
    )


@router.get(
    "/{utilisateur_id}/sessions",
    response_model=PaginatedResponse[SessionUtilisateurResponse],
)
async def lister_sessions(
    utilisateur_id: uuid.UUID,
    actives_seulement: bool = Query(False),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("ADMIN:READ")),
):
    """Sessions ouvertes d'un compte — pour voir qui est connecté, et terminer."""
    sessions = await UtilisateurService.lister_sessions(
        db, utilisateur_id, actives_seulement=actives_seulement
    )
    maintenant = datetime.now(timezone.utc)
    return paginate(
        [
            SessionUtilisateurResponse(
                id=s.id,
                ip_address=s.ip_address,
                user_agent=s.user_agent,
                est_revoque=s.est_revoque,
                expire_at=s.expire_at,
                derniere_activite=s.derniere_activite,
                expiree=s.expire_at < maintenant,
            )
            for s in sessions
        ],
        len(sessions),
        PaginationParams(page=1, limit=LIMITE_PAGE_MAX),
    )


@router.delete("/{utilisateur_id}/sessions", status_code=status.HTTP_200_OK)
async def revoquer_sessions(
    utilisateur_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("ADMIN:UPDATE")),
):
    """Termine toutes les sessions ouvertes d'un compte."""
    nombre = await UtilisateurService.revoquer_sessions(db, utilisateur_id)
    return APIResponse(message=f"{nombre} session(s) terminée(s).", data={"revoquees": nombre})
