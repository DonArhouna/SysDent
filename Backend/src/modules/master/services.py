import asyncio
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload
from src.core.config import settings
from src.core.database import tenant_db_manager
from src.core.exceptions import AppException, BusinessRuleViolationException, EntityNotFoundException
from src.core.migrations import upgrade_tenant_to_head
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_secret,
    encrypt_secret,
    get_password_hash,
    verify_password,
)
from src.modules.master.models import AuditLogGlobal, Societe, SuperAdmin, SuperAdminSession, TenantDB
from src.modules.master.schemas import SocieteCreate, SocieteUpdate
from src.modules.tenants.models import Cabinet, CabinetPraticien, Praticien, Role, Utilisateur

logger = structlog.get_logger(__name__)

# Nombre de tentatives de connexion Super Admin avant verrouillage temporaire.
MAX_TENTATIVES_SUPER_ADMIN = 5
DUREE_VERROUILLAGE_MINUTES = 15


def sanitize_db_name(name: str) -> str:
    """Génère un nom de base PostgreSQL valide et sécurisé."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower().strip())
    return f"sysdent_tenant_{clean[:30]}_{uuid.uuid4().hex[:6]}"


async def _create_physical_database(db_name: str) -> None:
    """
    Exécute un CREATE DATABASE réel sur le serveur PostgreSQL des tenants.
    CREATE DATABASE ne peut pas tourner dans une transaction : on utilise une connexion
    autocommit, courte durée de vie, vers la base de maintenance `postgres`.
    """
    maintenance_url = (
        f"postgresql+asyncpg://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
        f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/postgres"
    )
    admin_engine: AsyncEngine = create_async_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            )
            if not exists.scalar_one_or_none():
                # db_name provient uniquement de sanitize_db_name() ([a-z0-9_] + uuid) : pas d'injection possible.
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("tenant_database_created", db_name=db_name)
    finally:
        await admin_engine.dispose()


async def _bootstrap_tenant_schema_and_admin(societe_id: uuid.UUID, db_name: str, data: SocieteCreate) -> None:
    """
    Crée le schéma applicatif sur la nouvelle base tenant (via Alembic), le RBAC
    (permissions + rôles + matrice), le cabinet, le compte admin et son profil
    praticien.

    L'import de `RbacService` est local : au niveau module il créerait un cycle
    (master -> rbac -> auth.dependencies -> master.models).
    """
    from src.modules.rbac.services import RbacService

    # Référentiel médicamenteux : sans lui, aucune ordonnance ne peut être émise
    # et le contrôle de contre-indication n'a aucune règle à appliquer.
    from src.modules.ordonnances.services import MedicamentService
    tenant_sync_url = (
        f"postgresql+psycopg2://{settings.TENANT_DB_USER}:{settings.TENANT_DB_PASSWORD}"
        f"@{settings.TENANT_DB_HOST}:{settings.TENANT_DB_PORT}/{db_name}"
    )
    # Alembic est synchrone : on l'exécute dans un thread pour ne pas bloquer l'event loop asyncio.
    await asyncio.to_thread(upgrade_tenant_to_head, tenant_sync_url)

    await tenant_db_manager.get_or_create_engine(
        tenant_id=str(societe_id),
        db_name=db_name,
        host=settings.TENANT_DB_HOST,
        port=settings.TENANT_DB_PORT,
        user=settings.TENANT_DB_USER,
        password=settings.TENANT_DB_PASSWORD,
    )
    session_factory = await tenant_db_manager.get_session_factory(str(societe_id))
    async with session_factory() as tenant_session:
        # Un cabinet sans enregistrement ne peut ni consulter ni facturer : le
        # premier cabinet se crée donc d'office.
        cabinet = Cabinet(
            nom=data.nom,
            adresse=data.adresse_siege,
            ville=data.ville,
            telephone=data.telephone,
            email=str(data.email) if data.email else None,
            logo_url=data.logo_url,
            actif=True,
        )
        tenant_session.add(cabinet)
        await tenant_session.flush()

        # RBAC : sans ces trois étapes, aucun rôle non-administrateur n'aurait
        # la moindre permission et chaque route protégée répondrait 403.
        await RbacService.bootstrap_complet(tenant_session)
        await MedicamentService.semer_formulaire(tenant_session)

        # `ADMIN_CABINET` a DÉJÀ été créé par `semer_roles()`. Le recréer ici
        # violerait la contrainte UNIQUE sur roles.nom et ferait échouer tout
        # provisionnement : on récupère donc le rôle existant.
        admin_role = (
            await tenant_session.execute(select(Role).where(Role.nom == "ADMIN_CABINET"))
        ).scalar_one()

        admin_user = Utilisateur(
            email=data.admin_email.lower(),
            mot_de_passe=get_password_hash(data.admin_password),
            role_id=admin_role.id,
            prenom=data.admin_prenom,
            nom=data.admin_nom,
            actif=True,
        )
        tenant_session.add(admin_user)
        await tenant_session.flush()

        # Le compte fondateur porte aussi un profil praticien : sans lui, aucun
        # acte ne peut être attribué (la consultation exige un auteur clinique
        # identifié). Une clinique peut ainsi facturer dès le premier jour.
        praticien = Praticien(
            utilisateur_id=admin_user.id,
            titre="Dr",
            specialite="Chirurgien-Dentiste",
        )
        tenant_session.add(praticien)
        await tenant_session.flush()

        # ... et il est rattaché au cabinet fondateur. Sans ce lien, le cabinet
        # n'a AUCUN praticien rattaché : `GET /praticiens?cabinet_id=...` renvoie
        # une liste vide, et l'agenda (D2B) n'a personne à proposer au patient.
        tenant_session.add(
            CabinetPraticien(
                cabinet_id=cabinet.id,
                praticien_id=praticien.id,
                date_debut=date.today(),
                actif=True,
            )
        )
        await tenant_session.commit()

        return admin_user


class MasterAuthService:
    """
    Authentification de la console Super Admin (base Master).

    Séparée de `AuthService` (qui authentifie les utilisateurs de cabinet) : les
    deux vivaient dans des bases différentes et n'ont ni les mêmes tables ni les
    mêmes règles. Une session Super Admin ne porte aucun `tenant_id`.
    """

    @staticmethod
    async def _journaliser(
        db: AsyncSession, auteur: str, action: str, cible: Optional[str], details: dict, ip: Optional[str]
    ) -> None:
        db.add(
            AuditLogGlobal(
                auteur_email=auteur,
                action=action,
                cible_id=cible,
                details=details,
                ip_address=ip,
            )
        )
        await db.flush()

    @staticmethod
    async def authentifier(
        db: AsyncSession, email: str, password: str, client_ip: Optional[str] = None
    ) -> Tuple[SuperAdmin, str, str]:
        """
        Vérifie les identifiants d'un Super Admin et ouvre une session.

        Retourne : (super_admin, access_token, refresh_token).
        """
        from src.core.exceptions import AuthenticationException

        email_normalise = email.strip().lower()
        stmt = select(SuperAdmin).where(SuperAdmin.email == email_normalise)
        admin = (await db.execute(stmt)).scalar_one_or_none()

        if admin is None or not admin.actif:
            await MasterAuthService._journaliser(
                db,
                auteur=email_normalise,
                action="SUPER_ADMIN_LOGIN_ECHOUCHE",
                cible=None,
                details={"raison": "compte_inconnu_ou_inactif"},
                ip=client_ip,
            )
            await db.commit()
            raise AuthenticationException("Identifiants invalides.", code="INVALID_CREDENTIALS")

        # Verrouillage temporaire après N échecs (anti force brute).
        maintenant = datetime.now(timezone.utc)
        if admin.verrouille_jusqua and admin.verrouille_jusqua > maintenant:
            restantes = int((admin.verrouille_jusqua - maintenant).total_seconds())
            from src.core.exceptions import TooManyRequestsException

            await MasterAuthService._journaliser(
                db,
                auteur=admin.email,
                action="SUPER_ADMIN_LOGIN_BLOQUE",
                cible=str(admin.id),
                details={"secondes_restantes": restantes},
                ip=client_ip,
            )
            await db.commit()
            raise TooManyRequestsException(
                "Compte temporairement verrouillé après trop de tentatives.", retry_after_seconds=restantes
            )

        if not verify_password(password, admin.mot_de_passe):
            admin.tentatives_echouees += 1
            if admin.tentatives_echouees >= MAX_TENTATIVES_SUPER_ADMIN:
                admin.verrouille_jusqua = maintenant + timedelta(minutes=DUREE_VERROUILLAGE_MINUTES)
                admin.tentatives_echouees = 0
                logger.warning(
                    "super_admin_verrouille", email=admin.email, minutes=DUREE_VERROUILLAGE_MINUTES
                )
            await MasterAuthService._journaliser(
                db,
                auteur=admin.email,
                action="SUPER_ADMIN_LOGIN_ECHOUCHE",
                cible=str(admin.id),
                details={"tentatives_echouees": admin.tentatives_echouees},
                ip=client_ip,
            )
            await db.commit()
            raise AuthenticationException("Identifiants invalides.", code="INVALID_CREDENTIALS")

        # Succès : remise à zéro du compteur et ouverture de session.
        admin.tentatives_echouees = 0
        admin.verrouille_jusqua = None
        admin.dernier_login = maintenant

        jti = uuid.uuid4().hex
        expire = maintenant + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = create_refresh_token(
            user_id=str(admin.id), tenant_id=None, jti=jti, expires_delta=expire - maintenant
        )
        db.add(
            SuperAdminSession(
                super_admin_id=admin.id,
                refresh_token=refresh_token,
                jti=jti,
                ip_address=client_ip,
                expire_at=expire,
            )
        )

        access_token = create_access_token(
            user_id=str(admin.id), tenant_id=None, role="SUPER_ADMIN", permissions=["*"]
        )

        await MasterAuthService._journaliser(
            db,
            auteur=admin.email,
            action="SUPER_ADMIN_LOGIN",
            cible=str(admin.id),
            details={"role": "SUPER_ADMIN"},
            ip=client_ip,
        )
        await db.commit()

        logger.info("super_admin_login", email=admin.email)
        return admin, access_token, refresh_token

    @staticmethod
    async def renouveller(
        db: AsyncSession, refresh_token: str, client_ip: Optional[str] = None
    ) -> Tuple[str, str]:
        """Rotation du refresh token Super Admin. Retourne (access, refresh)."""
        from src.core.exceptions import InvalidTokenException
        from src.core.security import decode_token

        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh" or payload.get("tenant_id") is not None:
            raise InvalidTokenException()

        jti = payload.get("jti")
        if not jti:
            raise InvalidTokenException()

        stmt = (
            select(SuperAdminSession)
            .options(selectinload(SuperAdminSession.super_admin))
            .where(SuperAdminSession.jti == jti)
        )
        session = (await db.execute(stmt)).scalar_one_or_none()

        if session is None or session.est_revoque:
            raise InvalidTokenException()
        if session.expire_at <= datetime.now(timezone.utc):
            raise InvalidTokenException()
        if session.super_admin is None or not session.super_admin.actif:
            raise InvalidTokenException("Compte désactivé.")

        session.est_revoque = True

        nouveau_jti = uuid.uuid4().hex
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        nouveau_refresh = create_refresh_token(
            user_id=str(session.super_admin_id), tenant_id=None, jti=nouveau_jti, expires_delta=expire - datetime.now(timezone.utc)
        )
        db.add(
            SuperAdminSession(
                super_admin_id=session.super_admin_id,
                refresh_token=nouveau_refresh,
                jti=nouveau_jti,
                ip_address=client_ip or session.ip_address,
                expire_at=expire,
            )
        )

        access_token = create_access_token(
            user_id=str(session.super_admin_id), tenant_id=None, role="SUPER_ADMIN", permissions=["*"]
        )
        await db.commit()
        return access_token, nouveau_refresh

    @staticmethod
    async def revoquer(db: AsyncSession, refresh_token: str) -> bool:
        from src.core.exceptions import InvalidTokenException
        from src.core.security import decode_token

        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if not jti:
            return False

        stmt = select(SuperAdminSession).where(SuperAdminSession.jti == jti)
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None or session.est_revoque:
            return False
        session.est_revoque = True
        await db.commit()
        return True


class MasterTenantService:
    @staticmethod
    async def create_societe_and_provision_tenant(
        session: AsyncSession,
        data: SocieteCreate,
        client_ip: str = "unknown",
    ) -> Societe:
        # Vérification si NINEA existe déjà
        if data.ninea:
            stmt = select(Societe).where(Societe.ninea == data.ninea)
            res = await session.execute(stmt)
            if res.scalar_one_or_none():
                raise BusinessRuleViolationException("Une société avec ce numéro NINEA existe déjà.")

        # 1. Création de l'entité Société dans Master
        societe = Societe(
            nom=data.nom,
            ninea=data.ninea,
            logo_url=data.logo_url,
            adresse_siege=data.adresse_siege,
            ville=data.ville,
            pays=data.pays or "Sénégal",
            telephone=data.telephone,
            email=data.email,
            site_web=data.site_web,
            actif=True,
        )
        session.add(societe)
        await session.flush()

        # 2. Définition du nom et paramètres de la base de données dédiée
        db_name = sanitize_db_name(data.nom)
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
        session.add(tenant_db)

        # 3. Log d'audit Master
        audit = AuditLogGlobal(
            auteur_email="system@sysdent.pro",
            action="TENANT_PROVISION_INIT",
            cible_id=str(societe.id),
            details={"nom": societe.nom, "db_name": db_name, "admin_email": data.admin_email},
            ip_address=client_ip,
        )
        session.add(audit)

        await session.commit()

        # 4. Provisionnement réel : création de la base physique, du schéma et de l'admin cabinet.
        # Fait après le commit ci-dessus pour que la Société existe déjà en base même si cette
        # étape échoue (statut reste "PROVISIONING", visible et reprenable manuellement).
        admin_user = None
        try:
            await _create_physical_database(db_name)
            admin_user = await _bootstrap_tenant_schema_and_admin(societe.id, db_name, data)
        except Exception as e:
            logger.exception("tenant_provisioning_failed", societe_id=str(societe.id), db_name=db_name, error=str(e))
            raise AppException(
                message=(
                    f"La société '{societe.nom}' a été enregistrée mais le provisionnement de sa base de "
                    "données a échoué. Statut laissé à PROVISIONING pour reprise manuelle."
                ),
                code="TENANT_PROVISIONING_FAILED",
                status_code=500,
                details={"societe_id": str(societe.id), "db_name": db_name},
            ) from e

        tenant_db.statut = "ACTIVE"
        session.add(tenant_db)

        # 5. Index de routage email -> société dans la base Master.
        # C'est ce qui permet un login en O(1) au lieu de parcourir tous les cabinets.
        from src.modules.auth.services import AuthService

        await AuthService.enregistrer_index(
            session,
            email=data.admin_email,
            societe_id=societe.id,
            utilisateur_id=admin_user.id,
        )

        await session.commit()

        # Rechargement explicite : `tenant_db` est inclus dans le schéma de
        # réponse, et un lazy-load ici échouerait en contexte async.
        societe = (
            await session.execute(
                select(Societe)
                .options(selectinload(Societe.tenant_db))
                .where(Societe.id == societe.id)
            )
        ).scalar_one()

        logger.info(
            "tenant_provisioned_successfully",
            societe_id=str(societe.id),
            db_name=db_name,
            nom=societe.nom,
        )
        return societe

    @staticmethod
    async def get_all_societes(session: AsyncSession) -> list[Societe]:
        # `tenant_db` est inclus dans `SocieteResponse` : il faut le charger
        # explicitement. Un accès paresseux ici déclencherait une requête SQL
        # hors du contexte greenlet async (MissingGreenlet) et le scheduler
        # sérialiserait l'accès en 500.
        stmt = (
            select(Societe)
            .options(selectinload(Societe.tenant_db))
            .order_by(Societe.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_societe_by_id(session: AsyncSession, societe_id: uuid.UUID) -> Societe:
        stmt = (
            select(Societe)
            .options(selectinload(Societe.tenant_db))
            .where(Societe.id == societe_id)
        )
        result = await session.execute(stmt)
        societe = result.scalar_one_or_none()
        if not societe:
            raise EntityNotFoundException("Société", societe_id)
        return societe

    @staticmethod
    async def basculer_statut(
        session: AsyncSession, societe_id: uuid.UUID, actif: bool, auteur: str, client_ip: str = "unknown"
    ) -> Societe:
        """
        Suspend ou réactive un cabinet.

        La suspension coupe l'accès au cabinet sans détruire aucune donnée : les
        données médicales sont conservées (obligation médico-légale).
        """
        societe = (
            await session.execute(
                select(Societe)
                .options(selectinload(Societe.tenant_db))
                .where(Societe.id == societe_id)
            )
        ).scalar_one_or_none()
        if societe is None:
            raise EntityNotFoundException("Société", societe_id)

        societe.actif = actif
        if societe.tenant_db:
            societe.tenant_db.statut = "ACTIVE" if actif else "SUSPENDED"

        await session.flush()
        session.add(
            AuditLogGlobal(
                auteur_email=auteur,
                action="TENANT_ACTIVATE" if actif else "TENANT_SUSPEND",
                cible_id=str(societe.id),
                details={"nom": societe.nom, "actif": actif},
                ip_address=client_ip,
            )
        )
        await session.commit()
        logger.info("tenant_statut_bascule", societe_id=str(societe.id), actif=actif)
        return societe

    @staticmethod
    async def statistiques(session: AsyncSession) -> dict:
        """Vue d'ensemble de la plateforme pour la console Master."""
        total_societes = int((await session.execute(select(func.count(Societe.id)))).scalar_one())
        actives = int(
            (
                await session.execute(
                    select(func.count(Societe.id)).where(Societe.actif.is_(True))
                )
            ).scalar_one()
        )
        total_super_admins = int((await session.execute(select(func.count(SuperAdmin.id)))).scalar_one())
        sessions_actives = int(
            (
                await session.execute(
                    select(func.count(SuperAdminSession.id)).where(
                        SuperAdminSession.est_revoque.is_(False)
                    )
                )
            ).scalar_one()
        )

        par_statut = (
            await session.execute(select(TenantDB.statut, func.count(TenantDB.id)).group_by(TenantDB.statut))
        ).all()

        return {
            "societes_total": total_societes,
            "societes_actives": actives,
            "societes_inactives": total_societes - actives,
            "super_admins": total_super_admins,
            "sessions_master_actives": sessions_actives,
            "tenants_par_statut": {statut: count for statut, count in par_statut},
        }
