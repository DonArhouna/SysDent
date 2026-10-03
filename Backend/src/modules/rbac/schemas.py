from typing import List, Optional
from pydantic import Field
from src.common.schemas import BaseSchema


class RoleCreate(BaseSchema):
    nom: str = Field(..., min_length=2, max_length=50, description="Nom unique du rôle (ex: SECRETAIRE_NUIT)")
    description: Optional[str] = Field(None, max_length=255)
    niveau_hierarchie: int = Field(3, ge=1, le=10, description="1 = plus élevé (ADMIN_CABINET)")


class PermissionGrant(BaseSchema):
    module: str = Field(..., min_length=2, max_length=50, description="Module (PATIENTS, CONSULTATIONS...)")
    action: str = Field(..., min_length=2, max_length=50, description="READ, CREATE, UPDATE, DELETE, EXPORT, SIGN")

    @classmethod
    def parse(cls, permission: str) -> "PermissionGrant":
        """Construit depuis la chaîne 'MODULE:ACTION' renvoyée par l'API."""
        module, _, action = permission.partition(":")
        return cls(module=module, action=action)


class RoleResponse(BaseSchema):
    id: str
    nom: str
    description: Optional[str] = None
    niveau_hierarchie: int
    permissions: List[str] = []
    nb_utilisateurs: int = 0


class PermissionResponse(BaseSchema):
    module: str
    action: str
    description: Optional[str] = None
