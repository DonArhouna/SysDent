"""
Accès des administrateurs d'un cabinet, depuis la console.

Cas typique : l'administrateur d'un cabinet a oublié son mot de passe ou perdu
son téléphone, et personne dans le cabinet ne peut le dépanner.

**La console ne fixe jamais un mot de passe choisi par un agent** : il
connaîtrait alors le secret d'un compte qui ouvre des dossiers médicaux. Trois
actions seulement :

- ``lien`` (recommandé) : lien de réinitialisation par e-mail, la personne
  choisit elle-même son mot de passe ;
- ``temporaire`` : mot de passe GÉNÉRÉ par le serveur, rendu une seule fois,
  changement imposé à la connexion suivante ;
- ``deux_facteurs`` : remise à zéro de la 2FA (téléphone perdu) ; elle est
  reconfigurée à la connexion suivante (obligatoire pour un administrateur).

Garde-fous, comme pour les rôles d'un cabinet : droit dédié et sensible
(``platform.tenants.reset_access``), motif obligatoire, sessions coupées, trace
dans le journal de la console ET dans celui du cabinet. Le périmètre est borné
aux comptes administrateurs : les autres comptes relèvent de l'administrateur
du cabinet lui-même.
"""

import uuid
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.platform.services.journal import JournalService

logger = structlog.get_logger(__name__)

ROLES_ADMIN = ("ADMIN_CABINET",)

LIBELLES = {
    "lien": "lien de réinitialisation envoyé",
    "temporaire": "mot de passe temporaire généré",
    "deux_facteurs": "double authentification réinitialisée",
}


def _vue(u) -> Dict[str, Any]:
    return {
        "id": str(u.id),
        "email": u.email,
        "prenom": u.prenom,
        "nom": u.nom,
        "actif": u.actif,
        "activation_requise": u.activation_requise,
        "doit_changer_mot_de_passe": u.doit_changer_mot_de_passe,
        "deux_facteurs": u.deux_facteurs,
        "dernier_login": u.dernier_login,
    }


class AccesCabinetService:
    @staticmethod
    async def lister_admins(tenant_id: uuid.UUID) -> List[Dict[str, Any]]:
        from src.modules.auth.securite import session_cabinet
        from src.modules.tenants.models import Role, Utilisateur

        async with await session_cabinet(str(tenant_id)) as db:
            lignes = (
                await db.execute(
                    select(Utilisateur)
                    .join(Role, Role.id == Utilisateur.role_id)
                    .where(Role.nom.in_(ROLES_ADMIN))
                    .order_by(Utilisateur.nom, Utilisateur.prenom)
                )
            ).scalars().all()
            return [_vue(u) for u in lignes]

    @staticmethod
    async def agir(
        platform_db: AsyncSession,
        tenant_id: uuid.UUID,
        utilisateur_id: uuid.UUID,
        action: str,
        motif: str,
        auteur_email: str,
        auteur_id: Optional[uuid.UUID] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exécute l'action ; rend la vue du compte et, pour `temporaire`, le mot de passe (une fois)."""
        from src.modules.audit.services import AuditService
        from src.modules.auth.securite import SecuriteCompte, session_cabinet
        from src.modules.auth.services import AuthService
        from src.modules.tenants.models import Utilisateur
        from src.modules.utilisateurs.services import _mot_de_passe_temporaire
        from src.core.security import get_password_hash

        if action not in LIBELLES:
            raise BusinessRuleViolationException("Action inconnue.", code="ACTION_INCONNUE")

        temporaire: Optional[str] = None
        async with await session_cabinet(str(tenant_id)) as db:
            u = (
                await db.execute(
                    select(Utilisateur).options(selectinload(Utilisateur.role)).where(Utilisateur.id == utilisateur_id)
                )
            ).scalar_one_or_none()
            if u is None:
                raise EntityNotFoundException("Compte du cabinet", str(utilisateur_id))
            if u.role is None or u.role.nom not in ROLES_ADMIN:
                raise BusinessRuleViolationException(
                    "Seuls les comptes administrateurs d'un cabinet se dépannent depuis la console. "
                    "Les autres comptes relèvent de l'administrateur du cabinet.",
                    code="COMPTE_HORS_PERIMETRE",
                )

            # Journal de la console d'abord (non validé) : un échec côté cabinet
            # l'annule, on ne journalise pas une action qui n'a pas eu lieu.
            await JournalService.journaliser(
                platform_db,
                action="PLATFORM_CABINET_ACCES_ADMIN",
                type_cible="TENANT",
                cible_id=str(tenant_id),
                tenant_id=tenant_id,
                acteur_email=auteur_email,
                acteur_id=auteur_id,
                apres={"compte": u.email, "action": action},
                motif=motif,
                ip_address=ip,
                user_agent=user_agent,
            )

            await AuthService.revoquer_toutes_sessions(db, u.id)
            if action == "temporaire":
                temporaire = _mot_de_passe_temporaire(14)
                u.mot_de_passe = get_password_hash(temporaire)
                u.doit_changer_mot_de_passe = True
                u.activation_requise = False
            elif action == "deux_facteurs":
                u.deux_facteurs = False
                u.secret_2fa = None
                u.secret_2fa_en_attente = None
                u.codes_secours_haches = None
                u.deux_facteurs_confirme_at = None

            await AuditService.log_action(
                db,
                action="ACCES_REINITIALISE_PAR_PLATEFORME",
                resource_type="UTILISATEUR",
                resource_id=str(u.id),
                user_email=f"console:{auteur_email}",
                # Jamais le mot de passe : seulement ce qui a été fait, et pourquoi.
                changes={"action": action, "motif": motif},
                ip_address=ip,
                user_agent=user_agent,
            )
            envoye = True
            if action == "lien":
                # Valide la session du cabinet PUIS envoie l'e-mail : le compte
                # est déjà modifié quand l'envoi est tenté.
                envoye = await SecuriteCompte.envoyer_activation(db, u, str(tenant_id), None)
            else:
                await db.commit()
            vue = _vue(u)

        # Le changement a eu lieu dans le cabinet : il est journalisé même si
        # l'e-mail n'est pas parti, puis l'échec d'envoi est signalé.
        await platform_db.commit()
        if not envoye:
            raise BusinessRuleViolationException(
                "Le compte a été réinitialisé, mais le lien n'a pas pu être envoyé par e-mail. "
                "Vérifiez la configuration SMTP, ou générez un mot de passe temporaire.",
                code="ENVOI_EMAIL_ECHOUE",
            )
        logger.info("acces_admin_cabinet", tenant_id=str(tenant_id), compte=vue["email"], action=action, auteur=auteur_email)
        return {"compte": vue, "mot_de_passe_temporaire": temporaire, "message": LIBELLES[action]}


async def changer_email_admin(
    platform_db: AsyncSession,
    tenant_id: uuid.UUID,
    utilisateur_id: uuid.UUID,
    nouvel_email: str,
    motif: str,
    auteur_email: str,
    auteur_id: Optional[uuid.UUID] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Change l'e-mail de CONNEXION d'un administrateur de cabinet.

    L'e-mail est la clé de routage du login (index master) : il est modifié à
    la fois dans la base du cabinet et dans l'index, ou pas du tout. Un lien
    d'activation part à la NOUVELLE adresse : la personne y choisit son mot de
    passe, ce qui prouve que l'adresse est bien la sienne. Jusque-là, le compte
    refuse toute connexion, et ses sessions sont coupées.
    """
    from sqlalchemy import update

    from src.core.database import MasterAsyncSessionFactory
    from src.modules.audit.services import AuditService
    from src.modules.auth.securite import SecuriteCompte, session_cabinet
    from src.modules.auth.services import AuthService
    from src.modules.master.models import UtilisateurIndex
    from src.modules.platform.models import TenantPlateforme
    from src.modules.tenants.models import Utilisateur

    nouvel_email = nouvel_email.strip().lower()

    async with MasterAsyncSessionFactory() as master, await session_cabinet(str(tenant_id)) as db:
        u = (
            await db.execute(
                select(Utilisateur).options(selectinload(Utilisateur.role)).where(Utilisateur.id == utilisateur_id)
            )
        ).scalar_one_or_none()
        if u is None:
            raise EntityNotFoundException("Compte du cabinet", str(utilisateur_id))
        if u.role is None or u.role.nom not in ROLES_ADMIN:
            raise BusinessRuleViolationException(
                "Seuls les comptes administrateurs d'un cabinet se gèrent depuis la console.",
                code="COMPTE_HORS_PERIMETRE",
            )
        ancien = u.email
        if nouvel_email == ancien:
            raise BusinessRuleViolationException("C'est déjà l'adresse de ce compte.", code="EMAIL_IDENTIQUE")

        # Unicité GLOBALE : l'index master couvre tous les cabinets.
        pris = (
            await master.execute(select(UtilisateurIndex.email).where(UtilisateurIndex.email == nouvel_email))
        ).scalar_one_or_none() or (
            await db.execute(select(Utilisateur.id).where(Utilisateur.email == nouvel_email))
        ).scalar_one_or_none()
        if pris:
            raise BusinessRuleViolationException(
                "Cette adresse est déjà utilisée par un autre compte.", code="EMAIL_DEJA_UTILISE"
            )

        await JournalService.journaliser(
            platform_db,
            action="PLATFORM_CABINET_EMAIL_ADMIN_MODIFIE",
            type_cible="TENANT",
            cible_id=str(tenant_id),
            tenant_id=tenant_id,
            acteur_email=auteur_email,
            acteur_id=auteur_id,
            avant={"email": ancien},
            apres={"email": nouvel_email},
            motif=motif,
            ip_address=ip,
            user_agent=user_agent,
        )

        # Index master d'abord (non validé), puis le cabinet (validé avec l'envoi
        # du lien), puis l'index. Si l'index échoue en dernier, le cabinet est
        # remis à l'ancienne adresse : jamais un compte injoignable.
        await master.execute(
            update(UtilisateurIndex).where(UtilisateurIndex.email == ancien).values(email=nouvel_email)
        )
        u.email = nouvel_email
        await AuthService.revoquer_toutes_sessions(db, u.id)
        await AuditService.log_action(
            db,
            action="EMAIL_MODIFIE_PAR_PLATEFORME",
            resource_type="UTILISATEUR",
            resource_id=str(u.id),
            user_email=f"console:{auteur_email}",
            changes={"avant": ancien, "apres": nouvel_email, "motif": motif},
            ip_address=ip,
            user_agent=user_agent,
        )
        envoye = await SecuriteCompte.envoyer_activation(db, u, str(tenant_id), None)
        try:
            await master.commit()
        except Exception:
            u.email = ancien
            await db.commit()
            raise
        vue = _vue(u)

    # Adresse de l'administrateur connue de la console, si c'était celle-ci.
    await platform_db.execute(
        update(TenantPlateforme)
        .where(TenantPlateforme.tenant_id == tenant_id, TenantPlateforme.admin_email == ancien)
        .values(admin_email=nouvel_email)
    )
    await platform_db.commit()
    logger.info("email_admin_cabinet_modifie", tenant_id=str(tenant_id), auteur=auteur_email)
    if not envoye:
        raise BusinessRuleViolationException(
            "L'adresse a été changée, mais le lien d'activation n'a pas pu être envoyé. "
            "Renvoyez-le avec « Lien de réinitialisation », ou générez un mot de passe temporaire.",
            code="ENVOI_EMAIL_ECHOUE",
        )
    return vue
