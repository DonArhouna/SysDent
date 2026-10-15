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
    #: Double authentification : active, méthodes utilisables, obligatoire
    #: pour le rôle (dans ce cas « Mon compte » ne propose pas de la retirer).
    deux_facteurs: bool = False
    methodes_2fa: List[str] = []
    deux_facteurs_obligatoire: bool = False
    #: Logo du cabinet (adresse publique relative à l'API), s'il en a un.
    cabinet_logo_url: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Sécurité des comptes : activation, étapes de connexion, 2FA
# ─────────────────────────────────────────────────────────────────────────────


class LoginEtapeResponse(BaseSchema):
    """
    Issue d'une connexion, ou d'une étape franchie.

    `etape` dit quoi faire ensuite :
    - `session` : connecté (jetons présents) ;
    - `changement_mot_de_passe` : mot de passe temporaire à remplacer ;
    - `deux_facteurs` : code de vérification à saisir ;
    - `enrolement_2fa` : double authentification à configurer (rôle concerné).
    """

    etape: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    tenant_id: Optional[str] = None
    jeton_etape: Optional[str] = None
    methodes: List[str] = []
    expiration_secondes: Optional[int] = None
    # Session ouverte sans 2FA, pour un rôle où elle est facultative.
    deux_facteurs_recommande: bool = False
    # Rendus UNE fois, à l'activation de la 2FA.
    codes_secours: Optional[List[str]] = None


class JetonActivationRequest(BaseSchema):
    jeton: str = Field(..., description="Jeton reçu dans le lien d'activation")


class ActivationRequest(BaseSchema):
    jeton: str
    mot_de_passe: str = Field(..., min_length=8, max_length=128)


class ActivationInfoResponse(BaseSchema):
    email: str
    prenom: str
    nom: str
    # Repères du cabinet, pour que la personne sache où elle entre.
    cabinet_nom: Optional[str] = None
    cabinet_logo_url: Optional[str] = None


class EtapeJetonRequest(BaseSchema):
    jeton_etape: str


class EtapeMotDePasseRequest(BaseSchema):
    jeton_etape: str
    nouveau: str = Field(..., min_length=8, max_length=128)


class EtapeCodeRequest(BaseSchema):
    jeton_etape: str
    code: str = Field(..., min_length=6, max_length=12)


class ActivationDeuxFacteursRequest(BaseSchema):
    """`jeton_etape` pendant la connexion ; absent quand on est déjà connecté."""

    jeton_etape: Optional[str] = None
    methode: str = Field(..., pattern="^(totp|email)$")
    code: str = Field(..., min_length=6, max_length=12)


class PreparationTotpResponse(BaseSchema):
    secret: str
    uri: str


class EnvoiCodeResponse(BaseSchema):
    destinataire: str
    expiration_secondes: int


class CodesSecoursResponse(BaseSchema):
    codes_secours: List[str]
