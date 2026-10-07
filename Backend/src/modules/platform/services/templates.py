"""
Gabarits de semis versionnés (Phase B.6).

Avant cette mission, la nomenclature d'actes, le formulaire médicamenteux et la
matrice RBAC étaient écrits EN DUR dans le code
(`ordonnances/services.FORMULAIRE_DENTAIRE`, `common/permissions.py`). Corriger
la base de démonstration d'un client exigeait donc un redéploiement — et
l'impossibilité de corriger la base d'un cabinet existant sans le faire.

Ici, ces données deviennent des **gabarits versionnés** en base, publiés par
l'équipe éditrice et COPIÉS dans chaque nouveau cabinet. Un cabinet déjà
provisionné n'est pas modifié : c'est le comportement attendu d'un catalogue de
produit, et c'est ce qui rend la correction d'un gabarit sans risque.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.platform.models import GabaritSemis, TypeGabarit

logger = structlog.get_logger(__name__)

#: Codes de gabarits attendus par le provisionnement. Un gabarit manquant n'est
#: pas bloquant : le provisionnement journalise un avertissement et continue avec
#: le comportement par défaut du code, pour qu'une erreur de catalogue n'empêche
#: pas de créer un cabinet.
GABARITS_ATTENDUS = ("formulaire", "roles", "parametres", "actes")


class TemplateService:
    @staticmethod
    async def publier(
        db: AsyncSession,
        *,
        code: str,
        type_gabarit: TypeGabarit,
        libelle: str,
        contenu: Any,
        auteur: str,
        activer: bool = True,
    ) -> GabaritSemis:
        """
        Publie une NOUVELLE VERSION d'un gabarit (jamais de mise à jour en place).

        Le contenu précédent est conservé : c'est ce qui permet de savoir ce
        qu'un cabinet a réellement reçu à son provisionnement.
        """
        dernier = await TemplateService.version_active(db, code)
        version = (dernier.version + 1) if dernier is not None else 1

        if activer:
            # Une seule version active par code : le provisionnement prend
            # toujours la dernière publiée, jamais un mélange.
            stmt = select(GabaritSemis).where(GabaritSemis.code == code, GabaritSemis.actif.is_(True))
            for ancien in (await db.execute(stmt)).scalars().all():
                ancien.actif = False

        gabarit = GabaritSemis(
            code=code,
            version=version,
            type_gabarit=type_gabarit,
            libelle=libelle,
            contenu=contenu,
            actif=activer,
            cree_par=auteur,
        )
        db.add(gabarit)
        await db.flush()
        logger.info(
            "gabarit_publie", code=code, version=version, type=type_gabarit.value
        )
        return gabarit

    @staticmethod
    async def version_active(db: AsyncSession, code: str) -> Optional[GabaritSemis]:
        stmt = (
            select(GabaritSemis)
            .where(GabaritSemis.code == code, GabaritSemis.actif.is_(True))
            .order_by(GabaritSemis.version.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def historique(db: AsyncSession, code: str) -> List[GabaritSemis]:
        stmt = (
            select(GabaritSemis)
            .where(GabaritSemis.code == code)
            .order_by(GabaritSemis.version.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def obtenir_contenu(db: AsyncSession, code: str) -> Optional[Any]:
        """Contenu du gabarit actif, ou `None` s'il n'en existe pas."""
        gabarit = await TemplateService.version_active(db, code)
        return gabarit.contenu if gabarit is not None else None

    @staticmethod
    async def lister(db: AsyncSession, type_gabarit: Optional[str] = None) -> List[GabaritSemis]:
        stmt = select(GabaritSemis).order_by(GabaritSemis.code, GabaritSemis.version.desc())
        if type_gabarit:
            stmt = stmt.where(GabaritSemis.type_gabarit == type_gabarit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def basculer(db: AsyncSession, gabarit_id, actif: bool) -> GabaritSemis:
        stmt = select(GabaritSemis).where(GabaritSemis.id == gabarit_id)
        gabarit = (await db.execute(stmt)).scalar_one_or_none()
        if gabarit is None:
            raise EntityNotFoundException("Gabarit de semis", gabarit_id)
        gabarit.actif = actif
        await db.flush()
        return gabarit