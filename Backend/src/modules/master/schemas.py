from datetime import datetime
import uuid
from typing import Optional
from pydantic import EmailStr, Field
from src.common.schemas import BaseSchema


class SocieteCreate(BaseSchema):
    nom: str = Field(..., min_length=2, max_length=150, description="Nom commercial ou raison sociale")
    ninea: Optional[str] = Field(None, max_length=50, description="Numéro NINEA ou Registre de commerce")
    logo_url: Optional[str] = None
    adresse_siege: Optional[str] = None
    ville: Optional[str] = "Dakar"
    pays: Optional[str] = "Sénégal"
    telephone: Optional[str] = None
    email: Optional[EmailStr] = None
    site_web: Optional[str] = None
    # Identifiants du premier compte administrateur du cabinet
    admin_email: EmailStr = Field(..., description="Email de l'administrateur du cabinet")
    admin_prenom: str = Field(..., min_length=2, max_length=50)
    admin_nom: str = Field(..., min_length=2, max_length=50)
    admin_password: str = Field(..., min_length=8, description="Mot de passe initial")


class SocieteUpdate(BaseSchema):
    nom: Optional[str] = None
    ninea: Optional[str] = None
    logo_url: Optional[str] = None
    adresse_siege: Optional[str] = None
    ville: Optional[str] = None
    pays: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[EmailStr] = None
    site_web: Optional[str] = None
    actif: Optional[bool] = None


class TenantDBResponse(BaseSchema):
    id: uuid.UUID
    db_name: str
    db_host: str
    db_port: int
    statut: str
    schema_version: str


class SocieteResponse(BaseSchema):
    id: uuid.UUID
    nom: str
    ninea: Optional[str] = None
    logo_url: Optional[str] = None
    adresse_siege: Optional[str] = None
    ville: Optional[str] = None
    pays: str
    telephone: Optional[str] = None
    email: Optional[str] = None
    site_web: Optional[str] = None
    actif: bool
    date_creation: datetime
    tenant_db: Optional[TenantDBResponse] = None


class SocieteStatutUpdate(BaseSchema):
    actif: bool = Field(..., description="true pour réactiver, false pour suspendre l'accès du cabinet")


class SuperAdminLogin(BaseSchema):
    email: EmailStr
    password: str


class MasterTokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Durée de validité de l'access token en secondes")
    email: Optional[str] = None
    nom_complet: Optional[str] = None


class SuperAdminResponse(BaseSchema):
    id: uuid.UUID
    email: EmailStr
    nom_complet: str
    actif: bool
    dernier_login: Optional[datetime] = None


class SuperAdminSessionResponse(BaseSchema):
    id: uuid.UUID
    super_admin_id: uuid.UUID
    ip_address: Optional[str] = None
    expire_at: datetime
    derniere_activite: datetime
