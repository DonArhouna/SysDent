"""
Routeur Stock : catalogue, mouvements, alertes, fournisseurs, commandes, réceptions.

Permissions : `STOCK:READ` pour lire, `STOCK:CREATE` pour créer et recevoir,
`STOCK:UPDATE` pour modifier, `STOCK:DELETE` pour supprimer.

**La réception n'exige que `STOCK:CREATE`**, pas de validation supplémentaire :
la sécurité vient de la traçabilité, pas d'un second approbateur.
"""

from typing import List

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.pagination import PaginationParams, paginate
from src.common.schemas import APIResponse, PaginatedResponse
from src.modules.auth.dependencies import (
    get_current_user,
    get_tenant_db,
    require_permissions,
)
from src.modules.stock.schemas import (
    AlerteStockResponse,
    ArticleStockCreate,
    ArticleStockResponse,
    ArticleStockUpdate,
    CommandeCreate,
    CommandeResponse,
    FournisseurCreate,
    FournisseurResponse,
    FournisseurUpdate,
    MouvementStockCreate,
    MouvementStockResponse,
    ReceptionCreate,
    ReceptionResponse,
    StatutCommandeUpdate,
)
from src.modules.stock.services import (
    AlerteStockService,
    ArticleStockService,
    CommandeFournisseurService,
    FournisseurService,
    MouvementStockService,
    ReceptionService,
)
from src.modules.tenants.models import (
    StatutCommandeEnum,
    TypeMouvementStockEnum,
    Utilisateur,
)

router = APIRouter(prefix="/stock", tags=["Stock & Fournisseurs"])


def _serialiser_article(article, *, cabinet_id: uuid.UUID | None = None) -> ArticleStockResponse:
    """
    Construit la réponse d'un article, quantité totale et répartition par site.

    La quantité affichée est la somme des sites, pas une colonne de l'article :
    c'est le total qui INTEREST le cabinet, et la répartition qui indique où
    chercher un produit en urgence.
    """
    stocks = list(article.stocks_sites or [])
    total = sum(s.quantite for s in stocks)
    return ArticleStockResponse(
        id=article.id,
        code=article.code,
        designation=article.designation,
        categorie=article.categorie,
        unite=article.unite,
        quantite_stock=total,
        seuil_alerte=article.seuil_alerte,
        prix_achat=article.prix_achat,
        date_peremption=article.date_peremption,
        emplacement=article.emplacement,
        gere_par_lot=article.gere_par_lot,
        actif=article.actif,
        stocks_sites=[
            {
                "cabinet_id": str(s.cabinet_id),
                "quantite": s.quantite,
                "quantite_site_courante": s.quantite == total,
            }
            for s in stocks
        ],
    )


def _serialiser_mouvement(mouvement) -> MouvementStockResponse:
    return MouvementStockResponse(
        id=mouvement.id,
        article_id=mouvement.article_id,
        article_designation=mouvement.article.designation if mouvement.article else None,
        article_code=mouvement.article.code if mouvement.article else None,
        cabinet_id=mouvement.cabinet_id,
        type_mouvement=mouvement.type_mouvement,
        quantite=mouvement.quantite,
        stock_avant=mouvement.stock_avant,
        stock_apres=mouvement.stock_apres,
        motif=mouvement.motif,
        auteur=str(mouvement.auteur_id) if mouvement.auteur_id else None,
        auteur_email=mouvement.auteur_email,
        commande_id=mouvement.commande_id,
        date_mouvement=mouvement.date_mouvement,
    )


def _serialiser_commande(commande) -> CommandeResponse:
    lignes = []
    total = 0
    for ligne in commande.lignes or []:
        lignes.append(
            {
                "id": ligne.id,
                "article_id": ligne.article_id,
                "article_code": ligne.article.code if ligne.article else None,
                "article_designation": ligne.article.designation if ligne.article else None,
                "quantite_commandee": ligne.quantite_commandee,
                "quantite_recue": ligne.quantite_recue,
                "prix_unitaire": ligne.prix_unitaire,
            }
        )
        total += float(ligne.quantite_commandee) * float(ligne.prix_unitaire or 0)
    return CommandeResponse(
        id=commande.id,
        numero=commande.numero,
        fournisseur_id=commande.fournisseur_id,
        fournisseur_nom=commande.fournisseur.nom if commande.fournisseur else None,
        statut=commande.statut,
        date_commande=commande.date_commande,
        notes=commande.notes,
        auteur=commande.auteur_email,
        lignes=lignes,
        montant_total=total,
    )


# ==============================================================================
# ARTICLES
# ==============================================================================


@router.get("/articles", response_model=PaginatedResponse[ArticleStockResponse])
async def lister_articles(
    cabinet_id: uuid.UUID = Query(..., description="Site dont on veut le stock"),
    q: str | None = None,
    categorie: str | None = None,
    alerte_seuil: bool = False,
    peremption_proche: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:READ")),
):
    articles, total = await ArticleStockService.lister(
        db,
        cabinet_id=cabinet_id,
        q=q,
        categorie=categorie,
        alerte_seuil=alerte_seuil,
        peremption_proche=peremption_proche,
        offset=(page - 1) * limit,
        limit=limit,
    )
    return paginate(
        [_serialiser_article(a) for a in articles],
        total,
        PaginationParams(page=page, limit=limit),
    )


@router.post(
    "/articles",
    response_model=APIResponse[ArticleStockResponse],
    status_code=201,
)
async def creer_article(
    data: ArticleStockCreate,
    cabinet_id: uuid.UUID = Query(..., description="Site qui reçoit le stock initial"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("STOCK:CREATE")),
):
    """
    Crée un article de stock.

    La quantité initiale est enregistrée comme un mouvement d'entrée, pas
    écrite directement : le stock d'un article créé doit pouvoir s'expliquer
    comme n'importe quelle autre entrée.
    """
    article = await ArticleStockService.creer(
        db, data=data, cabinet_id=cabinet_id, auteur=current_user
    )
    return APIResponse(
        message="Article créé.", data=_serialiser_article(article)
    )


@router.patch(
    "/articles/{article_id}", response_model=APIResponse[ArticleStockResponse]
)
async def modifier_article(
    article_id: uuid.UUID,
    data: ArticleStockUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:UPDATE")),
):
    article = await ArticleStockService.modifier(db, article_id, data=data)
    return APIResponse(message="Article mis à jour.", data=_serialiser_article(article))


# ==============================================================================
# MOUVEMENTS
# ==============================================================================


@router.post("/mouvements", response_model=APIResponse[MouvementStockResponse], status_code=201)
async def enregistrer_mouvement(
    data: MouvementStockCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("STOCK:CREATE")),
):
    """
    Enregistre une entrée ou une sortie de matière.

    Le stock n'est jamais écrit directement : tout passe par un mouvement, ce qui
    rend chaque écart d'inventaire explicable ligne par ligne.
    """
    article = await ArticleStockService.obtenir(db, data.article_id)
    mouvement = await MouvementStockService.enregistrer(
        db,
        article=article,
        cabinet_id=data.cabinet_id,
        type_mouvement=data.type_mouvement,
        quantite=data.quantite,
        motif=data.motif,
        auteur=current_user,
        lot_id=data.lot_id,
    )
    await db.commit()
    return APIResponse(
        message="Mouvement enregistré.", data=_serialiser_mouvement(mouvement)
    )


@router.get("/mouvements", response_model=PaginatedResponse[MouvementStockResponse])
async def lister_mouvements(
    article_id: uuid.UUID | None = None,
    cabinet_id: uuid.UUID | None = None,
    type_mouvement: TypeMouvementStockEnum | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:READ")),
):
    """Historique des mouvements, du plus récent au plus ancien."""
    mouvements = await MouvementStockService.lister(
        db,
        article_id=article_id,
        cabinet_id=cabinet_id,
        type_mouvement=type_mouvement,
        limit=limit,
    )
    return paginate(
        [_serialiser_mouvement(m) for m in mouvements],
        len(mouvements),
        PaginationParams(page=page, limit=limit),
    )


# ==============================================================================
# ALERTES
# ==============================================================================


@router.get("/alertes", response_model=APIResponse[List[AlerteStockResponse]])
async def lister_alertes(
    cabinet_id: uuid.UUID = Query(..., description="Site à surveiller"),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:READ")),
):
    """
    Alertes de stock minimum et de péremption.

    Elles sont calculées à la demande et non stockées : une alerte enregistrée
    vieillit et finit par annoncer un problème qui n'existe plus.
    """
    alertes = await AlerteStockService.lister(db, cabinet_id=cabinet_id)
    return APIResponse(data=[AlerteStockResponse(**a) for a in alertes])


# ==============================================================================
# FOURNISSEURS
# ==============================================================================


@router.get("/fournisseurs", response_model=PaginatedResponse[FournisseurResponse])
async def lister_fournisseurs(
    q: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:READ")),
):
    """
    Fournisseurs du cabinet, paginés.

    La liste était renvoyée en entier. Un cabinet qui travaille avec un
    grossiste, un laboratoire et un fournisseur d'urgence en a quelques
    dizaines : la liste entière reste gérable, mais la réponse ne doit pas
    grossir indéfiniment alors qu'une borne est disponible.
    """
    fournisseurs, total = await FournisseurService.lister(
        db, q=q, offset=(page - 1) * limit, limit=limit
    )
    return paginate(
        [FournisseurResponse.model_validate(f, from_attributes=True) for f in fournisseurs],
        total,
        PaginationParams(page=page, limit=limit),
    )


@router.post(
    "/fournisseurs",
    response_model=APIResponse[FournisseurResponse],
    status_code=201,
)
async def creer_fournisseur(
    data: FournisseurCreate,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:CREATE")),
):
    fournisseur = await FournisseurService.creer(db, data=data)
    return APIResponse(
        message="Fournisseur créé.",
        data=FournisseurResponse.model_validate(fournisseur, from_attributes=True),
    )


@router.patch(
    "/fournisseurs/{fournisseur_id}",
    response_model=APIResponse[FournisseurResponse],
)
async def modifier_fournisseur(
    fournisseur_id: uuid.UUID,
    data: FournisseurUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:UPDATE")),
):
    fournisseur = await FournisseurService.modifier(db, fournisseur_id, data=data)
    return APIResponse(
        message="Fournisseur mis à jour.",
        data=FournisseurResponse.model_validate(fournisseur, from_attributes=True),
    )


# ==============================================================================
# COMMANDES FOURNISSEUR
# ==============================================================================


@router.get("/commandes", response_model=PaginatedResponse[CommandeResponse])
async def lister_commandes(
    statut: StatutCommandeEnum | None = None,
    fournisseur_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:READ")),
):
    """
    Commandes fournisseur, paginées.

    **Correction d'un silence** : la route plafonnait à 50 lignes sans `page` ni
    `offset`. Au-delà, les commandes existantes disparaissaient de l'écran sans
    aucun message — l'utilisateur croyait qu'il n'y avait rien d'autre. Une liste
    tronquée sans le dire est la même famille de défaut que le « aucune donnée »
    affiché comme un zéro.
    """
    commandes, total = await CommandeFournisseurService.lister(
        db,
        statut=statut,
        fournisseur_id=fournisseur_id,
        offset=(page - 1) * limit,
        limit=limit,
    )
    return paginate(
        [_serialiser_commande(c) for c in commandes],
        total,
        PaginationParams(page=page, limit=limit),
    )


@router.post(
    "/commandes", response_model=APIResponse[CommandeResponse], status_code=201
)
async def creer_commande(
    data: CommandeCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("STOCK:CREATE")),
):
    """
    Crée un bon de commande en brouillon.

    Émettre une commande n'ajoute rien au stock : la matière n'arrive qu'à la
    réception. Sans cette séparation, le stock annoncerait des produits que le
    cabinet n'a pas.
    """
    commande = await CommandeFournisseurService.creer(db, data=data, auteur=current_user)
    return APIResponse(
        message="Commande créée.", data=_serialiser_commande(commande)
    )


@router.patch(
    "/commandes/{commande_id}", response_model=APIResponse[CommandeResponse]
)
async def changer_statut_commande(
    commande_id: uuid.UUID,
    data: StatutCommandeUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    _: bool = Depends(require_permissions("STOCK:UPDATE")),
):
    """
    Fait avancer la commande dans son cycle de vie.

    Les transitions autorisées sont explicites : une commande reçue ne se
    rouvre pas, une commande envoyée ne revient pas en brouillon.
    """
    commande = await CommandeFournisseurService.changer_statut(
        db, commande_id, data.statut
    )
    return APIResponse(
        message="Statut de la commande mis à jour.",
        data=_serialiser_commande(commande),
    )


# ==============================================================================
# RÉCEPTIONS
# ==============================================================================


@router.post(
    "/receptions", response_model=APIResponse[ReceptionResponse], status_code=201
)
async def enregistrer_reception(
    data: ReceptionCreate,
    commande_id: uuid.UUID = Query(..., description="Commande réceptionnée"),
    site_id: uuid.UUID = Query(..., description="Site qui reçoit la matière"),
    db: AsyncSession = Depends(get_tenant_db),
    current_user: Utilisateur = Depends(get_current_user),
    _: bool = Depends(require_permissions("STOCK:CREATE")),
):
    """
    Enregistre une réception : le stock est crédité immédiatement.

    Le crédit est automatique et tracable, sans validation à deux mains. Dans un
    cabinet d'une ou deux personnes, la double validation empêche la réception —
    donc le stock devient faux, et un stock faux est cru. Qui, quand et depuis
    quelle commande : la trace est complète, et c'est elle qui fait la sécurité.
    """
    reception = await ReceptionService.enregistrer(
        db,
        commande_id=commande_id,
        lignes=data.lignes,
        site_id=site_id,
        auteur=current_user,
        notes=data.notes,
    )
    return APIResponse(
        message="Réception enregistrée : le stock a été crédité.",
        data=ReceptionResponse(
            id=reception.id,
            numero=reception.numero,
            commande_id=reception.commande_id,
            date_reception=reception.date_reception,
            notes=reception.notes,
            auteur=reception.auteur_email,
            lignes=[
                {
                    "id": ligne.id,
                    "ligne_commande_id": ligne.ligne_commande_id,
                    "quantite_recue": ligne.quantite_recue,
                    "lot_code": ligne.lot_code,
                    "date_peremption": ligne.date_peremption,
                }
                for ligne in reception.lignes
            ],
        ),
    )
