"""
Logo d'un cabinet, stocké en base master.

Le format est reconnu **sur le contenu** (signature des premiers octets), jamais
sur le nom ou le type annoncé par le navigateur : un fichier `logo.png` qui est
en réalité autre chose est refusé.

**SVG exclu** : un SVG peut embarquer du script ; servi depuis le domaine de
l'API, il deviendrait une faille. PNG, JPEG et WebP suffisent pour un logo.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BusinessRuleViolationException, EntityNotFoundException
from src.modules.master.models import Societe

TAILLE_MAX = 512 * 1024


def type_image(contenu: bytes) -> Optional[str]:
    """Type MIME d'après la signature du fichier ; `None` si non reconnu."""
    if contenu.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenu.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(contenu) >= 12 and contenu[:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    return None


def url_logo(societe_id: uuid.UUID, maj: datetime) -> str:
    """Adresse publique ; `v` change à chaque envoi, ce qui contourne les caches."""
    return f"/api/v1/logos/{societe_id}?v={int(maj.timestamp())}"


class LogoService:
    @staticmethod
    async def enregistrer(master_db: AsyncSession, societe_id: uuid.UUID, contenu: bytes) -> str:
        if not contenu:
            raise BusinessRuleViolationException("Fichier vide.", code="LOGO_VIDE")
        if len(contenu) > TAILLE_MAX:
            raise BusinessRuleViolationException(
                f"Logo trop lourd ({len(contenu) // 1024} Ko) : 512 Ko maximum.", code="LOGO_TROP_LOURD"
            )
        mime = type_image(contenu)
        if mime is None:
            raise BusinessRuleViolationException(
                "Format non accepté : PNG, JPEG ou WebP uniquement.", code="LOGO_FORMAT"
            )
        existe = (await master_db.execute(select(Societe.id).where(Societe.id == societe_id))).scalar_one_or_none()
        if existe is None:
            raise EntityNotFoundException("Cabinet", str(societe_id))
        maj = datetime.now(timezone.utc)
        url = url_logo(societe_id, maj)
        await master_db.execute(
            update(Societe)
            .where(Societe.id == societe_id)
            .values(logo_contenu=contenu, logo_type=mime, logo_maj=maj, logo_url=url)
        )
        await master_db.commit()
        return url

    @staticmethod
    async def supprimer(master_db: AsyncSession, societe_id: uuid.UUID) -> None:
        await master_db.execute(
            update(Societe)
            .where(Societe.id == societe_id)
            .values(logo_contenu=None, logo_type=None, logo_maj=None, logo_url=None)
        )
        await master_db.commit()

    @staticmethod
    async def lire(master_db: AsyncSession, societe_id: uuid.UUID) -> Optional[tuple[bytes, str]]:
        ligne = (
            await master_db.execute(
                select(Societe.logo_contenu, Societe.logo_type).where(Societe.id == societe_id)
            )
        ).first()
        if ligne is None or ligne[0] is None:
            return None
        return ligne[0], ligne[1]
