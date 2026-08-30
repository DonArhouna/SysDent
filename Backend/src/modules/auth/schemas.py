from typing import List, Optional
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
