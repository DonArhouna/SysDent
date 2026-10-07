"""
Quotas et feature flags — point central d'application (Phase C.3 et C.4).

C'est le SEUL endroit du code où l'on décide « cette action dépasse-t-elle le
contrat ? ». L'application cliente l'appelle depuis ses propres routes (création
d'un utilisateur, d'un site, d'un praticien, envoi d'un SMS, dépôt d'un fichier) ;
la console l'appelle pour simuler un tenant avant une intervention.

Deux principes :

- **Une valeur « illimitée » explicite**, jamais un `None` ambigu. Une limite
  `null` signifie « pas de quota configuré » et ne bloque jamais : c'est le
  filet de sécurité qui empêche un catalogue incomplet de couper un client en
  production.
- **Un dépassement est un refus EXPLIQUÉ**, avec le code `QUOTA_EXCEEDED` et les
  trois nombres utiles (ressource, limite, consommation). Le frontend peut
  afficher « Vous avez atteint la limite de 5 utilisateurs de la formule
  Essentiel » au lieu d'un message technique.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import PlatformFeatureException, QuotaExceededException
from src.modules.platform.models import Abonnement, StatsTenant, StatutAbonnement

logger = structlog.get_logger(__name__)

#: Ressources soumises à quota, et libellé lisible pour l'utilisateur.
LIBELLES_RESSOURCES: Dict[str, str] = {
    "utilisateurs": "utilisateurs",
    "sites": "sites",
    "praticiens": "praticiens",
    "stockage_octets": "stockage",
    "sms_par_mois": "SMS par mois",
}


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class QuotaService:
    """
    Lecture du contrat d'un cabinet et application des limites.

    Toutes les méthodes acceptent une session plateforme déjà ouverte : l'appel
    est fait dans le contexte de la requête appelante, pas dans une connexion
    séparée.
    """

    @staticmethod
    async def quotas(platform_db: AsyncSession, tenant_id) -> Dict[str, Any]:
        """
        Quotas et fonctionnalités applicables AUJOURD'HUI à un cabinet.

        Hors abonnement (cabinet nouvellement provisionné, base de démo
        antérieure au rattrapage) : on retourne des quotas illimités plutôt que
        de bloquer. Le rattrapage de la Phase C crée l'abonnement manquant.
        """
        abonnement = await QuotaService.abonnement_effectif(platform_db, tenant_id)
        if abonnement is None:
            return {"plan": None, "quotas": {}, "features": {}, "illimite": True}

        fige = abonnement.plan_fige or {}
        quotas = dict(fige.get("quotas") or {})
        # Un abonnement résilié ou suspendu conserve ses quotas : couper l'accès
        # au produit est déjà fait par le statut du tenant, et mélanger les deux
        # donnerait deux messages concurrents pour un même problème.
        return {
            "plan": fige.get("code"),
            "plan_nom": fige.get("nom"),
            "version_plan": fige.get("version"),
            "quotas": quotas,
            "features": dict(fige.get("features") or {}),
            "statut_abonnement": abonnement.statut.value,
            "illimite": False,
        }

    @staticmethod
    async def abonnement_effectif(
        platform_db: AsyncSession, tenant_id
    ) -> Optional[Abonnement]:
        return (
            await platform_db.execute(
                select(Abonnement).where(Abonnement.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def limite(platform_db: AsyncSession, tenant_id, ressource: str) -> Optional[int]:
        """
        Limite d'une ressource, ou `None` si elle n'est pas plafonnée.

        `None` signifie « illimité » et n'est jamais comparé à une consommation :
        `consommation > None` lèverait un `TypeError`, pas un refus.
        """
        quotas = (await QuotaService.quotas(platform_db, tenant_id))["quotas"]
        valeur = quotas.get(ressource)
        if valeur is None:
            return None
        try:
            return int(valeur)
        except (TypeError, ValueError):
            logger.warning("quota_incoherent", ressource=ressource, valeur=valeur)
            return None

    @staticmethod
    async def verifier(
        platform_db: AsyncSession,
        tenant_id,
        ressource: str,
        consommation_actuelle: int,
        ajoute: int = 1,
    ) -> None:
        """
        Vérifie qu'une consommation reste dans le contrat. Lève si dépassement.

        `consommation_actuelle` est fourni par l'appelant, qui connaît déjà le
        décompte dans sa base (nombre d'utilisateurs, de salles…). Le service ne
        requête jamais la base du cabinet : il ne ferait qu'ajouter un aller-retour
        réseau à un point de contrôle à chaud.
        """
        contexte = await QuotaService.quotas(platform_db, tenant_id)
        if contexte["illimite"]:
            return

        limite = contexte["quotas"].get(ressource)
        if limite is None:
            return

        try:
            limite_int = int(limite)
        except (TypeError, ValueError):
            return

        nouvelle = consommation_actuelle + ajoute
        if nouvelle > limite_int:
            raise QuotaExceededException(
                ressource=LIBELLES_RESSOURCES.get(ressource, ressource),
                limite=limite_int,
                utilise=nouvelle - 1,
                plan_code=str(contexte.get("plan") or ""),
            )

    @staticmethod
    async def simuler(
        platform_db: AsyncSession, tenant_id, ressource: str, consommation: int
    ) -> Dict[str, Any]:
        """
        Simulation d'un dépassement, pour l'écran « votre consommation » de la
        console. Ne lève jamais : une simulation qui échoue n'apprend rien à
        l'opérateur.
        """
        contexte = await QuotaService.quotas(platform_db, tenant_id)
        if contexte["illimite"]:
            return {
                "ressource": ressource,
                "illimite": True,
                "consommation": consommation,
                "limite": None,
                "taux": None,
            }
        limite = contexte["quotas"].get(ressource)
        if limite is None:
            return {
                "ressource": ressource,
                "illimite": True,
                "consommation": consommation,
                "limite": None,
                "taux": None,
            }
        limite_int = int(limite)
        return {
            "ressource": ressource,
            "illimite": False,
            "consommation": consommation,
            "limite": limite_int,
            "taux": round(consommation / limite_int * 100, 1) if limite_int else None,
            "depasse": consommation > limite_int,
        }

    @staticmethod
    async def exiger_feature(platform_db: AsyncSession, tenant_id, feature: str) -> None:
        """
        Refuse une fonctionnalité absente du contrat.

        403 et non 404 : la ressource existe, c'est la formule qui ne la couvre
        pas. L'interface peut ainsi proposer une mise à niveau au lieu d'un
        écran vide.
        """
        contexte = await QuotaService.quotas(platform_db, tenant_id)
        if contexte["illimite"]:
            return
        features = contexte.get("features") or {}
        if features.get(feature) is True:
            return
        raise PlatformFeatureException(feature, plan_code=str(contexte.get("plan") or ""))

    @staticmethod
    async def features(platform_db: AsyncSession, tenant_id) -> Dict[str, bool]:
        """Drapeaux de fonctionnalités, pour `GET /auth/me` côté client."""
        contexte = await QuotaService.quotas(platform_db, tenant_id)
        if contexte["illimite"]:
            return {}
        return dict(contexte.get("features") or {})

    @staticmethod
    async def resume_quotas(
        platform_db: AsyncSession, tenant_id, jour: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Résumé consommation/limite par ressource, croisé avec le dernier relevé
        d'agrégats. L'affichage « 4/5 praticiens » n'a pas besoin d'une requête
        par ressource.
        """
        jour = jour or date.today()
        contexte = await QuotaService.quotas(platform_db, tenant_id)
        releve = (
            await platform_db.execute(
                select(StatsTenant).where(
                    StatsTenant.tenant_id == tenant_id, StatsTenant.jour <= jour
                )
                .order_by(StatsTenant.jour.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if contexte["illimite"]:
            return {"plan": None, "illimite": True, "ressources": []}

        compteurs = {
            "utilisateurs": releve.utilisateurs_actifs if releve else 0,
            "sites": releve.sites if releve else 0,
            "praticiens": releve.praticiens if releve else 0,
            "stockage_octets": releve.stockage_octets if releve else 0,
            "sms_par_mois": releve.sms_envoyes if releve else 0,
        }

        ressources: List[Dict[str, Any]] = []
        for ressource, limite in (contexte["quotas"] or {}).items():
            try:
                limite_int = int(limite)
            except (TypeError, ValueError):
                continue
            consomme = int(compteurs.get(ressource, 0) or 0)
            ressources.append(
                {
                    "ressource": ressource,
                    "libelle": LIBELLES_RESSOURCES.get(ressource, ressource),
                    "consommation": consomme,
                    "limite": limite_int,
                    "taux": round(consomme / limite_int * 100, 1) if limite_int else None,
                    "depasse": consomme > limite_int,
                }
            )
        return {
            "plan": contexte.get("plan"),
            "plan_nom": contexte.get("plan_nom"),
            "illimite": False,
            "releve_jour": releve.jour.isoformat() if releve else None,
            "ressources": ressources,
        }

    @staticmethod
    async def cabinets_proches_du_quota(
        platform_db: AsyncSession, seuil: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Liste des cabinets dont la consommation dépasse `seuil` de leur contrat.

        Alimente la vue « à surveiller » de la supervision (Phase E.1). Le calcul
        est borné par le nombre d'abonnements, pas par le nombre de patients :
        c'est le dernier relevé agrégé qui est lu, jamais les bases clients.
        """
        abonnements = (
            await platform_db.execute(select(Abonnement))
        ).scalars().all()

        proches: List[Dict[str, Any]] = []
        for abonnement in abonnements:
            if abonnement.statut in (StatutAbonnement.RESILIE, StatutAbonnement.EXPIRE):
                continue
            resume = await QuotaService.resume_quotas(platform_db, abonnement.tenant_id)
            if resume["illimite"]:
                continue
            depasses = [r for r in resume["ressources"] if (r["taux"] or 0) >= seuil * 100]
            if depasses:
                proches.append(
                    {
                        "tenant_id": str(abonnement.tenant_id),
                        "plan": resume.get("plan"),
                        "ressources": [
                            {
                                "ressource": r["ressource"],
                                "taux": r["taux"],
                                "consommation": r["consommation"],
                                "limite": r["limite"],
                            }
                            for r in depasses
                        ],
                    }
                )
        return proches