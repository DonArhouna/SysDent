"""
Schemas de la tarification et de la prise en charge (CDC 5.6 et 5.7).

**Aucun `dict` ici, et c'est le point.** La nomenclature repondait
`PaginatedResponse[dict]`, ce qui veut dire que le contrat OpenAPI ne decrivait
rien : le client ne pouvait pas etre type, et une reponse qui perdait un champ
passait inapercue. Chaque reponse a donc un schema nomme, ce qui permet a la
garde OpenAPI de refuser un `dict` sans proprietes.

Les montants sont des `Decimal` cote serveur. Un `float` perdrait de la
precision sur un montant de facture, et `tarif_applique` est deja un `NUMERIC`
cote base : le type doit suivre dans les deux sens.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from src.common.schemas import BaseSchema

#: Code de la categorie de reference, cree automatiquement pour tout cabinet.
CODE_CATEGORIE_STANDARD = "standard"

#: Taux maximal de prise en charge, en pourcentage. La meme borne est portee
#: par un `CHECK` en base : une valeur hors bornes doit etre refusee par
#: PostgreSQL meme si elle passe le validateur.
TAUX_PRISE_EN_CHARGE_MAX = Decimal("100")


# ---------------------------------------------------------------------------
# Categories de patient
# ---------------------------------------------------------------------------


class CategoriePatientBase(BaseSchema):
    libelle: str = Field(..., min_length=2, max_length=200)
    ordre: int = Field(100, ge=0, le=999)


class CategoriePatientCreate(CategoriePatientBase):
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    par_defaut: bool = False

    @field_validator("code")
    @classmethod
    def _code_n_minuscule(cls, v: str) -> str:
        return v.strip().lower()


class CategoriePatientUpdate(BaseSchema):
    """Mise a jour partielle. `None` = ne pas toucher."""

    libelle: Optional[str] = Field(None, min_length=2, max_length=200)
    ordre: Optional[int] = Field(None, ge=0, le=999)


class CategoriePatientResponse(BaseSchema):
    id: uuid.UUID
    code: str
    libelle: str
    ordre: int
    par_defaut: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Nomenclature et tarifs
# ---------------------------------------------------------------------------


class TarifActeResponse(BaseSchema):
    id: uuid.UUID
    acte_id: uuid.UUID
    categorie_code: str
    montant: Decimal


class TarifActeUpsert(BaseSchema):
    """Ecrit un tarif. Cree la ligne si absente, remplace le montant sinon."""

    categorie_code: str = Field(..., min_length=2, max_length=50)
    montant: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)

    @field_validator("categorie_code")
    @classmethod
    def _code_n_minuscule(cls, v: str) -> str:
        return v.strip().lower()


class ActeNomenclatureBase(BaseSchema):
    libelle: str = Field(..., min_length=2, max_length=200)
    categorie: str = Field(..., min_length=2, max_length=100)
    duree_estimee_min: int = Field(30, ge=1, le=480)
    unitaire: bool = False


class ActeNomenclatureCreate(ActeNomenclatureBase):
    code: str = Field(..., min_length=2, max_length=50)
    #: Repris dans `tarifs_actes` sous la categorie `standard` a la creation. Ce
    #: n'est pas un doublon : c'est le tarif de reference, et c'est lui que la
    #: facturation lira apres la transition.
    tarif_base: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)


class ActeNomenclatureUpdate(BaseSchema):
    """Mise a jour partielle. `None` = ne pas toucher."""

    libelle: Optional[str] = Field(None, min_length=2, max_length=200)
    categorie: Optional[str] = Field(None, min_length=2, max_length=100)
    duree_estimee_min: Optional[int] = Field(None, ge=1, le=480)
    unitaire: Optional[bool] = None
    actif: Optional[bool] = None


class ActeNomenclatureResponse(BaseSchema):
    id: uuid.UUID
    code: str
    libelle: str
    categorie: str
    tarif_base: Decimal
    duree_estimee_min: int
    unitaire: bool
    actif: bool
    #: Tarifs par categorie. Vide si l'acte n'a que son `tarif_base` repris a la
    #: migration : la liste est alors remplie depuis `tarifs_actes` par le service,
    #: jamais devinee.
    tarifs: list[TarifActeResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Organismes payeurs et droits de prise en charge
# ---------------------------------------------------------------------------


class OrganismeAssuranceBase(BaseSchema):
    nom: str = Field(..., min_length=2, max_length=200)
    type_organisme: str = Field("ASSURANCE", pattern=r"^(ASSURANCE|MUTUELLE)$")
    actif: bool = True


class OrganismeAssuranceCreate(OrganismeAssuranceBase):
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("code")
    @classmethod
    def _code_n_minuscule(cls, v: str) -> str:
        return v.strip().lower()


class OrganismeAssuranceUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=2, max_length=200)
    type_organisme: Optional[str] = Field(None, pattern=r"^(ASSURANCE|MUTUELLE)$")
    actif: Optional[bool] = None


class OrganismeAssuranceResponse(BaseSchema):
    id: uuid.UUID
    code: str
    nom: str
    type_organisme: str
    actif: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DroitPriseEnChargeBase(BaseSchema):
    numero_police: Optional[str] = Field(None, max_length=80)
    #: Pourcentage de 0 a 100. `max_digits=5, decimal_places=2` porte la meme
    #: borne que le `CHECK` de la base.
    taux_prise_en_charge: Decimal = Field(
        ..., ge=0, le=TAUX_PRISE_EN_CHARGE_MAX, max_digits=5, decimal_places=2
    )
    priorite: int = Field(1, ge=1, le=99)
    actif: bool = True


class DroitPriseEnChargeCreate(DroitPriseEnChargeBase):
    organisme_id: uuid.UUID


class DroitPriseEnChargeUpdate(BaseSchema):
    organisme_id: Optional[uuid.UUID] = None
    numero_police: Optional[str] = Field(None, max_length=80)
    taux_prise_en_charge: Optional[Decimal] = Field(
        None, ge=0, le=TAUX_PRISE_EN_CHARGE_MAX, max_digits=5, decimal_places=2
    )
    priorite: Optional[int] = Field(None, ge=1, le=99)
    actif: Optional[bool] = None


class DroitPriseEnChargeResponse(DroitPriseEnChargeBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    organisme_id: uuid.UUID
    #: Denormalise pour l'ecran : afficher "le taux de 70 %" sans un aller-retour
    #: par ligne. Ce n'est pas une copie - c'est une lecture de la jointure.
    organisme_nom: Optional[str] = None
    organisme_code: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None