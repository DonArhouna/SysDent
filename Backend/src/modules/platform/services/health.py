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
| Bases absentes     | registre contre `pg_database`     | un dossier ACTIVE sans base      |
| Schémas en retard  | `alembic_version` contre la tête  | une base migrée à moitié         |
| Gabarits / plans   | presence du plan par défaut       | un provisionnement échouerait    |

Aucun secret, aucune donnée de santé n'apparaît dans le résultat : ni mot de
passe de connexion d'un cabinet, ni nom de patient. Les erreurs sont
troncées — une trace complète pourrait contenir la chaîne de connexion.
"""

from datetime import datetime, timezone
import pathlib
import re
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

logger = structlog.get_logger(__name__)

#: Longueur maximale d'un message d'erreur exposé. Au-delà, on tronque.
MAX_LONGUEUR_ERREUR = 200


def _racine_backend() -> pathlib.Path:
    """Dossier `Backend/`, depuis n'importe quel module de l'application."""
    return pathlib.Path(__file__).resolve().parents[4]


def _tete_attendue() -> Optional[str]:
    """
    Tête de la chaîne de migrations des cabinets, lue sur le disque.

    **Jamais écrite en dur.** Une tête écrite en dur devient fausse au premier
    commit qui ajoute une migration, et l'écran de santé continue d'annoncer
    « à jour » pendant que le code ne l'est plus. C'est précisément ce qui a
    laissé passer un cabinet deux migrations en retard : rien ne le comparait
    à quoi que ce soit.

    Renvoie `None` si la chaîne est illisible ou si elle a **plus d'une tête** :
    dans ce cas, « être à jour » n'a pas de sens, et il vaut mieux le dire que
    mentir.
    """
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        racine = _racine_backend()
        cfg = Config(str(racine / "alembic_tenant.ini"))
        cfg.set_main_option("script_location", str(racine / "alembic_tenant"))
        tetes = ScriptDirectory.from_config(cfg).get_heads()
        return tetes[0] if len(tetes) == 1 else None
    except Exception:  # noqa: BLE001 - un contrôle ne doit jamais faire tomber la page
        return None


def _migrations_manquantes(courante: Optional[str], tete: str) -> Optional[int]:
    """
    Nombre de migrations à appliquer pour passer de `courante` à `tete`.

    `None` si la révision courante est inconnue de la chaîne : c'est un état
    distinct d'« en retard », et le confondre avec un nombre serait faux.
    """
    if not courante:
        return None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        racine = _racine_backend()
        cfg = Config(str(racine / "alembic_tenant.ini"))
        cfg.set_main_option("script_location", str(racine / "alembic_tenant"))
        script = ScriptDirectory.from_config(cfg)
        # `iterate_revisions(tete, courante)` descend de la tête **jusqu'à la
        # révision courante exclue** : chaque entrée est une migration à
        # appliquer. Le nombre est donc la longueur exacte, sans correction.
        return max(0, len(list(script.iterate_revisions(tete, courante))))
    except Exception:  # noqa: BLE001
        return None


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
    async def bases_absentes(master_db: AsyncSession) -> Dict[str, Any]:
        """
        Lignes du registre dont la base n'existe plus sur l'instance des tenants.

        **Le contrôle qui manquait.** Le 08/10, 130 lignes du registre se sont
        retrouvées sans base : le login de ces cabinets est tombé en 500, et la
        supervision continuait de répondre « ok ». `files_clients` comptait des
        statuts — il comptait aussi les lignes orphelines comme des cabinets en
        règle.

        Une seule lecture du catalogue `pg_database`, jamais un ping par
        cabinet : 130 connexions par appel serait exactement le défaut que cette
        page est censée révéler.
        """
        from src.core.config import settings
        from src.modules.master.models import TenantDB

        #: Lignes détaillées au maximum. Au-delà, seule la comptition compte.
        LIMITE_AFFICHEE = 25

        try:
            lignes = (await master_db.execute(select(TenantDB.db_name, TenantDB.statut))).all()
        except SQLAlchemyError as exc:
            return {"composant": "bases_absentes", "ok": False, "detail": _tronquer(str(exc))}

        moteur = create_async_engine(
            f"postgresql+asyncpg://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
            f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/postgres",
            isolation_level="AUTOCOMMIT",
        )
        try:
            async with moteur.connect() as conn:
                existantes = {
                    ligne[0]
                    for ligne in (
                        await conn.execute(
                            text("SELECT datname FROM pg_database WHERE datistemplate = false")
                        )
                    ).fetchall()
                }
        except SQLAlchemyError as exc:
            return {"composant": "bases_absentes", "ok": False, "detail": _tronquer(str(exc))}
        finally:
            await moteur.dispose()

        absentes = [(db, statut) for db, statut in lignes if db not in existantes]
        par_statut: Dict[str, int] = {}
        for _, statut in absentes:
            par_statut[statut] = par_statut.get(statut, 0) + 1

        # **Le total par statut, depuis la meme source que les absences.**
        # Le tableau de bord lit ses statuts metier dans la base *plateforme*,
        # et le registre *master* ici : deux tables, deux vocabulaires de
        # statut. Melanger les deux produirait un « total » incoherent avec le
        # « dont base absente » qu'on lui oppose. On expose donc les deux
        # comptes depuis la meme lecture, pour qu'ils soient comparables.
        total_par_statut: Dict[str, int] = {}
        for _, statut in lignes:
            total_par_statut[statut] = total_par_statut.get(statut, 0) + 1

        # Un dossier PROVISIONING sans base est normal, c'est l'état transitoire
        # d'une création. Un dossier **ACTIVE** sans base, c'est un cabinet dont
        # le login est cassé : c'est le seul cas qui dégrade la santé.
        actives = par_statut.get("ACTIVE", 0)
        return {
            "composant": "bases_absentes",
            "ok": actives == 0,
            "detail": (
                None
                if actives == 0
                else f"{actives} dossier(s) ACTIVE sans base : le login de ces cabinets échoue."
            ),
            "total_registre": len(lignes),
            "absentes": len(absentes),
            "absentes_par_statut": par_statut,
            "total_par_statut": total_par_statut,
            "exemples": [
                {"db_name": db, "statut": statut} for db, statut in absentes[:LIMITE_AFFICHEE]
            ],
            "exemples_limite": min(len(absentes), LIMITE_AFFICHEE),
        }

    @staticmethod
    async def schemas_tenants(master_db: AsyncSession) -> Dict[str, Any]:
        """
        Écart de révision de schéma, base par base.

        **Le contrôle qui manquait à côté de `bases_absentes`.** Une base peut
        être parfaitement présente et parfaitement inexploitable : il lui
        manque deux migrations. La connexion réussit, puis la première requête
        échoue — c'est exactement l'état du cabinet restauré le 10/10, et
        `bases_absentes` n'en voyait rien, puisqu'elle ne regarde que le
        catalogue : la base est là.

        La tête attendue est **lue sur la chaîne de migrations du dépôt**, jamais
        écrite en dur : une tête écrite en dur devient fausse au premier commit
        qui ajoute une migration, et l'écran dit « à jour » pendant que le code,
        lui, ne l'est plus.

        Une base sans table `alembic_version` n'est pas comptée comme « en
        retard » : elle n'est pas migrée du tout, ce qui est un autre état.
        Elle estSignalée à part, pour qu'un cabinet cassé n'empêche pas le
        contrôle de rendre son verdict sur les autres.
        """
        from src.core.config import settings
        from src.modules.master.models import TenantDB

        LIMITE_AFFICHEE = 25

        tete = _tete_attendue()
        if tete is None:
            return {
                "composant": "schemas_tenants",
                "ok": False,
                "detail": "Chaîne de migrations tenant illisible : tête inconnue.",
            }

        try:
            lignes = (await master_db.execute(select(TenantDB.db_name, TenantDB.statut))).all()
        except SQLAlchemyError as exc:
            return {"composant": "schemas_tenants", "ok": False, "detail": _tronquer(str(exc))}

        moteur = create_async_engine(
            f"postgresql+asyncpg://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
            f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/postgres",
            isolation_level="AUTOCOMMIT",
        )
        derriere: List[Dict[str, Any]] = []
        non_migrees: List[str] = []
        analysees = 0
        non_inspectees = 0

        try:
            async with moteur.connect() as conn:
                existantes = {
                    ligne[0]
                    for ligne in (
                        await conn.execute(
                            text("SELECT datname FROM pg_database WHERE datistemplate = false")
                        )
                    ).fetchall()
                }

            candidates = [
                (db_name, statut)
                for db_name, statut in lignes
                if db_name in existantes and NOM_BASE_SURE.match(db_name)
            ]
            non_inspectees = max(0, len(candidates) - MAX_BASES_INSPECTEES)
            candidates = candidates[:MAX_BASES_INSPECTEES]

            # **PostgreSQL n'a aucune syntaxe inter-base** : `base.table` designe
            # un *schema* de ce nom, pas une autre base. Une seule requete pour
            # toutes les bases echouait donc partout, et chaque cabinet -
            # migre ou non - etait declare « sans table de migrations ». Le
            # symptome est discret et faux : la page de sante tournait, et ne
            # controlait rien. Il faut une connexion par base.
            for db_name, statut in candidates:
                moteur_base = create_async_engine(
                    f"postgresql+asyncpg://{settings.TENANT_DB_USER}"
                    f":{settings.TENANT_DB_PASSWORD}"
                    f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/{db_name}",
                    isolation_level="AUTOCOMMIT",
                    poolclass=NullPool,
                )
                revision = None
                try:
                    async with moteur_base.connect() as conn:
                        revision = (
                            await conn.execute(text("SELECT version_num FROM alembic_version"))
                        ).scalar_one_or_none()
                except SQLAlchemyError:
                    revision = None
                finally:
                    await moteur_base.dispose()

                analysees += 1
                if revision is None:
                    non_migrees.append(db_name)
                    continue
                if revision == tete:
                    continue
                derriere.append(
                    {
                        "db_name": db_name,
                        "statut": statut,
                        "revision_courante": revision,
                        "migrations_manquantes": _migrations_manquantes(revision, tete),
                    }
                )
        except SQLAlchemyError as exc:
            return {"composant": "schemas_tenants", "ok": False, "detail": _tronquer(str(exc))}
        finally:
            await moteur.dispose()

        return {
            "composant": "schemas_tenants",
            "ok": not derriere,
            "detail": (
                None
                if not derriere
                else f"{len(derriere)} cabinet(s) en retard de migrations : leur code echoue."
            ),
            "tete_attendue": tete,
            "bases_analysees": analysees,
            "derriere_tete": derriere[:LIMITE_AFFICHEE],
            "derriere_tete_limite": min(len(derriere), LIMITE_AFFICHEE),
            "sans_table_migrations": non_migrees[:LIMITE_AFFICHEE],
            "bases_non_inspectees": non_inspectees,
        }

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

        **Chaque contrôle est donc contenu ici, et pas seulement dans son propre
        `try`.** Les contrôles internes ne rattrapent qu'un `SQLAlchemyError`.
        Or un échec de connexion n'est **pas** encapsulé par SQLAlchemy : il
        remonte nu, en `ConnectionRefusedError` ou en `OSError` — c'est mesuré,
        et c'est ce qui transformait la page de santé en 500 dès qu'une base de
        cabinet ne répondait plus. Une promesse écrite dans une docstring et
        tenue uniquement par le bon vouloir de chaque appelant est une
        promesse qui tient jusqu'au premier appelant oublié.
        """

        async def _contenu(composant: str, awaitable):
            """Exécute un contrôle et garantit une réponse, quelle qu'elle soit."""
            try:
                return await awaitable
            except SQLAlchemyError as exc:
                return {"composant": composant, "ok": False, "detail": _tronquer(str(exc))}
            except Exception as exc:  # noqa: BLE001
                # Forms non encapsulees : echec de connexion, liste vide
                # malformee, valeur absente. La page doit rester lisible.
                # Le type est journalise, pas la requete : un detail SQL ne
                # doit pas sortir vers le client.
                logger.error(
                    "controle_sante_en_panne",
                    composant=composant,
                    erreur=type(exc).__name__,
                )
                return {
                    "composant": composant,
                    "ok": False,
                    "detail": f"Contrôle indisponible : {type(exc).__name__}.",
                }

        controles: List[Dict[str, Any]] = [
            await _contenu("base_plateforme", HealthService.base_plateforme(platform_db)),
            await _contenu("base_master", HealthService.base_master()),
            await _contenu("files_clients", HealthService.files_clients(master_db)),
            await _contenu("bases_absentes", HealthService.bases_absentes(master_db)),
            await _contenu("schemas_tenants", HealthService.schemas_tenants(master_db)),
            await _contenu(
                "migrations_par_tenant", HealthService.migrations_par_tenant(platform_db)
            ),
            await _contenu("catalogue", HealthService.catalogue(platform_db)),
            await _contenu("jobs_planifies", HealthService.jobs_planifies(platform_db)),
        ]
        en_panne = [c for c in controles if not c["ok"]]
        return {
            "statut": "ok" if not en_panne else "degrade",
            "verifie_le": datetime.now(timezone.utc).isoformat(),
            "controles": controles,
            "en_panne": [c["composant"] for c in en_panne],
        }


#: Un nom de base ne peut contenir que cela. Le contrôle interroge chaque base
#: par son nom : un nom venue du registre ne doit pas pouvoir devenir une
#: injection SQL dans une requête qui traverse les bases.
NOM_BASE_SURE = re.compile(r"^[A-Za-z0-9_]{1,63}$")

#: Combien de bases on ouvre au plus pour lire leur révision. Chaque base coûte
#: une connexion : un registre de plusieurs milliers de cabinets ne doit pas
#: transformer un écran de santé en deni de service.
MAX_BASES_INSPECTEES = 40

#: `user:password@` à l'intérieur d'une URL, y compris `postgresql+asyncpg://`.
IDENTIFIANTS_URL = re.compile(r"(://[^:/@\s]+):[^@\s]+@")


def _sans_identifiants(texte: str) -> str:
    """Masque `user:password@` d'une chaîne pouvant contenir une URL de connexion."""
    return IDENTIFIANTS_URL.sub(r"\1:***@", texte)


def _tronquer(texte: str) -> str:
    """
    Retire les identifiants, puis tronque un message d'erreur technique.

    Les erreurs SQLAlchemy peuvent contenir la chaîne de connexion complète,
    donc le mot de passe du compte applicatif. Une page de santé affichée sur un
    écran de supervision deviendrait alors un écran de secrets.

    La troncature seule ne suffisait pas : un mot de passe tient aisément dans
    les 200 premiers caractères. Le retrait des identifiants est donc fait
    **avant**.
    """
    propre = _sans_identifiants(texte)
    return propre[:MAX_LONGUEUR_ERREUR] + "…" if len(propre) > MAX_LONGUEUR_ERREUR else propre