"""
Journal d'audit de la console PLATEFORME (Phase E.2).

Le journal est APPEND-ONLY à deux niveaux :

- **en base** : le déclencheur `journal_audit_plateforme_append_only` interdit
  `UPDATE`, `DELETE` et `TRUNCATE` (migrations `bc633ae8cd75` et `a41d7c93e2b6`) ;
- **en code** : ce service n'expose que `journaliser()`. Il n'existe aucun
  `update()` ni `delete()` dans tout le module plateforme, donc aucune route ne
  peutAltérer l'historique même par erreur.

Le second niveau est une commodité ; le premier est la garantie. Si une
régression introduisait demain une suppression depuis l'application, la base la
refuserait.
"""

import uuid
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.models import JournalAuditPlateforme
from src.modules.platform.permissions import PERMISSIONS_SENSIBLES

logger = structlog.get_logger(__name__)


class JournalService:
    """Écriture et consultation du journal d'audit plateforme."""

    @staticmethod
    async def journaliser(
        db: AsyncSession,
        *,
        action: str,
        type_cible: str,
        acteur_email: str,
        acteur_id: Optional[uuid.UUID] = None,
        cible_id: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        avant: Optional[Dict[str, Any]] = None,
        apres: Optional[Dict[str, Any]] = None,
        motif: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> JournalAuditPlateforme:
        """
        Ajoute une entrée au journal. Ne valide PAS (flush seulement) : l'entrée
        est écrite dans la transaction métier, donc une action annulée n'a pas
        laissé de trace d'audit d'un changement qui n'a pas eu lieu.
        """
        entree = JournalAuditPlateforme(
            acteur_id=acteur_id,
            acteur_email=acteur_email,
            action=action,
            type_cible=type_cible,
            cible_id=str(cible_id) if cible_id else None,
            tenant_id=tenant_id,
            avant=_assainir(avant),
            apres=_assainir(apres),
            motif=motif,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        db.add(entree)
        await db.flush()

        if action in PERMISSIONS_SENSIBLES:
            logger.warning(
                "action_plateforme_sensible",
                action=action,
                cible=type_cible,
                cible_id=cible_id,
                tenant_id=str(tenant_id) if tenant_id else None,
                acteur=acteur_email,
                motif=motif,
            )
        return entree

    @staticmethod
    async def compter(db: AsyncSession, filtres: Dict[str, Any]) -> int:
        stmt = select(func.count(JournalAuditPlateforme.id))
        stmt = _appliquer_filtres(stmt, filtres)
        resultat = await db.execute(stmt)
        return int(resultat.scalar_one())

    @staticmethod
    async def lister(
        db: AsyncSession,
        filtres: Dict[str, Any],
        limit: int = 50,
        offset: int = 0,
    ) -> List[JournalAuditPlateforme]:
        stmt = select(JournalAuditPlateforme)
        stmt = _appliquer_filtres(stmt, filtres)
        stmt = stmt.order_by(JournalAuditPlateforme.horodatage.desc()).limit(limit).offset(offset)
        resultat = await db.execute(stmt)
        return list(resultat.scalars().all())

    @staticmethod
    async def export_csv(db: AsyncSession, filtres: Dict[str, Any], limite: int = 50_000) -> str:
        """
        Export CSV du journal, pour une analyse externe (RGPD, audit sécurité).

        Le journal étant append-only (déclencheurs PostgreSQL interdisant UPDATE,
        DELETE et TRUNCATE), un export est le seul moyen de le sortir du système —
        d'où l'importance qu'il soit délimité : un `SELECT` sans borne sur une
        table qui ne se purge jamais est une denial of service à retardement.
        """
        import csv
        import io as _io

        stmt = _appliquer_filtres(select(JournalAuditPlateforme), filtres)
        stmt = stmt.order_by(JournalAuditPlateforme.horodatage.desc()).limit(limite)
        entrees = list((await db.execute(stmt)).scalars().all())

        tampon = _io.StringIO()
        colonnes = [
            "horodatage",
            "acteur_email",
            "acteur_id",
            "action",
            "type_cible",
            "cible_id",
            "tenant_id",
            "ip_address",
            "user_agent",
            "motif",
            "avant",
            "apres",
        ]
        writer = csv.DictWriter(tampon, fieldnames=colonnes, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for e in entrees:
            writer.writerow(
                {
                    "horodatage": e.horodatage.isoformat() if e.horodatage else "",
                    "acteur_email": e.acteur_email or "",
                    "acteur_id": str(e.acteur_id) if e.acteur_id else "",
                    "action": e.action,
                    "type_cible": e.type_cible or "",
                    "cible_id": e.cible_id or "",
                    "tenant_id": str(e.tenant_id) if e.tenant_id else "",
                    "ip_address": e.ip_address or "",
                    "user_agent": e.user_agent or "",
                    "motif": e.motif or "",
                    "avant": _json_bien_forme(e.avant),
                    "apres": _json_bien_forme(e.apres),
                }
            )
        return tampon.getvalue()


def _json_bien_forme(valeur) -> str:
    """JSON compact sur une seule ligne : un champ multi-ligne casserait le CSV."""
    import json

    if not valeur:
        return ""
    return json.dumps(valeur, ensure_ascii=False, separators=(",", ":"), default=str)


def _appliquer_filtres(stmt, filtres: Dict[str, Any]):
    """Applique les filtres de consultation du journal (acteur, tenant, action, période)."""
    from datetime import datetime

    if filtres.get("acteur_email"):
        stmt = stmt.where(JournalAuditPlateforme.acteur_email == filtres["acteur_email"])
    if filtres.get("acteur_id"):
        stmt = stmt.where(JournalAuditPlateforme.acteur_id == uuid.UUID(str(filtres["acteur_id"])))
    if filtres.get("tenant_id"):
        stmt = stmt.where(JournalAuditPlateforme.tenant_id == uuid.UUID(str(filtres["tenant_id"])))
    if filtres.get("action"):
        stmt = stmt.where(JournalAuditPlateforme.action == filtres["action"])
    if filtres.get("type_cible"):
        stmt = stmt.where(JournalAuditPlateforme.type_cible == filtres["type_cible"])
    if filtres.get("cible_id"):
        stmt = stmt.where(JournalAuditPlateforme.cible_id == str(filtres["cible_id"]))
    if filtres.get("debut"):
        stmt = stmt.where(JournalAuditPlateforme.horodatage >= filtres["debut"])
    if filtres.get("fin"):
        stmt = stmt.where(JournalAuditPlateforme.horodatage <= filtres["fin"])
    if filtres.get("motif"):
        stmt = stmt.where(JournalAuditPlateforme.motif.ilike(f"%{filtres['motif']}%"))
    return stmt


CHAMPS_INTERDITS_AUDIT = {
    "mot_de_passe",
    "mot_de_passe_hash",
    "secret",
    "secret_2fa",
    "secret_2fa_chiffre",
    "refresh_token",
    "refresh_token_hash",
    "token",
    "db_password",
    "code",
    "code_2fa",
}


def _assainir(donnees: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Retire les secrets d'un instantané avant/après.

    Le journal est consulté par des rôles « lecture seule » et exportable en CSV :
    il ne doit contenir à aucun moment un hachage de mot de passe, un secret TOTP
    ou un jeton de session. On échoue bruyamment si on en trouve un, plutôt que de
    le retirer en silence — un champ oublié est un signal, pas un détail.
    """
    if donnees is None:
        return None
    trouves = CHAMPS_INTERDITS_AUDIT.intersection(donnees)
    if trouves:
        raise ValueError(
            f"Refus d'écrire dans le journal : champ(s) sensible(s) {sorted(trouves)}. "
            "Un instantané d'audit ne doit contenir aucun secret."
        )
    return donnees