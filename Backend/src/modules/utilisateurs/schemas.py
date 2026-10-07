"""Schémas du module Utilisateurs."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import ConfigDict, Field, field_validator

from src.common.schemas import BaseSchema


class UtilisateurCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., max_length=150)
    mot_de_passe: str = Field(..., min_length=10, max_length=128)
    prenom: str = Field(..., min_length=1, max_length=100)
    nom: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=2, max_length=50)
    telephone: Optional[str] = Field(None, max_length=30)
    cabinet_id: Optional[uuid.UUID] = None

    @field_validator("email")
    @classmethod
    def _email_normalise(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("Adresse email invalide.")
        return v

    @field_validator("role")
    @classmethod
    def _role_normalise(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("mot_de_passe")
    @classmethod
    def mot_de_passe_solide(cls, v: str) -> str:
        """
        Un mot de passe trop simple sur un compte qui donne accès au dossier
        médical est un incident, pas une gêne.
        """
        if v.isdigit() or v.isalpha():
            raise ValueError(
                "Le mot de passe doit mélanger lettres et chiffres."
            )
        return v


class UtilisateurUpdate(BaseSchema):
    """Modification de profil, de rôle ou d'état. Jamais de mot de passe."""

    model_config = ConfigDict(extra="forbid")

    prenom: Optional[str] = Field(None, min_length=1, max_length=100)
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    telephone: Optional[str] = Field(None, max_length=30)
    role: Optional[str] = Field(None, min_length=2, max_length=50)
    actif: Optional[bool] = None
    cabinet_id: Optional[uuid.UUID] = None

    @field_validator("role")
    @classmethod
    def _role_normalise(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v is not None else None


class UtilisateurResponse(BaseSchema):
    id: uuid.UUID
    email: str
    prenom: str
    nom: str
    #: Nom du rôle : c'est lui qui porte les permissions, pas le compte.
    role: str
    actif: bool
    telephone: Optional[str] = None
    cabinet_id: Optional[uuid.UUID] = None
    cabinet_nom: Optional[str] = None
    deux_facteurs: bool = False
    dernier_login: Optional[datetime] = None
    #: Vrai si le compte porte un profil professionnel (Chantier 5).
    a_profil_professionnel: bool = False
    numero_ordre: Optional[str] = None
    created_at: Optional[datetime] = None


class MotDePasseTemporaireResponse(BaseSchema):
    """
    Mot de passe temporaire, renvoyé **une seule fois**.

    Le serveur n'en conserve que l'empreinte : il ne peut donc pas le
    redonner. L'interface doit le dire explicitement, sinon l'utilisateur
    croira avoir saisir un mot de passe définitif.
    """

    temporaire: str
    avertissement: str = (
        "Communiquez ce mot de passe à l'utilisateur. "
        "Il ne sera plus jamais affiché : seul son empreinte est conservée."
    )


class SessionUtilisateurResponse(BaseSchema):
    id: uuid.UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    est_revoque: bool
    expire_at: datetime
    derniere_activite: datetime
    expiree: bool


class UtilisateurDetailResponse(UtilisateurResponse):
    sessions: List[SessionUtilisateurResponse] = []
