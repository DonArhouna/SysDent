"""
Schémas Pydantic de la console PLATEFORME — Phase A.

Conventions reprises de `src/common/schemas.py` pour que le futur frontend ait
un seul réflexe : enveloppe `{success, message, data}` pour le cas nominal,
`{success:false, error:{code, message, details, request_id}}` pour l'erreur, et
pagination `{items, meta}` pour les listes.
"""

import uuid
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import EmailStr, Field

from src.common.schemas import BaseSchema


# ==============================================================================
# AUTHENTIFICATION
# ==============================================================================


class PlatformLoginRequest(BaseSchema):
    email: EmailStr = Field(..., description="Adresse e-mail du compte de la console")
    mot_de_passe: str = Field(..., min_length=1, max_length=200)


class Challenge2FARequest(BaseSchema):
    jeton_challenge: str = Field(
        ..., description="Défi reçu à l'étape précédente (valable 5 minutes, à usage unique)"
    )
    code: str = Field(
        ..., min_length=6, max_length=8, description="Code TOTP à 6 chiffres fourni par l'application"
    )


class PlatformRefreshRequest(BaseSchema):
    refresh_token: str = Field(..., description="Refresh token de la session courante")


class PlatformTokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Durée de validité de l'access token, en secondes")
    refresh_expires_in: int = Field(..., description="Durée de validité du refresh token, en secondes")


class LoginChallengeResponse(BaseSchema):
    """Réponse intermédiaire : le mot de passe est juste, le 2FA reste à faire."""

    deux_facteurs_requis: bool = True
    activation_requise: bool = Field(
        False,
        description="Vrai si le second facteur doit encore être activé : le code saisi "
        "à cette étape l'active et ouvre la session dans le même mouvement "
        "(première connexion)",
    )
    jeton_challenge: str
    expiration_secondes: int


class PlatformProfilResponse(BaseSchema):
    id: uuid.UUID
    email: EmailStr
    prenom: str
    nom: str
    telephone: Optional[str] = None
    statut: str
    roles: List[str]
    permissions: List[str]
    deux_facteurs_actif: bool
    dernier_login: Optional[datetime] = None
    cree_le: datetime


class Activation2FAResponse(BaseSchema):
    secret: str = Field(..., description="Secret TOTP base32 — affiché UNE seule fois")
    uri: str = Field(..., description="URI otpauth:// à encoder en QR Code")
    instruction: str


class Confirmer2FARequest(BaseSchema):
    code: str = Field(..., min_length=6, max_length=8, description="Code TOTP à 6 chiffres")


# ==============================================================================
# UTILISATEURS PLATEFORME
# ==============================================================================


class UtilisateurPlateformeCreate(BaseSchema):
    email: EmailStr
    prenom: str = Field(..., min_length=1, max_length=80)
    nom: str = Field(..., min_length=1, max_length=80)
    mot_de_passe: str = Field(
        ...,
        min_length=8,
        description="Mot de passe initial — doit respecter la politique de sécurité (12 caractères, "
        "majuscule, minuscule, chiffre, caractère spécial)",
    )
    roles: List[str] = Field(
        ..., min_length=1, description="Codes de rôles (platform roles) à attribuer"
    )
    telephone: Optional[str] = None
    activer_2fa: bool = Field(
        True, description="Générer immédiatement le secret TOTP à activer (recommandé : true)"
    )


class UtilisateurPlateformeUpdate(BaseSchema):
    prenom: Optional[str] = Field(None, max_length=80)
    nom: Optional[str] = Field(None, max_length=80)
    telephone: Optional[str] = None
    roles: Optional[List[str]] = Field(None, min_length=1)
    motif: Optional[str] = Field(None, max_length=500, description="Motif de la modification (journalisé)")


class UtilisateurPlateformeResponse(BaseSchema):
    id: uuid.UUID
    email: EmailStr
    prenom: str
    nom: str
    telephone: Optional[str] = None
    statut: str
    roles: List[str]
    deux_facteurs_actif: bool
    dernier_login: Optional[datetime] = None
    tentatives_echouees: int = 0
    verrouille_jusqua: Optional[datetime] = None
    motif_desactivation: Optional[str] = None
    cree_le: datetime
    modifie_le: datetime


class DesactivationRequest(BaseSchema):
    motif: str = Field(..., min_length=5, max_length=500, description="Motif obligatoire (journalisé)")


class SuppressionRequest(BaseSchema):
    motif: str = Field(..., min_length=5, max_length=500, description="Motif obligatoire (journalisé)")
    confirmation: str = Field(
        ...,
        description="Doit valoir exactement 'SUPPRIMER' : double confirmation explicite",
    )


class ReinitialisationAccesRequest(BaseSchema):
    motif: str = Field(..., min_length=5, max_length=500)


class ChangementMotDePasseRequest(BaseSchema):
    ancien: str = Field(..., min_length=1)
    nouveau: str = Field(..., min_length=8)


class RolePlateformeResponse(BaseSchema):
    id: uuid.UUID
    code: str
    libelle: str
    description: Optional[str] = None
    niveau_hierarchie: int
    systeme: bool
    permissions: List[str]
    nb_utilisateurs: int


class PermissionPlateformeResponse(BaseSchema):
    code: str
    ressource: str
    action: str
    description: str
    sensible: bool


class CreationUtilisateurResponse(BaseSchema):
    utilisateur: UtilisateurPlateformeResponse
    activation_2fa: Optional[Activation2FAResponse] = Field(
        None, description="À transmettre à l'utilisateur : le secret n'est plus jamais renvoyé ensuite"
    )


class DetailUtilisateurResponse(BaseSchema):
    utilisateur: UtilisateurPlateformeResponse
    permissions: List[str]
    sessions_actives: int


class ErrorDetailResponse(BaseSchema):
    """Modèle documenté pour que le frontend puisse typer ses erreurs."""

    code: str = Field(..., examples=["QUOTA_EXCEEDED"])
    message: str
    details: Optional[Dict] = None
    request_id: Optional[str] = None

# ==============================================================================
# TENANTS — CYCLE DE VIE (Phase B)
# ==============================================================================


class TenantCreate(BaseSchema):
    """Création et provisionnement complets d'un cabinet (Phase B.4)."""

    nom: str = Field(..., min_length=2, max_length=150, description="Nom commercial du cabinet")
    ninea: Optional[str] = Field(None, max_length=50, description="Numéro d'enregistrement (unique)")
    adresse_siege: Optional[str] = None
    ville: Optional[str] = "Dakar"
    pays: Optional[str] = "Sénégal"
    telephone: Optional[str] = None
    site_web: Optional[str] = None
    logo_url: Optional[str] = None
    langue: str = Field("fr", max_length=5)
    fuseau_horaire: str = Field("Africa/Dakar", max_length=50)
    devise: str = Field("XOF", min_length=3, max_length=3)

    admin_email: EmailStr = Field(..., description="E-mail du premier administrateur")
    admin_prenom: str = Field(..., min_length=1, max_length=80)
    admin_nom: str = Field(..., min_length=1, max_length=80)

    statut_initial: str = Field(
        "ACTIF", description="ESSAI pour un cabinet en période d'essai, ACTIF sinon"
    )
    plan_code: Optional[str] = Field(
        None, description="Plan souscrit ; absent = plan par défaut"
    )
    jours_essai: int = Field(14, ge=1, le=365, description="Durée d'essai si ESSAI")
    motif: Optional[str] = Field(None, max_length=500)


class TenantUpdate(BaseSchema):
    nom: Optional[str] = Field(None, min_length=2, max_length=150)
    ninea: Optional[str] = Field(None, max_length=50)
    adresse_siege: Optional[str] = None
    ville: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[EmailStr] = None
    site_web: Optional[str] = None
    logo_url: Optional[str] = None
    pays: Optional[str] = None
    langue: Optional[str] = None
    fuseau_horaire: Optional[str] = None
    devise: Optional[str] = Field(None, min_length=3, max_length=3)
    motif: Optional[str] = Field(None, max_length=500)


class TransitionStatut(BaseSchema):
    motif: str = Field(
        ..., min_length=5, max_length=1000, description="Motif OBLIGATOIRE, journalisé"
    )


class Archivage(BaseSchema):
    archiver: bool = Field(..., description="true pour archiver logiquement, false pour rétablir")
    motif: str = Field(..., min_length=5, max_length=1000)


class SuppressionTenant(BaseSchema):
    motif: str = Field(..., min_length=10, max_length=1000, description="Motif obligatoire (journalisé)")
    confirmation: str = Field(
        ..., description="Doit valoir exactement 'SUPPRIMER DEFINITIVEMENT'"
    )
    retention_validee: bool = Field(
        ..., description="Confirmation que la période de rétention a été respectée"
    )


class TenantResponse(BaseSchema):
    tenant_id: uuid.UUID
    nom: str
    ville: Optional[str] = None
    pays: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    statut: str
    statut_technique: Optional[str] = None
    archivable: bool = False
    langue: str = "fr"
    devise: str = "XOF"
    fuseau_horaire: str = "Africa/Dakar"
    date_creation: Optional[str] = None
    date_debut_essai: Optional[str] = None
    date_fin_essai: Optional[str] = None
    db_name: Optional[str] = None
    transitions_possibles: List[str] = []


class TenantDetailResponse(TenantResponse):
    adresse_siege: Optional[str] = None
    site_web: Optional[str] = None
    logo_url: Optional[str] = None
    ninea: Optional[str] = None
    abonnement: Optional[dict] = None


class TenantCreationResponse(BaseSchema):
    tenant: TenantResponse
    etapes: List[str] = Field(..., description="Étapes réellement accomplies")
    gabarits_appliques: dict = Field(
        default_factory=dict, description="Gabarits utilisés et leur version"
    )
    invitation_admin_envoyee: bool


class HistoriqueStatutEntry(BaseSchema):
    horodatage: datetime
    statut_precedent: str
    statut_nouveau: str
    motif: str
    auteur_email: str
    ip_address: Optional[str] = None


# ==============================================================================
# PLANS, ABONNEMENTS, FACTURES (Phase C)
# ==============================================================================


class PlanCreate(BaseSchema):
    code: str = Field(..., min_length=2, max_length=40, description="Code unique, normalisé en majuscules")
    nom: str = Field(..., min_length=2, max_length=80)
    description: Optional[str] = None
    prix: float = Field(..., ge=0, description="Prix HT par période")
    periodicite: str = Field("MENSUEL", description="MENSUEL | ANNUEL | GRATUIT")
    devise: str = Field("XOF", min_length=3, max_length=3)
    quotas: dict = Field(
        default_factory=dict,
        description="{'utilisateurs': 5, 'sites': 1, 'praticiens': 2, "
        "'stockage_octets': 1073741824, 'sms_par_mois': 200}",
    )
    features: dict = Field(
        default_factory=dict, description="{'stock': true, 'sms': true, 'rapports': true}"
    )
    jours_essai: int = Field(14, ge=0, le=365)
    plan_defaut: bool = False


class PlanUpdate(BaseSchema):
    nom: Optional[str] = None
    description: Optional[str] = None
    prix: Optional[float] = Field(None, ge=0)
    periodicite: Optional[str] = None
    devise: Optional[str] = None
    quotas: Optional[dict] = None
    features: Optional[dict] = None
    jours_essai: Optional[int] = Field(None, ge=0, le=365)
    actif: Optional[bool] = None
    motif: Optional[str] = Field(None, max_length=500)


class PlanResponse(BaseSchema):
    id: uuid.UUID
    code: str
    nom: str
    description: Optional[str] = None
    prix: str
    periodicite: str
    devise: str
    quotas: dict
    features: dict
    version: int
    actif: bool
    plan_defaut: bool
    jours_essai: int


class PlanRevisionResponse(BaseSchema):
    version: int
    instantane: dict
    motif: Optional[str] = None
    auteur: str
    created_at: datetime


class AbonnementResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    numero: str
    plan_id: Optional[uuid.UUID] = None
    plan: Optional[str] = None
    plan_nom: Optional[str] = None
    statut: str
    plan_fige: dict
    date_debut: datetime
    date_fin: Optional[datetime] = None
    date_debut_essai: Optional[datetime] = None
    date_fin_essai: Optional[datetime] = None
    renouvellement_auto: bool


class ChangementPlan(BaseSchema):
    plan_code: str = Field(..., description="Code du nouveau plan")
    motif: Optional[str] = Field(None, max_length=500)


class FacturePlateformeCreate(BaseSchema):
    lignes: List[dict] = Field(
        ..., min_length=1,
        description="[{ 'libelle': str, 'quantite': int, 'prix_unitaire': float, 'montant': float }]",
    )
    periode_debut: Optional[date] = None
    periode_fin: Optional[date] = None
    date_echeance: Optional[date] = None
    statut: str = Field("BROUILLON", description="BROUILLON | EMISE")
    notes: Optional[str] = None


class FacturePlateformeResponse(BaseSchema):
    id: uuid.UUID
    numero: str
    tenant_id: uuid.UUID
    lignes: list
    montant: str
    devise: str
    statut: str
    periode_debut: Optional[date] = None
    periode_fin: Optional[date] = None
    date_emission: Optional[date] = None
    date_echeance: Optional[date] = None
    date_paiement: Optional[date] = None
    reference_externe: Optional[str] = None
    notes: Optional[str] = None


class QuotaResumeResponse(BaseSchema):
    plan: Optional[str] = None
    plan_nom: Optional[str] = None
    illimite: bool = True
    releve_jour: Optional[str] = None
    ressources: List[dict] = []


# ==============================================================================
# ACCÈS SUPPORT (Phase D)
# ==============================================================================


class AccesSupportCreate(BaseSchema):
    """Demande d'accès au dossier d'un cabinet par un agent de la plateforme."""

    motif: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description=(
            "Obligatoire. Raison de l intervention, telle qu'elle sera lue dans "
            "le journal du cabinet. En écriture, 40 caractères minimum."
        ),
        examples=["Ticket SUP-4821 — le praticien ne peut plus créer de rendez-vous"],
    )
    ticket: Optional[str] = Field(
        None, max_length=80, description="Référence du ticket, si elle existe"
    )
    lecture_seule: bool = Field(
        True,
        description=(
            "False demande une élévation : permission "
            "`platform.support.grant_elevated` + motif renforcé + "
            "PLATFORM_SUPPORT_ELEVATION_ABILITEE=true."
        ),
    )


class SupportTokenResponse(BaseSchema):
    """Jeton d'accès support. À traiter comme un secret : il n'est pas renewable."""

    id: uuid.UUID
    jeton: str
    expire_le: datetime
    duree_minutes: int
    lecture_seule: bool
    administrateur_notifie: bool = False


class AccesSupportResponse(BaseSchema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_email: str
    motif: str
    ticket: Optional[str] = None
    lecture_seule: bool
    statut: str
    expire_le: datetime
    revoque_at: Optional[datetime] = None
    motif_revoque: Optional[str] = None
    administrateur_notifie: bool = False
    cree_le: datetime


# ==============================================================================
# SUPERVISION, JOURNAL ET ANNONCES (Phase E)
# ==============================================================================


class StatsGlobalesResponse(BaseSchema):
    total_cabinets: int = 0
    par_statut: Dict[str, int] = {}
    par_formule: Dict[str, int] = {}
    croissance_mensuelle: List[dict] = []
    inactifs_30j: List[dict] = []
    proches_du_quota: List[dict] = []


class StatsTenantResponse(BaseSchema):
    tenant_id: uuid.UUID
    releve: Optional[dict] = None
    serie: List[dict] = []


class AuditEntryResponse(BaseSchema):
    id: uuid.UUID
    horodatage: datetime
    acteur_email: Optional[str] = None
    acteur_id: Optional[uuid.UUID] = None
    action: str
    type_cible: Optional[str] = None
    cible_id: Optional[str] = None
    tenant_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    motif: Optional[str] = None
    avant: Optional[dict] = None
    apres: Optional[dict] = None


class AnnonceCreate(BaseSchema):
    titre: str = Field(..., min_length=3, max_length=150)
    message: str = Field(..., min_length=3, max_length=2000)
    type_annonce: str = Field("INFO", description="INFO | MAINTENANCE | NOUVEAUTE | INCIDENT")
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    plans_cibles: List[str] = []
    tenants_cibles: List[uuid.UUID] = []


class AnnonceResponse(BaseSchema):
    id: uuid.UUID
    titre: str
    message: str
    type_annonce: str
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    active: bool
    plans_cibles: List[str] = []
    tenants_cibles: List[str] = []
    cree_par: Optional[str] = None
    cree_le: datetime


# ==============================================================================
# ONBOARDING PUBLIC (Phase F)
# ==============================================================================


class InscriptionCreate(BaseSchema):
    """Formulaire d'inscription publique. Tous les messages d'erreur sont génériques."""

    nom_cabinet: str = Field(..., min_length=2, max_length=150)
    admin_prenom: str = Field(..., min_length=1, max_length=100)
    admin_nom: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    mot_de_passe: str = Field(..., min_length=12, max_length=128)
    telephone: Optional[str] = Field(None, max_length=30)
    ville: Optional[str] = Field(None, max_length=100)
    pays: str = Field("Sénégal", max_length=100)
    plan_code: Optional[str] = Field(
        None, description="Formule d'essai ; le plan par défaut si absent"
    )
    jours_essai: Optional[int] = Field(None, ge=1, le=90)
    site_web_trap: Optional[str] = Field(
        None,
        max_length=200,
        description=(
            "Champ-piège anti-robot, masqué en CSS côté client. Un humain ne le "
            "remplit jamais ; un robot le remplit. À laisser vide."
        ),
    )


class InscriptionResponse(BaseSchema):
    inscription_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    statut: str


class VerificationEmailRequest(BaseSchema):
    jeton: str = Field(..., min_length=10, max_length=200)


class OnboardingEtatResponse(BaseSchema):
    tenant_id: str
    terminees: int
    total: int
    progression: int
    etapes: List[dict] = []
