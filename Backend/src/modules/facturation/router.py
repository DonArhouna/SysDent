"""
Routes API du module Facturation & Caisse (D2C).

Toutes les routes sont authentifiées, scopées au cabinet du JWT et protégées
par permission RBAC `FACTURATION:*`.

Le contrat avec le module Consultations tient en une ligne : la facture d'une
consultation est générée depuis `GET /consultations/{id}/total`, le montant
n'est jamais ressaisi (RG07).
"""

import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.modules.auth.dependencies import (
    get_current_user,
    get_tenant_db,
    require_permissions,
)
from src.modules.facturation.schemas import (
    DevisCreate,
    DevisResponse,
    DevisStatutUpdate,
    EcheanceResponse,
    FactureConsultationCreate,
    FactureLibreCreate,
    FactureResponse,
    LigneDevisResponse,
    LigneFactureResponse,
    PaiementCreate,
    PaiementResponse,
    PlanEchelonnementCreate,
    PlanEchelonnementResponse,
)
from src.modules.facturation.services import (
    DevisService,
    EchelonnementService,
    FactureService,
    PaiementService,
)
from src.modules.tenants.models import Utilisateur

router = APIRouter(prefix="/factures", tags=["Facturation & Caisse"])
devis_router = APIRouter(prefix="/devis", tags=["Facturation & Devis"])


def _ctx(request: Request):
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# Marqueur « paramètre non fourni » : distinct de `None`, qui est une valeur
# métier légitime (un paiement sans échéance).
_NON_FOURNI = object()


# ==============================================================================
# SÉRIALISATION
# ==============================================================================

def _ligne_vers_reponse(ligne) -> LigneFactureResponse:
    return LigneFactureResponse(
        id=ligne.id,
        acte_realise_id=ligne.acte_realise_id,
        designation=ligne.designation,
        quantite=ligne.quantite,
        prix_unitaire=ligne.prix_unitaire,
        montant=ligne.montant,
    )


def _paiement_vers_reponse(paiement, echeance_id=_NON_FOURNI) -> PaiementResponse:
    """
    Sérialise un paiement.

    `echeance_id` est passé explicitement depuis la requête d'encaissement :
    un paiement FRAÎCHEMENT créé n'a pas sa relation échéance chargée, et la
    lire déclencherait un lazy-load interdit (MissingGreenlet). Les paiements
    relus via `_charger` ont la relation peuplée par selectinload — le défaut
    suffit alors.
    """
    if echeance_id is _NON_FOURNI:
        echeance_id = paiement.echeance.id if paiement.echeance else None
    return PaiementResponse(
        id=paiement.id,
        facture_id=paiement.facture_id,
        montant=paiement.montant,
        mode=paiement.mode,
        reference=paiement.reference,
        recu_numero=paiement.recu_numero,
        date_paiement=paiement.date_paiement,
        echeance_id=echeance_id,
    )


def _facture_vers_reponse(facture) -> FactureResponse:
    return FactureResponse(
        id=facture.id,
        numero=facture.numero,
        patient_id=facture.patient_id,
        cabinet_id=facture.cabinet_id,
        consultation_id=facture.consultation_id,
        praticien_id=facture.praticien_id,
        montant_total=facture.montant_total,
        montant_tva=facture.montant_tva,
        montant_paye=facture.montant_paye,
        montant_restant=facture.montant_restant,
        statut=facture.statut,
        date_emission=facture.date_emission,
        date_echeance=facture.date_echeance,
        lignes=[_ligne_vers_reponse(l) for l in facture.lignes],
        paiements=[_paiement_vers_reponse(p) for p in facture.paiements],
    )


def _echeance_vers_reponse(echeance) -> EcheanceResponse:
    return EcheanceResponse(
        id=echeance.id,
        numero=echeance.numero,
        montant_prevu=echeance.montant_prevu,
        montant_paye=echeance.montant_paye,
        date_prevue=echeance.date_prevue,
        date_paiement=echeance.date_paiement,
        paiement_id=echeance.paiement_id,
        statut=echeance.statut,
    )


def _plan_vers_reponse(plan) -> PlanEchelonnementResponse:
    return PlanEchelonnementResponse(
        id=plan.id,
        facture_id=plan.facture_id,
        montant_total=plan.montant_total,
        nombre_echeances=plan.nombre_echeances,
        date_debut=plan.date_debut,
        frequence=plan.frequence,
        notes=plan.notes,
        actif=plan.actif,
        echeances=[_echeance_vers_reponse(e) for e in plan.echeances],
    )


def _ligne_devis_vers_reponse(ligne) -> LigneDevisResponse:
    return LigneDevisResponse(
        id=ligne.id,
        acte_id=ligne.acte_id,
        designation=ligne.designation,
        dent_numero=ligne.dent_numero,
        quantite=ligne.quantite,
        prix_unitaire=ligne.prix_unitaire,
        montant=ligne.montant,
    )


def _devis_vers_reponse(devis) -> DevisResponse:
    return DevisResponse(
        id=devis.id,
        numero=devis.numero,
        patient_id=devis.patient_id,
        praticien_id=devis.praticien_id,
        cabinet_id=devis.cabinet_id,
        montant_total=devis.montant_total,
        statut=devis.statut,
        date_validite=devis.date_validite,
        signature_patient=devis.signature_patient,
        date_signature=devis.date_signature,
        notes=devis.notes,
        facture_id=devis.facture_id,
        lignes=[_ligne_devis_vers_reponse(l) for l in devis.lignes],
    )


# ==============================================================================
# FACTURES
# ==============================================================================

@router.post(
    "/consultation/{consultation_id}",
    response_model=APIResponse[FactureResponse],
    status_code=status.HTTP_201_CREATED,
)
async def facturer_consultation(
    consultation_id: uuid.UUID,
    data: FactureConsultationCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """
    Émet la facture d'une consultation terminée depuis ses actes réalisés.

    Les lignes sont importées des actes, le total est recalculé (RG07) :
    le montant n'est jamais fourni par le client. Une consultation déjà
    facturée est refusée (anti-doublon).
    """
    ip, ua = _ctx(request)
    facture_creee = await FactureService.emettre_depuis_consultation(
        db, consultation_id, data, current_user, client_ip=ip, user_agent=ua
    )
    # Rechargement complet (lignes + paiements) : un objet fraîchement créé n'a
    # pas ses collections chargées, et les lire déclencherait un lazy-load
    # interdit en contexte async (MissingGreenlet).
    facture = await FactureService.obtenir(db, facture_creee.id)
    return APIResponse(
        message=f"Facture {facture.numero} émise.", data=_facture_vers_reponse(facture)
    )


@router.post(
    "", response_model=APIResponse[FactureResponse], status_code=status.HTTP_201_CREATED
)
async def facturer_libre(
    data: FactureLibreCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """Émet une facture hors consultation (produit, forfait, prestation directe)."""
    ip, ua = _ctx(request)
    facture_creee = await FactureService.emettre_libre(
        db, data, current_user, client_ip=ip, user_agent=ua
    )
    # Rechargement complet avant sérialisation (cf. note dans émission consultation).
    facture = await FactureService.obtenir(db, facture_creee.id)
    return APIResponse(
        message=f"Facture {facture.numero} émise.", data=_facture_vers_reponse(facture)
    )


@router.get("", response_model=PaginatedResponse[FactureResponse])
async def list_factures(
    patient_id: Optional[uuid.UUID] = Query(None),
    statut: Optional[str] = Query(None, description="BROUILLON|EMISE|PARTIELLEMENT_PAYEE|PAYEE|ANNULEE"),
    q: Optional[str] = Query(None, description="Recherche par numéro de facture"),
    date_debut: Optional[str] = Query(None, description="AAAA-MM-JJ (date d'émission min.)"),
    date_fin: Optional[str] = Query(None, description="AAAA-MM-JJ (date d'émission max.)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Liste paginée des factures du cabinet."""
    from datetime import date as date_type

    params = PaginationParams(page=page, limit=limit)
    factures, total = await FactureService.lister(
        db,
        patient_id=patient_id,
        statut=statut,
        q=q,
        date_debut=date_type.fromisoformat(date_debut) if date_debut else None,
        date_fin=date_type.fromisoformat(date_fin) if date_fin else None,
        offset=params.offset,
        limit=params.limit,
    )
    return paginate(items=[_facture_vers_reponse(f) for f in factures], total_records=total, params=params)


@router.get("/journal-caisse", response_model=PaginatedResponse[dict])
async def journal_caisse(
    date_debut: Optional[str] = Query(None, description="AAAA-MM-JJ"),
    date_fin: Optional[str] = Query(None, description="AAAA-MM-JJ"),
    mode: Optional[str] = Query(None, description="ESPECES|CARTE_BANCAIRE|CHEQUE|VIREMENT|MOBILE_MONEY|ASSURANCE"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """
    Journal de caisse : tous les encaissements avec facture, patient et mode.
    ⚠️ Déclaré AVANT `/factures/{facture_id}` : FastAPI teste les routes dans
    l'ordre de déclaration, le littéral serait sinon absorbé comme un UUID.
    """
    from datetime import date as date_type

    params = PaginationParams(page=page, limit=limit)
    items, total = await PaiementService.journal_caisse(
        db,
        date_debut=date_type.fromisoformat(date_debut) if date_debut else None,
        date_fin=date_type.fromisoformat(date_fin) if date_fin else None,
        mode=mode,
        offset=params.offset,
        limit=params.limit,
    )
    return paginate(items=items, total_records=total, params=params)


@router.get("/{facture_id}", response_model=APIResponse[FactureResponse])
async def get_facture(
    facture_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Détail d'une facture : lignes, paiements, statut et reste à payer."""
    facture = await FactureService.obtenir(db, facture_id)
    return APIResponse(data=_facture_vers_reponse(facture))


@router.post("/{facture_id}/paiements", response_model=APIResponse[PaiementResponse], status_code=status.HTTP_201_CREATED)
async def encaisser(
    facture_id: uuid.UUID,
    data: PaiementCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """
    Encaisse un paiement (multi-moyens : espèces, Wave, Orange Money, chèque...).

    Sans `echeance_id` : paiement libre dans la limite du reste à payer.
    Avec `echeance_id` : montant EXACT du reste dû sur l'échéance.
    Le reçu est numéroté automatiquement (RECU-AAAAMMJJ-NNNN).
    """
    ip, ua = _ctx(request)
    paiement = await PaiementService.encaisser(
        db, facture_id, data, current_user, client_ip=ip, user_agent=ua
    )
    facture = await FactureService.obtenir(db, facture_id)
    return APIResponse(
        message=(
            f"Paiement encaissé. Reçu {paiement.recu_numero}. "
            f"Reste à payer : {facture.montant_restant} FCFA."
        ),
        data=_paiement_vers_reponse(paiement, echeance_id=data.echeance_id),
    )


@router.post("/{facture_id}/annuler", response_model=APIResponse[FactureResponse])
async def annuler_facture(
    facture_id: uuid.UUID,
    motif: str = Query(..., min_length=2, description="Motif de l'annulation (conservé en audit)"),
    request: Request = None,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:DELETE")),
):
    """Annule une facture sans encaissement. Interdite si des paiements existent."""
    ip, ua = _ctx(request) if request else (None, None)
    facture = await FactureService.annuler(
        db, facture_id, motif, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(message=f"Facture {facture.numero} annulée.", data=_facture_vers_reponse(facture))


# ==============================================================================
# ÉCHELONNEMENT (RG08)
# ==============================================================================

@router.post("/{facture_id}/echelonnement", response_model=APIResponse[PlanEchelonnementResponse], status_code=status.HTTP_201_CREATED)
async def creer_echelonnement(
    facture_id: uuid.UUID,
    data: PlanEchelonnementCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:UPDATE")),
):
    """
    Crée le plan d'échelonnement du RESTE À PAYER et génère les échéances
    (RG08). Un seul plan actif par facture.
    """
    ip, ua = _ctx(request)
    plan = await EchelonnementService.creer(
        db, facture_id, data, current_user, client_ip=ip, user_agent=ua
    )
    # `plan.echeances` a été assigné au service : la collection est chargée, on
    # sérialise tel quel. Un rechargement serait contre-productif ici — la
    # relation `facture.plan_echelonnement` est déjà en cache (None) du premier
    # `_charger`, et un selectinload ne rafraîchit pas un attribut chargé
    # (il faudrait populate_existing, cf. pièges documentés dans COMMANDS.md).
    return APIResponse(
        message=f"Plan créé : {plan.nombre_echeances} échéances.",
        data=_plan_vers_reponse(plan),
    )


@router.get("/{facture_id}/echelonnement", response_model=APIResponse[PlanEchelonnementResponse])
async def get_echelonnement(
    facture_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Plan d'échelonnement de la facture, échéances comprises (null si absent)."""
    plan = await EchelonnementService.obtenir(db, facture_id)
    if plan is None:
        return APIResponse(message="Aucun plan d'échelonnement.", data=None)
    return APIResponse(data=_plan_vers_reponse(plan))


# ==============================================================================
# DEVIS (RG14)
# ==============================================================================

@devis_router.post("", response_model=APIResponse[DevisResponse], status_code=status.HTTP_201_CREATED)
async def creer_devis(
    data: DevisCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """Émet un devis (brouillon). Les montants sont calculés depuis les lignes."""
    ip, ua = _ctx(request)
    devis_cree = await DevisService.creer(db, data, current_user, client_ip=ip, user_agent=ua)
    devis = await DevisService.obtenir(db, devis_cree.id)
    return APIResponse(message=f"Devis {devis.numero} créé.", data=_devis_vers_reponse(devis))


@devis_router.get("", response_model=PaginatedResponse[DevisResponse])
async def list_devis(
    patient_id: Optional[uuid.UUID] = Query(None),
    statut: Optional[str] = Query(None, description="BROUILLON|ENVOYE|ACCEPTE|REFUSE|EXPIRE"),
    q: Optional[str] = Query(None, description="Recherche par numéro de devis"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Liste paginée des devis."""
    params = PaginationParams(page=page, limit=limit)
    devis_list, total = await DevisService.lister(
        db, patient_id=patient_id, statut=statut, q=q, offset=params.offset, limit=params.limit
    )
    return paginate(
        items=[_devis_vers_reponse(d) for d in devis_list], total_records=total, params=params
    )


@devis_router.get("/{devis_id}", response_model=APIResponse[DevisResponse])
async def get_devis(
    devis_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("FACTURATION:READ")),
):
    """Détail d'un devis avec ses lignes."""
    devis = await DevisService.obtenir(db, devis_id)
    return APIResponse(data=_devis_vers_reponse(devis))


@devis_router.post("/{devis_id}/statut", response_model=APIResponse[DevisResponse])
async def changer_statut_devis(
    devis_id: uuid.UUID,
    data: DevisStatutUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:UPDATE")),
):
    """
    Fait avancer le cycle : BROUILLON → ENVOYE → ACCEPTE/REFUSE.

    Le passage à ACCEPTE exige `signature_patient: true` et une validité en
    cours. Un devis refusé ne se rouvre pas.
    """
    ip, ua = _ctx(request)
    devis = await DevisService.changer_statut(
        db, devis_id, data, current_user, client_ip=ip, user_agent=ua
    )
    return APIResponse(
        message=f"Devis {devis.numero} : {devis.statut.value}.", data=_devis_vers_reponse(devis)
    )


@devis_router.post("/{devis_id}/convertir", response_model=APIResponse[FactureResponse], status_code=status.HTTP_201_CREATED)
async def convertir_devis(
    devis_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("FACTURATION:CREATE")),
):
    """RG14 : convertit un devis accepté en facture, lignes comprises. Une seule fois."""
    ip, ua = _ctx(request)
    facture_creee = await DevisService.convertir_en_facture(
        db, devis_id, current_user, client_ip=ip, user_agent=ua
    )
    # Rechargement complet avant sérialisation (cf. note dans émission consultation).
    facture = await FactureService.obtenir(db, facture_creee.id)
    return APIResponse(
        message=f"Devis converti en facture {facture.numero}.",
        data=_facture_vers_reponse(facture),
    )
