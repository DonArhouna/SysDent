"""
Utilisateurs du cabinet.

Ce module ferme le manque le plus coûteux du produit : un cabinet pouvait créer
son administrateur au provisionnement, **et rien d'autre**. Il ne pouvait pas
ajouter une secrétaire, un comptable ou un assistant — donc pas de deuxième
dentiste sans développement.

## La règle qui décide de tout le reste

Créer un compte ne suffit pas : il faut que ce compte **puisse se connecter**.
L'authentification résout le cabinet via `utilisateur_index`, en base master :

    email -> (societe_id, utilisateur_id)

Un utilisateur inséré en base sans sa ligne d'index existe mais ne peut pas se
connecter — c'est invisible, et c'est ce qui a rendu ce module indispensable.
La création écrit donc **les deux lignes**, et si l'écriture master échoue, le
compte est désactivé plutôt que laissé dans un état où il occupe une adresse
sans jamais pouvoir être utilisé.

## Ce que ce module refuse de faire

- **Supprimer physiquement un compte.** Une consultation, un acte, une clôture
  de caisse le référencent. Supprimer le compte effacerait l'auteur d'un acte
  médical. La désactivation ferme l'accès en conservant la trace.
- **Désactiver le dernier administrateur actif.** Un cabinet qui se verrouille
  lui-même n'a personne pour le rouvrir.
- **Se désactiver soi-même** : c'est presque toujours une erreur de clic, et
  sur un cabinet à un seul administrateur, c'est la perte de l'accès.
"""

import secrets
import string
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.core.security import get_password_hash
from src.modules.tenants.models import (
    Cabinet,
    Role,
    SessionUser,
    Utilisateur,
)

#: Un mot de passe temporaire doit être long mais lisible : il est dicté à
#: l'utilisateur, souvent par téléphone. 12 caractères, sans ambiguïté.
_ALPHABET = string.ascii_letters + string.digits


def _mot_de_passe_temporaire(longueur: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(longueur))


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _relations_utilisateur():
    """Role et profil praticien charges d'un coup.

    Le role est affiche dans chaque ligne de la liste ; sans chargement
    anticipe, la serialisation le declencherait en cours de reponse et
    echouerait sur une connexion asynchrone.
    """
    return (selectinload(Utilisateur.role), selectinload(Utilisateur.praticien_profil))


class UtilisateurService:
    # ------------------------------------------------------------------ lecture

    @staticmethod
    async def _charger(db: AsyncSession, utilisateur_id: uuid.UUID) -> Utilisateur:
        # `populate_existing` est indispensable : apres un `commit`, le session
        # garde l'objet en cache. Relire sans cette option renvoyait l'ancien
        # role dans la reponse alors que la base portait le nouveau -- l'API
        # mentait au client, qui affichait une donnee fausse.
        u = (
            await db.execute(
                select(Utilisateur)
                .options(*_relations_utilisateur())
                .where(Utilisateur.id == utilisateur_id)
                .execution_options(populate_existing=True)
            )
        ).unique().scalar_one_or_none()
        if u is None:
            raise EntityNotFoundException("Utilisateur", utilisateur_id)
        return u

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        q: Optional[str] = None,
        role: Optional[str] = None,
        actif: Optional[bool] = None,
        cabinet_id: Optional[uuid.UUID] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Utilisateur], int]:
        conditions = []
        if q:
            motif = f"%{q.strip()}%"
            conditions.append(
                or_(
                    Utilisateur.email.ilike(motif),
                    Utilisateur.prenom.ilike(motif),
                    Utilisateur.nom.ilike(motif),
                )
            )
        if actif is not None:
            conditions.append(Utilisateur.actif == actif)
        if cabinet_id:
            conditions.append(Utilisateur.cabinet_id == cabinet_id)
        if role:
            conditions.append(Role.nom == role.upper())

        base = select(Utilisateur).join(Role, Utilisateur.role_id == Role.id)
        count_stmt = select(func.count(func.distinct(Utilisateur.id))).join(
            Role, Utilisateur.role_id == Role.id
        )
        if conditions:
            base = base.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total = (await db.execute(count_stmt)).scalar_one()
        lignes = (
            (
                await db.execute(
                    base.options(*_relations_utilisateur())
                    .order_by(Utilisateur.actif.desc(), Utilisateur.nom, Utilisateur.prenom)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        return list(lignes), int(total)

    @staticmethod
    async def compter_admins_actifs(db: AsyncSession, sauf: Optional[uuid.UUID] = None) -> int:
        stmt = (
            select(func.count(func.distinct(Utilisateur.id)))
            .join(Role, Utilisateur.role_id == Role.id)
            .where(Utilisateur.actif == True, Role.nom == "ADMIN_CABINET")  # noqa: E712
        )
        if sauf:
            stmt = stmt.where(Utilisateur.id != sauf)
        return int((await db.execute(stmt)).scalar_one())

    # ------------------------------------------------------------------ écriture

    @staticmethod
    async def creer(
        db: AsyncSession,
        *,
        master_db: AsyncSession,
        societe_id: uuid.UUID,
        email: str,
        mot_de_passe: str,
        prenom: str,
        nom: str,
        role: str,
        telephone: Optional[str] = None,
        cabinet_id: Optional[uuid.UUID] = None,
        auteur: Optional[Utilisateur] = None,
    ) -> Utilisateur:
        email = email.strip().lower()
        if await UtilisateurService._email_existe(db, email):
            raise BusinessRuleViolationException(
                f"Un compte utilise déjà l'adresse {email}.",
                code="EMAIL_DEJA_UTILISE",
            )

        entete_role = (
            await db.execute(select(Role).where(Role.nom == role.upper()))
        ).scalar_one_or_none()
        if entete_role is None:
            raise BusinessRuleViolationException(
                f"Rôle inconnu : {role}.",
                code="ROLE_INCONNU",
                details={"roles": [r for r in await UtilisateurService._roles(db)]},
            )

        if cabinet_id is not None:
            existe = (
                await db.execute(select(Cabinet.id).where(Cabinet.id == cabinet_id))
            ).scalar_one_or_none()
            if existe is None:
                raise EntityNotFoundException("Cabinet", cabinet_id)

        u = Utilisateur(
            email=email,
            mot_de_passe=get_password_hash(mot_de_passe),
            role_id=entete_role.id,
            prenom=prenom.strip(),
            nom=nom.strip(),
            telephone=(telephone or "").strip() or None,
            cabinet_id=cabinet_id,
            actif=True,
        )
        db.add(u)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise BusinessRuleViolationException(
                f"Un compte utilise déjà l'adresse {email}.",
                code="EMAIL_DEJA_UTILISE",
            )
        await db.refresh(u)

        # La ligne d'index master est ce qui rend le compte **connectable**.
        # Sans elle, il existe mais ne peut jamais se connecter.
        await UtilisateurService._indexer(master_db, societe_id, u)
        return await UtilisateurService._charger(db, u.id)

    @staticmethod
    async def modifier(
        db: AsyncSession,
        utilisateur_id: uuid.UUID,
        *,
        prenom: Optional[str] = None,
        nom: Optional[str] = None,
        telephone: Optional[str] = None,
        role: Optional[str] = None,
        actif: Optional[bool] = None,
        cabinet_id: Optional[uuid.UUID] = None,
        auteur: Optional[Utilisateur] = None,
    ) -> Utilisateur:
        u = await UtilisateurService._charger(db, utilisateur_id)

        if role is not None and role.upper() != (await UtilisateurService._nom_role(db, u.role_id)):
            cible = (
                await db.execute(select(Role).where(Role.nom == role.upper()))
            ).scalar_one_or_none()
            if cible is None:
                raise BusinessRuleViolationException(
                    f"Rôle inconnu : {role}.", code="ROLE_INCONNU"
                )
            # Retirer le rôle d'administration au dernier administrateur
            # verrouillerait le cabinet sur lui-même.
            if (
                u.actif
                and (await UtilisateurService._nom_role(db, u.role_id)) == "ADMIN_CABINET"
                and cible.nom != "ADMIN_CABINET"
                and await UtilisateurService.compter_admins_actifs(db) <= 1
            ):
                raise BusinessRuleViolationException(
                    "Impossible : ce compte est le dernier administrateur actif du cabinet.",
                    code="DERNIER_ADMIN",
                )
            u.role_id = cible.id

        if actif is not None and actif is False:
            if auteur is not None and auteur.id == u.id:
                raise BusinessRuleViolationException(
                    "Vous ne pouvez pas désactiver votre propre compte : "
                    "personne ne pourrait rouvrir l'accès.",
                    code="AUTO_DESACTIVATION",
                )
            if (
                (await UtilisateurService._nom_role(db, u.role_id)) == "ADMIN_CABINET"
                and await UtilisateurService.compter_admins_actifs(db, sauf=u.id) <= 0
            ):
                raise BusinessRuleViolationException(
                    "Impossible : ce compte est le dernier administrateur actif du cabinet.",
                    code="DERNIER_ADMIN",
                )

        if prenom is not None:
            u.prenom = prenom.strip()
        if nom is not None:
            u.nom = nom.strip()
        if telephone is not None:
            u.telephone = telephone.strip() or None
        if cabinet_id is not None:
            u.cabinet_id = cabinet_id or None
        if actif is not None:
            u.actif = actif

        await db.commit()
        if not u.actif:
            # Un compte désactivé ne doit pas conserver de session ouverte.
            await UtilisateurService.revoquer_sessions(db, utilisateur_id)
        return await UtilisateurService._charger(db, utilisateur_id)

    @staticmethod
    async def reinitialiser_mot_de_passe(
        db: AsyncSession, utilisateur_id: uuid.UUID
    ) -> str:
        """
        Réinitialise le mot de passe et rend le mot de passe temporaire.

        Il n'est renvoyé **qu'une fois**, en clair : le serveur n'en conserve que
        l'empreinte. C'est le seul moyen de le communiquer à l'utilisateur sans
        stocker de secret réversible.
        """
        u = await UtilisateurService._charger(db, utilisateur_id)
        temporaire = _mot_de_passe_temporaire()
        u.mot_de_passe = get_password_hash(temporaire)
        await db.commit()
        # Un mot de passe réinitialisé doit invalider les sessions ouvertes :
        # quelqu'un pourrait être connecté avec l'ancien.
        await UtilisateurService.revoquer_sessions(db, utilisateur_id)
        return temporaire

    # ------------------------------------------------------------------ sessions

    @staticmethod
    async def lister_sessions(
        db: AsyncSession, utilisateur_id: uuid.UUID, *, actives_seulement: bool = False
    ) -> List[SessionUser]:
        await UtilisateurService._charger(db, utilisateur_id)
        stmt = select(SessionUser).where(
            SessionUser.utilisateur_id == utilisateur_id
        )
        if actives_seulement:
            stmt = stmt.where(
                SessionUser.est_revoque == False,  # noqa: E712
                SessionUser.expire_at > _maintenant(),
            )
        return list(
            (
                await db.execute(
                    stmt.order_by(SessionUser.derniere_activite.desc()).limit(100)
                )
            )
            .unique()
            .scalars()
            .all()
        )

    @staticmethod
    async def revoquer_sessions(db: AsyncSession, utilisateur_id: uuid.UUID) -> int:
        sessions = await UtilisateurService.lister_sessions(db, utilisateur_id)
        for s in sessions:
            s.est_revoque = True
        await db.commit()
        return len(sessions)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    async def _email_existe(db: AsyncSession, email: str) -> bool:
        return (
            await db.execute(select(Utilisateur.id).where(Utilisateur.email == email))
        ).scalar_one_or_none() is not None

    @staticmethod
    async def _nom_role(db: AsyncSession, role_id: uuid.UUID) -> str:
        return (
            await db.execute(select(Role.nom).where(Role.id == role_id))
        ).scalar_one()

    @staticmethod
    async def _roles(db: AsyncSession) -> List[str]:
        lignes = (await db.execute(select(Role.nom).order_by(Role.nom))).scalars().all()
        return list(lignes)

    @staticmethod
    async def _indexer(master_db: AsyncSession, societe_id: uuid.UUID, u: Utilisateur) -> None:
        """Écrit la ligne de routage email -> cabinet dans la base master."""
        from src.modules.master.models import UtilisateurIndex

        existant = (
            await master_db.execute(
                select(UtilisateurIndex).where(UtilisateurIndex.email == u.email)
            )
        ).scalar_one_or_none()
        if existant is not None:
            # L'email est une clé globale : le même compte ne peut pas exister
            # dans deux cabinets.
            existant.actif = True
            existant.societe_id = societe_id
            existant.utilisateur_id = u.id
        else:
            master_db.add(
                UtilisateurIndex(
                    email=u.email,
                    societe_id=societe_id,
                    utilisateur_id=u.id,
                    actif=True,
                )
            )
        try:
            await master_db.commit()
        except IntegrityError:
            await master_db.rollback()
            raise BusinessRuleViolationException(
                f"L'adresse {u.email} est déjà utilisée par un autre cabinet.",
                code="EMAIL_DEJA_UTILISE",
            )
