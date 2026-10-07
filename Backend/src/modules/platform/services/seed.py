"""
Semis d'un cabinet neuf (Phase B.4 et B.6).

C'est ici que le provisionnement « remplit » la base d'un cabinet : RBAC,
référentiel médicamenteux, nomenclature d'actes, paramètres, premier cabinet
physique et premier administrateur.

Les données de référence proviennent des **gabarits versionnés** de la base
plateforme (`gabarits_semis`). En l'absence de gabarit pour un code, le service
retombe sur le comportement historique du code et journalise un avertissement :
une erreur de catalogue ne doit pas empêcher un client de s'abonner.
"""

from datetime import date
from typing import Any, Dict, Optional
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import tenant_db_manager
from src.core.security import get_password_hash
from src.modules.tenants.models import (
    Cabinet,
    CabinetPraticien,
    Praticien,
    Role,
    Utilisateur,
)

logger = structlog.get_logger(__name__)

GABARIT_FORMULAIRE = "formulaire"


class TenantSeedService:
    @staticmethod
    async def semer(
        societe_id: uuid.UUID,
        db_name: str,
        platform_db: AsyncSession,
        *,
        nom_cabinet: Optional[str] = None,
        admin_email: Optional[str] = None,
        admin_prenom: Optional[str] = None,
        admin_nom: Optional[str] = None,
        admin_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Remplit la base du cabinet et renvoie les gabarits appliqués ET
        l'identifiant du compte administrateur.

        L'identifiant est nécessaire au provisionnement : la colonne
        `utilisateur_index.utilisateur_id` est NOT NULL, donc l'index de routage
        ne peut être écrit qu'APRÈS la création du compte.

        L'import de `RbacService` est local : au niveau module il créerait un
        cycle (platform → rbac → auth.dependencies → master.models).
        """
        from src.modules.rbac.services import RbacService
        from src.modules.platform.services.templates import TemplateService

        await tenant_db_manager.get_or_create_engine(
            tenant_id=str(societe_id),
            db_name=db_name,
        )
        session_factory = await tenant_db_manager.get_session_factory(str(societe_id))

        gabarit_formulaire = await TemplateService.obtenir_contenu(
            platform_db, GABARIT_FORMULAIRE
        )

        async with session_factory() as session:
            # ── RBAC : permissions + rôles + matrice ──────────────────────────
            await RbacService.bootstrap_complet(session)

            # ── Référentiel médicamenteux ─────────────────────────────────────
            # Sans lui, aucune ordonnance ne peut être émise et le contrôle de
            # contre-indication n'a aucune règle à appliquer.
            await TenantSeedService._semer_formulaire(session, gabarit_formulaire)

            # ── Premier cabinet ────────────────────────────────────────────────
            # Un cabinet sans enregistrement ne peut ni consulter ni facturer :
            # le premier cabinet se crée donc d'office.
            nom = nom_cabinet or "Cabinet principal"
            cabinet = Cabinet(nom=nom, actif=True)
            session.add(cabinet)
            await session.flush()

            # ── Administrateur initial ─────────────────────────────────────────
            # `ADMIN_CABINET` a DÉJÀ été créé par `semer_roles()`. Le recréer ici
            # violerait la contrainte UNIQUE sur roles.nom et ferait échouer tout
            # provisionnement : on récupère donc le rôle existant.
            admin_role = (
                await session.execute(select(Role).where(Role.nom == "ADMIN_CABINET"))
            ).scalar_one()

            admin_user = Utilisateur(
                email=(admin_email or "").lower(),
                # Mot de passe initial aléatoire : l'invitation envoyée par
                # e-mail est le seul chemin d'accès réel. Un mot de passe fixe
                # « en attendant l'invitation » serait un accès permanent que
                # personne ne pense à changer.
                mot_de_passe=get_password_hash(admin_password or AdminPasswordAléatoire.genere()),
                role_id=admin_role.id,
                prenom=admin_prenom or "Administrateur",
                nom=admin_nom or "Cabinet",
                actif=True,
            )
            session.add(admin_user)
            await session.flush()

            # Le compte fondateur porte aussi un profil praticien : sans lui,
            # aucun acte ne peut être attribué (la consultation exige un auteur
            # clinique identifié). Une clinique peut ainsi facturer dès le
            # premier jour.
            praticien = Praticien(
                utilisateur_id=admin_user.id,
                titre="Dr",
                specialite="Chirurgien-Dentiste",
            )
            session.add(praticien)
            await session.flush()

            # ... et il est rattaché au cabinet fondateur. Sans ce lien, le
            # cabinet n'a AUCUN praticien rattaché : l'agenda n'a personne à
            # proposer au patient.
            session.add(
                CabinetPraticien(
                    cabinet_id=cabinet.id,
                    praticien_id=praticien.id,
                    date_debut=date.today(),
                    actif=True,
                )
            )
            await session.commit()

            utilisateur_id = admin_user.id

        await TenantSeedService._renseigner_index(
            platform_db, societe_id, admin_email, utilisateur_id
        )

        return {
            "gabarits": {
                "rbac": "code",
                GABARIT_FORMULAIRE: (
                    "gabarit" if gabarit_formulaire is not None else "code (repli)"
                ),
                "cabinet": "code",
                "admin": "code",
            },
            "utilisateur_id": str(utilisateur_id),
            "db_name": db_name,
        }

    @staticmethod
    async def _semer_formulaire(session: AsyncSession, gabarit: Optional[Any]) -> None:
        """
        Référentiel médicamenteux : gabarit plateforme si publié, code sinon.

        Le gabarit est prioritaire : c'est tout l'intérêt de la Phase B.6 — un
        correctif de contre-indication se publie sans redéploiement et atteint
        les cabinets créés après la publication.
        """
        from src.modules.tenants.models import MedicamentReferentiel
        from src.modules.ordonnances.services import MedicamentService

        if gabarit is None:
            await MedicamentService.semer_formulaire(session)
            return

        try:
            entrees = gabarit["medicaments"] if isinstance(gabarit, dict) else list(gabarit)
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "gabarit_formulaire_inutilisable",
                raison="structure inattendue, repli sur le formulaire du code",
            )
            await MedicamentService.semer_formulaire(session)
            return

        existantes = {
            m.dci.strip().lower(): m
            for m in (await session.execute(select(MedicamentReferentiel))).scalars().all()
        }
        for entree in entrees:
            cle = str(entree["dci"]).strip().lower()
            if cle in existantes:
                # Le gabarit fait autorité : on met à jour les règles.
                existantes[cle].contre_indications = entree.get("contre_indications")
                existantes[cle].precautions = entree.get("precautions")
                existantes[cle].posologie_adulte = entree.get("posologie_adulte")
                existantes[cle].classe_therapeutique = entree.get("classe_therapeutique")
                continue
            session.add(MedicamentReferentiel(**entree))
        await session.flush()

    @staticmethod
    async def _renseigner_index(
        platform_db: AsyncSession,
        societe_id: uuid.UUID,
        email: Optional[str],
        utilisateur_id: uuid.UUID,
    ) -> None:
        """Renseigne l'identifiant utilisateur dans l'index de routage master."""
        from src.core.database import MasterAsyncSessionFactory
        from src.modules.master.models import UtilisateurIndex

        if not email:
            return
        async with MasterAsyncSessionFactory() as master:
            entree = (
                await master.execute(
                    select(UtilisateurIndex).where(UtilisateurIndex.email == email.lower())
                )
            ).scalar_one_or_none()
            if entree is None:
                return
            entree.utilisateur_id = utilisateur_id
            await master.commit()

    @staticmethod
    async def etat_onboarding(tenant_id: uuid.UUID, db_name: str) -> Dict[str, bool]:
        """
        État de la checklist de démarrage (Phase F.3).

        Interroge le cabinet pour répondre à « qu'a-t-il déjà fait ? » : sans
        cela, l'assistant afficherait une liste de tâches dont certaines sont
        déjà accomplies.
        """
        from src.modules.tenants.models import Facture, Patient, Praticien, Salle

        await tenant_db_manager.get_or_create_engine(tenant_id=str(tenant_id), db_name=db_name)
        session_factory = await tenant_db_manager.get_session_factory(str(tenant_id))
        async with session_factory() as session:
            async def _existe(modele, colonne=None) -> bool:
                from sqlalchemy import func

                stmt = select(func.count()).select_from(modele)
                if colonne is not None:
                    stmt = stmt.where(colonne.is_not(None))
                return int((await session.execute(stmt)).scalar_one()) > 0

            return {
                "informations_cabinet": True,  # toujours vrai : créé au provisionnement
                "sites": await _existe(Salle),
                "praticiens": await _existe(Praticien),
                "patients": await _existe(Patient),
                "actes_tarifs": await _existe(Facture),
            }


class AdminPasswordAléatoire:
    """
    Génère un mot de passe initial jamais communiqué.

    Le premier administrateur reçoit un lien d'invitation à usage unique ; ce
    mot de passe n'est qu'un verrou provisoire. Il est aléatoire, jamais réutilisé
    d'un cabinet à l'autre, et n'apparaît dans aucun journal.
    """

    @staticmethod
    def genere(longueur: int = 32) -> str:
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(longueur))