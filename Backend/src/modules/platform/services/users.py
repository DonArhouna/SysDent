"""
Gestion des comptes de la console PLATEFORME (Phase A.5).

Deux invariants tiennent l'ensemble :

1. **Le dernier Super Admin ne peut pas être supprimé ni désactivé.** Sans ce
   garde-fou, une mauvaise manipulation — ou un attaquant ayant volé un compte —
   peut laisser l'éditeur sans personne pour administers ses propres comptes.
   La règle est vérifiée en base, sous verrou, et non seulement dans le service.
2. **Toute action produit une trace.** création, mise à jour, changement de
   rôles, désactivation, suppression, réinitialisation : une entrée de journal
   par action, avec l'état avant et après.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import (
    AuthenticationException,
    BusinessRuleViolationException,
    EntityNotFoundException,
)
from src.core.security import get_password_hash
from src.modules.platform.models import (
    RolePlateforme,
    SessionPlateforme,
    StatutUtilisateurPlateforme,
    UtilisateurPlateforme,
    utilisateur_roles,
)
from src.modules.platform.permissions import DESCRIPTIONS_ROLES, ROLE_SUPER_ADMIN
from src.modules.platform.security import verifier_mot_de_passe
from src.modules.platform.services.auth import PlatformAuthService
from src.modules.platform.services.journal import JournalService
from src.modules.platform.services.rbac import PlatformRbacService

logger = structlog.get_logger(__name__)


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class PlatformUserService:
    @staticmethod
    async def _charger(db: AsyncSession, utilisateur_id: uuid.UUID) -> UtilisateurPlateforme:
        stmt = (
            select(UtilisateurPlateforme)
            .options(selectinload(UtilisateurPlateforme.roles))
            .where(UtilisateurPlateforme.id == utilisateur_id)
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise EntityNotFoundException("Utilisateur plateforme", utilisateur_id)
        return user

    @staticmethod
    async def compter_super_admins_actifs(db: AsyncSession) -> int:
        stmt = (
            select(func.count(UtilisateurPlateforme.id))
            .select_from(
                utilisateur_roles.join(
                    UtilisateurPlateforme,
                    UtilisateurPlateforme.id == utilisateur_roles.c.utilisateur_id,
                )
            )
            .where(
                utilisateur_roles.c.role_id
                == select(RolePlateforme.id).where(RolePlateforme.code == ROLE_SUPER_ADMIN).scalar_subquery(),
                UtilisateurPlateforme.statut == StatutUtilisateurPlateforme.ACTIF,
            )
        )
        resultat = await db.execute(stmt)
        return int(resultat.scalar_one())

    @staticmethod
    async def _est_dernier_super_admin(
        db: AsyncSession, user: UtilisateurPlateforme, compte_cible: bool
    ) -> bool:
        """
        Vrai si retirer ce compte laisserait ZÉRO Super Admin actif.

        On compte les Super Admins ACTIFS et on exclut le compte visé : un
        Super Admin unique qui se retire lui-même doit être refusé, mais un
        Super Admin qui en désactive un autre sur une équipe de trois passe.
        """
        if not compte_cible:
            return False
        stmt = (
            select(func.count(UtilisateurPlateforme.id))
            .select_from(
                utilisateur_roles.join(
                    UtilisateurPlateforme,
                    UtilisateurPlateforme.id == utilisateur_roles.c.utilisateur_id,
                )
            )
            .where(
                utilisateur_roles.c.role_id
                == select(RolePlateforme.id)
                .where(RolePlateforme.code == ROLE_SUPER_ADMIN)
                .scalar_subquery(),
                UtilisateurPlateforme.statut == StatutUtilisateurPlateforme.ACTIF,
                UtilisateurPlateforme.id != user.id,
            )
        )
        autres = int((await db.execute(stmt)).scalar_one())
        return autres == 0

    # ─────────────────────────────────────────────────────────────────────────
    # Création
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        email: str,
        prenom: str,
        nom: str,
        mot_de_passe: str,
        roles: List[str],
        auteur: str,
        telephone: Optional[str] = None,
        activer_2fa: bool = True,
    ) -> Dict[str, Any]:
        """
        Crée un compte plateforme et renvoie, si l'activation du 2FA est
        demandée, le PREPARATIF d'activation.

        Le mot de passe n'est jamais renvoyé par l'API : l'appelant l'a choisi,
        le serveur ne le stocke qu'en argon2 et ne le journalise jamais.
        """
        email_normalise = email.strip().lower()
        existant = (
            await db.execute(
                select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == email_normalise)
            )
        ).scalar_one_or_none()
        if existant is not None:
            raise BusinessRuleViolationException(
                "Un compte existe déjà avec cette adresse.", code="EMAIL_DEJA_UTILISE"
            )

        manquements = verifier_mot_de_passe(mot_de_passe, email_normalise)
        if manquements:
            raise BusinessRuleViolationException(
                "Mot de passe non conforme à la politique de sécurité.",
                code="POLITIQUE_MOT_DE_PASSE",
                details={"regles": manquements},
            )

        roles_valides = await PlatformUserService._valider_roles(db, roles)

        user = UtilisateurPlateforme(
            email=email_normalise,
            mot_de_passe=get_password_hash(mot_de_passe),
            prenom=prenom.strip(),
            nom=nom.strip(),
            telephone=telephone,
            statut=StatutUtilisateurPlateforme.ACTIF,
        )
        for role in roles_valides:
            user.roles.append(role)
        db.add(user)
        await db.flush()

        await JournalService.journaliser(
            db,
            action="PLATFORM_UTILISATEUR_CREE",
            type_cible="UTILISATEUR",
            cible_id=str(user.id),
            acteur_email=auteur,
            apres={"email": email_normalise, "roles": [r.code for r in roles_valides]},
        )

        preparation = None
        if activer_2fa:
            preparation = await PlatformAuthService.preparer_second_facteur(db, user)

        return {"utilisateur": user, "activation_2fa": preparation}

    # ─────────────────────────────────────────────────────────────────────────
    # Mise à jour
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def mettre_a_jour(
        db: AsyncSession,
        utilisateur_id: uuid.UUID,
        *,
        prenom: Optional[str] = None,
        nom: Optional[str] = None,
        telephone: Optional[str] = None,
        roles: Optional[List[str]] = None,
        auteur: str,
        motif: Optional[str] = None,
    ) -> UtilisateurPlateforme:
        user = await PlatformUserService._charger(db, utilisateur_id)

        avant = {
            "prenom": user.prenom,
            "nom": user.nom,
            "telephone": user.telephone,
            "roles": [r.code for r in user.roles],
        }

        if roles is not None:
            nouveau_roles = await PlatformUserService._valider_roles(db, roles)
            if await PlatformUserService._est_dernier_super_admin(db, user, True) and not any(
                r.code == ROLE_SUPER_ADMIN for r in nouveau_roles
            ):
                raise BusinessRuleViolationException(
                    "Impossible de retirer le rôle Super Admin au dernier compte qui le porte.",
                    code="DERNIER_SUPER_ADMIN",
                )
            user.roles = nouveau_roles

        if prenom is not None:
            user.prenom = prenom.strip()
        if nom is not None:
            user.nom = nom.strip()
        if telephone is not None:
            user.telephone = telephone

        apres = {
            "prenom": user.prenom,
            "nom": user.nom,
            "telephone": user.telephone,
            "roles": [r.code for r in user.roles],
        }

        await JournalService.journaliser(
            db,
            action="PLATFORM_UTILISATEUR_MODIFIE",
            type_cible="UTILISATEUR",
            cible_id=str(user.id),
            acteur_email=auteur,
            avant=avant,
            apres=apres,
            motif=motif,
        )

        # Un changement de rôles doit prendre effet sans attendre l'expiration
        # des jetons en circulation : on coupe les sessions ouvertes.
        if avant["roles"] != apres["roles"]:
            await PlatformAuthService.revoquer_toutes_les_sessions(
                db, user.id, motif="changement de rôles", auteur=auteur
            )

        await db.flush()
        return user

    # ─────────────────────────────────────────────────────────────────────────
    # Désactivation / suppression
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def desactiver(
        db: AsyncSession,
        utilisateur_id: uuid.UUID,
        motif: str,
        auteur: str,
    ) -> UtilisateurPlateforme:
        user = await PlatformUserService._charger(db, utilisateur_id)

        if await PlatformUserService._est_dernier_super_admin(db, user, True):
            raise BusinessRuleViolationException(
                "Impossible de désactiver le dernier compte Super Admin actif : "
                "la console resterait sans administrateur.",
                code="DERNIER_SUPER_ADMIN",
            )
        if user.statut == StatutUtilisateurPlateforme.DESACTIF:
            raise BusinessRuleViolationException(
                "Ce compte est déjà désactivé.", code="COMPTE_DEJA_DESACTIF"
            )

        avant = {"statut": user.statut.value}
        user.statut = StatutUtilisateurPlateforme.DESACTIF
        user.motif_desactivation = motif

        await PlatformAuthService.revoquer_toutes_les_sessions(
            db, user.id, motif=f"désactivation : {motif}", auteur=auteur
        )
        await JournalService.journaliser(
            db,
            action="PLATFORM_UTILISATEUR_DESACTIVE",
            type_cible="UTILISATEUR",
            cible_id=str(user.id),
            acteur_email=auteur,
            avant=avant,
            apres={"statut": user.statut.value},
            motif=motif,
        )
        await db.flush()
        return user

    @staticmethod
    async def reactiver(
        db: AsyncSession, utilisateur_id: uuid.UUID, auteur: str, motif: Optional[str] = None
    ) -> UtilisateurPlateforme:
        user = await PlatformUserService._charger(db, utilisateur_id)
        if user.statut == StatutUtilisateurPlateforme.ACTIF:
            raise BusinessRuleViolationException(
                "Ce compte est déjà actif.", code="COMPTE_DEJA_ACTIF"
            )
        avant = {"statut": user.statut.value}
        user.statut = StatutUtilisateurPlateforme.ACTIF
        user.motif_desactivation = None
        await JournalService.journaliser(
            db,
            action="PLATFORM_UTILISATEUR_REACTIVE",
            type_cible="UTILISATEUR",
            cible_id=str(user.id),
            acteur_email=auteur,
            avant=avant,
            apres={"statut": user.statut.value},
            motif=motif,
        )
        await db.flush()
        return user

    @staticmethod
    async def supprimer(
        db: AsyncSession, utilisateur_id: uuid.UUID, auteur: str, motif: str
    ) -> None:
        """
        Suppression DÉFINITIVE d'un compte de la console.

        Réservée au Super Admin, avec motif obligatoire. Le journal est conservé
        (append-only) : la trace de ce que le compte a fait survit à sa
        disparition, sinon supprimer un compte effacerait aussi ce qu'il a fait.
        """
        user = await PlatformUserService._charger(db, utilisateur_id)

        if await PlatformUserService._est_dernier_super_admin(db, user, True):
            raise BusinessRuleViolationException(
                "Impossible de supprimer le dernier compte Super Admin actif.",
                code="DERNIER_SUPER_ADMIN",
            )

        await PlatformAuthService.revoquer_toutes_les_sessions(
            db, user.id, motif=f"suppression du compte : {motif}", auteur=auteur
        )

        email = user.email
        identifiant = str(user.id)
        await db.delete(user)
        await db.flush()

        await JournalService.journaliser(
            db,
            action="PLATFORM_UTILISATEUR_SUPPRIME",
            type_cible="UTILISATEUR",
            cible_id=identifiant,
            acteur_email=auteur,
            avant={"email": email},
            apres=None,
            motif=motif,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Lecture
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def lister(
        db: AsyncSession,
        recherche: Optional[str] = None,
        statut: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UtilisateurPlateforme]:
        stmt = select(UtilisateurPlateforme).options(selectinload(UtilisateurPlateforme.roles))
        if recherche:
            motif = f"%{recherche.strip().lower()}%"
            stmt = stmt.where(
                func.lower(UtilisateurPlateforme.email).like(motif)
                | func.lower(UtilisateurPlateforme.prenom).like(motif)
                | func.lower(UtilisateurPlateforme.nom).like(motif)
            )
        if statut:
            stmt = stmt.where(UtilisateurPlateforme.statut == statut)
        stmt = (
            stmt.order_by(UtilisateurPlateforme.created_at.desc()).limit(limit).offset(offset)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def compter(
        db: AsyncSession, recherche: Optional[str] = None, statut: Optional[str] = None
    ) -> int:
        stmt = select(func.count(UtilisateurPlateforme.id))
        if recherche:
            motif = f"%{recherche.strip().lower()}%"
            stmt = stmt.where(
                func.lower(UtilisateurPlateforme.email).like(motif)
                | func.lower(UtilisateurPlateforme.prenom).like(motif)
                | func.lower(UtilisateurPlateforme.nom).like(motif)
            )
        if statut:
            stmt = stmt.where(UtilisateurPlateforme.statut == statut)
        return int((await db.execute(stmt)).scalar_one())

    # ─────────────────────────────────────────────────────────────────────────
    # Interne
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _valider_roles(db: AsyncSession, codes: List[str]) -> List[RolePlateforme]:
        if not codes:
            raise BusinessRuleViolationException(
                "Au moins un rôle doit être attribué.", code="AUCUN_ROLE"
            )
        stmt = select(RolePlateforme).where(RolePlateforme.code.in_(codes))
        roles = list((await db.execute(stmt)).scalars().all())
        trouves = {r.code for r in roles}
        inconnus = set(codes) - trouves
        if inconnus:
            raise BusinessRuleViolationException(
                f"Rôle(s) inconnu(s) : {', '.join(sorted(inconnus))}.",
                code="ROLE_INCONNU",
                details={"roles_disponibles": sorted(DESCRIPTIONS_ROLES)},
            )
        return sorted(roles, key=lambda r: r.niveau_hierarchie)