"""
Amorçage de la console PLATEFORME — commande CLI explicite.

Ce script est le SEUL moyen de créer le premier Super Admin. Il n'existe aucun
endpoint public qui le fasse, et aucun mot de passe par défaut dans le dépôt :
le mot de passe vient soit de la variable d'environnement
`PLATFORM_ADMIN_PASSWORD`, soit d'une saisie masquée à l'exécution. Dans les
deux cas il n'est jamais écrit dans un journal, un fichier ni une variable
persistée.

Usage :

    # 1. Préparer la base plateforme (idempotent)
    python init_platform.py --migrate

    # 2. Créer le RBAC (catalogue + 5 rôles + matrice) — idempotent
    python init_platform.py --bootstrap-rbac

    # 3. Créer le premier Super Admin (le secret 2FA s'affiche UNE fois)
    python init_platform.py --admin --email admin@sysdent.pro --prenom Amina --nom Diop

Sans `--password`, le mot de passe est demandé à l'exécution (saisie masquée).
Sans `--sans-2fa`, un secret TOTP est généré et affiché : le compte ne pourra PAS
se connecter tant qu'il n'a pas été activé depuis la console.
"""

import argparse
import asyncio
import getpass
import os
import sys

from src.core.config import settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="init_platform.py",
        description="Amorçage de la console plateforme SysDent Pro (backoffice éditeur).",
    )
    parser.add_argument(
        "--migrate", action="store_true", help="Applique les migrations Alembic de la base plateforme."
    )
    parser.add_argument(
        "--bootstrap-rbac",
        action="store_true",
        help="Sème le catalogue de permissions, les 5 rôles système et les plans par défaut (idempotent).",
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Crée le premier compte Super Admin (mot de passe saisi ou via PLATFORM_ADMIN_PASSWORD).",
    )
    parser.add_argument("--email", help="E-mail du compte à créer.")
    parser.add_argument("--prenom", default="Admin", help="Prénom (défaut : Admin).")
    parser.add_argument("--nom", default="Plateforme", help="Nom (défaut : Plateforme).")
    parser.add_argument(
        "--sans-2fa",
        action="store_true",
        help="DÉCONSEILLÉ : crée le compte sans second facteur. Le compte ne pourra pas se connecter.",
    )
    parser.add_argument(
        "--afficher-totp",
        action="store_true",
        help="Affiche un code TOTP valide (utile pour valider la chaîne de bout en bout).",
    )
    return parser


def _mot_de_passe(args) -> str:
    """
    Récupère le mot de passe : variable d'environnement sinon saisie masquée.

    Aucun mot de passe par défaut n'existe nulle part dans ce dépôt. Une saisie
    masquée (`getpass`) est la seule source en développement, ce qui évite qu'un
    mot de passe de démonstration traîne dans l'historique du shell.
    """
    from_env = os.environ.get("PLATFORM_ADMIN_PASSWORD")
    if from_env:
        return from_env
    if not sys.stdin.isatty():
        raise SystemExit(
            "Aucun mot de passe fourni.\n"
            "  • Exportez PLATFORM_ADMIN_PASSWORD puis relancez la commande, ou\n"
            "  • lancez-la depuis un terminal interactif (saisie masquée).\n"
            "  Ce script n'embarque aucun mot de passe par défaut, volontairement."
        )
    return getpass.getpass("Mot de passe du Super Admin (saisie masquée) : ")


async def _migrer() -> None:
    from src.core.migrations import upgrade_platform_to_head

    print(f"Migrations plateforme -> {settings.PLATFORM_DB_NAME} …")
    upgrade_platform_to_head()
    print("  ✓ base plateforme à jour")


async def _bootstrap_rbac() -> None:
    from decimal import Decimal
    from typing import Dict

    from sqlalchemy import select

    from src.core.platform_database import PlatformSessionFactory
    from src.modules.platform.models import Plan, RolePlateforme
    from src.modules.platform.services.plans import PlanService
    from src.modules.platform.services.rbac import PlatformRbacService

    # Catalogue commercial de départ. Les quotas sont volontairement généreux :
    # ces plans servent de référence, et resserrer un quota actif d'un client en
    # production est une décision commerciale, pas un effet de bord technique.
    plans_depart: Dict[str, Dict] = {
        "ESSENTIEL": {
            "nom": "Essentiel",
            "description": "Formule de démarrage — pour un cabinet naissant",
            "prix": Decimal("0"),
            "periodicite": "MENSUEL",
            "quotas": {
                "utilisateurs": 20,
                "sites": 3,
                "praticiens": 5,
                "stockage_octets": 5 * 1024**3,
                "sms_par_mois": 500,
            },
            "features": {
                "stock": True,
                "sms": True,
                "rapports": True,
                "export_patients": True,
                "api": False,
            },
            "jours_essai": 14,
            "plan_defaut": True,
        },
        "PRO": {
            "nom": "Pro",
            "description": "Cabinet multi-praticiens avec site secondaire",
            "prix": Decimal("45000"),
            "periodicite": "MENSUEL",
            "quotas": {
                "utilisateurs": 50,
                "sites": 10,
                "praticiens": 15,
                "stockage_octets": 50 * 1024**3,
                "sms_par_mois": 5000,
            },
            "features": {
                "stock": True,
                "sms": True,
                "rapports": True,
                "export_patients": True,
                "api": True,
            },
            "jours_essai": 14,
            "plan_defaut": False,
        },
        "PREMIUM": {
            "nom": "Premium",
            "description": "Groupe de cabinets, multi-sites, API et support prioritaire",
            "prix": Decimal("120000"),
            "periodicite": "MENSUEL",
            "quotas": {
                "utilisateurs": 200,
                "sites": 50,
                "praticiens": 60,
                "stockage_octets": 500 * 1024**3,
                "sms_par_mois": 25000,
            },
            "features": {
                "stock": True,
                "sms": True,
                "rapports": True,
                "export_patients": True,
                "api": True,
                "support_prioritaire": True,
            },
            "jours_essai": 14,
            "plan_defaut": False,
        },
    }

    async with PlatformSessionFactory() as session:
        resume = await PlatformRbacService.bootstrap_complet(session)
        await session.commit()
        roles = (await session.execute(select(RolePlateforme))).scalars().all()

        crees = []
        for code, definition in plans_depart.items():
            existant = await PlanService.par_code(session, code)
            if existant is not None:
                continue
            await PlanService.creer(session, code=code, auteur="cli:init_platform", **definition)
            crees.append(code)
        await session.commit()

    print(
        f"  ✓ RBAC amorcé : {resume['permissions']} permissions, "
        f"{len(roles)} rôles, {resume['liens']} liens"
    )
    print(
        f"  ✓ Plans : {len(plans_depart)} catalogue(s)"
        + (f", {len(crees)} créé(s) ({', '.join(crees)})" if crees else ", déjà à jour")
    )


async def _creer_admin(args) -> int:
    from sqlalchemy import select

    from src.core.platform_database import PlatformSessionFactory
    from src.modules.platform.models import UtilisateurPlateforme
    from src.modules.platform.permissions import ROLE_SUPER_ADMIN
    from src.modules.platform.services.users import PlatformUserService

    if not args.email:
        print("  ✗ --email est obligatoire avec --admin", file=sys.stderr)
        return 2

    mot_de_passe = _mot_de_passe(args)

    async with PlatformSessionFactory() as session:
        existant = (
            await session.execute(
                select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == args.email.lower())
            )
        ).scalar_one_or_none()
        if existant is not None:
            print(f"  ✗ le compte {args.email} existe déjà (rien n'a été modifié)")
            return 1

        try:
            resultat = await PlatformUserService.creer(
                session,
                email=args.email,
                prenom=args.prenom,
                nom=args.nom,
                mot_de_passe=mot_de_passe,
                roles=[ROLE_SUPER_ADMIN],
                auteur="cli:init_platform",
                activer_2fa=not args.sans_2fa,
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - CLI : on affiche, on n'avale pas
            await session.rollback()
            code = getattr(exc, "code", None)
            details = getattr(exc, "details", None)
            print(f"  ✗ création refusée : {exc}")
            if details:
                for regle in details.get("regles", []):
                    print(f"      - {regle}")
            if code == "POLITIQUE_MOT_DE_PASSE":
                return 3
            raise

        user = resultat["utilisateur"]
        activation = resultat["activation_2fa"]

    print(f"  ✓ compte créé : {user.email} ({user.prenom} {user.nom}) — rôle {ROLE_SUPER_ADMIN}")

    if activation:
        print()
        print("  ┌─ Second facteur TOTP — À CONSERVER, AFFICHÉ UNE SEULE FOIS ─┐")
        print(f"  │  secret : {activation['secret']}")
        print(f"  │  uri    : {activation['uri']}")
        print("  └────────────────────────────────────────────────────────────────┘")
        print()
        print("  1. Ouvrez l'application 2FA (Aegis, Google Authenticator, 1Password).")
        print("  2. Ajoutez le compte en saisissant le secret ci-dessus.")
        print("  3. Connectez-vous sur /platform/auth/login puis /platform/auth/2fa.")
        print("  ⚠ Le secret n'est stocké QUE chiffré : il ne sera plus jamais affiché.")

        if args.afficher_totp:
            from src.modules.platform.security import codes_totp, dechiffrer_secret_2fa

            code, _precedent = codes_totp(activation["secret"])
            print()
            print(f"  Code TOTP de validation (change toutes les 30 s) : {code}")
            _ = dechiffrer_secret_2fa  # silence pylint sur l'import de contrôle
    else:
        print("  ⚠ --sans-2fa : ce compte ne pourra PAS se connecter (2FA obligatoire).")
    return 0


async def _main() -> int:
    args = _parser().parse_args()

    if not (args.migrate or args.bootstrap_rbac or args.admin):
        _parser().print_help()
        print()
        print("  Aucune action demandée : précisez --migrate, --bootstrap-rbac ou --admin.")
        return 2

    print(f"SysDent Pro — amorçage de la console PLATEFORME ({settings.APP_ENV})")

    if args.migrate:
        await _migrer()

    if args.bootstrap_rbac or args.admin:
        await _bootstrap_rbac()

    if args.admin:
        code = await _creer_admin(args)
        if code != 0:
            return code

    print()
    print("Terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))