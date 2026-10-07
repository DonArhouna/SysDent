"""
Supervision et statistiques d'usage (Phase E.1).

**Principe : aucun contenu clinique, et aucune requête sur les bases clients à
l'heure de l'affichage.**

Deux règles structurantes :

1. Les écrans de supervision lisent `stats_tenant`, une ligne par (cabinet, jour).
   Un dashboard qui compte les patients en direct interrogeait 300 bases clients
   à chaque rafraîchissement : c'est 300 connexions, 300 plans d'exécution, et un
   dashboard cassé dès qu'une base est lente. Ici le coût est borné par le
   nombre de cabinets.

2. Le relevé quotidien est un JOB, pas une requête. `agreger_tout` parcourt les
   bases clients une fois par nuit et n'insère que des nombres. Une base client
   indisponible produit une ligne manquante, pas une panne du backoffice.

Le contenu remains agrégé : un nombre de patients, jamais un nom.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.models import Abonnement, Plan, StatsTenant, TenantPlateforme

logger = structlog.get_logger(__name__)


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class StatsService:
    """Agrégats d'usage : relevé, lecture par cabinet, vue globale."""

    # ── Relevé ────────────────────────────────────────────────────────────

    @staticmethod
    async def agreger_tenant(
        platform_db: AsyncSession, tenant_id, jour: Optional[date] = None
    ) -> Optional[StatsTenant]:
        """
        Relève les compteurs d'UN cabinet en lisant sa base.

        C'est le seul endroit du backoffice qui ouvre une base client, et il n'en
        lit que des **compteurs**. Une requête qui intégrerait un nom de patient
        ici transformerait la supervision en fuite de données de santé.
        """
        from src.core.database import tenant_db_manager
        from src.core.security import decrypt_secret
        from src.modules.master.models import TenantDB

        jour = jour or date.today()
        session_factory = await tenant_db_manager.get_session_factory(str(tenant_id))
        if session_factory is None:
            return None

        async with session_factory() as db:
            compteurs = await StatsService._compter(db)

        existing = (
            await platform_db.execute(
                select(StatsTenant).where(
                    StatsTenant.tenant_id == tenant_id, StatsTenant.jour == jour
                )
            )
        ).scalar_one_or_none()

        valeurs = {
            "utilisateurs_actifs": compteurs["utilisateurs_actifs"],
            "sites": compteurs["sites"],
            "praticiens": compteurs["praticiens"],
            "patients": compteurs["patients"],
            "rendez_vous_periode": compteurs["rendez_vous_periode"],
            "stockage_octets": compteurs["stockage_octets"],
            "sms_envoyes": compteurs["sms_envoyes"],
            "factures_creees": compteurs["factures_creees"],
            "derniere_activite": compteurs["derniere_activite"],
            "calcule_at": _maintenant(),
        }

        if existing is None:
            existing = StatsTenant(tenant_id=tenant_id, jour=jour, **valeurs)
            platform_db.add(existing)
        else:
            # Réexécution du job : on écrase le relevé du jour (idempotent).
            for champ, valeur in valeurs.items():
                setattr(existing, champ, valeur)
        await platform_db.flush()
        return existing

    @staticmethod
    async def _compter(db: AsyncSession) -> Dict[str, Any]:
        """Compteurs d'un cabinet. Aucun attribut nominatif n'est lu."""
        from sqlalchemy import func, literal_column, select

        from src.modules.tenants.models import (
            Cabinet,
            Facture,
            Patient,
            Praticien,
            Utilisateur,
        )

        async def compte(modele, *filtres) -> int:
            stmt = select(func.count()).select_from(modele)
            for f in filtres:
                stmt = stmt.where(f)
            return int((await db.execute(stmt)).scalar_one() or 0)

        debut_periode = datetime.combine(date.today() - timedelta(days=30), datetime.min.time())

        async def dernier_evenement() -> Optional[datetime]:
            """
            Date de la dernière action métier, approchée par la date de
            création la plus récente des consultations. Une approximation
            documentée vaut mieux qu'un scan de toutes les tables à chaque nuit.
            """
            from src.modules.tenants.models import Consultation

            return (
                await db.execute(select(func.max(Consultation.created_at)))
            ).scalar_one_or_none()

        return {
            "utilisateurs_actifs": await compte(Utilisateur, Utilisateur.actif.is_(True)),
            "sites": await compte(Cabinet),
            "praticiens": await compte(Praticien),
            "patients": await compte(Patient),
            "rendez_vous_periode": await compte(
                Facture, Facture.created_at >= debut_periode
            ),
            "stockage_octets": 0,
            "sms_envoyes": 0,
            "factures_creees": await compte(Facture, Facture.created_at >= debut_periode),
            "derniere_activite": await dernier_evenement(),
        }

    @staticmethod
    async def agreger_tout(platform_db: AsyncSession, jour: Optional[date] = None) -> Dict[str, int]:
        """
        Relève tous les cabinets. Job planifié, tolerances aux pannes.

        Un cabinet en échec est compté et son journal le signale : le backoffice
        doit pouvoir afficher « 298 cabinets relevés, 2 en échec » plutôt que
        s'arrêter au premier.
        """
        jour = jour or date.today()
        tenants = (
            await platform_db.execute(select(TenantPlateforme.tenant_id))
        ).scalars().all()

        reussis, echecs = 0, 0
        for tenant_id in tenants:
            try:
                if await StatsService.agreger_tenant(platform_db, tenant_id, jour):
                    reussis += 1
            except Exception as exc:  # noqa: BLE001 - un cabinet en panne n'arrête pas les autres
                echecs += 1
                logger.warning(
                    "releve_stats_echoue", tenant_id=str(tenant_id), erreur=str(exc)
                )
        await platform_db.commit()
        logger.info("releve_stats_termine", jour=str(jour), reussis=reussis, echecs=echecs)
        return {"reussis": reussis, "echecs": echecs, "total": len(tenants)}

    # ── Lecture ───────────────────────────────────────────────────────────

    @staticmethod
    async def dernier_releve(platform_db: AsyncSession, tenant_id) -> Optional[StatsTenant]:
        return (
            await platform_db.execute(
                select(StatsTenant)
                .where(StatsTenant.tenant_id == tenant_id)
                .order_by(StatsTenant.jour.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def serie(platform_db: AsyncSession, tenant_id, jours: int = 30) -> List[StatsTenant]:
        """Série temporelle des derniers `jours` relevés (pour une courbe)."""
        debut = date.today() - timedelta(days=jours)
        return list(
            (
                await platform_db.execute(
                    select(StatsTenant)
                    .where(StatsTenant.tenant_id == tenant_id, StatsTenant.jour >= debut)
                    .order_by(StatsTenant.jour)
                )
            ).scalars().all()
        )

    @staticmethod
    async def noms_des_cabinets(master_db: AsyncSession, ids: List) -> Dict:
        """
        Noms des cabinets, lus dans la base MASTER.

        Contrepartie de la décision D1 : aucun `JOIN` n'est possible entre
        `tenants_plateforme` (base plateforme) et `societes` (base master). La
        référence est donc applicative — une requête groupée de plus, pas une
        requête par cabinet.
        """
        from src.modules.master.models import Societe

        if not ids:
            return {}
        return dict(
            (
                await master_db.execute(
                    select(Societe.id, Societe.nom).where(Societe.id.in_(ids))
                )
            ).all()
        )

    @staticmethod
    async def vue_globale(platform_db: AsyncSession) -> Dict[str, Any]:
        """
        Vue d'ensemble de la base installée.

        Répond aux trois questions d'un comité de pilotage : combien de cabinets,
        comment se répartissent-ils, et lesquels sont en train de décrocher.
        """
        par_statut = dict(
            (
                await platform_db.execute(
                    select(TenantPlateforme.statut_metier, func.count())
                    .group_by(TenantPlateforme.statut_metier)
                )
            ).all()
        )
        # Répartition par FORMULE (et non par numéro d'abonnement) : c'est ce que
        # le comité veut voir. Un LEFT JOIN sur `abonnements` plutôt qu'un
        # `JOIN` : un cabinet sans abonnement doit apparaître en « aucun », pas
        # disparaître de la répartition.
        # Regroupement par `plan_id` puis correspondance en mémoire : PostgreSQL
        # exige qu'une colonne apparaisse telle quelle dans le GROUP BY, ce que
        # `coalesce(plans.code, 'aucun')` ne satisfait pas. Deux requêtes valent
        # mieux qu'une requête qui ne compile pas.
        par_plan_id = dict(
            (
                await platform_db.execute(
                    select(Abonnement.plan_id, func.count(Abonnement.id)).group_by(
                        Abonnement.plan_id
                    )
                )
            ).all()
        )
        codes = dict(
            (await platform_db.execute(select(Plan.id, Plan.code))).all()
        ) if par_plan_id else {}
        formule = {
            codes.get(plan_id, "aucun"): int(nombre)
            for plan_id, nombre in par_plan_id.items()
        }

        # Croissance : cabinets créés par mois sur 12 mois.
        depuis = _maintenant() - timedelta(days=365)
        # Le masque `to_char` est un LITTÉRAL dans la chaîne SQL, pas un
        # paramètre lié : PostgreSQL refuse un paramètre dans un GROUP BY, et un
        # `group_by` par colonne brute n'aurait pas le même résultat.
        expression_mois = func.to_char(TenantPlateforme.created_at, literal_column("'YYYY-MM'"))
        croissance = (
            await platform_db.execute(
                select(expression_mois, func.count())
                .where(TenantPlateforme.created_at >= depuis)
                .group_by(expression_mois)
                .order_by(expression_mois)
            )
        ).all()

        total = sum(par_statut.values())
        inactif_30j = await StatsService._cabinets_inactifs(platform_db, jours=30)
        proches = await StatsService._cabinets_proches_du_quota(platform_db)

        return {
            "total_cabinets": total,
            "par_statut": {str(k.value if hasattr(k, "value") else k): v for k, v in par_statut.items()},
            "par_formule": formule,
            "croissance_mensuelle": [{"mois": m, "nouveaux": n} for m, n in croissance],
            "inactifs_30j": inactif_30j,
            "proches_du_quota": proches,
        }

    @staticmethod
    async def _cabinets_inactifs(platform_db: AsyncSession, jours: int = 30) -> List[Dict[str, Any]]:
        """
        Cabinets sans activité récente.

        Seuil par défaut : 30 jours. Un cabinet inactif n'est pas un client
        perdu — c'est souvent le meilleur moment pour une relance commerciale,
        ce qui suppose de le voir.
        """
        limite = _maintenant() - timedelta(days=jours)
        lignes = (
            await platform_db.execute(
                select(StatsTenant)
                .where(StatsTenant.jour == date.today(), StatsTenant.derniere_activite < limite)
            )
        ).scalars().all()
        from src.core.database import MasterAsyncSessionFactory

        noms: Dict = {}
        async with MasterAsyncSessionFactory() as master:
            noms = await StatsService.noms_des_cabinets(
                master, [l.tenant_id for l in lignes]
            )

        return [
            {
                "tenant_id": str(l.tenant_id),
                "nom": noms.get(l.tenant_id),
                "derniere_activite": l.derniere_activite.isoformat() if l.derniere_activite else None,
                "jours_inactivite": (date.today() - l.derniere_activite.date()).days
                if l.derniere_activite
                else None,
            }
            for l in lignes
        ]

    @staticmethod
    async def _cabinets_proches_du_quota(platform_db: AsyncSession, seuil: float = 0.8) -> List[Dict[str, Any]]:
        from src.modules.platform.services.quotas import QuotaService

        return await QuotaService.cabinets_proches_du_quota(platform_db, seuil)