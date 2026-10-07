"""
Authentification de la console PLATEFORME (Phase A.3 et A.4).

Séquence de connexion, volontairement en deux temps :

    POST /platform/auth/login        (email + mot de passe)
        └─ si 2FA actif  → { "deux_facteurs_requis": true, "jeton_challenge": … }
    POST /platform/auth/2fa          (jeton_challenge + code TOTP)
        └─ → { access_token, refresh_token }

Le jeton de défi est opaque, à 5 minutes, **haché en base** et consommé une
seule fois. Il ne permet pas d'obtenir des jetons de session sans le second
facteur : le vol d'un mot de passe seul ne donne rien.

Un compte sans second facteur activé ne peut **jamais** obtenir de jeton de
session : `verifier_second_facteur_obligatoire` le refuse. Le second facteur est
donc obligatoire par construction, pas par une case à cocher.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.exceptions import (
    AuthenticationException,
    InvalidStateException,
    InvalidTokenException,
    TooManyRequestsException,
)
from src.core.security import (
    create_platform_access_token,
    create_platform_refresh_token,
    get_password_hash,
    verify_password,
)
from src.modules.platform.models import (
    JetonUsageUnique,
    SessionPlateforme,
    StatutUtilisateurPlateforme,
    UtilisateurPlateforme,
    UsageJeton,
)
from src.modules.platform.security import (
    chiffrer_secret_2fa,
    generer_jeton_opaque,
    generer_secret_totp,
    hacher_jeton,
    hacher_refresh,
    valider_secret_2fa,
    verifier_code_totp,
    verifier_mot_de_passe,
)
from src.modules.platform.services.journal import JournalService
from src.modules.platform.services.rbac import PlatformRbacService

logger = structlog.get_logger(__name__)

DUREE_CHALLENGE_2FA_MINUTES = 5


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class PlatformAuthService:
    # ─────────────────────────────────────────────────────────────────────────
    # Connexion
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def authentifier(
        db: AsyncSession,
        email: str,
        mot_de_passe: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Première étape : vérifie e-mail + mot de passe.

        Retourne soit `{ "deux_facteurs_requis": False, "tokens": … }` (compte
        sans 2FA — impossible en pratique, cf. `activer_2fa`), soit
        `{ "deux_facteurs_requis": True, "jeton_challenge": … }`.
        """
        email_normalise = email.strip().lower()

        stmt = (
            select(UtilisateurPlateforme)
            .options(selectinload(UtilisateurPlateforme.roles))
            .where(UtilisateurPlateforme.email == email_normalise)
        )
        user = (await db.execute(stmt)).scalar_one_or_none()

        if user is None:
            # Message volontairement IDENTIQUE à celui d'un mot de passe faux :
            # la console ne doit pas révéler quelles adresses existent.
            await JournalService.journaliser(
                db,
                action="PLATFORM_LOGIN_ECHOUCHE",
                type_cible="AUTH",
                acteur_email=email_normalise,
                cible_id=None,
                apres={"raison": "compte_inconnu"},
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationException("Identifiants invalides.", code="INVALID_CREDENTIALS")

        if user.statut == StatutUtilisateurPlateforme.DESACTIF:
            await JournalService.journaliser(
                db,
                action="PLATFORM_LOGIN_REFUSE",
                type_cible="AUTH",
                acteur_email=email_normalise,
                acteur_id=user.id,
                apres={"raison": "compte_desactive"},
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            # Même message que des identifiants invalides : un attaquant ne doit
            # pas pouvoir distinguer « ce compte existe mais est désactivé ».
            raise AuthenticationException("Identifiants invalides.", code="INVALID_CREDENTIALS")

        # Verrouillage progressif après N échecs.
        if user.verrouille_jusqua and user.verrouille_jusqua > _maintenant():
            restantes = int((user.verrouille_jusqua - _maintenant()).total_seconds())
            await JournalService.journaliser(
                db,
                action="PLATFORM_LOGIN_BLOQUE",
                type_cible="AUTH",
                acteur_email=user.email,
                acteur_id=user.id,
                apres={"secondes_restantes": restantes},
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            raise TooManyRequestsException(
                "Compte temporairement verrouillé après trop de tentatives.",
                retry_after_seconds=restantes,
            )

        if not verify_password(mot_de_passe, user.mot_de_passe):
            user.tentatives_echouees += 1
            if user.tentatives_echouees >= settings.PLATFORM_MAX_FAILED_LOGINS:
                user.verrouille_jusqua = _maintenant() + timedelta(
                    minutes=settings.PLATFORM_LOCKOUT_MINUTES
                )
                user.tentatives_echouees = 0
                user.statut = StatutUtilisateurPlateforme.VERROUILLE
                logger.warning(
                    "plateforme_compte_verrouille", email=user.email,
                    minutes=settings.PLATFORM_LOCKOUT_MINUTES,
                )
            await JournalService.journaliser(
                db,
                action="PLATFORM_LOGIN_ECHOUCHE",
                type_cible="AUTH",
                acteur_email=user.email,
                acteur_id=user.id,
                apres={"tentatives_echouees": user.tentatives_echouees},
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationException("Identifiants invalides.", code="INVALID_CREDENTIALS")

        # Mot de passe correct : le compte n'est plus verrouillé, le compteur repart.
        if user.statut == StatutUtilisateurPlateforme.VERROUILLE:
            user.statut = StatutUtilisateurPlateforme.ACTIF
        user.tentatives_echouees = 0
        user.verrouille_jusqua = None

        # ── Second facteur ────────────────────────────────────────────────────
        secret = valider_secret_2fa(user.secret_2fa_chiffre)

        if secret is None:
            # Aucun secret n'existe : le compte est orphelin (créé `--sans-2fa`,
            # ou clé de chiffrement changée). Aucun jeton de session ne peut être
            # délivré. La sortie passe par un Super Admin
            # (`POST /platform/users/{id}/reinitialisation-acces`), tracée.
            await JournalService.journaliser(
                db,
                action="PLATFORM_2FA_REQUIS",
                type_cible="AUTH",
                acteur_email=user.email,
                acteur_id=user.id,
                apres={"raison": "second_facteur_non_active"},
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            raise InvalidStateException(
                "La double authentification n'est pas activée sur ce compte. "
                "Contactez un Super Admin pour la réinitialiser.",
                code="DEUX_FACTEURS_NON_ACTIVE",
            )

        jeton_challenge = await PlatformAuthService._emettre_challenge(
            db, user, client_ip=client_ip, user_agent=user_agent
        )

        # Un secret préparé mais pas encore confirmé (« en attente
        # d'activation ») ouvre quand même le défi : c'est ce qui évite
        # l'impasse du tout premier login, où exiger un 2FA actif alors que
        # personne ne l'a jamais activé rendrait le compte inaccessible à son
        # propre titulaire. Le code TOTP saisi à cette étape ACTIVE le second
        # facteur et ouvre la session dans le même mouvement.
        activation_requise = not user.deux_facteurs_actif

        await JournalService.journaliser(
            db,
            action="PLATFORM_2FA_DEFI",
            type_cible="AUTH",
            acteur_email=user.email,
            acteur_id=user.id,
            apres={
                "deux_facteurs_requis": True,
                "activation_requise": activation_requise,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()

        return {
            "deux_facteurs_requis": True,
            "activation_requise": activation_requise,
            "jeton_challenge": jeton_challenge,
            "expiration_secondes": DUREE_CHALLENGE_2FA_MINUTES * 60,
        }

    @staticmethod
    async def confirmer_second_facteur(
        db: AsyncSession,
        jeton_challenge: str,
        code: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deuxième étape : vérifie le code TOTP et ouvre la session."""
        hash_challenge = hacher_jeton(jeton_challenge)
        stmt = (
            select(JetonUsageUnique)
            .where(
                JetonUsageUnique.hash_jeton == hash_challenge,
                JetonUsageUnique.usage == UsageJeton.CHALLENGE_2FA,
            )
        )
        jeton = (await db.execute(stmt)).scalar_one_or_none()

        if jeton is None or jeton.utilise or jeton.expire_le <= _maintenant():
            raise InvalidTokenException("Session de connexion expirée, reprenez l'identification.")

        user_id = uuid.UUID(str(jeton.cible_id))
        stmt_user = (
            select(UtilisateurPlateforme)
            .options(selectinload(UtilisateurPlateforme.roles))
            .where(UtilisateurPlateforme.id == user_id)
        )
        user = (await db.execute(stmt_user)).scalar_one_or_none()
        if user is None or user.statut != StatutUtilisateurPlateforme.ACTIF:
            raise AuthenticationException("Compte indisponible.", code="COMPTE_NON_ACTIF")

        secret = valider_secret_2fa(user.secret_2fa_chiffre)
        if secret is None or not verifier_code_totp(secret, code):
            await JournalService.journaliser(
                db,
                action="PLATFORM_2FA_ECHOUCHE",
                type_cible="AUTH",
                acteur_email=user.email,
                acteur_id=user.id,
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            # MÊME message qu'un code expiré : on ne dit pas si le code était
            # faux ou le jeton périmé.
            raise AuthenticationException("Code de vérification invalide.", code="CODE_2FA_INVALIDE")

        # Jeton consommé : un défi ne sert qu'une fois.
        jeton.utilise = True
        jeton.utilise_at = _maintenant()

        # Première connexion : le code TOTP saisi vaut confirmation du second
        # facteur. Sans cela, un compte créé par la CLI ne pourrait jamais se
        # connecter, puisque la console exige le 2FA pour ouvrir une session.
        if not user.deux_facteurs_actif:
            user.deux_facteurs_actif = True
            user.deux_facteurs_confirme_at = _maintenant()
            await JournalService.journaliser(
                db,
                action="PLATFORM_2FA_ACTIVATE",
                type_cible="AUTH",
                acteur_email=user.email,
                acteur_id=user.id,
                apres={"deux_facteurs_actif": True},
                ip_address=client_ip,
                user_agent=user_agent,
            )
        await db.flush()

        tokens = await PlatformAuthService._ouvrir_session(db, user, client_ip, user_agent)
        await JournalService.journaliser(
            db,
            action="PLATFORM_LOGIN",
            type_cible="AUTH",
            acteur_email=user.email,
            acteur_id=user.id,
            apres={"roles": await PlatformRbacService.roles_utilisateur(db, user.id)},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()
        return tokens

    # ─────────────────────────────────────────────────────────────────────────
    # Second facteur : enrollment
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def preparer_second_facteur(
        db: AsyncSession, user: UtilisateurPlateforme
    ) -> Dict[str, str]:
        """
        Génère un secret TOTP et le renvoie UNE SEULE FOIS, en clair.

        L'opérateur doit le scanner avant de quitter la commande : ni la base ni
        le journal ne le conservent en clair. `secret_2fa_chiffre` est alimenté à
        l'ACTIVATION, pas ici, pour qu'un secret jamais scanné ne soit pas
        accepté.
        """
        from src.modules.platform.security import uri_otpauth

        secret = generer_secret_totp()
        user.secret_2fa_chiffre = chiffrer_secret_2fa(secret)
        user.deux_facteurs_actif = False
        await db.flush()
        return {
            "secret": secret,
            "uri": uri_otpauth(secret, user.email),
            "instruction": (
                "Scannez ce secret avec une application TOTP (Aegis, Google "
                "Authenticator, 1Password), puis confirmez avec un code pour activer."
            ),
        }

    @staticmethod
    async def activer_second_facteur(
        db: AsyncSession, user: UtilisateurPlateforme, code: str
    ) -> None:
        secret = valider_secret_2fa(user.secret_2fa_chiffre)
        if secret is None:
            raise InvalidStateException(
                "Aucun secret 2FA en attente d'activation.", code="SECRET_2FA_ABSENT"
            )
        if not verifier_code_totp(secret, code):
            raise AuthenticationException("Code de vérification invalide.", code="CODE_2FA_INVALIDE")
        user.deux_facteurs_actif = True
        user.deux_facteurs_confirme_at = _maintenant()
        await db.flush()

    # ─────────────────────────────────────────────────────────────────────────
    # Sessions
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def renouveller(
        db: AsyncSession, refresh_token: str, client_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rotation du refresh token.

        L'ancien est marqué révoqué et un nouveau `jti` est émis : un jeton volé
        est donc détectable (la session qu'il désigne est déjà révoquée) et le
        rôle relu en base à chaque appel, donc un droit retiré s'applique à la
        requête suivante.
        """
        from src.core.security import decode_platform_token

        try:
            payload = decode_platform_token(refresh_token)
        except AuthenticationException:
            raise InvalidTokenException()

        if payload.get("type") != "refresh":
            raise InvalidTokenException("Type de jeton invalide.")

        jti = payload.get("jti")
        if not jti:
            raise InvalidTokenException()

        stmt = (
            select(SessionPlateforme)
            .options(selectinload(SessionPlateforme.utilisateur).selectinload(UtilisateurPlateforme.roles))
            .where(SessionPlateforme.jti == jti)
        )
        session = (await db.execute(stmt)).scalar_one_or_none()

        if session is None or session.est_revoque:
            raise InvalidTokenException()
        if session.expire_at <= _maintenant():
            raise InvalidTokenException()
        if session.refresh_token_hash != hacher_refresh(refresh_token):
            raise InvalidTokenException()
        if session.utilisateur is None or session.utilisateur.statut != StatutUtilisateurPlateforme.ACTIF:
            raise InvalidTokenException("Compte désactivé.")

        session.est_revoque = True

        nouveau = await PlatformAuthService._emettre_session(
            db, session.utilisateur, client_ip or session.ip_address, session.user_agent
        )
        await db.commit()
        return nouveau

    @staticmethod
    async def revoquer(db: AsyncSession, refresh_token: str) -> bool:
        from src.core.security import decode_platform_token

        try:
            payload = decode_platform_token(refresh_token)
        except AuthenticationException:
            return False
        jti = payload.get("jti")
        if not jti:
            return False
        stmt = select(SessionPlateforme).where(SessionPlateforme.jti == jti)
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None or session.est_revoque:
            return False
        session.est_revoque = True
        await db.commit()
        return True

    @staticmethod
    async def revoquer_toutes_les_sessions(
        db: AsyncSession, utilisateur_id: uuid.UUID, motif: str, auteur: str
    ) -> int:
        """
        Révoque TOUTES les sessions d'un compte (désactivation, changement de rôle,
        incident de sécurité). Un agent dont le compte est compromis mais qui a
        d'autres sessions ouvertes les perd toutes.
        """
        stmt = select(SessionPlateforme).where(
            SessionPlateforme.utilisateur_id == utilisateur_id,
            SessionPlateforme.est_revoque.is_(False),
        )
        sessions = (await db.execute(stmt)).scalars().all()
        for session in sessions:
            session.est_revoque = True
        await JournalService.journaliser(
            db,
            action="PLATFORM_SESSIONS_REVOQUEES",
            type_cible="UTILISATEUR",
            cible_id=str(utilisateur_id),
            acteur_email=auteur,
            apres={"nombre": len(sessions)},
            motif=motif,
        )
        await db.commit()
        return len(sessions)

    # ─────────────────────────────────────────────────────────────────────────
    # Interne
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def _emettre_challenge(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> str:
        jeton = generer_jeton_opaque()
        db.add(
            JetonUsageUnique(
                usage=UsageJeton.CHALLENGE_2FA,
                hash_jeton=hacher_jeton(jeton),
                cible_type="UTILISATEUR",
                cible_id=str(user.id),
                expire_le=_maintenant() + timedelta(minutes=DUREE_CHALLENGE_2FA_MINUTES),
                ip_address=client_ip,
            )
        )
        await db.flush()
        return jeton

    @staticmethod
    async def _ouvrir_session(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> Dict[str, Any]:
        tokens = await PlatformAuthService._emettre_session(db, user, client_ip, user_agent)
        user.dernier_login = _maintenant()
        await db.flush()
        return tokens

    @staticmethod
    async def _emettre_session(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> Dict[str, Any]:
        roles = await PlatformRbacService.roles_utilisateur(db, user.id)
        permissions = await PlatformRbacService.permissions_utilisateur(db, user.id)

        jti = uuid.uuid4().hex
        expire = _maintenant() + timedelta(hours=settings.PLATFORM_REFRESH_TOKEN_EXPIRE_HOURS)
        refresh_token = create_platform_refresh_token(
            user_id=str(user.id), jti=jti, expires_delta=expire - _maintenant()
        )
        db.add(
            SessionPlateforme(
                utilisateur_id=user.id,
                refresh_token_hash=hacher_refresh(refresh_token),
                jti=jti,
                ip_address=client_ip,
                user_agent=user_agent,
                expire_at=expire,
            )
        )
        await db.flush()

        access_token = create_platform_access_token(
            user_id=str(user.id), roles=roles, permissions=permissions
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.PLATFORM_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_expires_in": settings.PLATFORM_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Réinitialisation d'accès (Super Admin) — Phase A.5
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def reinitialiser_acces(
        db: AsyncSession, user: UtilisateurPlateforme, motif: str, auteur: str
    ) -> Dict[str, str]:
        """
        Remet à zéro l'authentification d'un compte : nouveau secret 2FA en attente
        et révocation de toutes les sessions.

        Cette action est TOUJOURS tracée et JAMAIS silencieuse : elle sert
        après une perte de téléphone, donc c'est précisément le moment où un
        attaquant tenterait de s'installer.
        """
        avant = {
            "deux_facteurs_actif": user.deux_facteurs_actif,
            "statut": user.statut.value,
        }
        preparation = await PlatformAuthService.preparer_second_facteur(db, user)
        await PlatformAuthService.revoquer_toutes_les_sessions(
            db, user.id, motif="réinitialisation d'accès", auteur=auteur
        )
        await JournalService.journaliser(
            db,
            action="PLATFORM_ACCES_REINITIALISE",
            type_cible="UTILISATEUR",
            cible_id=str(user.id),
            acteur_email=auteur,
            avant=avant,
            apres={"deux_facteurs_actif": False},
            motif=motif,
        )
        return preparation

    @staticmethod
    async def changer_mot_de_passe(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        nouveau: str,
        auteur: Optional[str] = None,
        ancien: Optional[str] = None,
    ) -> None:
        manquements = verifier_mot_de_passe(nouveau, user.email)
        if manquements:
            from src.core.exceptions import BusinessRuleViolationException

            raise BusinessRuleViolationException(
                "Mot de passe non conforme à la politique de sécurité.",
                code="POLITIQUE_MOT_DE_PASSE",
                details={"regles": manquements},
            )
        if ancien is not None and not verify_password(ancien, user.mot_de_passe):
            raise AuthenticationException("Mot de passe actuel incorrect.", code="INVALID_CREDENTIALS")
        if verify_password(nouveau, user.mot_de_passe):
            from src.core.exceptions import BusinessRuleViolationException

            raise BusinessRuleViolationException(
                "Le nouveau mot de passe doit être différent de l'ancien.",
                code="MOT_DE_PASSE_IDENTIQUE",
            )

        await JournalService.journaliser(
            db,
            action="PLATFORM_MOT_DE_PASSE_CHANGE",
            type_cible="UTILISATEUR",
            cible_id=str(user.id),
            acteur_email=auteur or user.email,
            acteur_id=user.id,
        )
        user.mot_de_passe = get_password_hash(nouveau)
        await db.flush()