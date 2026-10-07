"""
Catalogue de permissions et matrice des rôles de la console PLATEFORME.

Espace de noms `platform.<ressource>.<action>`, volontairement différent du
`MODULE:ACTION` des cabinets (`src/common/permissions.py`). Deux catalogues qui
ne se ressemblent pas rendent impossible qu'un droit lu dans l'un soit
interprété comme un droit de l'autre : c'est la première barrière de l'étanchéité
des permissions, avant même létanchéité des jetons.

Deux règles de conception retenues :

- **Aucun rôle n'a de droit implicite.** Contrairement au client où `ADMIN_CABINET`
  court-circuite `require_permissions`, ici le rôle `SUPER_ADMIN_PLATEFORME` reçoit
  ses droits par la matrice comme les autres. Un droit « open sesame » est un
  droit qu'on ne peut pas retirer à personne, et une fuite de ce compte est
  irrattrapable.
- **Les droits sensibles sont nommés, pas déduits.** `platform.tenants.delete`
  (suppression DÉFINITIVE d'un dossier) est distinct de
  `platform.tenants.archive` (archivage logique, réversible).
"""

from typing import Dict, FrozenSet, List, Tuple

Permission = Tuple[str, str]  # (ressource, action)

# ---------------------------------------------------------------------------
# Ressources
# ---------------------------------------------------------------------------
R_TENANTS = "tenants"
R_USERS = "users"
R_PLANS = "plans"
R_SUBSCRIPTIONS = "subscriptions"
R_BILLING = "billing"
R_SUPPORT = "support"
R_AUDIT = "audit"
R_STATS = "stats"
R_HEALTH = "health"
R_ANNOUNCEMENTS = "announcements"
R_TEMPLATES = "templates"
R_ONBOARDING = "onboarding"
R_MIGRATIONS = "migrations"
R_EXPORTS = "exports"

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
A_READ = "read"
A_CREATE = "create"
A_UPDATE = "update"
A_ARCHIVE = "archive"
A_SUSPEND = "suspend"
A_ACTIVATE = "activate"
A_TERMINATE = "terminate"
A_DELETE = "delete"
A_EXPORT = "export"
A_RUN = "run"
A_GRANT = "grant"
A_REVOKE = "revoke"
A_ASSIGN = "assign"
A_RESET = "reset"
A_DEACTIVATE = "deactivate"
A_WRITE = "write"


def p(ressource: str, action: str) -> Permission:
    return (ressource, action)


def format_permission(ressource: str, action: str) -> str:
    """Chaîne attendue dans le JWT plateforme : `platform.<ressource>.<action>`."""
    return f"platform.{ressource}.{action}"


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
CATALOGUE_PERMISSIONS: List[Permission] = [
    # ── Tenants (cycle de vie) ───────────────────────────────────────────────
    p(R_TENANTS, A_READ),
    p(R_TENANTS, A_CREATE),
    p(R_TENANTS, A_UPDATE),
    p(R_TENANTS, A_ARCHIVE),
    p(R_TENANTS, A_SUSPEND),
    p(R_TENANTS, A_ACTIVATE),
    p(R_TENANTS, A_TERMINATE),
    # Suppression DÉFINITIVE : irrécversible, droit à part entière.
    p(R_TENANTS, A_DELETE),
    p(R_TENANTS, A_EXPORT),
    # ── Utilisateurs plateforme ──────────────────────────────────────────────
    p(R_USERS, A_READ),
    p(R_USERS, A_CREATE),
    p(R_USERS, A_UPDATE),
    p(R_USERS, A_DEACTIVATE),
    p(R_USERS, A_DELETE),
    p(R_USERS, A_ASSIGN),  # attribuer / retirer un rôle
    p(R_USERS, A_RESET),  # réinitialiser l'accès (2FA, mot de passe)
    # ── Accès support ────────────────────────────────────────────────────────
    p(R_SUPPORT, A_READ),  # voir les accès actifs
    p(R_SUPPORT, A_GRANT),  # émettre un jeton lecture seule
    p(R_SUPPORT, A_REVOKE),  # révoquer un accès
    # Élévation : autorise un accès support NON lecture seule. Séparée de `grant`
    # pour qu'un agent support puisse diagnostiquer sans pouvoir écrire.
    p(R_SUPPORT, "grant_elevated"),
    # ── Plans / abonnements / facturation ────────────────────────────────────
    p(R_PLANS, A_READ),
    p(R_PLANS, A_WRITE),
    p(R_SUBSCRIPTIONS, A_READ),
    p(R_SUBSCRIPTIONS, A_WRITE),
    p(R_BILLING, A_READ),
    p(R_BILLING, A_WRITE),
    # ── Supervision ──────────────────────────────────────────────────────────
    p(R_STATS, A_READ),
    p(R_AUDIT, A_READ),
    p(R_AUDIT, A_EXPORT),
    p(R_HEALTH, A_READ),
    p(R_ANNOUNCEMENTS, A_READ),
    p(R_ANNOUNCEMENTS, A_WRITE),
    # ── Outillage éditeur ────────────────────────────────────────────────────
    p(R_TEMPLATES, A_READ),
    p(R_TEMPLATES, A_WRITE),
    p(R_MIGRATIONS, A_READ),
    p(R_MIGRATIONS, A_RUN),
    p(R_EXPORTS, A_READ),
    p(R_EXPORTS, A_CREATE),
    p(R_ONBOARDING, A_READ),
]

#: Permissions « sensibles » : elles sont journalisées avec le détail avant/après
#: ET signalées dans l'export d'audit. Une permission non listée ici est
#: journalisée elle aussi, mais sans emphase particulière.
PERMISSIONS_SENSIBLES: FrozenSet[str] = frozenset(
    {
        format_permission(R_USERS, A_CREATE),
        format_permission(R_USERS, A_DEACTIVATE),
        format_permission(R_USERS, A_DELETE),
        format_permission(R_USERS, A_ASSIGN),
        format_permission(R_USERS, A_RESET),
        format_permission(R_TENANTS, A_DELETE),
        format_permission(R_TENANTS, A_TERMINATE),
        format_permission(R_TENANTS, A_SUSPEND),
        format_permission(R_TENANTS, A_CREATE),
        format_permission(R_SUPPORT, A_GRANT),
        format_permission(R_SUPPORT, "grant_elevated"),
        format_permission(R_SUPPORT, A_REVOKE),
        format_permission(R_MIGRATIONS, A_RUN),
        format_permission(R_EXPORTS, A_CREATE),
        format_permission(R_PLANS, A_WRITE),
        format_permission(R_BILLING, A_WRITE),
    }
)

DESCRIPTIONS_PERMISSIONS: Dict[Permission, str] = {
    p(R_TENANTS, A_READ): "Consulter le registre des cabinets et leur fiche",
    p(R_TENANTS, A_CREATE): "Créer et provisionner un cabinet",
    p(R_TENANTS, A_UPDATE): "Modifier les informations administratives d'un cabinet",
    p(R_TENANTS, A_ARCHIVE): "Archiver logiquement un cabinet (réversible)",
    p(R_TENANTS, A_SUSPEND): "Suspendre l'accès d'un cabinet",
    p(R_TENANTS, A_ACTIVATE): "Réactiver un cabinet suspendu ou en essai",
    p(R_TENANTS, A_TERMINATE): "Résilier un cabinet (irréversible côté métier)",
    p(R_TENANTS, A_DELETE): "Supprimer DÉFINITIVEMENT le dossier d'un cabinet",
    p(R_TENANTS, A_EXPORT): "Demander l'export d'un dossier client",
    p(R_USERS, A_READ): "Consulter les comptes de la console",
    p(R_USERS, A_CREATE): "Créer un compte de la console",
    p(R_USERS, A_UPDATE): "Modifier un compte de la console",
    p(R_USERS, A_DEACTIVATE): "Désactiver un compte de la console",
    p(R_USERS, A_DELETE): "Supprimer un compte de la console",
    p(R_USERS, A_ASSIGN): "Attribuer ou retirer un rôle de la console",
    p(R_USERS, A_RESET): "Réinitialiser le second facteur ou le mot de passe d'un compte",
    p(R_SUPPORT, A_READ): "Consulter les accès support en cours",
    p(R_SUPPORT, A_GRANT): "Ouvrir un accès support en lecture seule",
    p(R_SUPPORT, A_REVOKE): "Révoquer un accès support",
    p(R_SUPPORT, "grant_elevated"): "Ouvrir un accès support avec des droits d'écriture",
    p(R_PLANS, A_READ): "Consulter les plans et leurs quotas",
    p(R_PLANS, A_WRITE): "Créer ou modifier un plan",
    p(R_SUBSCRIPTIONS, A_READ): "Consulter les abonnements",
    p(R_SUBSCRIPTIONS, A_WRITE): "Créer ou modifier un abonnement",
    p(R_BILLING, A_READ): "Consulter les factures plateforme",
    p(R_BILLING, A_WRITE): "Créer ou modifier une facture plateforme",
    p(R_STATS, A_READ): "Consulter les statistiques d'usage agrégées",
    p(R_AUDIT, A_READ): "Consulter le journal d'audit plateforme",
    p(R_AUDIT, A_EXPORT): "Exporter le journal d'audit en CSV",
    p(R_HEALTH, A_READ): "Consulter l'état de santé de la plateforme",
    p(R_ANNOUNCEMENTS, A_READ): "Consulter les annonces",
    p(R_ANNOUNCEMENTS, A_WRITE): "Publier ou modifier une annonce",
    p(R_TEMPLATES, A_READ): "Consulter les gabarits de semis",
    p(R_TEMPLATES, A_WRITE): "Publier une nouvelle version d'un gabarit de semis",
    p(R_MIGRATIONS, A_READ): "Consulter l'état des migrations par cabinet",
    p(R_MIGRATIONS, A_RUN): "Appliquer les migrations sur un ou plusieurs cabinets",
    p(R_EXPORTS, A_READ): "Consulter les demandes d'export",
    p(R_EXPORTS, A_CREATE): "Lancer un export de dossier",
    p(R_ONBOARDING, A_READ): "Consulter les inscriptions en attente",
}

# ---------------------------------------------------------------------------
# Rôles
# ---------------------------------------------------------------------------
ROLE_SUPER_ADMIN = "SUPER_ADMIN_PLATEFORME"
ROLE_SUPPORT = "SUPPORT"
ROLE_FACTURATION = "FACTURATION"
ROLE_COMMERCIAL = "COMMERCIAL"
ROLE_AUDITEUR = "AUDITEUR"

DESCRIPTIONS_ROLES: Dict[str, str] = {
    ROLE_SUPER_ADMIN: "Accès total à la console, y compris la gestion des comptes",
    ROLE_SUPPORT: "Consultation des cabinets et accès support encadré, sans facturation",
    ROLE_FACTURATION: "Plans, abonnements et factures de l'éditeur",
    ROLE_COMMERCIAL: "Création et suivi des cabinets en essai (onboarding)",
    ROLE_AUDITEUR: "Lecture seule : consultation et journal d'audit",
}

NIVEAUX_HIERARCHIE: Dict[str, int] = {
    ROLE_SUPER_ADMIN: 1,
    ROLE_SUPPORT: 2,
    ROLE_FACTURATION: 3,
    ROLE_COMMERCIAL: 4,
    ROLE_AUDITEUR: 5,
}


def _toutes() -> List[Permission]:
    return list(CATALOGUE_PERMISSIONS)


#: Matrice rôle → permissions. Source de vérité du seed initial ET garde-fou :
#: `appliquer_matrice` la réaligne sur la base, un rôle créé à la main ne reçoit
#: jamais un droit non déclaré ici.
MATRICE_ROLES: Dict[str, List[Permission]] = {
    ROLE_SUPER_ADMIN: _toutes(),
    ROLE_SUPPORT: [
        p(R_TENANTS, A_READ),
        p(R_SUPPORT, A_READ),
        p(R_SUPPORT, A_GRANT),
        p(R_SUPPORT, A_REVOKE),
        p(R_STATS, A_READ),
        p(R_ANNOUNCEMENTS, A_READ),
        p(R_ONBOARDING, A_READ),
        p(R_MIGRATIONS, A_READ),
        p(R_AUDIT, A_READ),
    ],
    ROLE_FACTURATION: [
        p(R_TENANTS, A_READ),
        p(R_PLANS, A_READ),
        p(R_PLANS, A_WRITE),
        p(R_SUBSCRIPTIONS, A_READ),
        p(R_SUBSCRIPTIONS, A_WRITE),
        p(R_BILLING, A_READ),
        p(R_BILLING, A_WRITE),
        p(R_STATS, A_READ),
        p(R_AUDIT, A_READ),
    ],
    ROLE_COMMERCIAL: [
        p(R_TENANTS, A_READ),
        p(R_TENANTS, A_CREATE),
        p(R_TENANTS, A_UPDATE),
        p(R_ONBOARDING, A_READ),
        p(R_STATS, A_READ),
        p(R_ANNOUNCEMENTS, A_READ),
    ],
    ROLE_AUDITEUR: [
        p(R_TENANTS, A_READ),
        p(R_PLANS, A_READ),
        p(R_SUBSCRIPTIONS, A_READ),
        p(R_BILLING, A_READ),
        p(R_STATS, A_READ),
        p(R_AUDIT, A_READ),
        p(R_AUDIT, A_EXPORT),
        p(R_HEALTH, A_READ),
    ],
}

ROLES_SYSTEME: FrozenSet[str] = frozenset(DESCRIPTIONS_ROLES)