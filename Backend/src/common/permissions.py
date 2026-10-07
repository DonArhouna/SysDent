"""
Catalogue des permissions RBAC et matrice des rôles.

Ce module est l'unique source de vérité du RBAC côté tenant. Le format des
permissions est **"MODULE:ACTION"** (ex: `"PATIENTS:READ"`), celui que produit
`AuthService.authenticate` en combinant `permissions.module` et
`permissions.action`, et celui attendu par `require_permissions(...)`.

Pourquoi une table de permissions dans la base ET une matrice ici ?
  - la table permet au Super Admin d'accorder une permission à un rôle sans
    redéployer le code ;
  - la matrice ci-dessous sert au seed initial et de garde-fou : un rôle créé à
    la main sans permission ne peut pas obtenir un accès non déclaré.
"""

from typing import Dict, List, Tuple

Permission = Tuple[str, str]

# ---------------------------------------------------------------------------
# Modules métier (le vocabulaire suit les routes et non l'organigramme)
# ---------------------------------------------------------------------------
MODULE_PATIENTS = "PATIENTS"
MODULE_CONSULTATIONS = "CONSULTATIONS"
MODULE_ODONTOGRAMME = "ODONTOGRAMME"
MODULE_ORDONNANCES = "ORDONNANCES"
MODULE_CABINETS = "CABINETS"
MODULE_PRATICIENS = "PRATICIENS"
MODULE_DISPONIBILITES = "DISPONIBILITES"
MODULE_AGENDA = "AGENDA"
MODULE_FACTURATION = "FACTURATION"
MODULE_STOCK = "STOCK"
MODULE_AUDIT = "AUDIT"
MODULE_ADMIN = "ADMIN"

ACTION_READ = "READ"
ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_DELETE = "DELETE"
ACTION_EXPORT = "EXPORT"
ACTION_SIGN = "SIGN"


def p(module: str, action: str) -> Permission:
    return (module, action)


def format_permission(module: str, action: str) -> str:
    """Construit la chaîne attendue dans le JWT : "MODULE:ACTION"."""
    return f"{module}:{action}"


# ---------------------------------------------------------------------------
# Catalogue complet des permissions
# ---------------------------------------------------------------------------
CATALOGUE_PERMISSIONS: List[Permission] = [
    p(MODULE_PATIENTS, ACTION_READ),
    p(MODULE_PATIENTS, ACTION_CREATE),
    p(MODULE_PATIENTS, ACTION_UPDATE),
    p(MODULE_PATIENTS, ACTION_DELETE),
    p(MODULE_PATIENTS, ACTION_EXPORT),
    p(MODULE_CONSULTATIONS, ACTION_READ),
    p(MODULE_CONSULTATIONS, ACTION_CREATE),
    p(MODULE_CONSULTATIONS, ACTION_UPDATE),
    p(MODULE_CONSULTATIONS, ACTION_DELETE),
    p(MODULE_CONSULTATIONS, ACTION_SIGN),
    p(MODULE_ODONTOGRAMME, ACTION_READ),
    p(MODULE_ODONTOGRAMME, ACTION_UPDATE),
    p(MODULE_ORDONNANCES, ACTION_READ),
    p(MODULE_ORDONNANCES, ACTION_CREATE),
    p(MODULE_ORDONNANCES, ACTION_UPDATE),
    p(MODULE_ORDONNANCES, ACTION_SIGN),
    # ── Pôle 2 : ressources physiques et profils ─────────────────────────────
    # `CABINETS` couvre le cabinet et ses ressources (salles, fauteuils) : ce
    # sont un seul et même objet d'organisation, administré par la même
    # personne. Les séparer en `SALLES:*` / `FAUTEUILS:*` créerait trois
    # permissions pour un seul geste.
    p(MODULE_CABINETS, ACTION_READ),
    p(MODULE_CABINETS, ACTION_CREATE),
    p(MODULE_CABINETS, ACTION_UPDATE),
    p(MODULE_CABINETS, ACTION_DELETE),
    p(MODULE_PRATICIENS, ACTION_READ),
    p(MODULE_PRATICIENS, ACTION_CREATE),
    p(MODULE_PRATICIENS, ACTION_UPDATE),
    p(MODULE_PRATICIENS, ACTION_DELETE),
    # `DISPONIBILITES` est volontairement distinct de `AGENDA` :
    # AGENDA = prendre un rendez-vous avec un patient (secrétariat) ;
    # DISPONIBILITES = dire quand un praticien travaille (praticien).
    # Confondre les deux donnerait au secrétariat le droit de modifier
    # l'agenda de travail des dentistes.
    p(MODULE_DISPONIBILITES, ACTION_READ),
    p(MODULE_DISPONIBILITES, ACTION_CREATE),
    p(MODULE_DISPONIBILITES, ACTION_UPDATE),
    p(MODULE_DISPONIBILITES, ACTION_DELETE),
    p(MODULE_AGENDA, ACTION_READ),
    p(MODULE_AGENDA, ACTION_CREATE),
    p(MODULE_AGENDA, ACTION_UPDATE),
    p(MODULE_AGENDA, ACTION_DELETE),
    p(MODULE_FACTURATION, ACTION_READ),
    p(MODULE_FACTURATION, ACTION_CREATE),
    p(MODULE_FACTURATION, ACTION_UPDATE),
    p(MODULE_FACTURATION, ACTION_DELETE),
    p(MODULE_FACTURATION, ACTION_EXPORT),
    p(MODULE_STOCK, ACTION_READ),
    p(MODULE_STOCK, ACTION_CREATE),
    p(MODULE_STOCK, ACTION_UPDATE),
    p(MODULE_STOCK, ACTION_DELETE),
    p(MODULE_AUDIT, ACTION_READ),
    p(MODULE_AUDIT, ACTION_EXPORT),
    p(MODULE_ADMIN, ACTION_READ),
    p(MODULE_ADMIN, ACTION_UPDATE),
]

# Rôles qui n'ont aucun contrôle de permission (accès complet par conception).
# Ils sont court-circuités dans `require_permissions` : ne pas essayer de
# restreindre ces rôles via le RBAC.
ROLES_SANS_CONTROLE_PERMISSIONS = {"ADMIN_CABINET", "SUPER_ADMIN"}

# ---------------------------------------------------------------------------
# Matrice des rôles métier
#
# Elle suit la matrice de permissions de `Analyse/docs/regles.md` :
#   - la secrétaire enregistre les patients mais n'accède pas au dossier médical ;
#   - le dentiste lit le dossier médical mais ne modifie pas la facturation ;
#   - le comptable gère la facturation mais pas le dossier patient.
# ---------------------------------------------------------------------------

_MEDICAL_COMPLET = [
    p(MODULE_PATIENTS, ACTION_READ),
    p(MODULE_PATIENTS, ACTION_CREATE),
    p(MODULE_PATIENTS, ACTION_UPDATE),
    p(MODULE_PATIENTS, ACTION_EXPORT),
    p(MODULE_CONSULTATIONS, ACTION_READ),
    p(MODULE_CONSULTATIONS, ACTION_CREATE),
    p(MODULE_CONSULTATIONS, ACTION_UPDATE),
    p(MODULE_CONSULTATIONS, ACTION_SIGN),
    p(MODULE_ODONTOGRAMME, ACTION_READ),
    p(MODULE_ODONTOGRAMME, ACTION_UPDATE),
    p(MODULE_ORDONNANCES, ACTION_READ),
    p(MODULE_ORDONNANCES, ACTION_CREATE),
    p(MODULE_ORDONNANCES, ACTION_UPDATE),
    p(MODULE_ORDONNANCES, ACTION_SIGN),
    p(MODULE_CABINETS, ACTION_READ),
    p(MODULE_PRATICIENS, ACTION_READ),
    p(MODULE_DISPONIBILITES, ACTION_READ),
    p(MODULE_DISPONIBILITES, ACTION_CREATE),
    p(MODULE_DISPONIBILITES, ACTION_UPDATE),
    p(MODULE_DISPONIBILITES, ACTION_DELETE),
]

MATRICE_ROLES: Dict[str, List[Permission]] = {
    # Administrateur du cabinet : tout sauf le RBAC global (réservé au Super Admin).
    "ADMIN_CABINET": [
        # Deux exclusions, et deux raisons distinctes.
        # `ADMIN:UPDATE` : un administrateur delegate ne doit pas pouvoir
        # reecrire la matrice des roles — c'est le seul droit qu'on lui retire
        # pour garantir qu'un cabinet ne se verrouille pas hors de sa base.
        # `AUDIT:READ` : le journal d'audit est reserve a la plateforme.
        # `AUDIT:EXPORT` suit `AUDIT:READ` : il n'a aucun endpoint cote cabinet,
        # l'export du journal d'audit est une fonction de la plateforme
        # (`/platform/audit/export`). Le conserver ici serait une permission
        # morte.
        *(
            permission
            for permission in CATALOGUE_PERMISSIONS
            if permission
            not in (
                p(MODULE_ADMIN, ACTION_UPDATE),
                p(MODULE_AUDIT, ACTION_READ),
                p(MODULE_AUDIT, ACTION_EXPORT),
            )
        ),
    ],
    # Chirurgien-dentiste : cœur clinique.
    "PRATICIEN": _MEDICAL_COMPLET,
    # Assistant dentaire : prépare les actes, lit le dossier, n'écrit pas le diagnostic.
    "ASSISTANT": [
        p(MODULE_PATIENTS, ACTION_READ),
        p(MODULE_PATIENTS, ACTION_CREATE),
        p(MODULE_CONSULTATIONS, ACTION_READ),
        p(MODULE_CONSULTATIONS, ACTION_CREATE),
        p(MODULE_ODONTOGRAMME, ACTION_READ),
        p(MODULE_ORDONNANCES, ACTION_READ),
        p(MODULE_CABINETS, ACTION_READ),
        p(MODULE_PRATICIENS, ACTION_READ),
        p(MODULE_DISPONIBILITES, ACTION_READ),
        p(MODULE_AGENDA, ACTION_READ),
        p(MODULE_STOCK, ACTION_READ),
    ],
    # Secrétariat / accueil : enregistre les patients et gère l'agenda et la caisse.
    # PAS d'accès au dossier médical (règle clinique) ni aux antécédents.
    "SECRETAIRE": [
        p(MODULE_PATIENTS, ACTION_CREATE),
        p(MODULE_PATIENTS, ACTION_READ),
        p(MODULE_CONSULTATIONS, ACTION_READ),
        # Le secrétariat programme : il doit VOIR les salles et les fauteuils
        # pour placer un patient, et connaître les disponibilités des
        # praticiens pour proposer un créneau. Il ne modifie ni l'un ni l'autre.
        p(MODULE_CABINETS, ACTION_READ),
        p(MODULE_PRATICIENS, ACTION_READ),
        p(MODULE_DISPONIBILITES, ACTION_READ),
        p(MODULE_AGENDA, ACTION_READ),
        p(MODULE_AGENDA, ACTION_CREATE),
        p(MODULE_AGENDA, ACTION_UPDATE),
        p(MODULE_FACTURATION, ACTION_READ),
        p(MODULE_FACTURATION, ACTION_CREATE),
        p(MODULE_STOCK, ACTION_READ),
    ],
    # Comptable : lit et corrige la facturation, aucun accès au dossier médical.
    "COMPTABLE": [
        p(MODULE_FACTURATION, ACTION_READ),
        p(MODULE_FACTURATION, ACTION_CREATE),
        p(MODULE_FACTURATION, ACTION_UPDATE),
        p(MODULE_FACTURATION, ACTION_DELETE),
        p(MODULE_FACTURATION, ACTION_EXPORT),
        p(MODULE_STOCK, ACTION_READ),
        p(MODULE_STOCK, ACTION_UPDATE),
        # Aucune permission AUDIT : le journal d'audit est une tracabilite de
        # plateforme. Il reste ecrit en base et consultable par le support et le
        # backoffice, mais aucun role du cabinet n'y accede — pas meme par URL
        # directe. Cf. docs/corrections/04_PLATEFORME_UI.md.
    ],
    # Gestionnaire de stock.
    "GESTIONNAIRE_STOCK": [
        p(MODULE_STOCK, ACTION_READ),
        p(MODULE_STOCK, ACTION_CREATE),
        p(MODULE_STOCK, ACTION_UPDATE),
        p(MODULE_STOCK, ACTION_DELETE),
        p(MODULE_FACTURATION, ACTION_READ),
    ],
}

# Niveau hiérarchique associé à chaque rôle (1 = plus élevé).
NIVEAUX_HIERARCHIE: Dict[str, int] = {
    "ADMIN_CABINET": 1,
    "PRATICIEN": 2,
    "COMPTABLE": 2,
    "GESTIONNAIRE_STOCK": 2,
    "ASSISTANT": 3,
    "SECRETAIRE": 3,
}

DESCRIPTIONS_ROLES: Dict[str, str] = {
    "ADMIN_CABINET": "Administrateur du cabinet (accès complet hors plateforme)",
    "PRATICIEN": "Chirurgien-dentiste (diagnostic, soins, prescription)",
    "ASSISTANT": "Assistant dentaire (préparation des actes)",
    "SECRETAIRE": "Secrétariat / accueil (patients, agenda, caisse)",
    "COMPTABLE": "Comptable (facturation et encaissements)",
    "GESTIONNAIRE_STOCK": "Gestionnaire de stock et fournisseurs",
}


def permissions_for_role(role: str) -> List[Permission]:
    """Permissions accordées à un rôle à la création. Inconnu = aucun accès."""
    return list(MATRICE_ROLES.get(role, []))


def toutes_les_permissions() -> List[str]:
    """Le catalogue complet au format chaîne, pour le seed de la base."""
    return [format_permission(module, action) for module, action in CATALOGUE_PERMISSIONS]
