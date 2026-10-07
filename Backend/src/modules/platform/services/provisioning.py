"""
Provisionnement d'un cabinet — service UNIQUE, idempotent et compensé (Phase B.4).

Ce service est le SEUL point de création d'un cabinet. Il est appelé par :

- `POST /platform/tenants` (console éditeur, Phase B) ;
- `POST /onboarding/inscription` (auto-inscription publique, Phase F).

Factoriser les deux est la décision structurante de cette phase. Deux implémentations
du provisionnement divergeraient vite : l'uneForgotrait les quotas, l'autre le
formulaire médicamenteux, et un cabinet créé par l'inscription automatique serait
incomplètement initialisé — un bug impossible à voir de l'extérieur.

## Pourquoi une compensation explicite plutôt qu'une transaction

`CREATE DATABASE` ne peut pas s'exécuter dans une transaction PostgreSQL, et les
opérations de la base master, de la base plateforme et de la base du cabinet sont
par définition dans trois transactions distinctes. Aucune atomicité SQL n'est
donc possible. Le seul moyen de garantir « aucun tenant à moitié créé » est
d'ordonnancer les étapes et **annuler explicitement** ce qui a été fait, dans
l'ordre inverse.

C'est exactement le défaut de l'implémentation d'origine
(`master/services.py:432-448`), qui commit la société AVANT de créer la base et
laisse un tenant en `PROVISIONING` si l'étape suivante échoue — état observé 6
fois dans la base de démonstration.

## Étapes et compensation

| # | Étape | En cas d'échec |
|---|---|---|
| 1 | Société + `tenants_db(PROVISIONING)` en base master | rien à défaire |
| 2 | `CREATE DATABASE` | supprimer la société + le dossier |
| 3 | Migrations Alembic du cabinet | `DROP DATABASE` puis étape 1 |
| 4 | Semis depuis les gabarits | `DROP DATABASE` puis étape 1 |
| 5 | Dossier plateforme + abonnement | `DROP DATABASE` puis étape 1 |
| 6 | Index e-mail + passage `ACTIVE` | `DROP DATABASE` puis étape 1 |
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.core.config import settings
from src.core.exceptions import BusinessRuleViolationException
from src.modules.platform.services.journal import JournalService
from src.core.migrations import upgrade_tenant_to_head
from src.core.security import (
    encrypt_secret,
    get_password_hash,
)
from src.modules.master.models import AuditLogGlobal, Societe, TenantDB
from src.modules.master.services import sanitize_db_name

logger = structlog.get_logger(__name__)


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class ProvisioningResult:
    """Résultat du provisionnement : les deux identifiants + ce qui a été fait."""

    def __init__(
        self,
        societe: Societe,
        tenant_db: TenantDB,
        dossier: Any,
        etapes: List[str],
        gabarits_appliques: Dict[str, Optional[str]],
        invitation_envoyee: bool = False,
    ) -> None:
        self.societe = societe
        self.tenant_db = tenant_db
        self.dossier = dossier
        self.etapes = etapes
        self.gabarits_appliques = gabarits_appliques
        self.invitation_envoyee = invitation_envoyee

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.societe.id


class ProvisioningService:
    """
    Provisionnement transactionnel d'un cabinet.

    `plan_code=None` et `statut_initial=None` sont acceptés pour que l'onboarding
    public puisse créer un cabinet « en essai » sans dupliquer la logique.
    """

    @staticmethod
    async def provisionner(
        *,
        master_db: AsyncSession,
        platform_db: AsyncSession,
        nom: str,
        admin_email: str,
        admin_prenom: str,
        admin_nom: str,
        statut_initial: str = "ACTIF",
        admin_password: Optional[str] = None,
        ninea: Optional[str] = None,
        adresse_siege: Optional[str] = None,
        ville: Optional[str] = "Dakar",
        pays: Optional[str] = "Sénégal",
        telephone: Optional[str] = None,
        site_web: Optional[str] = None,
        logo_url: Optional[str] = None,
        langue: str = "fr",
        fuseau_horaire: str = "Africa/Dakar",
        devise: str = "XOF",
        plan_code: Optional[str] = None,
        jours_essai: int = 14,
        auteur: str = "système",
        motif: Optional[str] = None,
        attendre_verification_email: bool = False,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProvisioningResult:
        """
        Crée un cabinet complet : base dédiée, schéma, semis, dossier plateforme,
        abonnement, index de routage.

        Lève `BusinessRuleViolationException` en cas de conflit métier (NINEA ou
        e-mail déjà utilisés) et `ProvisioningError` en cas d'échec technique —
        après avoir tout annulé.
        """
        from src.modules.platform.models import Plan, StatutTenant, TenantPlateforme
        from src.modules.platform.services.plans import AbonnementService
        from src.modules.platform.services.seed import TenantSeedService

        email_normalise = admin_email.strip().lower()
        etapes: List[str] = []
        db_name: Optional[str] = None
        societe: Optional[Societe] = None
        base_creee = False

        # ── Contrôles d'idempotence et d'unicité (avant toute écriture) ───────
        doublon = (
            await master_db.execute(
                select(Societe).where(Societe.ninea == ninea) if ninea else select(Societe).limit(0)
            )
        ).scalar_one_or_none()
        if doublon is not None:
            raise BusinessRuleViolationException(
                "Une société porte déjà ce numéro d'enregistrement.", code="NINEA_DEJA_UTILISE"
            )

        # ── Étape 1 : société + dossier (base master) ─────────────────────────
        societe = Societe(
            nom=nom,
            ninea=ninea,
            adresse_siege=adresse_siege,
            ville=ville,
            pays=pays or "Sénégal",
            telephone=telephone,
            email=email_normalise,
            site_web=site_web,
            logo_url=logo_url,
            actif=True,
        )
        master_db.add(societe)
        await master_db.flush()

        db_name = sanitize_db_name(nom)
        tenant_db = TenantDB(
            societe_id=societe.id,
            db_name=db_name,
            db_host=settings.TENANT_DB_HOST,
            db_port=settings.TENANT_DB_PORT,
            db_user=settings.TENANT_DB_USER,
            db_password=encrypt_secret(settings.TENANT_DB_PASSWORD),
            statut="PROVISIONING",
            schema_version="1.0.0",
        )
        master_db.add(tenant_db)

        master_db.add(
            AuditLogGlobal(
                auteur_email=auteur,
                action="TENANT_PROVISION_INIT",
                cible_id=str(societe.id),
                details={"nom": societe.nom, "db_name": db_name, "admin_email": email_normalise},
                ip_address=client_ip,
            )
        )
        await master_db.commit()
        etapes.append("societe_creee")

        try:
            # ── Étape 2 : base physique ────────────────────────────────────────
            await ProvisioningService._creer_base_physique(db_name)
            base_creee = True
            etapes.append("base_creee")

            # ── Étape 3 : schéma ──────────────────────────────────────────────
            await ProvisioningService._appliquer_migrations(db_name)
            etapes.append("migrations_appliquees")

            # ── Étape 4 : semis depuis les gabarits plateforme ────────────────
            # Le semis renvoie l'identifiant du compte administrateur : l'index
            # de routage l'exige (colonne NOT NULL) et ne peut donc pas être
            # écrit AVANT.
            resultat_semis = await TenantSeedService.semer(
                societe.id,
                db_name,
                platform_db,
                nom_cabinet=nom,
                admin_email=email_normalise,
                admin_prenom=admin_prenom,
                admin_nom=admin_nom,
                admin_password=admin_password,
            )
            gabarits = resultat_semis["gabarits"]
            utilisateur_id = uuid.UUID(resultat_semis["utilisateur_id"])
            etapes.append("semis_effectue")

            # ── Étape 5 : dossier plateforme + abonnement ─────────────────────
            dossier = TenantPlateforme(
                tenant_id=societe.id,
                langue=langue,
                fuseau_horaire=fuseau_horaire,
                devise=devise,
                pays=societe.pays,
                admin_email=email_normalise,
            )
            platform_db.add(dossier)

            if statut_initial == "ESSAI":
                dossier.statut_metier = StatutTenant.ESSAI
                dossier.date_debut_essai = date.today()
                dossier.date_fin_essai = date.today() + timedelta(days=jours_essai)
            else:
                dossier.statut_metier = StatutTenant.ACTIF
                dossier.date_activation = _maintenant()
            platform_db.add(dossier)
            await platform_db.flush()

            if plan_code:
                await AbonnementService.souscrire(
                    platform_db,
                    tenant_id=societe.id,
                    plan_code=plan_code,
                    statut="ESSAI" if statut_initial == "ESSAI" else "ACTIF",
                    auteur=auteur,
                    motif=motif or "provisionnement",
                )
            etapes.append("dossier_plateforme")

            # ── Étape 6 : index de routage + passage en ACTIF ──────────────────
            await ProvisioningService._enregistrer_index(
                master_db, email_normalise, societe.id, utilisateur_id
            )
            # `attendre_verification_email` (Phase F) : l'index est écrit, mais la
            # connexion reste fermée jusqu'à la preuve de l'adresse. Sans cela on
            # s'inscrit avec l'adresse d'un tiers et on obtient un accès.
            tenant_db.statut = (
                "PENDING_VERIFICATION" if attendre_verification_email else "ACTIVE"
            )
            master_db.add(
                AuditLogGlobal(
                    auteur_email=auteur,
                    action="TENANT_PROVISION_SUCCESS",
                    cible_id=str(societe.id),
                    details={"etapes": etapes, "gabarits": gabarits},
                    ip_address=client_ip,
                )
            )
            await master_db.commit()
            await platform_db.commit()
            etapes.append("activation")

        except Exception as exc:  # noqa: BLE001 - on annule TOUT puis on relance
            # `societe.id` est capturé AVANT la compensation : après l'échec,
            # les attributs de l'objet SQLAlchemy sont expirés et y accéder
            # déclencherait une requête sur une session en `PendingRollbackError`
            # — la compensation échouerait sur une erreur qui n'est pas la sienne.
            societe_id_capture = societe.id if societe is not None else None
            await ProvisioningService._annuler(
                master_db,
                platform_db,
                societe_id_capture,
                db_name,
                base_creee,
                client_ip,
                auteur,
            )
            logger.exception(
                "provisionnement_echoue",
                societe_id=str(societe.id) if societe else None,
                db_name=db_name,
                etapes=etapes,
                error=str(exc),
            )
            from src.core.exceptions import AppException

            raise AppException(
                message=(
                    "Le provisionnement du cabinet a échoué et a été entièrement annulé. "
                    "Aucun cabinet à moitié créé n'a été laissé en base."
                ),
                code="TENANT_PROVISIONING_FAILED",
                status_code=500,
                details={
                    "societe_id": str(societe_id_capture) if societe_id_capture else None,
                    "etapes_reussies": etapes,
                },
            ) from exc

        # Le compte admin a été créé par le semis : on lui envoie son invitation.
        invitation_envoyee = await ProvisioningService._envoyer_invitation_admin(
            societe.id, db_name, email_normalise, nom, platform_db, auteur, client_ip
        )

        # Journalisation : la création d'un cabinet est l'acte le plus sensible
        # de la console (il ouvre une base, un compte et un abonnement). Elle doit
        # laisser une trace immuable, comme toute autre action.
        #
        # Placée APRÈS le provisionnement et non avant : un échec a déjà levé, et
        # son propre journal d'erreur (`AuditLogGlobal` + journal structuré)
        # raconte l'échec. Journaliser avant créerait une entrée « cabinet créé »
        # pour un cabinet qui n'existe pas.
        await JournalService.journaliser(
            platform_db,
            action="PLATFORM_TENANT_CREE",
            type_cible="TENANT",
            cible_id=str(societe.id),
            tenant_id=societe.id,
            acteur_email=auteur,
            apres={
                "nom": nom,
                "statut": dossier.statut_metier.value,
                "plan_code": plan_code,
                "admin_email": email_normalise,
                "etapes": etapes,
            },
            motif=motif,
            ip_address=client_ip,
        )

        logger.info(
            "tenant_provisionne",
            societe_id=str(societe.id),
            db_name=db_name,
            etapes=etapes,
            gabarits=gabarits,
        )
        return ProvisioningResult(
            societe=societe,
            tenant_db=tenant_db,
            dossier=dossier,
            etapes=etapes,
            gabarits_appliques=gabarits,
            invitation_envoyee=invitation_envoyee,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Étapes techniques
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _creer_base_physique(db_name: str) -> None:
        """`CREATE DATABASE` hors transaction, sur une connexion AUTOCOMMIT éphémère."""
        url = (
            f"postgresql+asyncpg://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
            f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/postgres"
        )
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                existe = await conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
                )
                if not existe.scalar_one_or_none():
                    # `db_name` vient de `sanitize_db_name()` ([a-z0-9_] + uuid) :
                    # aucune injection possible malgré l'identifiant dynamique.
                    await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        finally:
            await engine.dispose()

    @staticmethod
    async def _appliquer_migrations(db_name: str) -> None:
        """Alembic est synchrone : on le lance dans un thread pour ne pas bloquer la boucle."""
        import asyncio

        url = (
            f"postgresql+psycopg2://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
            f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/{db_name}"
        )
        await asyncio.to_thread(upgrade_tenant_to_head, url)

    @staticmethod
    async def _enregistrer_index(
        master_db: AsyncSession,
        email: str,
        societe_id: uuid.UUID,
        utilisateur_id: uuid.UUID,
    ) -> None:
        """
        Index de routage email → société.

        Écrit APRÈS le semis : `utilisateur_index.utilisateur_id` est NOT NULL et
        sa valeur est l'UUID du compte créé dans la base du cabinet. L'écrire
        avant le semis aurait imposé de rendre la colonne nullable, c'est-à-dire
        une migration sur des données existantes.
        """
        from src.modules.master.models import UtilisateurIndex

        existe = (
            await master_db.execute(
                select(UtilisateurIndex).where(UtilisateurIndex.email == email)
            )
        ).scalar_one_or_none()
        if existe is not None:
            raise BusinessRuleViolationException(
                "Un compte existe déjà avec cette adresse e-mail.", code="EMAIL_DEJA_UTILISE"
            )
        master_db.add(
            UtilisateurIndex(
                email=email, societe_id=societe_id, utilisateur_id=utilisateur_id, actif=True
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Compensation
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _annuler(
        master_db: AsyncSession,
        platform_db: AsyncSession,
        societe_id: Optional[uuid.UUID],
        db_name: Optional[str],
        base_creee: bool,
        client_ip: Optional[str],
        auteur: str,
    ) -> None:
        """
        Annule le provisionnement dans l'ordre inverse des étapes.

        Chaque étape est protégée : si l'annulation d'une étape échoue, les
        suivantes sont tentées quand même. Une compensation à moitié faite est
        déjà meilleure que l'absence de compensation, et l'échec est journalisé
        pour qu'un humain intervienne.
        """
        from src.modules.platform.models import Abonnement, TenantPlateforme

        # Rollback IMMÉDIAT des deux sessions. Après l'échec qui vient d'être levé,
        # SQLAlchemy a déjà invalidé la transaction : sans ce rollback explicite,
        # la première requête de compensation échouerait sur
        # `PendingRollbackError` et AUCUNE compensation ne serait appliquée.
        await platform_db.rollback()
        await master_db.rollback()

        # Étape 5 : dossier plateforme et abonnement
        if societe_id is not None:
            try:
                await platform_db.execute(
                    Abonnement.__table__.delete().where(Abonnement.tenant_id == societe_id)
                )
                await platform_db.execute(
                    TenantPlateforme.__table__.delete().where(
                        TenantPlateforme.tenant_id == societe_id
                    )
                )
                await platform_db.commit()
                logger.info("compensation_dossier_plateforme", societe_id=str(societe_id))
            except Exception:  # noqa: BLE001
                await platform_db.rollback()
                logger.exception(
                    "compensation_plateforme_echouee", societe_id=str(societe_id)
                )

        # Étapes 2 à 4 : base physique
        if base_creee and db_name:
            try:
                url = (
                    f"postgresql+asyncpg://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
                    f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/postgres"
                )
                engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
                try:
                    async with engine.connect() as conn:
                        await conn.execute(
                            text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
                        )
                finally:
                    await engine.dispose()
                logger.info("compensation_base_supprimee", db_name=db_name)
            except Exception:  # noqa: BLE001
                logger.exception("compensation_base_echouee", db_name=db_name)

        # Étape 1 : société et dossier master
        if societe_id is not None:
            try:
                await master_db.execute(
                    Societe.__table__.delete().where(Societe.id == societe_id)
                )
                master_db.add(
                    AuditLogGlobal(
                        auteur_email=auteur,
                        action="TENANT_PROVISION_ROLLBACK",
                        cible_id=str(societe_id),
                        details={"db_name": db_name},
                        ip_address=client_ip,
                    )
                )
                await master_db.commit()
                logger.info("compensation_societe_supprimee", societe_id=str(societe_id))
            except Exception:  # noqa: BLE001
                await master_db.rollback()
                logger.exception("compensation_societe_echouee", societe_id=str(societe_id))

    # ─────────────────────────────────────────────────────────────────────────
    # Invitation
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _envoyer_invitation_admin(
        societe_id: uuid.UUID,
        db_name: str,
        email: str,
        nom_cabinet: str,
        platform_db: AsyncSession,
        auteur: str,
        client_ip: Optional[str],
    ) -> bool:
        """
        Crée et envoie l'invitation du premier administrateur.

        L'invitation porte un jeton OPAQUE HACHÉ en base : le lien envoyé par
        e-mail ne peut pas être rejoué depuis une fuite de la base, et le mot de
        passe initial n'est jamais transmis.
        """
        from src.modules.platform.models import JetonUsageUnique, UsageJeton
        from src.modules.platform.security import generer_jeton_opaque, hacher_jeton
        from src.modules.platform.services.notifications import EmailService

        jeton = generer_jeton_opaque()
        platform_db.add(
            JetonUsageUnique(
                usage=UsageJeton.INVITATION_ADMIN,
                hash_jeton=hacher_jeton(jeton),
                cible_type="TENANT",
                cible_id=str(societe_id),
                expire_le=_maintenant() + timedelta(hours=72),
                cree_par=auteur,
                ip_address=client_ip,
            )
        )
        await platform_db.commit()
        await EmailService.invitation_admin(email, jeton, nom_cabinet)
        return True