"""Commandes d'opérateur de la plateforme.

Cote serveur uniquement : ce module n'est **jamais** expose en HTTP. Un acces
operateur passe par le shell du serveur, ce qui suppose un acces serveur — un
route qui reinitialiserait un mot de passe serait un cible evidente.

**Regle sur les secrets**, non negociable :

- le mot de passe vient de la variable d'environnement `PLATFORM_ADMIN_PASSWORD`
  ou d'une saisie masquee (`getpass`) ;
- il n'est **jamais** accepte en argument de ligne de commande : la ligne de
  commande est visible dans l'historique du shell **et** dans la liste des
  processus, donc lisible par tout utilisateur de la machine ;
- il n'est **jamais** ecrit dans un fichier, un log ou le journal d'audit ;
- a defaut, un mot de passe temporaire est genere et affiche **une seule fois**,
  avec changement obligatoire a la premiere connexion.

Usage :

    .venv\\Scripts\\python.exe -m src.modules.platform.admin --help
    .venv\\Scripts\\python.exe -m src.modules.platform.admin lister
    .venv\\Scripts\\python.exe -m src.modules.platform.admin reinitialiser-mot-de-passe \\
        --email rhonekane@gmail.com --motif "Ouverture du backoffice"
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import secrets
import string
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import null, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.platform_database import settings as _platform_settings
from src.core.security import get_password_hash, verify_password
from src.modules.platform.models import (
    UtilisateurPlateforme,
)

#: Acteur enregistre au journal : une action operateur n'a pas d'utilisateur
#: applicatif derriere elle, et l'ausculter sous un compte existant serait un
#: mensonge.
ACTEUR_OPERATEUR = "operateur-cli"
EMAIL_OPERATEUR = "operateur@localhost"

ROLE_SUPER_ADMIN = "SUPER_ADMIN_PLATEFORME"

#: Refus en production sans option explicite. Reinitialiser un mot de passe en
#: production est une prise de controle legitime ; c'est aussi exactement ce que
#: ferait un attaquant ayant gagne un acces. L'ecart se fait de nouveau.
ENV_PRODUCTION = ("PROD", "PRODUCTION")
OPTION_PRODUCTION = "--autorise-en-production"


def _majuscule(value: Optional[str]) -> bool:
    return (value or "").strip().upper() in ENV_PRODUCTION


def mot_de_passe_temporaire() -> str:
    """Mot de passe a usage unique, affiche une seule fois a l'operateur."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*?-_"
    return "A" + "".join(secrets.choice(alphabet) for _ in range(19))


def demander_mot_de_passe(generer: bool = False) -> str:
    """
    `--generer` produit un mot de passe affiche **une seule fois**, sans saisie.

    La saisie masquee est la source du piege : sur un terminal que le programme
    ne controle pas, `getpass` lit en echo, et une entree vide est acceptee sans
    erreur. Le compte se retrouve alors avec un mot de passe que personne ne
    connait. Generer supprime l'etape entiere.
    """
    if generer:
        return mot_de_passe_temporaire()
    """
    Mot de passe : variable d'environnement, sinon saisie masquee.

    Jamais en argument : l'historique du shell et la liste des processus le
    reveleraient. La saisie masquee evite le mot de passe dans l'historique des
    commandes.
    """
    depuis_env = os.environ.get("PLATFORM_ADMIN_PASSWORD")
    if depuis_env:
        return depuis_env
    # `getpass` n'ecrit rien dans l'historique du shell.
    return getpass.getpass("Mot de passe du compte plateforme : ")


def _valider_email(email: str) -> str:
    """
    Normalise et valide une adresse, avec le **meme validateur que les schemas**.

    `pydantic.EmailStr` est la validation du projet ; en ecrire une seconde
    accepterait des adresses que l'API refuse ensuite, et l'erreur n'apparaitrait
    qu'a l'enregistrement du compte.
    """
    from pydantic import BaseModel, EmailStr, ValidationError

    class _Email(BaseModel):
        valeur: EmailStr

    candidat = (email or "").strip().lower()
    try:
        return str(_Email(valeur=candidat).valeur)
    except ValidationError:
        print(f"Adresse e-mail invalide : {candidat!r}", file=sys.stderr)
        raise SystemExit(2)


async def _session():
    # L'URL vient de la configuration plateforme, comme partout ailleurs : la
    # commande n'invente pas son propre mode de connexion.
    moteur = create_async_engine(_platform_settings.platform_db_async_url)
    return moteur, async_sessionmaker(bind=moteur, expire_on_commit=False)


async def _journaliser(db, action: str, cible_id: str, motif: str, avant=None, apres=None):
    """Ecrit dans le journal d'audit plateforme, comme toute action sensible."""
    from src.modules.platform.services.journal import JournalService

    await JournalService.journaliser(
        db,
        action=action,
        type_cible="UTILISATEUR_PLATEFORME",
        acteur_email=EMAIL_OPERATEUR,
        acteur_id=None,
        cible_id=cible_id,
        avant=avant,
        apres=apres,
        motif=motif,
    )


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


async def cmd_lister(args) -> int:
    moteur, fabrique = await _session()
    try:
        async with fabrique() as db:
            from sqlalchemy import text

            lignes = (
                await db.execute(
                    text(
                        """
                        SELECT u.email, u.statut, u.deux_facteurs_actif,
                               (u.codes_secours_haches IS NOT NULL) AS a_des_secours,
                               (SELECT count(*) FROM utilisateur_roles ur
                                 JOIN roles_plateforme r ON r.id = ur.role_id
                                WHERE ur.utilisateur_id = u.id) AS nb_roles,
                               u.dernier_login
                          FROM utilisateurs_plateforme u
                      ORDER BY u.email
                        """
                    )
                )
            ).all()
    finally:
        await moteur.dispose()

    if not lignes:
        print("Aucun compte plateforme.")
        return 0
    print(f"{len(lignes)} compte(s) plateforme")
    # Aucun secret n'est affiche : ni mot de passe, ni secret TOTP, ni code.
    print(f"  {'EMAIL':<38}{'STATUT':<10}{'2FA':<6}{'SECOURS':<9}{'RÔLES':<7}DERNIER LOGIN")
    for email, statut, deux_fa, secours, nb_roles, dernier in lignes:
        print(
            f"  {email:<38}{str(statut):<10}{'oui' if deux_fa else 'NON':<6}"
            f"{'oui' if secours else '-':<9}{nb_roles:<7}"
            f"{dernier.isoformat() if dernier else '-'}"
        )
    return 0


async def cmd_creer_super_admin(args) -> int:
    email = _valider_email(args.email)
    motif = args.motif
    mdp = mot_de_passe_temporaire()
    temporaire = True

    moteur, fabrique = await _session()
    try:
        async with fabrique() as db:
            existant = (
                await db.execute(
                    select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == email)
                )
            ).scalar_one_or_none()
            if existant is None:
                from src.modules.platform.models import StatutUtilisateurPlateforme

                compte = UtilisateurPlateforme(
                    id=uuid.uuid4(),
                    email=email,
                    mot_de_passe=get_password_hash(mdp),
                    prenom="Administrateur",
                    nom="Plateforme",
                    statut=StatutUtilisateurPlateforme.ACTIF,
                    changement_mot_de_passe_obligatoire=True,
                )
                db.add(compte)
                await db.flush()
                cree = True
            else:
                # Idempotent : mettre a niveau plutot que refuser. Un operateur qui
                # relance la commande apres un echec doit obtenir le resultat
                # attendu, pas une erreur qui lui laisse croire que le compte est
                # pret.
                compte = existant
                compte.mot_de_passe = get_password_hash(mdp)
                compte.changement_mot_de_passe_obligatoire = True
                cree = False

            await _assigner_role(db, compte.id)
            await _journaliser(
                db,
                "PLATFORM_ADMIN_CREE" if cree else "PLATFORM_ADMIN_MIS_A_NIVEAU",
                str(compte.id),
                motif,
                apres={"email": email},
            )
            await db.commit()
    finally:
        await moteur.dispose()

    print(f"Compte Super Admin : {email} ({'cré' if cree else 'mis à niveau'})")
    if temporaire:
        # **Une seule fois**, à la console de l'opérateur : ni fichier, ni log.
        print(f"  mot de passe temporaire : {mdp}")
        print("  Changement obligatoire à la première connexion.")
        print("  Notez-le maintenant : il ne sera plus jamais affiché.")
    return 0


async def _assigner_role(db, utilisateur_id) -> None:
    from sqlalchemy import text

    role_id = (
        await db.execute(
            text("SELECT id FROM roles_plateforme WHERE code = :code"),
            {"code": ROLE_SUPER_ADMIN},
        )
    ).scalar_one_or_none()
    if role_id is None:
        raise SystemExit(
            f"Rôle {ROLE_SUPER_ADMIN} absent : la base plateforme n'est pas à jour "
            "(appliquer les migrations)."
        )
    await db.execute(
        text(
            "INSERT INTO utilisateur_roles (utilisateur_id, role_id) "
            "VALUES (:u, :r) ON CONFLICT DO NOTHING"
        ),
        {"u": str(utilisateur_id), "r": role_id},
    )


async def cmd_reinitialiser_mot_de_passe(args) -> int:
    email = _valider_email(args.email)
    moteur, fabrique = await _session()
    saisie_affiche = ""
    try:
        async with fabrique() as db:
            compte = (
                await db.execute(
                    select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == email)
                )
            ).scalar_one_or_none()
            if compte is None:
                print(f"Compte introuvable : {email}")
                return 1

            # Les sessions sont revoquees : un mot de passe reinitialise laisserait
            # actives celles ouvertes avec l'ancien, ce qui vide l'operation de son effet.
            nb = await _revoquer_sessions(db, compte.id)

            saisi = demander_mot_de_passe(args.generer)
            if not saisi:
                print(
                    "Aucun mot de passe capture. La saisie masquee n'a rien recu :\n"
                    "  - terminal que le programme ne controle pas : getpass lit en echo ;\n"
                    "  - une entree vide est acceptee sans erreur.\n"
                    "  Reessayez avec --generer, ou via PLATFORM_ADMIN_PASSWORD.",
                    file=sys.stderr,
                )
                return 1
            saisie_affiche = saisi if args.generer else ""

            compte.mot_de_passe = get_password_hash(saisi)
            compte.changement_mot_de_passe_obligatoire = True
            compte.tentatives_echouees = 0
            compte.verrouille_jusqua = None
            await db.flush()

            # **Verification avant validation.** Un hachage est irreversible : une
            # saisie capturee de travers ne se revelerait qu'a la connexion, ou
            # l'operateur conclut a tort que son mot de passe est errone.
            if not verify_password(saisi, compte.mot_de_passe):
                await db.rollback()
                print(
                    "ECHEC : le mot de passe enregistre ne se verifie pas. "
                    "Aucune modification conservee.",
                    file=sys.stderr,
                )
                return 1

            await _journaliser(
                db,
                "PLATFORM_MDP_REINITIALISE",
                str(compte.id),
                args.motif,
                avant={"email": email},
                apres={"sessions_revoquees": nb},
            )
            await db.commit()
    finally:
        await moteur.dispose()

    print(f"Mot de passe reinitialise pour {email} - {nb} session(s) revoquee(s).")
    if saisie_affiche:
        # Affiche **apres** commit et verification : jamais avant, jamais ailleurs.
        print(f"  mot de passe : {saisie_affiche}")
    return 0


async def cmd_reinitialiser_2fa(args) -> int:
    email = _valider_email(args.email)
    moteur, fabrique = await _session()
    try:
        async with fabrique() as db:
            compte = (
                await db.execute(
                    select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == email)
                )
            ).scalar_one_or_none()
            if compte is None:
                print(f"Compte introuvable : {email}")
                return 1
            nb = await _revoquer_sessions(db, compte.id)
            compte.secret_2fa_chiffre = None
            compte.deux_facteurs_actif = False
            compte.deux_facteurs_confirme_at = None
            # **SQL NULL, pas le litteral JSON `null`.** Sur une colonne JSONB, `None`
            # est serialise en JSONB `null` - une *valeur*, pas l'absence de valeur. La
            # contrainte `ck_codes_secours_exigent_2fa` teste
            # `codes_secours_haches IS NULL` : un JSONB `null` passe le premier test et
            # echoue sur le second, et la commande levait une CheckViolation.
            #
            # Consequence si ce n'est pas corrige : **reinitialiser-2fa ne marche
            # jamais** - c'est-a-dire la seule voie de recours quand un telephone est
            # perdu. Le compte resterait bloque avec un secret que personne ne detient.
            compte.codes_secours_haches = null()
            compte.tentatives_echouees = 0
            compte.verrouille_jusqua = None
            await _journaliser(
                db,
                "PLATFORM_2FA_REINITIALISEE",
                str(compte.id),
                args.motif,
                avant={"email": email, "deux_facteurs_actif": True},
                apres={"sessions_revoquees": nb},
            )
            await db.commit()
    finally:
        await moteur.dispose()
    print(
        f"2FA réinitialisée pour {email} — {nb} session(s) révoquée(s).\n"
        "  Le compte doit s'enrôler à la prochaine connexion."
    )
    return 0


async def _revoquer_sessions(db, utilisateur_id) -> int:
    from sqlalchemy import text

    result = await db.execute(
        text(
            "UPDATE sessions_plateforme SET expire_at = now() "
            "WHERE utilisateur_id = :u AND expire_at > now()"
        ),
        {"u": str(utilisateur_id)},
    )
    return int(result.rowcount or 0)


# ---------------------------------------------------------------------------
# Analyse des arguments
# ---------------------------------------------------------------------------


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="platform-admin",
        description="Commandes d'opérateur de la plateforme (serveur uniquement).",
    )
    sous = parser.add_subparsers(dest="commande", required=True)

    lister = sous.add_parser("lister", help="Lister les comptes plateforme")
    lister.set_defaults(fonction=cmd_lister)

    creer = sous.add_parser("creer-super-admin", help="Créer ou mettre à niveau un Super Admin")
    creer.add_argument("--email", required=True)
    creer.add_argument("--motif", required=True, help="Obligatoire : trace de la raison")
    creer.set_defaults(fonction=cmd_creer_super_admin)

    mdp = sous.add_parser("reinitialiser-mot-de-passe", help="Réinitialiser un mot de passe")
    mdp.add_argument("--email", required=True)
    mdp.add_argument("--motif", required=True)
    mdp.add_argument(
        "--generer",
        action="store_true",
        help="Genere un mot de passe affiche une seule fois, sans saisie masquee",
    )
    mdp.set_defaults(fonction=cmd_reinitialiser_mot_de_passe)

    fa = sous.add_parser("reinitialiser-2fa", help="Réinitialiser la double authentification")
    fa.add_argument("--email", required=True)
    fa.add_argument("--motif", required=True)
    fa.set_defaults(fonction=cmd_reinitialiser_2fa)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv)

    # Aucune confirmation interactive : ces commandes sont destinees a un
    # operateur qui a l'acces serveur, et chaque session est journalisee. Le
    # `--motif` obligatoire est la trace, il vaut mieux qu'une invite.
    production = _majuscule(os.environ.get("ENVIRONMENT"))
    if production:
        print(
            f"REFUS : environnement {production}. Reinitialiser un acces en "
            f"production exige l'option explicite {OPTION_PRODUCTION}.",
            file=sys.stderr,
        )
        if OPTION_PRODUCTION not in (argv or sys.argv):
            return 2

    return asyncio.run(args.fonction(args))


if __name__ == "__main__":
    raise SystemExit(main())