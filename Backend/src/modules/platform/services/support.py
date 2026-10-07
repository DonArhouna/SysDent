"""
Accès SUPPORT encadré au dossier d'un cabinet (Phase D).

Le principe tient en une phrase : **le support diagnostique, il n'agit pas.**

Un accès est une LIGNE en base (`acces_support`), révocable indépendamment, et un
jeton de 30 minutes non renouvelable. Aucune de ces deux garanties ne repose sur
la seule expiration du jeton : une révocation doit prendre effet IMMÉDIATEMENT,
donc chaque usage est revalidé côté base.

Trois propriétés sont défendues ici :

1. **Motif obligatoire.** Un accès sans raison écrite n'est pas un accès, c'est
   une intrusion. Le motif est journalisé AVEC le jeton (`support_reason`) et
   lisible dans le journal du cabinet.
2. **Lecture seule par défaut.** Lever cette contrainte exige la permission
   `platform.support.elevation` ET un motif renforcé (au moins
   `LONGUEUR_MOTIF_ELEVATION` caractères) : l'élévation se voit, se justifie et
   se distingue dans le journal.
3. **Traçabilité double.** Journal plateforme (immuable) + journal d'audit du
   cabinet, pour que le client puisse voir qu'un éditeur a ouvert son dossier.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    AuthenticationException,
    EntityNotFoundException,
    InvalidStateException,
    PermissionDeniedException,
)
from src.core.security import create_support_access_token
from src.modules.platform.models import (
    AccesSupport,
    StatutAccesSupport,
    TenantPlateforme,
)
from src.modules.platform.services.journal import JournalService

logger = structlog.get_logger(__name__)

#: Longueur minimale du motif lorsqu'un accès sort de la lecture seule.
LONGUEUR_MOTIF_ELEVATION = 40


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class SupportAccessService:
    """Émission, vérification et révocation des accès support."""

    # ── Émission ──────────────────────────────────────────────────────────

    @staticmethod
    async def demander(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        agent_id: uuid.UUID,
        agent_email: str,
        motif: str,
        ticket: Optional[str] = None,
        lecture_seule: bool = True,
        eleve: bool = False,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ouvre un accès et renvoie le jeton correspondant.

        Lève si le cabinet est résilié : on ne redonne pas accès à un dossier
        clos. Suspendu reste autorisé (un client suspendu appelle précisément le
        support pour comprendre pourquoi il est coupé).
        """
        motif = (motif or "").strip()
        if not motif:
            raise PermissionDeniedException(
                "Un motif est obligatoire pour ouvrir un accès support.",
                code="MOTIF_OBLIGATOIRE",
            )

        if not lecture_seule:
            if len(motif) < LONGUEUR_MOTIF_ELEVATION:
                raise PermissionDeniedException(
                    "Un accès en écriture exige un motif renforcé "
                    f"(au moins {LONGUEUR_MOTIF_ELEVATION} caractères) expliquant "
                    "pourquoi la lecture seule ne suffit pas.",
                    code="MOTIF_ELEVATION_INSUFFISANT",
                )
            if not settings.PLATFORM_SUPPORT_ELEVATION_ABILITEE:
                raise PermissionDeniedException(
                    "L'élévation d'un accès support est désactivée sur cette "
                    "installation (PLATFORM_SUPPORT_ELEVATION_ABILITEE=false).",
                    code="ELEVATION_DESACTIVEE",
                )

        tenant = (
            await db.execute(
                select(TenantPlateforme).where(TenantPlateforme.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if tenant is None:
            raise EntityNotFoundException("Cabinet", tenant_id)
        if tenant.statut_metier.value == "RESILIE":
            raise InvalidStateException(
                "Ce cabinet est résilié : son dossier n'est plus accessible au support."
            )

        duree = settings.PLATFORM_SUPPORT_TOKEN_EXPIRE_MINUTES
        acces = AccesSupport(
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_email=agent_email,
            motif=motif,
            ticket=ticket,
            lecture_seule=lecture_seule,
            statut=StatutAccesSupport.ACTIF,
            expire_le=_maintenant() + timedelta(minutes=duree),
            ip_address=ip_address,
        )
        db.add(acces)
        await db.flush()

        await JournalService.journaliser(
            db,
            action="PLATFORM_ACCES_SUPPORT_OUVERT",
            type_cible="TENANT",
            cible_id=str(tenant_id),
            tenant_id=tenant_id,
            acteur_email=agent_email,
            apres={
                "access_id": str(acces.id),
                "lecture_seule": lecture_seule,
                "ticket": ticket,
                "expire_le": acces.expire_le.isoformat(),
            },
            motif=motif,
            ip_address=ip_address,
        )
        logger.info(
            "support_acces_ouvert",
            access_id=str(acces.id),
            tenant_id=str(tenant_id),
            agent=agent_email,
            lecture_seule=lecture_seule,
        )

        token = create_support_access_token(
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            agent_email=agent_email,
            access_id=str(acces.id),
            motif=motif,
            ticket=ticket,
            lecture_seule=lecture_seule,
        )

        notifie = await _notifier_administrateur(db, tenant, acces, agent_email)
        acces.admin_notifie = notifie
        await db.flush()

        return {
            "id": acces.id,
            "jeton": token,
            "expire_le": acces.expire_le,
            "duree_minutes": duree,
            "lecture_seule": lecture_seule,
            "administrateur_notifie": notifie,
        }

    # ── Révocation ────────────────────────────────────────────────────────

    @staticmethod
    async def revoquer(
        db: AsyncSession, acces_id: uuid.UUID, revoque_par: str, motif: str
    ) -> AccesSupport:
        """
        Révoque immédiatement. Un accès déjà expiré est renvoyé tel quel plutôt
        qu'une erreur : l'opérateur doit pouvoir «确保 » l'absence d'accès sans
        Fail.
        """
        acces = (
            await db.execute(select(AccesSupport).where(AccesSupport.id == acces_id))
        ).scalar_one_or_none()
        if acces is None:
            raise EntityNotFoundException("Accès support", acces_id)
        if acces.statut == StatutAccesSupport.REVOQUE:
            return acces

        acces.statut = StatutAccesSupport.REVOQUE
        acces.revoque_at = _maintenant()
        acces.motif_revoque = motif
        await db.flush()

        await JournalService.journaliser(
            db,
            action="PLATFORM_ACCES_SUPPORT_REVOQUE",
            type_cible="TENANT",
            cible_id=str(acces.tenant_id),
            tenant_id=acces.tenant_id,
            acteur_email=revoque_par,
            avant={"statut": "ACTIF"},
            apres={"statut": "REVOQUE", "access_id": str(acces.id)},
            motif=motif,
        )
        logger.info(
            "support_acces_revoque",
            access_id=str(acces.id),
            tenant_id=str(acces.tenant_id),
            par=revoque_par,
        )
        return acces

    # ── Consultation ──────────────────────────────────────────────────────

    @staticmethod
    async def lister(
        db: AsyncSession,
        *,
        tenant_id: Optional[uuid.UUID] = None,
        seulement_actifs: bool = False,
    ) -> List[AccesSupport]:
        stmt = select(AccesSupport)
        if tenant_id is not None:
            stmt = stmt.where(AccesSupport.tenant_id == tenant_id)
        if seulement_actifs:
            now = _maintenant()
            stmt = stmt.where(
                AccesSupport.statut == StatutAccesSupport.ACTIF,
                AccesSupport.expire_le > now,
            )
        return list((await db.execute(stmt.order_by(AccesSupport.created_at.desc()))).scalars().all())

    @staticmethod
    async def verifier_acces(db: AsyncSession, access_id: str) -> AccesSupport:
        """
        Revalide un accès à chaque usage.

        Indispensable : un jeton révoqué reste cryptographiquement valide
        jusqu'à son expiration. Sans cette relecture, « révocation immédiate »
        ne serait qu'une intention.
        """
        try:
            identifiant = uuid.UUID(str(access_id))
        except ValueError:
            raise AuthenticationException("Accès support inconnu.", code="SUPPORT_ACCESS_INCONNU")

        acces = (
            await db.execute(select(AccesSupport).where(AccesSupport.id == identifiant))
        ).scalar_one_or_none()
        if acces is None:
            raise AuthenticationException("Accès support inconnu.", code="SUPPORT_ACCESS_INCONNU")
        if acces.statut == StatutAccesSupport.REVOQUE:
            raise AuthenticationException(
                "Cet accès support a été révoqué.", code="SUPPORT_ACCESS_REVOQUE"
            )
        if acces.expire_le <= _maintenant():
            acces.statut = StatutAccesSupport.EXPIRE
            await db.flush()
            raise AuthenticationException(
                "Cet accès support a expiré.", code="SUPPORT_ACCESS_EXPIRE"
            )
        return acces


async def _notifier_administrateur(
    db: AsyncSession, tenant: TenantPlateforme, acces: AccesSupport, agent_email: str
) -> bool:
    """
    Informe l'administrateur du cabinet de l'accès (optionnel, configurable).

    L'information n'est jamais bloquante : un serveur d'email indisponible ne
    doit pas empêcher un diagnostic. L'événement est de toute façon dans le
    journal du cabinet, qui est la preuve de référence.
    """
    if not settings.PLATFORM_SUPPORT_NOTIFIER_ADMIN:
        return False
    if not tenant.admin_email:
        return False

    try:
        from src.modules.platform.services.notifications import EmailService

        await EmailService.notification_acces_support(
            destinataire=tenant.admin_email,
            agent=agent_email,
            motif=acces.motif,
            ticket=acces.ticket or "",
        )
        return True
    except Exception as exc:  # noqa: BLE001 - la notification ne doit jamais bloquer
        logger.warning(
            "support_notification_admin_echouee",
            tenant_id=str(tenant.tenant_id),
            erreur=str(exc),
        )
        return False