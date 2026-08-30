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

    def __init__(self, message: str = "Vous n'avez pas les permissions nécessaires pour accéder à cette ressource."):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403,
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
