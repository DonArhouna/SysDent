from typing import Any, Dict, Optional


class AppException(Exception):
    """Exception de base pour toutes les erreurs applicatives du système SysDent."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundException(AppException):
    """Levée lorsqu'une ressource demandée n'existe pas."""

    def __init__(self, entity_name: str, entity_id: Any, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{entity_name} avec l'identifiant '{entity_id}' introuvable.",
            code=f"{entity_name.upper()}_NOT_FOUND",
            status_code=404,
            details=details or {"entity": entity_name, "id": str(entity_id)},
        )


class BusinessRuleViolationException(AppException):
    """Levée lorsqu'une règle métier est enfreinte (ex: suppression d'une facture déjà payée)."""

    def __init__(self, message: str, code: str = "BUSINESS_RULE_VIOLATION", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code=code,
            status_code=422,
            details=details,
        )


class AuthenticationException(AppException):
    """Levée lors d'un échec d'authentification ou token invalide."""

    def __init__(self, message: str = "Authentification requise ou identifiants invalides.", code: str = "AUTHENTICATION_FAILED"):
        super().__init__(
            message=message,
            code=code,
            status_code=401,
        )


class PermissionDeniedException(AppException):
    """Levée lorsque l'utilisateur n'a pas les droits requis pour effectuer l'action."""

    def __init__(
        self,
        message: str = "Vous n'avez pas les permissions nécessaires pour accéder à cette ressource.",
        code: str = "PERMISSION_DENIED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=403,
            details=details,
        )


class TenantNotFoundException(AppException):
    """Levée lorsque le dossier/société demandé n'existe pas ou n'est pas provisionné."""

    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Le dossier cabinet/société '{tenant_id}' est introuvable ou inactif.",
            code="TENANT_NOT_FOUND",
            status_code=404,
            details={"tenant_id": tenant_id},
        )


class TenantConnectionException(AppException):
    """Levée lors d'une impossibilité de connexion à la base de données d'un cabinet."""

    def __init__(self, tenant_id: str, original_error: Optional[str] = None):
        super().__init__(
            message=f"Impossible de se connecter à la base de données du cabinet '{tenant_id}'.",
            code="TENANT_DB_CONNECTION_FAILED",
            status_code=503,
            details={"tenant_id": tenant_id, "error": original_error},
        )


class TooManyRequestsException(AppException):
    """Levée lorsqu'un client dépasse une limite de débit (force brute sur le login)."""

    def __init__(self, message: str, retry_after_seconds: int):
        super().__init__(
            message=message,
            code="TOO_MANY_REQUESTS",
            status_code=429,
            details={"retry_after_seconds": retry_after_seconds},
        )


class InvalidTokenException(AppException):
    """Levée lorsqu'un jeton de rafraîchissement est inconnu, révoqué ou expiré."""

    def __init__(self, message: str = "Session expirée ou révoquée. Veuillez vous reconnecter."):
        super().__init__(
            message=message,
            code="INVALID_REFRESH_TOKEN",
            status_code=401,
        )


class InvalidStateException(AuthenticationException):
    """
    Levée lorsque l'état de la plateforme interdit l'opération.

    Exemple : tenter de supprimer le dernier Super Admin, ou de supprimer une
    société qui porte des cabinets en production.
    """

    def __init__(self, message: str, code: str = "INVALID_STATE"):
        super().__init__(message=message, code=code)


class QuotaExceededException(AppException):
    """
    Levée lorsqu'une ressource du plan est épuisée (Phase C.3).

    Le code d'erreur est STABLE et PUBLIC (`QUOTA_EXCEEDED`) et la réponse
    contient la ressource concernée et les deux nombres : c'est ce qui permet à
    l'interface cliente d'afficher « Vous avez atteint la limite de 5
    utilisateurs de votre formule » au lieu d'un message technique. Le message
    reste en français lisible, jamais un identifiant interne.
    """

    def __init__(self, ressource: str, limite: int, utilise: int, plan_code: str = ""):
        super().__init__(
            message=f"Limite du plan atteinte pour « {ressource} » ({utilise}/{limite}).",
            code="QUOTA_EXCEEDED",
            status_code=403,
            details={
                "ressource": ressource,
                "limite": limite,
                "utilise": utilise,
                "plan": plan_code,
            },
        )


class InvalidTransitionException(BusinessRuleViolationException):
    """
    Levée lorsqu'une transition de statut tenant n'est pas autorisée (Phase B.2).

    Le message nomme l'état courant, l'état demandé et la raison du refus : un
    opérateur qui reçoit « transition ESSAI → RÉSOLIE non autorisée » sait quoi
    corriger, contrairement à un « 422 » nu.
    """

    def __init__(
        self,
        statut_actuel: str,
        statut_cible: str,
        raison: str,
        transitions_possibles: Optional[list] = None,
    ):
        details: Dict[str, Any] = {
            "statut_actuel": statut_actuel,
            "statut_cible": statut_cible,
            "raison": raison,
        }
        if transitions_possibles is not None:
            details["transitions_possibles"] = list(transitions_possibles)
        super().__init__(
            message=f"Transition {statut_actuel} → {statut_cible} non autorisée : {raison}.",
            code="TRANSITION_STATUT_NON_AUTORISEE",
            details=details,
        )


class PlatformFeatureException(AppException):
    """
    Levée lorsqu'une fonctionnalité est désactivée pour le plan du tenant
    (Phase C.4, drapeaux de fonctionnalités).

    403 et non 404 : la ressource existe, c'est l'abonnement qui ne la couvre pas.
    Le frontend peut ainsi proposer une mise à niveau au lieu d'un écran vide.
    """

    def __init__(self, feature: str, plan_code: str = ""):
        super().__init__(
            message=f"La fonctionnalité '{feature}' n'est pas incluse dans votre formule.",
            code="FEATURE_NON_ACTIVEE",
            status_code=403,
            details={"feature": feature, "plan": plan_code},
        )
