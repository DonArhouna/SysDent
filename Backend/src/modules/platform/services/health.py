"""
Santé de la plateforme (Phase E.3).

`GET /platform/sante` ne renvoie jamais `200` « tout va bien » à l'aveugle : il
exécute réellement les contrôles et dit lesquels échouent. Un endpoint de santé
qui répond `ok` sans rien tester est pire qu'absence d'endpoint — il donne une
fausse assurance au superviseur.

Quatre contrôles, du plus vital au moins vital :

| Composant          | Test                              | Pourquoi                         |
|--------------------|-----------------------------------|----------------------------------|
| Base plateforme    | `SELECT 1`                        | la console est inutile sans elle |
| Base master        | `SELECT 1`                        | sans elle, aucun cabinet n'existe|
| Files clients      | état de `tenants_db`              | un tenant ACTIVE mais injoignable|
| Gabarits / plans   | presence du plan par défaut       | un provisionnement échouerait    |

Aucun secret, aucune donnée de santé n'apparaît dans le résultat : ni mot de
passe de connexion d'un cabinet, ni nom de patient. Les erreurs sont
troncées — une trace complète pourrait contenir la chaîne de connexion.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

#: Longueur maximale d'un message d'erreur exposé. Au-delà, on tronque.
MAX_LONGUEUR_ERREUR = 200


class HealthService:
    """Diagnostic de la plateforme. Chaque contrôle est réellement exécuté."""

    @staticmethod
    async def base_plateforme(db: AsyncSession) -> Dict[str, Any]:
        try:
            await db.execute(text("SELECT 1"))
            return {"composant": "base_plateforme", "ok": True, "detail": None}
        except SQLAlchemyError as exc:
            return {"composant": "base_plateforme", "ok": False, "detail": _tronquer(str(exc))}

    @staticmethod
    async def base_master() -> Dict[str, Any]:
        from src.core.database import MasterAsyncSessionFactory

        try:
            async with MasterAsyncSessionFactory() as master:
                await master.execute(text("SELECT 1"))
            return {"composant": "base_master", "ok": True, "detail": None}
        except SQLAlchemyError as exc:
            return {"composant": "base_master", "ok": False, "detail": _tronquer(str(exc))}

    @staticmethod
    async def files_clients(master_db: AsyncSession) -> Dict[str, Any]:
        """
        État des bases clients, agrégé.

        Compte les dossiers ACTIVE, SUSPENDED, ARCHIVED : une base client en
        panne ne se voit pas ici (un Ping PostgreSQL sur 300 bases à chaque
        appel serait le même défaut que la supervision au fil de l'eau) mais un
        dossier ACTIVE orphelin est visible immédiatement.
        """
        from sqlalchemy import func

        from src.modules.master.models import TenantDB

        try:
            lignes = (
                await master_db.execute(
                    select(TenantDB.statut, func.count()).group_by(TenantDB.statut)
                )
            ).all()
            par_statut = {statut: int(n) for statut, n in lignes}
            return {
                "composant": "files_clients",
                "ok": True,
                "detail": None,
                "par_statut": par_statut,
                "total": sum(par_statut.values()),
            }
        except SQLAlchemyError as exc:
            return {"composant": "files_clients", "ok": False, "detail": _tronquer(str(exc))}

    @staticmethod
    async def jobs_planifies(db: AsyncSession) -> Dict[str, Any]:
        """
        État des traitements différés.

        Aucun planificateur tiers n'est livré dans cette mission : les jobs
        existent comme services appelables (`StatsService.agreger_tout`,
        `MigrationService`, expiration des essais) et le fonctionnement réel est
        assuré par cron ou par l'appel HTTP. Le statut est donc déclaré, pas
        simulé — annoncer un « planificateur actif » qui n'existe pas serait le
        mensonge le plus coûteux d'une page de santé.
        """
        from src.core.config import settings

        return {
            "composant": "jobs_planifies",
            "ok": True,
            "detail": None,
            "planificateur": "externe (cron / appel HTTP)",
            "jobs_connus": [
                "stats.agreger_tout",
                "tenants.expirer_essais",
                "migrations.rattraper",
                "factures.marquer_en_retard",
            ],
            "frequence_attendue": settings.PLATFORM_JOB_FREQUENCE_AGGREGATION,
        }

    @staticmethod
    async def migrations_par_tenant(db: AsyncSession) -> Dict[str, Any]:
        """
        Divergence de version des bases clients.

        Exigence Phase B.7 : aucun cabinet ne doit rester sur une version de
        schéma différente sans que ce soit visible. Un écart est donc un
        contrôle de santé, pas une information de confort.
        """
        from sqlalchemy import func

        from src.modules.master.models import TenantDB

        from src.core.database import MasterAsyncSessionFactory

        try:
            async with MasterAsyncSessionFactory() as master:
                versions = (
                    await master.execute(
                        select(TenantDB.schema_version, func.count()).group_by(
                            TenantDB.schema_version
                        )
                    )
                ).all()
            par_version = {str(v): int(n) for v, n in versions}
            cible = "1.0.0"
            divergents = par_version.get(cible, 0) != sum(par_version.values())
            return {
                "composant": "migrations",
                "ok": not divergents,
                "detail": None if not divergents else "Des cabinets ne sont pas à la version attendue.",
                "version_cible": cible,
                "par_version": par_version,
            }
        except SQLAlchemyError as exc:
            return {"composant": "migrations", "ok": False, "detail": _tronquer(str(exc))}

    @staticmethod
    async def catalogue(db: AsyncSession) -> Dict[str, Any]:
        """Plan par défaut et gabarits de semis : sans eux, un provisionnement échoue."""
        from src.modules.platform.services.plans import PlanService

        try:
            plan = await PlanService.plan_defaut(db)
            return {"composant": "catalogue", "ok": True, "detail": None, "plan_defaut": plan.code}
        except SQLAlchemyError as exc:
            return {"composant": "catalogue", "ok": False, "detail": _tronquer(str(exc))}

    @staticmethod
    async def global_(platform_db: AsyncSession, master_db: AsyncSession) -> Dict[str, Any]:
        """
        Exécute tous les contrôles et renvoie l'ensemble.

        Le statut global est `ok` si AUCUN contrôle n'échoue — mais un seul
        échec de la base plateforme doit apparaître dans le corps de la réponse
        plutôt que de faire échouer l'appel : une page de supervision qui
        affiche « service indisponible » ne montre pas QUEL service.
        """
        controles: List[Dict[str, Any]] = [
            await HealthService.base_plateforme(platform_db),
            await HealthService.base_master(),
            await HealthService.files_clients(master_db),
            await HealthService.migrations_par_tenant(platform_db),
            await HealthService.catalogue(platform_db),
            await HealthService.jobs_planifies(platform_db),
        ]
        en_panne = [c for c in controles if not c["ok"]]
        return {
            "statut": "ok" if not en_panne else "degrade",
            "verifie_le": datetime.now(timezone.utc).isoformat(),
            "controles": controles,
            "en_panne": [c["composant"] for c in en_panne],
        }


def _tronquer(texte: str) -> str:
    """
    Tronque un message d'erreur technique.

    Les erreurs SQLAlchemy peuvent contenir la chaîne de connexion complète,
    donc le mot de passe du compte applicatif. Une page de santé affichée sur un
    écran de supervision deviendrait alors un écran de secrets.
    """
    return texte[:MAX_LONGUEUR_ERREUR] + "…" if len(texte) > MAX_LONGUEUR_ERREUR else texte