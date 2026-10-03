from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import uuid
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.core.database import tenant_db_manager
from src.core.exceptions import AuthenticationException, InvalidTokenException
from src.core.security import create_access_token, create_refresh_token, decrypt_secret, verify_password
from src.modules.master.models import Societe, TenantDB, UtilisateurIndex
from src.modules.tenants.models import Permission, PermissionRole, Role, SessionUser, Utilisateur

logger = structlog.get_logger(__name__)


def _charger_utilisateur_stmt():
    return (
        select(Utilisateur)
        .options(
            selectinload(Utilisateur.role)
            .selectinload(Role.permission_roles)
            .selectinload(PermissionRole.permission)
        )
        .where(Utilisateur.actif.is_(True))
    )


async def _permissions_de(db: AsyncSession, user: Utilisateur) -> List[str]:
    """
    Permissions du rôle de l'utilisateur, au format "MODULE:ACTION".

    Requête explicite plutôt que lecture de `user.role.permission_roles` : cette
    relation n'est pas toujours chargée, et un accès paresseux hors du greenlet
    async échoue (MissingGreenlet). Le tri garantit un JWT stable.
    """
    if user.role_id is None:
        return []

    stmt = (
        select(Permission.module, Permission.action)
        .join(PermissionRole, PermissionRole.permission_id == Permission.id)
        .where(PermissionRole.role_id == user.role_id)
    )
    lignes = (await db.execute(stmt)).all()
    return sorted({f"{module}:{action}" for module, action in lignes})


class AuthService:
    """
    Authentification des utilisateurs de cabinet (base tenant).

    Le routage email -> base du cabinet passe par la table Master
    `utilisateur_index`. L'ancienne implémentation parcourait toutes les bases
    de cabinets actives : le login était en O(n.tenants) et le serveur ouvrait
    une connexion vers chaque base, y compris celles d'autres clients.
    """

    @staticmethod
    async def _resoudre_tenant(
        master_db: AsyncSession, email: str
    ) -> Tuple[TenantDB, UtilisateurIndex]:
        """Retrouve la configuration de base du cabinet rattaché à cet email."""
        stmt = (
            select(UtilisateurIndex, TenantDB)
            .join(TenantDB, TenantDB.societe_id == UtilisateurIndex.societe_id)
            .join(Societe, Societe.id == TenantDB.societe_id)
            .where(
                UtilisateurIndex.email == email.strip().lower(),
                UtilisateurIndex.actif.is_(True),
                TenantDB.statut == "ACTIVE",
                Societe.actif.is_(True),
            )
        )
        result = await master_db.execute(stmt)
        row = result.first()
        if row is None:
            # Message volontairement indistinct : on ne révèle pas si l'email
            # existe, ni si le cabinet est suspendu.
            raise AuthenticationException("Email ou mot de passe incorrect.", code="INVALID_CREDENTIALS")

        index_entry, tenant_config = row[0], row[1]
        return tenant_config, index_entry

    @staticmethod
    async def authenticate(
        email: str,
        password: str,
        master_db: AsyncSession,
    ) -> Tuple[Utilisateur, str, List[str]]:
        """
        Résout le cabinet via l'index Master, puis valide le mot de passe dans sa
        base tenant.

        Retourne : (utilisateur, tenant_id, permissions).
        """
        email_normalise = email.strip().lower()
        tenant_config, index_entry = await AuthService._resoudre_tenant(master_db, email_normalise)

        tenant_id = str(tenant_config.societe_id)
        await tenant_db_manager.get_or_create_engine(
            tenant_id=tenant_id,
            db_name=tenant_config.db_name,
            host=tenant_config.db_host,
            port=tenant_config.db_port,
            user=tenant_config.db_user,
            password=decrypt_secret(tenant_config.db_password),
        )
        session_factory = await tenant_db_manager.get_session_factory(tenant_id)

        async with session_factory() as tenant_session:
            stmt_user = _charger_utilisateur_stmt().where(Utilisateur.email == email_normalise)
            user = (await tenant_session.execute(stmt_user)).scalar_one_or_none()

            if not user:
                logger.warning("login_email_inconnu_dans_tenant", email=email_normalise, tenant_id=tenant_id)
                raise AuthenticationException("Email ou mot de passe incorrect.", code="INVALID_CREDENTIALS")

            if not verify_password(password, user.mot_de_passe):
                logger.warning("login_wrong_password", email=email_normalise, tenant_id=tenant_id)
                raise AuthenticationException("Email ou mot de passe incorrect.", code="INVALID_CREDENTIALS")

            user.dernier_login = datetime.now(timezone.utc)
            await tenant_session.flush()

            permissions = await _permissions_de(tenant_session, user)
            role_nom = user.role.nom if user.role is not None else "INCONNU"

            await tenant_session.commit()
            logger.info("login_reussi", email=email_normalise, tenant_id=tenant_id, role=role_nom)

            return user, tenant_id, permissions

    @staticmethod
    async def ouvrir_session(
        db: AsyncSession,
        user: Utilisateur,
        tenant_id: str,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expire_days: Optional[int] = None,
    ) -> Tuple[str, str]:
        """
        Crée une session persistée et retourne (access_token, refresh_token).

        La session est écrite en base : c'est ce qui rend le logout et la
        révocation possibles (RG12 de Analyse/docs/regles.md).
        """
        from src.core.config import settings

        jti = uuid.uuid4().hex
        expire = datetime.now(timezone.utc) + timedelta(days=expire_days or settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token = create_refresh_token(
            user_id=str(user.id),
            tenant_id=tenant_id,
            jti=jti,
            expires_delta=expire - datetime.now(timezone.utc),
        )

        session = SessionUser(
            utilisateur_id=user.id,
            refresh_token=refresh_token,
            jti=jti,
            ip_address=ip_address,
            user_agent=user_agent,
            expire_at=expire,
        )
        db.add(session)
        await db.flush()

        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=tenant_id,
            role=user.role.nom if user.role is not None else "INCONNU",
            permissions=await _permissions_de(db, user),
        )
        return access_token, refresh_token

    @staticmethod
    async def renouveller_session(
        db: AsyncSession,
        refresh_token: str,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[Utilisateur, str, str, str]:
        """
        Rotation du refresh token. L'ancien est révoqué et le compte relu en base.

        Retourne : (utilisateur, nouveau_access_token, nouveau_refresh_token, tenant_id).

        Relire l'utilisateur est indispensable : le rôle et les permissions sont
        recalculés à chaque renouvellement. Sans cela, une révocation de rôle ne
        prendrait effet qu'à l'expiration de l'access token.
        """
        from src.core.config import settings
        from src.core.security import decode_token

        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenException("Jeton de rafraîchissement invalide.")

        jti = payload.get("jti")
        tenant_id = payload.get("tenant_id")
        user_id = payload.get("sub")
        if not jti or not tenant_id or not user_id:
            raise InvalidTokenException()

        stmt = (
            select(SessionUser)
            .options(selectinload(SessionUser.utilisateur).selectinload(Utilisateur.role))
            .where(SessionUser.jti == jti)
        )
        session = (await db.execute(stmt)).scalar_one_or_none()

        if session is None:
            raise InvalidTokenException("Session inconnue : reconnexion requise.")
        if session.est_revoque:
            # Un refresh token déjà utilisé revient ici : soit une réutilisation
            # (token volé), soit un bug. Dans les deux cas on refuse.
            logger.warning("refresh_token_revoque_utilise", jti=jti, user_id=user_id)
            raise InvalidTokenException()
        if session.expire_at <= datetime.now(timezone.utc):
            raise InvalidTokenException()

        user = session.utilisateur
        if user is None or not user.actif:
            logger.warning("refresh_compte_desactive", user_id=user_id)
            raise InvalidTokenException("Compte désactivé.")

        # Rotation : l'ancien jeton ne vaut plus rien dès cet instant.
        session.est_revoque = True

        nouveau_jti = uuid.uuid4().hex
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        nouveau_refresh = create_refresh_token(
            user_id=str(user.id),
            tenant_id=tenant_id,
            jti=nouveau_jti,
            expires_delta=expire - datetime.now(timezone.utc),
        )

        session_nouvelle = SessionUser(
            utilisateur_id=user.id,
            refresh_token=nouveau_refresh,
            jti=nouveau_jti,
            ip_address=ip_address or session.ip_address,
            user_agent=user_agent or session.user_agent,
            expire_at=expire,
        )
        db.add(session_nouvelle)
        await db.flush()

        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=tenant_id,
            role=user.role.nom if user.role is not None else "INCONNU",
            permissions=await _permissions_de(db, user),
        )

        logger.info("session_renouvelee", user_id=user_id, tenant_id=tenant_id)
        return user, access_token, nouveau_refresh, tenant_id

    @staticmethod
    async def revoquer_session(db: AsyncSession, refresh_token: str) -> bool:
        """
        Révoque une session par son refresh token. Retourne True si une session
        a effectivement été révoquée.
        """
        from src.core.security import decode_token

        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if not jti:
            return False

        stmt = select(SessionUser).where(SessionUser.jti == jti)
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None or session.est_revoque:
            return False

        session.est_revoque = True
        await db.flush()
        logger.info("session_revoquee", jti=jti, utilisateur_id=str(session.utilisateur_id))
        return True

    @staticmethod
    async def revoquer_toutes_sessions(db: AsyncSession, utilisateur_id: uuid.UUID) -> int:
        """Révoque toutes les sessions d'un compte (déconnexion forcée, RG12)."""
        from sqlalchemy import update

        stmt = (
            update(SessionUser)
            .where(SessionUser.utilisateur_id == utilisateur_id, SessionUser.est_revoque.is_(False))
            .values(est_revoque=True)
        )
        result = await db.execute(stmt)
        return int(result.rowcount or 0)

    @staticmethod
    async def enregistrer_index(
        master_db: AsyncSession,
        *,
        email: str,
        societe_id: uuid.UUID,
        utilisateur_id: uuid.UUID,
    ) -> None:
        """
        Enregistre le routage email -> société dans la base Master.

        Appelé à chaque création d'utilisateur cabinet. L'email est unique
        plateforme : un même login ne peut pas exister dans deux cabinets.
        """
        email_normalise = email.strip().lower()
        existant = (
            await master_db.execute(
                select(UtilisateurIndex).where(UtilisateurIndex.email == email_normalise)
            )
        ).scalar_one_or_none()

        if existant is not None:
            if existant.societe_id != societe_id:
                raise AuthenticationException(
                    "Cet email est déjà utilisé par un autre cabinet.",
                    code="EMAIL_DEJA_UTILISE",
                )
            return

        master_db.add(
            UtilisateurIndex(
                email=email_normalise,
                societe_id=societe_id,
                utilisateur_id=utilisateur_id,
                actif=True,
            )
        )

    @staticmethod
    async def marquer_connexion_index(
        master_db: AsyncSession, email: str, tenant_id: Optional[str] = None
    ) -> None:
        stmt = select(UtilisateurIndex).where(UtilisateurIndex.email == email.strip().lower())
        entry = (await master_db.execute(stmt)).scalar_one_or_none()
        if entry is not None:
            entry.derniere_connexion = datetime.now(timezone.utc)
