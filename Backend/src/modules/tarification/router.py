"""
Routes de la tarification et de la prise en charge (CDC 5.6 et 5.7).

**Deux ressources, deux permissions, deux raisons.** `TARIFS:*` protege le prix
des actes, `ASSURANCE:*` protege ce que le cabinet declare a un payeur. Un
profil peut avoir l'une sans l'autre : le dentiste lit les deux, l'accueil
declare une prise en charge sans fixer un tarif, et seul l'administrateur du
cabinet fait les deux.

**La nomenclature change de maison.** Elle etait sous
`/nomenclature/actes`, avec `CONSULTATIONS:READ` : un praticien pouvait donc
creer un acte de nomenclature en ayant le droit de creer une consultation. Les
deux gestes n'ont rien a voir, et le second engage l'argent du cabinet. Les
routes existantes restent, avec `TARIFS:*` a la place - meme URL, droit change -
et le travail complet se fait sous `/tarification`.

**Chaque liste est paginee et filtree cote serveur.** Les filtres (`q`,
`categorie`, `actif`) sont des parametres de requete, pas du tri cote client :
filtrer apres coup d'une page de 50 donne une page de 3 et un total faux.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import EntityNotFoundException
from src.common.pagination import LIMITE_PAGE_MAX, PaginationParams, paginate
from src.common.schemas import APIResponse, BaseSchema, PaginatedResponse
from src.modules.auth.dependencies import get_current_user, get_tenant_db, require_permissions
from src.modules.tarification.schemas import (
    ActeNomenclatureCreate,
    ActeNomenclatureResponse,
    ActeNomenclatureUpdate,
    CategoriePatientCreate,
    CategoriePatientResponse,
    CategoriePatientUpdate,
    DroitPriseEnChargeCreate,
    DroitPriseEnChargeResponse,
    DroitPriseEnChargeUpdate,
    OrganismeAssuranceCreate,
    OrganismeAssuranceResponse,
    OrganismeAssuranceUpdate,
    TarifActeResponse,
    TarifActeUpsert,
)
from src.modules.tarification.services import (
    ActeService,
    CategorieService,
    DroitPriseEnChargeService,
    OrganismeService,
    TarifService,
)
from src.modules.tenants.models import (
    ActeNomenclature,
    OrganismeAssurance,
    Utilisateur,
)

router = APIRouter(
    prefix="/tarification",
    tags=["Tarification et prise en charge"],
)


def _ctx(request: Request):
    """Adresse et agent : les deux seuls contextes utiles a un ecoute d'audit."""
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# ---------------------------------------------------------------------------
# Nomenclature des actes
# ---------------------------------------------------------------------------


async def _vers_acte(
    acte: ActeNomenclature, tarifs: Optional[List[dict]] = None
) -> ActeNomenclatureResponse:
    return ActeNomenclatureResponse(
        id=acte.id,
        code=acte.code,
        libelle=acte.libelle,
        categorie=acte.categorie,
        tarif_base=acte.tarif_base,
        duree_estimee_min=acte.duree_estimee_min,
        unitaire=acte.unitaire,
        actif=acte.actif,
        tarifs=tarifs or [],
    )


@router.get("/actes", response_model=PaginatedResponse[ActeNomenclatureResponse])
async def lister_actes(
    q: Optional[str] = Query(None, description="Recherche par code ou libelle"),
    categorie: Optional[str] = Query(None, description="Filtrer par categorie d'acte"),
    actif: Optional[bool] = Query(None, description="Filtrer sur les actes actifs ou retires"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:READ")),
):
    """Nomenclature des actes du cabinet, avec le tarif de chaque categorie."""
    params = PaginationParams(page=page, limit=limit)
    actes, total = await ActeService.lister(
        db, q=q, categorie=categorie, actif=actif, offset=params.offset, limit=params.limit
    )
    groupes = await ActeService.tarifs_de(db, [a.id for a in actes])
    items = [
        await _vers_acte(
            a,
            [
                TarifActeResponse(
                    id=t.id, acte_id=t.acte_id, categorie_code=t.categorie_code, montant=t.montant
                ).model_dump()
                for t in groupes.get(a.id, [])
            ],
        )
        for a in actes
    ]
    return paginate(items=items, total_records=total, params=params)


@router.post(
    "/actes",
    response_model=APIResponse[ActeNomenclatureResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_acte(
    data: ActeNomenclatureCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    """Ajoute un acte a la nomenclature, avec son tarif de reference."""
    ip, ua = _ctx(request)
    acte = await ActeService.creer(
        db,
        code=data.code,
        libelle=data.libelle,
        categorie=data.categorie,
        tarif_base=data.tarif_base,
        duree_estimee_min=data.duree_estimee_min,
        unitaire=data.unitaire,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    groupes = await ActeService.tarifs_de(db, [acte.id])
    return APIResponse(
        message="Acte ajoute a la nomenclature.",
        data=await _vers_acte(
            acte,
            [
                TarifActeResponse(
                    id=t.id, acte_id=t.acte_id, categorie_code=t.categorie_code, montant=t.montant
                ).model_dump()
                for t in groupes.get(acte.id, [])
            ],
        ),
    )


@router.get("/actes/{acte_id}", response_model=APIResponse[ActeNomenclatureResponse])
async def obtenir_acte(
    acte_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:READ")),
):
    acte = await ActeService.obtenir(db, acte_id)
    groupes = await ActeService.tarifs_de(db, [acte.id])
    return APIResponse(
        data=await _vers_acte(
            acte,
            [
                TarifActeResponse(
                    id=t.id, acte_id=t.acte_id, categorie_code=t.categorie_code, montant=t.montant
                ).model_dump()
                for t in groupes.get(acte.id, [])
            ],
        )
    )


@router.patch("/actes/{acte_id}", response_model=APIResponse[ActeNomenclatureResponse])
async def modifier_acte(
    acte_id: uuid.UUID,
    data: ActeNomenclatureUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    """
    Edition d'un acte.

    `tarif_base` n'est pas un champ modifiable ici, et c'est volontaire : le
    changer passe par un tarif de categorie. Un PATCH general qui l'accepterait
    finirait par etre appele par une edition ordinaire, et le prix changerait
    sous les factures deja emises.
    """
    ip, ua = _ctx(request)
    acte = await ActeService.obtenir(db, acte_id)
    acte = await ActeService.modifier(
        db,
        acte,
        libelle=data.libelle,
        categorie=data.categorie,
        duree_estimee_min=data.duree_estimee_min,
        unitaire=data.unitaire,
        actif=data.actif,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    groupes = await ActeService.tarifs_de(db, [acte.id])
    return APIResponse(
        message="Acte mis a jour.",
        data=await _vers_acte(
            acte,
            [
                TarifActeResponse(
                    id=t.id, acte_id=t.acte_id, categorie_code=t.categorie_code, montant=t.montant
                ).model_dump()
                for t in groupes.get(acte.id, [])
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Tarifs par categorie
# ---------------------------------------------------------------------------


@router.get(
    "/actes/{acte_id}/tarifs", response_model=PaginatedResponse[TarifActeResponse]
)
async def lister_tarifs_acte(
    acte_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:READ")),
):
    """Tarifs d'un acte, tries par categorie puis par id."""
    params = PaginationParams(page=page, limit=limit)
    await ActeService.obtenir(db, acte_id)
    tous = (await ActeService.tarifs_de(db, [acte_id])).get(acte_id, [])
    # La fenetre est appliquee ici et non en SQL : un acte a quelques tarifs par
    # categorie. Le tri vient deja du service, avec sa clef secondaire.
    fenetre = tous[params.offset : params.offset + params.limit]
    return paginate(items=fenetre, total_records=len(tous), params=params)


@router.put("/actes/{acte_id}/tarifs", response_model=APIResponse[TarifActeResponse])
async def definir_tarif_acte(
    acte_id: uuid.UUID,
    data: TarifActeUpsert,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    """Ecrit le tarif d'un acte pour une categorie ; cree la ligne si absente."""
    ip, ua = _ctx(request)
    acte = await ActeService.obtenir(db, acte_id)
    tarif = await TarifService.definir(
        db,
        acte=acte,
        categorie_code=data.categorie_code,
        montant=data.montant,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    return APIResponse(message="Tarif enregistre.", data=tarif)


@router.delete("/actes/{acte_id}/tarifs/{tarif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_tarif_acte(
    acte_id: uuid.UUID,
    tarif_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    """Retire un tarif de variante. Le tarif standard est protege."""
    await ActeService.obtenir(db, acte_id)
    tarifs = (await ActeService.tarifs_de(db, [acte_id])).get(acte_id, [])
    tarif = next((t for t in tarifs if t.id == tarif_id), None)
    if tarif is None:
        raise EntityNotFoundException("Tarif d'acte", tarif_id)
    await TarifService.supprimer(db, tarif)
    return None


# ---------------------------------------------------------------------------
# Categories de patient
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=PaginatedResponse[CategoriePatientResponse])
async def lister_categories(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:READ")),
):
    params = PaginationParams(page=page, limit=limit)
    categories, total = await CategorieService.lister(db, offset=params.offset, limit=params.limit)
    return paginate(items=categories, total_records=total, params=params)


@router.post(
    "/categories",
    response_model=APIResponse[CategoriePatientResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_categorie(
    data: CategoriePatientCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    ip, ua = _ctx(request)
    categorie = await CategorieService.creer(
        db,
        code=data.code,
        libelle=data.libelle,
        ordre=data.ordre,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    return APIResponse(message="Categorie ajoutee.", data=categorie)


@router.patch("/categories/{code}", response_model=APIResponse[CategoriePatientResponse])
async def modifier_categorie(
    code: str,
    data: CategoriePatientUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    ip, ua = _ctx(request)
    categorie = await CategorieService.obtenir_par_code(db, code.strip().lower())
    categorie = await CategorieService.modifier(
        db,
        categorie,
        libelle=data.libelle,
        ordre=data.ordre,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    return APIResponse(message="Categorie mise a jour.", data=categorie)


@router.delete("/categories/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_categorie(
    code: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("TARIFS:WRITE")),
):
    """Refuse si des tarifs s'y rattachent : desactiver est le geste correct."""
    categorie = await CategorieService.obtenir_par_code(db, code.strip().lower())
    await CategorieService.supprimer(db, categorie)
    return None


# ---------------------------------------------------------------------------
# Organismes payeurs
# ---------------------------------------------------------------------------


@router.get("/organismes", response_model=PaginatedResponse[OrganismeAssuranceResponse])
async def lister_organismes(
    q: Optional[str] = Query(None, description="Recherche par code ou nom"),
    type_organisme: Optional[str] = Query(None, pattern=r"^(ASSURANCE|MUTUELLE)$"),
    actif: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:READ")),
):
    params = PaginationParams(page=page, limit=limit)
    organismes, total = await OrganismeService.lister(
        db,
        q=q,
        type_organisme=type_organisme,
        actif=actif,
        offset=params.offset,
        limit=params.limit,
    )
    return paginate(items=organismes, total_records=total, params=params)


@router.post(
    "/organismes",
    response_model=APIResponse[OrganismeAssuranceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_organisme(
    data: OrganismeAssuranceCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:WRITE")),
):
    ip, ua = _ctx(request)
    organisme = await OrganismeService.creer(
        db,
        code=data.code,
        nom=data.nom,
        type_organisme=data.type_organisme,
        actif=data.actif,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    return APIResponse(message="Organisme ajoute.", data=organisme)


@router.get("/organismes/{organisme_id}", response_model=APIResponse[OrganismeAssuranceResponse])
async def obtenir_organisme(
    organisme_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:READ")),
):
    return APIResponse(data=await OrganismeService.obtenir(db, organisme_id))


@router.patch("/organismes/{organisme_id}", response_model=APIResponse[OrganismeAssuranceResponse])
async def modifier_organisme(
    organisme_id: uuid.UUID,
    data: OrganismeAssuranceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:WRITE")),
):
    ip, ua = _ctx(request)
    organisme = await OrganismeService.obtenir(db, organisme_id)
    organisme = await OrganismeService.modifier(
        db,
        organisme,
        nom=data.nom,
        type_organisme=data.type_organisme,
        actif=data.actif,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    return APIResponse(message="Organisme mis a jour.", data=organisme)


@router.delete("/organismes/{organisme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_organisme(
    organisme_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:WRITE")),
):
    """Refuse si des droits de patients y sont rattaches."""
    organisme = await OrganismeService.obtenir(db, organisme_id)
    await OrganismeService.supprimer(db, organisme)
    return None


# ---------------------------------------------------------------------------
# Droits de prise en charge d'un patient
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/droits", response_model=PaginatedResponse[DroitPriseEnChargeResponse]
)
async def lister_droits_patient(
    patient_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=LIMITE_PAGE_MAX),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:READ")),
):
    """Droits de prise en charge d'un patient, tries par priorite puis organisme."""
    params = PaginationParams(page=page, limit=limit)
    lignes = await DroitPriseEnChargeService.lister_par_patient(db, patient_id)
    tous = [
        DroitPriseEnChargeResponse(
            id=droit.id,
            patient_id=droit.patient_id,
            organisme_id=droit.organisme_id,
            numero_police=droit.numero_police,
            taux_prise_en_charge=droit.taux_prise_en_charge,
            priorite=droit.priorite,
            actif=droit.actif,
            organisme_nom=organisme.nom,
            organisme_code=organisme.code,
        )
        for droit, organisme in lignes
    ]
    fenetre = tous[params.offset : params.offset + params.limit]
    return paginate(items=fenetre, total_records=len(tous), params=params)


@router.post(
    "/patients/{patient_id}/droits",
    response_model=APIResponse[DroitPriseEnChargeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def creer_droit_patient(
    patient_id: uuid.UUID,
    data: DroitPriseEnChargeCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:WRITE")),
):
    ip, ua = _ctx(request)
    droit = await DroitPriseEnChargeService.creer(
        db,
        patient_id=patient_id,
        organisme_id=data.organisme_id,
        numero_police=data.numero_police,
        taux_prise_en_charge=data.taux_prise_en_charge,
        priorite=data.priorite,
        actif=data.actif,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    organisme = await OrganismeService.obtenir(db, droit.organisme_id)
    return APIResponse(
        message="Droit de prise en charge enregistre.",
        data=DroitPriseEnChargeResponse(
            id=droit.id,
            patient_id=droit.patient_id,
            organisme_id=droit.organisme_id,
            numero_police=droit.numero_police,
            taux_prise_en_charge=droit.taux_prise_en_charge,
            priorite=droit.priorite,
            actif=droit.actif,
            organisme_nom=organisme.nom,
            organisme_code=organisme.code,
        ),
    )


@router.patch("/droits/{droit_id}", response_model=APIResponse[DroitPriseEnChargeResponse])
async def modifier_droit_patient(
    droit_id: uuid.UUID,
    data: DroitPriseEnChargeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:WRITE")),
):
    ip, ua = _ctx(request)
    droit = await DroitPriseEnChargeService.obtenir(db, droit_id)
    droit = await DroitPriseEnChargeService.modifier(
        db,
        droit,
        organisme_id=data.organisme_id,
        numero_police=data.numero_police,
        taux_prise_en_charge=data.taux_prise_en_charge,
        priorite=data.priorite,
        actif=data.actif,
        auteur=current_user,
        ip=ip,
        ua=ua,
    )
    organisme = await OrganismeService.obtenir(db, droit.organisme_id)
    return APIResponse(
        message="Droit de prise en charge mis a jour.",
        data=DroitPriseEnChargeResponse(
            id=droit.id,
            patient_id=droit.patient_id,
            organisme_id=droit.organisme_id,
            numero_police=droit.numero_police,
            taux_prise_en_charge=droit.taux_prise_en_charge,
            priorite=droit.priorite,
            actif=droit.actif,
            organisme_nom=organisme.nom,
            organisme_code=organisme.code,
        ),
    )


@router.delete("/droits/{droit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_droit_patient(
    droit_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("ASSURANCE:WRITE")),
):
    droit = await DroitPriseEnChargeService.obtenir(db, droit_id)
    await DroitPriseEnChargeService.supprimer(db, droit)
    return None