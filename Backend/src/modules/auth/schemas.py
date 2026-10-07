from typing import Any, Dict, List, Optional
import uuid
from pydantic import EmailStr, Field
from src.common.schemas import BaseSchema


class LoginRequest(BaseSchema):
    email: EmailStr = Field(..., description="Email professionnel")
    password: str = Field(..., description="Mot de passe")
    cabinet_code: Optional[str] = Field(None, description="Code / Slug du cabinet si applicable")


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Durée de validité en secondes")
    tenant_id: Optional[str] = None


class RefreshTokenRequest(BaseSchema):
    refresh_token: str


class UserProfileResponse(BaseSchema):
    id: uuid.UUID
    email: EmailStr
    prenom: str
    nom: str
    role: str
    permissions: List[str] = []
    telephone: Optional[str] = None
    photo_url: Optional[str] = None
    tenant_id: Optional[str] = None
    # Contrat commercial du cabinet (Phase C.4) : permet au frontend de
    # piloter l'interface sans second appel. Ajouté avec un défaut : un client
    # plus ancien qui ignore ces champs continue de fonctionner.
    plan_code: Optional[str] = None
    quotas: Dict[str, Any] = {}
    features: Dict[str, bool] = {}
    #: Nom du cabinet, affiche en lecture seule dans la barre du haut.
    #:
    #: Il vient du profil et non de `GET /cabinets` : un role sans
    #: `CABINETS:READ` — le caissier, le gestionnaire de stock — ne perd pas
    #: pour autant le repere de « ou suis-je ». Savoir dans quel cabinet on
    #: travaille n'est pas une donnee sensible : c'est le sien.
    cabinet_nom: Optional[str] = None
    #: Site de rattachement de l'utilisateur, s'il en a un.
    cabinet_id: Optional[uuid.UUID] = None
