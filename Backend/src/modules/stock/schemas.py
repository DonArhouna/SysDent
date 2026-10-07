"""Schémas de saisie et de lecture du module Stock."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field, field_validator

from src.common.schemas import BaseSchema
from src.modules.tenants.models import StatutCommandeEnum, TypeMouvementStockEnum


# ==============================================================================
# ARTICLES
# ==============================================================================


class ArticleStockResponse(BaseSchema):
    id: uuid.UUID
    code: str
    designation: str
    categorie: str
    unite: str
    quantite_stock: int = 0
    seuil_alerte: int
    prix_achat: Decimal
    date_peremption: Optional[date] = None
    emplacement: Optional[str] = None
    gere_par_lot: bool = False
    actif: bool
    # Répartition par site : c'est ce qui permet de savoir où chercher un produit
    # en urgence, et pas seulement combien il en reste au total.
    stocks_sites: List[Dict[str, Any]] = []


class ArticleStockCreate(BaseSchema):
    # `extra="forbid"` : un champ inconnu doit être refusé, pas accepté puis
    # jeté. Sans cela, une faute de frappe dans le nom d'un champ répond 200
    # alors que la donnée n'a pas été enregistrée.
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=50)
    designation: str = Field(..., min_length=2, max_length=200)
    categorie: str = Field(..., min_length=1, max_length=100)
    unite: str = Field(..., min_length=1, max_length=30)
    quantite_stock: int = Field(0, ge=0)
    seuil_alerte: int = Field(0, ge=0)
    prix_achat: Decimal = Field(Decimal(0), ge=0)
    date_peremption: Optional[date] = None
    emplacement: Optional[str] = Field(None, max_length=100)
    gere_par_lot: bool = False
    motif_initial: Optional[str] = Field(
        None, max_length=300, description="Motif de l'entrée de stock initial"
    )


class ArticleStockUpdate(BaseSchema):
    """
    Mise à jour de la fiche d'un article.

    Ni `quantite_stock` ni `date_peremption` : ce sont des faits de stock, pas
    des propriétés de fiche. Ils se modifient par un mouvement, ce qui laisse
    une trace — sinon une correction d'inventaire serait indiscernable d'un
    vol.
    """

    model_config = ConfigDict(extra="forbid")

    code: Optional[str] = Field(None, min_length=1, max_length=50)
    designation: Optional[str] = Field(None, min_length=2, max_length=200)
    categorie: Optional[str] = Field(None, min_length=1, max_length=100)
    unite: Optional[str] = Field(None, min_length=1, max_length=30)
    seuil_alerte: Optional[int] = Field(None, ge=0)
    prix_achat: Optional[Decimal] = Field(None, ge=0)
    emplacement: Optional[str] = Field(None, max_length=100)
    gere_par_lot: Optional[bool] = None
    actif: Optional[bool] = None


# ==============================================================================
# MOUVEMENTS
# ==============================================================================


class MouvementStockCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    article_id: uuid.UUID
    cabinet_id: uuid.UUID
    type_mouvement: TypeMouvementStockEnum
    quantite: int = Field(..., gt=0)
    lot_id: Optional[uuid.UUID] = None
    motif: Optional[str] = Field(None, max_length=300)


class MouvementStockResponse(BaseSchema):
    id: uuid.UUID
    article_id: uuid.UUID
    article_designation: Optional[str] = None
    article_code: Optional[str] = None
    cabinet_id: uuid.UUID
    type_mouvement: TypeMouvementStockEnum
    quantite: int
    stock_avant: int
    stock_apres: int
    motif: Optional[str] = None
    # L'email est conservé en plus de l'identifiant : la traçabilité du matériel
    # doit survivre à la suppression du compte qui l'a manipulé.
    auteur: Optional[str] = None
    auteur_email: Optional[str] = None
    commande_id: Optional[uuid.UUID] = None
    date_mouvement: datetime


# ==============================================================================
# ALERTES
# ==============================================================================


class AlerteStockResponse(BaseSchema):
    article_id: str
    code: str
    designation: str
    type: str
    niveau: str
    stock_actuel: int
    seuil: Optional[int] = None
    unite: str
    date_peremption: Optional[str] = None
    jours_restants: Optional[int] = None
    message: str


# ==============================================================================
# FOURNISSEURS
# ==============================================================================


class FournisseurResponse(BaseSchema):
    id: uuid.UUID
    nom: str
    contact: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None
    actif: bool


class FournisseurCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    nom: str = Field(..., min_length=2, max_length=200)
    contact: Optional[str] = Field(None, max_length=150)
    telephone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=150)
    adresse: Optional[str] = None
    notes: Optional[str] = None


class FournisseurUpdate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    nom: Optional[str] = Field(None, min_length=2, max_length=200)
    contact: Optional[str] = Field(None, max_length=150)
    telephone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=150)
    adresse: Optional[str] = None
    notes: Optional[str] = None
    actif: Optional[bool] = None


# ==============================================================================
# COMMANDES
# ==============================================================================


class LigneCommandeCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    article_id: uuid.UUID
    quantite: int = Field(..., gt=0)
    prix_unitaire: Optional[Decimal] = Field(None, ge=0)


class CommandeCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    fournisseur_id: uuid.UUID
    notes: Optional[str] = None
    lignes: List[LigneCommandeCreate] = Field(..., min_length=1)


class LigneCommandeResponse(BaseSchema):
    id: uuid.UUID
    article_id: uuid.UUID
    article_code: Optional[str] = None
    article_designation: Optional[str] = None
    quantite_commandee: int
    quantite_recue: int
    prix_unitaire: Decimal


class CommandeResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    fournisseur_id: uuid.UUID
    fournisseur_nom: Optional[str] = None
    statut: StatutCommandeEnum
    date_commande: date
    notes: Optional[str] = None
    auteur: Optional[str] = None
    lignes: List[LigneCommandeResponse] = []
    montant_total: Decimal = Decimal(0)


class StatutCommandeUpdate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    statut: StatutCommandeEnum


# ==============================================================================
# RÉCEPTIONS
# ==============================================================================


class LigneReceptionCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    ligne_commande_id: uuid.UUID
    quantite_recue: int = Field(..., gt=0)
    lot_code: Optional[str] = Field(None, max_length=100)
    date_peremption: Optional[date] = None


class ReceptionCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = None
    lignes: List[LigneReceptionCreate] = Field(..., min_length=1)


class LigneReceptionResponse(BaseSchema):
    id: uuid.UUID
    ligne_commande_id: uuid.UUID
    quantite_recue: int
    lot_code: Optional[str] = None
    date_peremption: Optional[date] = None


class ReceptionResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    commande_id: uuid.UUID
    date_reception: date
    notes: Optional[str] = None
    auteur: Optional[str] = None
    lignes: List[LigneReceptionResponse] = []
