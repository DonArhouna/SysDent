"""
Sécurité des comptes des cabinets : activation par lien, mot de passe
temporaire, double authentification.

Connexion en étapes. Après un mot de passe correct, le serveur décide :

1. ``changement_mot_de_passe`` : le mot de passe est temporaire (réinitialisé ou
   fixé par un tiers) ; il faut le changer avant toute session ;
2. ``deux_facteurs`` : la 2FA est active ; un code (application, e-mail ou
   secours) ouvre la session ;
3. ``enrolement_2fa`` : la 2FA est obligatoire pour ce rôle mais pas encore
   configurée ; QR code ou e-mail, au choix ;
4. ``session`` : sinon, la session s'ouvre.

Chaque étape est portée par un **jeton opaque à usage unique**, de la forme
``<tenant_id>.<secret>`` : l'identifiant du cabinet dit dans quelle base
chercher, le secret n'est stocké que **haché**. Aucun jeton d'étape ne vaut
session.

Tout vit dans la base du cabinet : la connexion d'un cabinet ne dépend jamais
de la base de la console.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.database import tenant_db_manager
from src.core.exceptions import (
    AuthenticationException,
    BusinessRuleViolationException,
    InvalidStateException,
    InvalidTokenException,
)
from src.core.security import decrypt_secret, encrypt_secret, get_password_hash, verify_password
from src.modules.tenants.models import JetonAuth, Utilisateur

logger = structlog.get_logger(__name__)

# Usages des jetons (colonne `jetons_auth.usage`)
ACTIVATION = "ACTIVATION"
ETAPE_MDP = "ETAPE_MDP"
ETAPE_2FA = "ETAPE_2FA"
ETAPE_ENROLEMENT = "ETAPE_ENROLEMENT"
CODE_EMAIL = "CODE_EMAIL"

DUREE_ETAPE_MIN = 10
DUREE_CODE_EMAIL_MIN = 5

#: Message unique pour tout code refusé : ne pas dire s'il était faux, expiré ou rejoué.
CODE_INVALIDE = "Code de vérification invalide."


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _hacher(valeur: str) -> str:
    return hashlib.sha256(valeur.encode("utf-8")).hexdigest()


def _hacher_code_email(contexte: str, code: str) -> str:
    """HMAC avec la clé du serveur : un code à 6 chiffres haché en SHA nu se retrouve en un million d'essais."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), f"{contexte}:{code.strip()}".encode("utf-8"), hashlib.sha256
    ).hexdigest()


def masquer_email(email: str) -> str:
    local, _, domaine = email.partition("@")
    return f"{local[:2]}{'*' * max(len(local) - 2, 1)}@{domaine}"


def jeton_public(tenant_id: str, secret: str) -> str:
    return f"{tenant_id}.{secret}"


def decouper_jeton(jeton: str) -> Tuple[str, str]:
    """`<tenant_id>.<secret>` -> (tenant_id, secret). Refus générique si mal formé."""
    tenant, _, secret = (jeton or "").partition(".")
    try:
        uuid.UUID(tenant)
    except ValueError:
        raise InvalidTokenException("Lien ou étape de connexion invalide.")
    if len(secret) < 20:
        raise InvalidTokenException("Lien ou étape de connexion invalide.")
    return tenant, secret


async def session_cabinet(tenant_id: str) -> AsyncSession:
    """Session sur la base du cabinet, avec son compte dédié (registre master)."""
    fabrique = await tenant_db_manager.get_session_factory(tenant_id)
    return fabrique()


def deux_facteurs_obligatoire(user: Utilisateur) -> bool:
    roles = settings.TENANT_2FA_ROLES_OBLIGATOIRES or []
    return user.role is not None and user.role.nom in roles


def methodes_2fa(user: Utilisateur) -> List[str]:
    """`totp` si une application est configurée, `email` toujours."""
    return (["totp"] if user.secret_2fa else []) + ["email"]


class SecuriteCompte:
    # ── Jetons ───────────────────────────────────────────────────────────────

    @staticmethod
    async def emettre(
        db: AsyncSession,
        user_id: uuid.UUID,
        usage: str,
        duree: timedelta,
        contexte: Optional[str] = None,
        secret: Optional[str] = None,
        hash_force: Optional[str] = None,
    ) -> str:
        """
        Émet un jeton et annule les précédents du même usage pour ce compte : un
        seul lien d'activation, une seule étape, un seul code e-mail vivant à la fois.
        """
        await db.execute(
            update(JetonAuth)
            .where(JetonAuth.utilisateur_id == user_id, JetonAuth.usage == usage, JetonAuth.utilise.is_(False))
            .values(utilise=True)
        )
        secret = secret or secrets.token_urlsafe(32)
        db.add(
            JetonAuth(
                utilisateur_id=user_id,
                usage=usage,
                hash_jeton=hash_force or _hacher(secret),
                contexte=contexte,
                expire_le=_maintenant() + duree,
            )
        )
        await db.flush()
        return secret

    @staticmethod
    async def lire(db: AsyncSession, secret: str, usages: Tuple[str, ...]) -> Tuple[JetonAuth, Utilisateur]:
        """Jeton valable (non utilisé, non expiré) et son compte. Refus générique sinon."""
        jeton = (
            await db.execute(
                select(JetonAuth).where(JetonAuth.hash_jeton == _hacher(secret), JetonAuth.usage.in_(usages))
            )
        ).scalar_one_or_none()
        if jeton is None or jeton.utilise or jeton.expire_le <= _maintenant():
            raise InvalidTokenException("Lien expiré ou déjà utilisé. Reprenez depuis le début.")
        user = (
            await db.execute(
                select(Utilisateur).options(selectinload(Utilisateur.role)).where(Utilisateur.id == jeton.utilisateur_id)
            )
        ).scalar_one_or_none()
        if user is None or not user.actif:
            raise InvalidTokenException("Lien expiré ou déjà utilisé. Reprenez depuis le début.")
        return jeton, user

    @staticmethod
    def consommer(jeton: JetonAuth) -> None:
        jeton.utilise = True

    # ── Activation ───────────────────────────────────────────────────────────

    @staticmethod
    async def preparer_activation(db: AsyncSession, user: Utilisateur, tenant_id: str) -> str:
        """
        Met le compte en attente d'activation et rend le **lien** à envoyer.

        Le mot de passe existant est remplacé par un aléa que personne ne
        connaît : seul le titulaire du lien pourra en choisir un.
        """
        user.activation_requise = True
        user.doit_changer_mot_de_passe = False
        user.mot_de_passe = get_password_hash(secrets.token_urlsafe(32))
        secret = await SecuriteCompte.emettre(
            db, user.id, ACTIVATION, timedelta(hours=settings.TENANT_ACTIVATION_HEURES)
        )
        return f"{settings.CLIENT_APP_URL.rstrip('/')}/activation?jeton={jeton_public(tenant_id, secret)}"

    @staticmethod
    async def envoyer_activation(
        db: AsyncSession, user: Utilisateur, tenant_id: str, nom_cabinet: Optional[str]
    ) -> bool:
        from src.modules.platform.services.notifications import EmailService

        lien = await SecuriteCompte.preparer_activation(db, user, tenant_id)
        await db.commit()
        return await EmailService.activation_compte_cabinet(
            user.email, user.prenom, lien, nom_cabinet or "votre cabinet", settings.TENANT_ACTIVATION_HEURES
        )

    @staticmethod
    async def activer(db: AsyncSession, secret: str, mot_de_passe: str) -> Utilisateur:
        jeton, user = await SecuriteCompte.lire(db, secret, (ACTIVATION,))
        SecuriteCompte._exiger_politique(mot_de_passe, user.email)
        user.mot_de_passe = get_password_hash(mot_de_passe)
        user.activation_requise = False
        user.doit_changer_mot_de_passe = False
        SecuriteCompte.consommer(jeton)
        return user

    @staticmethod
    def _exiger_politique(mot_de_passe: str, email: str) -> None:
        from src.modules.platform.security import verifier_mot_de_passe

        manquements = verifier_mot_de_passe(mot_de_passe, email)
        if manquements:
            raise BusinessRuleViolationException(
                "Mot de passe non conforme à la politique de sécurité.",
                code="POLITIQUE_MOT_DE_PASSE",
                details={"regles": manquements},
            )

    # ── Connexion en étapes ──────────────────────────────────────────────────

    @staticmethod
    async def etape_suivante(db: AsyncSession, user: Utilisateur, tenant_id: str) -> Dict[str, Any]:
        """Décide de l'étape qui suit un mot de passe correct. `session` = rien à franchir."""
        if user.doit_changer_mot_de_passe:
            usage, etape = ETAPE_MDP, "changement_mot_de_passe"
        elif user.deux_facteurs:
            usage, etape = ETAPE_2FA, "deux_facteurs"
        elif deux_facteurs_obligatoire(user):
            usage, etape = ETAPE_ENROLEMENT, "enrolement_2fa"
        else:
            return {"etape": "session"}
        secret = await SecuriteCompte.emettre(db, user.id, usage, timedelta(minutes=DUREE_ETAPE_MIN))
        return {
            "etape": etape,
            "jeton_etape": jeton_public(tenant_id, secret),
            "methodes": methodes_2fa(user) if etape == "deux_facteurs" else ["totp", "email"],
            "expiration_secondes": DUREE_ETAPE_MIN * 60,
        }

    @staticmethod
    async def changer_mot_de_passe_initial(
        db: AsyncSession, secret: str, nouveau: str
    ) -> Tuple[Utilisateur, JetonAuth]:
        jeton, user = await SecuriteCompte.lire(db, secret, (ETAPE_MDP,))
        SecuriteCompte._exiger_politique(nouveau, user.email)
        if verify_password(nouveau, user.mot_de_passe):
            raise BusinessRuleViolationException(
                "Le nouveau mot de passe doit être différent du mot de passe temporaire.",
                code="MOT_DE_PASSE_IDENTIQUE",
            )
        user.mot_de_passe = get_password_hash(nouveau)
        user.doit_changer_mot_de_passe = False
        SecuriteCompte.consommer(jeton)
        return user, jeton

    # ── Codes ────────────────────────────────────────────────────────────────

    @staticmethod
    async def envoyer_code_email(db: AsyncSession, user: Utilisateur, contexte: str) -> Dict[str, Any]:
        from src.modules.platform.security import generer_code_email
        from src.modules.platform.services.notifications import EmailService

        code = generer_code_email()
        await SecuriteCompte.emettre(
            db, user.id, CODE_EMAIL, timedelta(minutes=DUREE_CODE_EMAIL_MIN),
            contexte=contexte, hash_force=_hacher_code_email(contexte, code),
        )
        await db.commit()
        if not await EmailService.code_connexion_cabinet(user.email, code, DUREE_CODE_EMAIL_MIN):
            raise InvalidStateException(
                "L'e-mail n'a pas pu être envoyé. Réessayez ou utilisez une autre méthode.",
                code="ENVOI_EMAIL_ECHOUE",
            )
        return {"destinataire": masquer_email(user.email), "expiration_secondes": DUREE_CODE_EMAIL_MIN * 60}

    @staticmethod
    async def _code_email_valide(db: AsyncSession, user: Utilisateur, contexte: str, code: str) -> bool:
        code = (code or "").strip()
        if len(code) != 6 or not code.isdigit():
            return False
        ligne = (
            await db.execute(
                select(JetonAuth).where(
                    JetonAuth.hash_jeton == _hacher_code_email(contexte, code),
                    JetonAuth.usage == CODE_EMAIL,
                    JetonAuth.utilisateur_id == user.id,
                    JetonAuth.utilise.is_(False),
                    JetonAuth.expire_le > _maintenant(),
                )
            )
        ).scalar_one_or_none()
        if ligne is None:
            return False
        ligne.utilise = True
        return True

    @staticmethod
    def _code_secours_valide(user: Utilisateur, code: str) -> bool:
        restants, trouve = [], False
        for h in list(user.codes_secours_haches or []):
            if not trouve and verify_password(code.strip().upper(), h):
                trouve = True
                continue
            restants.append(h)
        if trouve:
            user.codes_secours_haches = restants
        return trouve

    @staticmethod
    async def verifier_defi(db: AsyncSession, secret: str, code: str) -> Tuple[Utilisateur, JetonAuth]:
        """Étape `deux_facteurs` : application, code e-mail de CETTE étape, ou code de secours."""
        from src.modules.platform.security import verifier_code_totp

        jeton, user = await SecuriteCompte.lire(db, secret, (ETAPE_2FA,))
        totp = decrypt_secret(user.secret_2fa) if user.secret_2fa else None
        ok = (
            (totp is not None and verifier_code_totp(totp, code))
            or await SecuriteCompte._code_email_valide(db, user, jeton.hash_jeton, code)
            or SecuriteCompte._code_secours_valide(user, code)
        )
        if not ok:
            await db.commit()  # un code e-mail consommé par erreur reste consommé
            raise AuthenticationException(CODE_INVALIDE, code="CODE_2FA_INVALIDE")
        SecuriteCompte.consommer(jeton)
        return user, jeton

    # ── Enrôlement 2FA ───────────────────────────────────────────────────────

    @staticmethod
    def preparer_totp(user: Utilisateur, nom_cabinet: Optional[str] = None) -> Dict[str, str]:
        """Secret TOTP en attente, rendu UNE fois. Un nouveau QR invalide le précédent."""
        from urllib.parse import quote

        from src.modules.platform.security import generer_secret_totp

        secret = generer_secret_totp()
        user.secret_2fa_en_attente = encrypt_secret(secret)
        emetteur = quote(f"SysDent Pro{f' - {nom_cabinet}' if nom_cabinet else ''}")
        return {
            "secret": secret,
            "uri": (
                f"otpauth://totp/{emetteur}:{quote(user.email)}?secret={secret}&issuer={emetteur}"
                f"&digits={settings.PLATFORM_2FA_TOTP_DIGITS}&period={settings.PLATFORM_2FA_TOTP_INTERVAL}"
            ),
        }

    @staticmethod
    async def activer_2fa(
        db: AsyncSession, user: Utilisateur, methode: str, code: str, contexte: str
    ) -> List[str]:
        """
        Active la 2FA par l'application (code sur le secret EN ATTENTE) ou par
        e-mail (code reçu pour ce contexte). Rend les 10 codes de secours, une fois.
        """
        from src.modules.platform.security import (
            generer_codes_secours,
            hacher_codes_secours,
            verifier_code_totp,
        )

        if user.deux_facteurs:
            raise InvalidStateException("La double authentification est déjà active.", code="DEUX_FACTEURS_DEJA_ACTIF")
        if methode == "totp":
            attente = decrypt_secret(user.secret_2fa_en_attente) if user.secret_2fa_en_attente else None
            if attente is None:
                raise InvalidStateException("Affichez d'abord le QR code.", code="SECRET_2FA_ABSENT")
            if not verifier_code_totp(attente, code):
                raise AuthenticationException(CODE_INVALIDE, code="CODE_2FA_INVALIDE")
            user.secret_2fa = user.secret_2fa_en_attente
        elif methode == "email":
            if not await SecuriteCompte._code_email_valide(db, user, contexte, code):
                raise AuthenticationException(CODE_INVALIDE, code="CODE_2FA_INVALIDE")
        else:
            raise BusinessRuleViolationException("Méthode inconnue.", code="METHODE_2FA_INCONNUE")

        user.secret_2fa_en_attente = None
        user.deux_facteurs = True
        user.deux_facteurs_confirme_at = _maintenant()
        codes = generer_codes_secours()
        user.codes_secours_haches = hacher_codes_secours(codes)
        return codes
