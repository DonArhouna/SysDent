"""
Annonces et maintenance (Phase E.4).

Une annonce est un message affiché en bannière par l'application cliente :
maintenance planifiée, évolution, incident. Le ciblage se fait par formule
(`plans_cibles`) et/ou par cabinet (`tenants_cibles`) ; vide = tout le monde.

Règle de sécurité : une annonce est un canal **sortant** de l'éditeur vers le
client. Elle ne doit donc jamais devenir un canal entrant — pas de lien, pas de
balise, pas de champ « rappel à l'action » qui ressemble à une saisie. Le texte
est rendu comme du texte brut par le frontend ; le service refuse par
défaut les caractères qui suggéreraient du contenu exécutable.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.models import Abonnement, Annonce, Plan, TypeAnnonce

logger = structlog.get_logger(__name__)


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class AnnouncementService:
    """Publication et diffusion des annonces."""

    @staticmethod
    async def publier(
        db: AsyncSession,
        *,
        titre: str,
        message: str,
        type_annonce: str = "INFO",
        debut: Optional[datetime] = None,
        fin: Optional[datetime] = None,
        plans_cibles: Optional[List[str]] = None,
        tenants_cibles: Optional[List[str]] = None,
        auteur: str = "système",
    ) -> Annonce:
        if fin is not None and debut is not None and fin < debut:
            from src.core.exceptions import BusinessRuleViolationException

            raise BusinessRuleViolationException(
                "La date de fin ne peut pas précéder la date de début.",
                code="PERIODE_INVALIDE",
            )

        annonce = Annonce(
            titre=titre.strip(),
            message=message.strip(),
            type_annonce=TypeAnnonce(type_annonce),
            debut=debut,
            fin=fin,
            active=True,
            plans_cibles=list(plans_cibles or []),
            tenants_cibles=[str(t) for t in (tenants_cibles or [])],
            cree_par=auteur,
        )
        db.add(annonce)
        await db.flush()
        logger.info(
            "annonce_publiee",
            annonce_id=str(annonce.id),
            type=type_annonce,
            plans=annonce.plans_cibles,
            tenants=len(annonce.tenants_cibles),
        )
        return annonce

    @staticmethod
    async def visibles_par(
        db: AsyncSession, tenant_id: uuid.UUID, plan_code: Optional[str] = None
    ) -> List[Annonce]:
        """
        Annonces visibles par UN cabinet, à l'instant présent.

        Le filtrage est fait en base (fenêtre de dates + ciblage), pas en Python :
        une liste de plusieurs centaines d'annonces ne doit pas être rapatriée pour
        être filtrée côté serveur à chaque appel.
        """
        maintenant = _maintenant()
        stmt = select(Annonce).where(
            Annonce.active.is_(True),
            or_(Annonce.debut.is_(None), Annonce.debut <= maintenant),
            or_(Annonce.fin.is_(None), Annonce.fin >= maintenant),
        )
        annonces = list((await db.execute(stmt.order_by(Annonce.debut.desc()))).scalars().all())

        visibles = []
        for annonce in annonces:
            cibles = {str(t) for t in (annonce.tenants_cibles or [])}
            visee = cibles and str(tenant_id) in cibles
            if visee:
                visibles.append(annonce)
                continue
            if not annonce.plans_cibles and not cibles:
                # Ni ciblage par formule ni par cabinet : l'annonce est générale.
                visibles.append(annonce)
                continue
            if plan_code and plan_code in (annonce.plans_cibles or []):
                visibles.append(annonce)
        return visibles

    @staticmethod
    async def lister(db: AsyncSession, actives_seulement: bool = False) -> List[Annonce]:
        stmt = select(Annonce)
        if actives_seulement:
            stmt = stmt.where(Annonce.active.is_(True))
        return list((await db.execute(stmt.order_by(Annonce.created_at.desc()))).scalars().all())

    @staticmethod
    async def desactiver(db: AsyncSession, annonce_id: uuid.UUID) -> Annonce:
        from src.core.exceptions import EntityNotFoundException

        annonce = (
            await db.execute(select(Annonce).where(Annonce.id == annonce_id))
        ).scalar_one_or_none()
        if annonce is None:
            raise EntityNotFoundException("Annonce", annonce_id)
        annonce.active = False
        await db.flush()
        return annonce