"""Schémas de la session de caisse."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import ConfigDict, Field

from src.common.schemas import BaseSchema
from src.modules.tenants.models import ModePaiementEnum, StatutSessionCaisseEnum


class OuvertureCaisseCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    cabinet_id: uuid.UUID
    # Espèces déjà présentes dans le tiroir : le dépôt du caissier, pas une recette.
    ouverture_especes: Decimal = Field(Decimal("0.00"), ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class ClotureCaisseCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    #: Ce que le caissier déclare avoir compté dans le tiroir.
    especes_comptees: Decimal = Field(..., ge=0)
    #: L'écart est un fait, pas une faute : il est demandé quand il est != 0,
    #: mais il n'est pas obligatoire — un caissier peut ne pas savoir pourquoi
    #: il est en écart, et le forcer à inventer une explication serait pire que
    #: de laisser la case vide.
    motif_ecart: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = Field(None, max_length=500)


class SessionCaisseResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    cabinet_id: uuid.UUID
    statut: StatutSessionCaisseEnum
    ouverte_le: datetime
    ouverte_par: Optional[str] = None
    ouverture_especes: Decimal
    close_le: Optional[datetime] = None
    close_par: Optional[str] = None
    especes_comptees: Optional[Decimal] = None
    #: Ce qui devrait être dans le tiroir au moment de la clôture.
    especes_attendues: Decimal
    #: Compté moins attendu. Négatif = manque, positif = excédent.
    ecart_especes: Optional[Decimal] = None
    total_especes: Decimal
    total_carte: Decimal
    total_virement: Decimal
    total_mobile_money: Decimal
    total_cheque: Decimal
    #: Part assurance / tiers-payant encaissée dans la session.
    total_assurance: Decimal
    total_encaisse: Decimal
    nb_paiements: int
    motif_ecart: Optional[str] = None
    notes: Optional[str] = None


class PaiementCaisseResponse(BaseSchema):
    id: uuid.UUID
    facture_id: uuid.UUID
    recu_numero: str
    montant: Decimal
    mode: ModePaiementEnum
    reference: Optional[str] = None
    auteur: Optional[str] = None
    date_paiement: datetime
