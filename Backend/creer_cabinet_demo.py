"""
Crée un cabinet de démonstration et le remplit de données réalistes.

Usage (depuis `Backend/`, venv activé) :

    python creer_cabinet_demo.py --email admin.demo@sysdent.sn

Le mot de passe de l'administrateur du cabinet vient de la variable
`DEMO_ADMIN_PASSWORD`, sinon d'une saisie masquée. Il n'est **jamais** accepté en
argument : la ligne de commande reste dans l'historique du shell et dans la
liste des processus.

Ce que fait la commande :

1. provisionne le cabinet exactement comme le backoffice (base dédiée, compte
   PostgreSQL dédié, migrations, rôles, administrateur et son profil praticien) ;
2. le peuple via `_seed_demo.py`, qui passe par l'API comme un utilisateur :
   8 patients, la nomenclature des actes, des consultations, des rendez-vous,
   des factures, des paiements et des devis.

Relancée avec le même e-mail, elle ne recrée pas le cabinet : elle complète
seulement les données manquantes (le jeu de démonstration est idempotent).

Aucun e-mail n'est envoyé : le mot de passe étant connu, l'invitation de
l'administrateur n'a pas lieu d'être.
"""

import argparse
import asyncio
import getpass
import os
import sys

sys.path.insert(0, ".")

LONGUEUR_MIN = 12


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="creer_cabinet_demo.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--email", required=True, help="E-mail de l'administrateur du cabinet (identifiant de connexion).")
    p.add_argument("--nom", default="Cabinet Démo SysDent", help="Nom du cabinet.")
    p.add_argument("--prenom-admin", default="Awa", help="Prénom de l'administrateur.")
    p.add_argument("--nom-admin", default="Diallo", help="Nom de l'administrateur.")
    p.add_argument("--plan", default="ESSENTIEL", help="Code du plan souscrit (vide : aucun abonnement).")
    p.add_argument("--sans-donnees", action="store_true", help="Créer le cabinet sans le peupler.")
    return p


def _mot_de_passe() -> str:
    depuis_env = os.environ.get("DEMO_ADMIN_PASSWORD")
    if depuis_env:
        return depuis_env
    if not sys.stdin.isatty():
        raise SystemExit(
            "Aucun terminal interactif : définissez DEMO_ADMIN_PASSWORD, par exemple\n"
            "  $env:DEMO_ADMIN_PASSWORD='VotreMotDePasse12+'"
        )
    mdp = getpass.getpass("Mot de passe de l'administrateur du cabinet (saisie masquée) : ")
    if getpass.getpass("Confirmez : ") != mdp:
        raise SystemExit("Les deux saisies ne correspondent pas.")
    return mdp


async def _cabinet_existe(email: str) -> bool:
    from sqlalchemy import select

    from src.core.database import MasterAsyncSessionFactory
    from src.modules.master.models import UtilisateurIndex

    async with MasterAsyncSessionFactory() as master:
        return (
            await master.execute(select(UtilisateurIndex).where(UtilisateurIndex.email == email))
        ).scalar_one_or_none() is not None


async def _main(args) -> int:
    from src.core.database import MasterAsyncSessionFactory, master_engine, tenant_db_manager
    from src.core.platform_database import PlatformSessionFactory, close_platform_engine
    from src.modules.platform.services import notifications
    from src.modules.platform.services.provisioning import ProvisioningService

    email = args.email.strip().lower()
    # Même validation que l'écran de connexion : un domaine réservé (.local,
    # .test, .localhost…) créerait un compte avec lequel on ne peut pas se connecter.
    from pydantic import TypeAdapter, ValidationError
    from pydantic import EmailStr

    try:
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        print(
            f"  ✗ {email} : adresse refusée par l'écran de connexion (domaine réservé ?). "
            "Utilisez par exemple admin.demo@sysdent.sn",
            file=sys.stderr,
        )
        return 1
    mdp = _mot_de_passe()
    if len(mdp) < LONGUEUR_MIN:
        print(f"  ✗ mot de passe trop court ({LONGUEUR_MIN} caractères minimum)", file=sys.stderr)
        return 1

    # Pas d'invitation par e-mail : le mot de passe est connu de l'opérateur.
    notifications.definir_sender(notifications.ConsoleNotificationSender(afficher_corps=False))

    try:
        if await _cabinet_existe(email):
            print(f"Un cabinet existe déjà pour {email} : création ignorée, on complète les données.")
        else:
            print(f"Création du cabinet « {args.nom} » …")
            async with MasterAsyncSessionFactory() as master, PlatformSessionFactory() as plateforme:
                resultat = await ProvisioningService.provisionner(
                    master_db=master,
                    platform_db=plateforme,
                    nom=args.nom,
                    admin_email=email,
                    admin_prenom=args.prenom_admin,
                    admin_nom=args.nom_admin,
                    admin_password=mdp,
                    statut_initial="ACTIF",
                    plan_code=args.plan or None,
                    auteur="commande:creer_cabinet_demo",
                    motif="Cabinet de démonstration",
                )
                await plateforme.commit()
            print(f"  ✓ cabinet créé ({len(resultat.etapes)} étapes) — base {resultat.tenant_db.db_name}")

        if args.sans_donnees:
            return 0

        print("\nDonnées de démonstration …")
        import _seed_demo

        return await _seed_demo.peupler(email, mdp, fermer=False)
    finally:
        await tenant_db_manager.close_all()
        await close_platform_engine()
        await master_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(_parser().parse_args())))
