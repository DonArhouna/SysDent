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
from typing import Any, Dict, List, Optional

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
# L'enrolement ne demande qu'un scan puis une confirmation : dix minutes
# suffisent largement, et un jeton plus durable serait une surface d'attaque
# inutile.
DUREE_ENROLEMENT_2FA_MINUTES = 10
# Code e-mail : aussi court que le defi qu'il accompagne.
DUREE_CODE_EMAIL_MINUTES = 5


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def masquer_email(email: str) -> str:
    """`famillegueye50@gmail.com` -> `fa************@gmail.com` : dire ou chercher, sans tout reveler."""
    local, _, domaine = email.partition("@")
    visible = local[:2]
    return f"{visible}{'*' * max(len(local) - len(visible), 1)}@{domaine}"


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
        #
        # **La decision porte sur l'ETAT ACTIF, pas sur l'existence d'un secret.**
        # Tester « un secret existe ? » prenait un secret PREPARE — que personne
        # n'a jamais scanne — pour un compte configure : le login emettait un
        # defi, et le code saisi sur ce defi activait la 2FA sans emettre de
        # codes de secours. Deux voies d'activation, une seule emettant les
        # codes : telephone perdu, plus aucune voie de recours.
        #
        # Un secret en attente ne change donc rien au chemin : tant que
        # `deux_facteurs_actif` est faux, le compte recoit un jeton d'enrolement
        # (preparation + activation), jamais un defi.
        if not user.deux_facteurs_actif:
            # Premier acces, ou compte dont l'operateur a reinitialise la 2FA.
            # **Refuser ici rendait le compte definitivement inaccessible** :
            # la seule voie d'activation exigeait une session, et la seule voie
            # d'obtenir une session exigeait la 2FA. Impasse sur une plateforme
            # a un seul Super Admin.
            #
            # On emet donc un jeton d'enrolement : opaque, usage unique, et surtout
            # **borne** a la preparation et l'activation.
            jeton_enrolement = await PlatformAuthService._emettre_jeton_enrolement(
                db, user, client_ip=client_ip
            )
            await JournalService.journaliser(
                db,
                action="PLATFORM_2FA_ENROLEMENT",
                type_cible="AUTH",
                acteur_email=user.email,
                acteur_id=user.id,
                apres={"raison": "second_facteur_a_activer"},
                ip_address=client_ip,
                user_agent=user_agent,
            )
            await db.commit()
            return {
                "deux_facteurs_requis": True,
                "activation_requise": True,
                "jeton_enrolement": jeton_enrolement,
                "expiration_secondes": DUREE_ENROLEMENT_2FA_MINUTES * 60,
                "methodes": ["totp", "email"],
            }

        # Compte actif : le defi TOTP (ou un code de secours) ouvre la session.
        jeton_challenge = await PlatformAuthService._emettre_challenge(
            db, user, client_ip=client_ip, user_agent=user_agent
        )

        await JournalService.journaliser(
            db,
            action="PLATFORM_2FA_DEFI",
            type_cible="AUTH",
            acteur_email=user.email,
            acteur_id=user.id,
            apres={"deux_facteurs_requis": True},
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.commit()

        return {
            "deux_facteurs_requis": True,
            "activation_requise": False,
            "jeton_challenge": jeton_challenge,
            "expiration_secondes": DUREE_CHALLENGE_2FA_MINUTES * 60,
            "methodes": PlatformAuthService.methodes_disponibles(user),
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

        # **Le defi n'ouvre qu'un compte DEJA ENROLE.** Un compte dont la 2FA
        # n'est pas active ne doit recevoir qu'un jeton d'enrolement au login ;
        # si un defi lui parvient quand meme (jeton forge, ancien compte avec un
        # secret actif mais `deux_facteurs_actif` faux), le chemin refuse ici,
        # avec un message identique a un code invalide : dire « il faut s'enroller »
        # serait un oracle d'enumeration.
        #
        # Surtout, ce chemin **n'active jamais la 2FA** : c'etait le defaut — le
        # code saisi activait le second facteur sans emettre de codes de secours.
        if not user.deux_facteurs_actif:
            raise AuthenticationException("Code de vérification invalide.", code="CODE_2FA_INVALIDE")

        secret = valider_secret_2fa(user.secret_2fa_chiffre)
        # Un code de secours remplace le code TOTP quand le telephone n'est pas
        # sous la main. Cette tentative manquait ici : elle n'existait qu'a
        # l'ACTIVATION, donc un compte dont le telephone est perdu ne pouvait plus
        # se reconnecter du tout - le mecanisme des codes de secours etait
        # produit, stocke, et mort.
        # Usage unique : la consommation est un effet de bord, retire de la liste,
        # et le commit qui ouvre la session la rend definitive.
        code_valide = secret is not None and verifier_code_totp(secret, code)
        if not code_valide:
            # Code recu par e-mail : il ne vaut que pour CE defi (HMAC sur son
            # empreinte), donc un code intercepte ne sert pas a une autre connexion.
            code_valide = await PlatformAuthService._consommer_code_email(
                db, user, hash_challenge, code
            )
        if not code_valide:
            code_valide = await PlatformAuthService.consommer_code_de_secours(
                db, user, code
            )
        if not code_valide:
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
    async def consommer_code_de_secours(
        db: AsyncSession, user: UtilisateurPlateforme, code: str
    ) -> bool:
        """
        Consomme un code de secours : `True` s'il etait valide.

        **Usage unique.** Le code est retire de la liste qu'il a servi, donc un
        code vole et rejoue ne fonctionne qu'une fois. Si deux codes correspondant simultanement a la
        meme valeur (quasi impossible, collision sur 40 bits), tous les codes de
        cette valeur sont retires : en garder un rendrait le rejeu possible.
        """
        haches = list(user.codes_secours_haches or [])
        if not haches:
            return False

        from src.core.security import verify_password

        restants = []
        trouve = False
        for hash_stocke in haches:
            if not trouve and verify_password(code.strip().upper(), hash_stocke):
                trouve = True
                continue  # consomme
            restants.append(hash_stocke)
        if trouve:
            user.codes_secours_haches = restants
        return trouve

    @staticmethod
    async def preparer_second_facteur(
        db: AsyncSession, user: UtilisateurPlateforme
    ) -> Dict[str, str]:
        """
        Génère un secret TOTP et le renvoie UNE SEULE FOIS, en clair.

        L'opérateur doit le scanner avant de quitter la commande : ni la base ni
        le journal ne le conservent en clair.

        **La préparation n'écrit QUE `secret_2fa_en_attente`.** Jamais
        `secret_2fa_chiffre` — le secret actif — ni `deux_facteurs_actif`. Un
        secret préparé n'a encore été vu de personne : le traiter comme actif
        laissait le login conclure « compte configuré » sur un QR jamais scanné,
        et ouvrait la seconde voie d'activation sans codes de secours. La colonne
        est écrasée à chaque préparation : un second QR invalide le premier, donc
        l'ancien appareil ne peut plus être activé.
        """
        from src.modules.platform.security import uri_otpauth

        secret = generer_secret_totp()
        user.secret_2fa_en_attente = chiffrer_secret_2fa(secret)
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
    ) -> List[str]:
        """
        Active le second facteur et rend les **codes de secours en clair, une fois**.

        **Seule voie d'activation.** Elle vérifie un code TOTP **calculé sur le
        secret en attente** — celui que le compte vient de scanner — puis PROMeut
        ce secret dans `secret_2fa_chiffre` et vide la colonne en attente. Un
        secret préparé ne valait rien tant qu'il n'avait pas franchi cette porte.

        Un code de secours ne peut PAS activer : il ouvre une session sur un
        compte déjà enrôlé, il ne doit pas enrôler. L'accepter ici laisserait une
        seconde voie d'activation, celle-là sans nouveau secret ni nouvelle liste
        de codes.

        Les codes de secours sont stockés hachés et ne ressortent plus jamais :
        si l'opérateur les perd, la régénération (TOTP valide + motif) les
        remplace. C'est le prix de la sécurité, et c'est préférable à une liste
        consultable par quiconque lit la base.
        """
        from src.modules.platform.security import (
            generer_codes_secours,
            hacher_codes_secours,
        )

        if user.deux_facteurs_actif:
            raise InvalidStateException(
                "Le second facteur est déjà actif.", code="DEUX_FACTEURS_DEJA_ACTIF"
            )

        secret_en_attente = valider_secret_2fa(user.secret_2fa_en_attente)
        if secret_en_attente is None:
            raise InvalidStateException(
                "Aucun secret 2FA en attente d'activation.", code="SECRET_2FA_ABSENT"
            )

        # TOTP **calculé sur le secret en attente**, et rien d'autre.
        if not verifier_code_totp(secret_en_attente, code):
            raise AuthenticationException(
                "Code de vérification invalide.", code="CODE_2FA_INVALIDE"
            )

        # Promotion : le secret SCANNÉ devient le secret actif, et la colonne en
        # attente est vidée — un même secret ne sert qu'une seule activation.
        #
        # **On déplace le CHIFFRÉ, pas le clair.** `secret_2fa_chiffre` attend
        # du Fernet : y écrire le texte que `valider_secret_2fa` vient de
        # rendre — le clair — rend la colonne indechiffrable, et tout LOGIN
        # suivant échoue au déchiffrement (`secret_2fa_illisible`) alors que les
        # codes de secours, eux, continuent de passer. La preuve HTTP l'a
        # attrapé : la reconnexion TOTP après activation tombait en 401.
        user.secret_2fa_chiffre = user.secret_2fa_en_attente
        user.secret_2fa_en_attente = None
        user.deux_facteurs_actif = True
        user.deux_facteurs_confirme_at = _maintenant()

        # Dix codes, hachés Argon2, émis UNE fois — ici. `False` au lieu de
        # l'invariant : l'activation vient de garantir la présence des codes.
        codes = generer_codes_secours()
        user.codes_secours_haches = hacher_codes_secours(codes)
        user.codes_secours_a_regenerer = False
        await db.flush()
        return codes

    # ─────────────────────────────────────────────────────────────────────────
    # Second facteur par e-mail (alternative au TOTP)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def methodes_disponibles(user: UtilisateurPlateforme) -> List[str]:
        """
        Methodes proposees a l'ecran du defi.

        Le TOTP n'est propose que si un secret actif existe : un compte enrole par
        e-mail n'a pas d'application configuree, lui proposer serait une impasse.
        """
        methodes = ["totp"] if user.secret_2fa_chiffre else []
        return methodes + ["email"]

    @staticmethod
    async def resoudre_defi(
        db: AsyncSession, jeton_challenge: str
    ) -> tuple[UtilisateurPlateforme, str]:
        """Utilisateur d'un defi encore valable, et l'empreinte du defi."""
        hash_challenge = hacher_jeton(jeton_challenge)
        jeton = (
            await db.execute(
                select(JetonUsageUnique).where(
                    JetonUsageUnique.hash_jeton == hash_challenge,
                    JetonUsageUnique.usage == UsageJeton.CHALLENGE_2FA,
                )
            )
        ).scalar_one_or_none()
        if jeton is None or jeton.utilise or jeton.expire_le <= _maintenant():
            raise InvalidTokenException("Session de connexion expirée, reprenez l'identification.")
        user = await db.get(UtilisateurPlateforme, uuid.UUID(str(jeton.cible_id)))
        if user is None or user.statut != StatutUtilisateurPlateforme.ACTIF:
            raise AuthenticationException("Compte indisponible.", code="COMPTE_NON_ACTIF")
        return user, hash_challenge

    @staticmethod
    async def envoyer_code_email(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        contexte: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Envoie un code a 6 chiffres a l'adresse du compte.

        `contexte` est l'empreinte du defi ou du jeton d'enrolement : le code
        n'est valable que pour lui. Un nouvel envoi **annule** les codes encore
        valables du meme compte - un seul code vit a la fois, le dernier recu.

        Ni le code ni son empreinte ne sont journalises.
        """
        from src.modules.platform.security import generer_code_email, hacher_code_email
        from src.modules.platform.services.notifications import EmailService

        precedents = (
            await db.execute(
                select(JetonUsageUnique).where(
                    JetonUsageUnique.usage == UsageJeton.CODE_2FA_EMAIL,
                    JetonUsageUnique.cible_id == str(user.id),
                    JetonUsageUnique.utilise.is_(False),
                )
            )
        ).scalars().all()
        for precedent in precedents:
            precedent.utilise = True
            precedent.utilise_at = _maintenant()

        code = generer_code_email()
        db.add(
            JetonUsageUnique(
                usage=UsageJeton.CODE_2FA_EMAIL,
                hash_jeton=hacher_code_email(contexte, code),
                cible_type="UTILISATEUR",
                cible_id=str(user.id),
                expire_le=_maintenant() + timedelta(minutes=DUREE_CODE_EMAIL_MINUTES),
                ip_address=client_ip,
            )
        )
        await JournalService.journaliser(
            db,
            action="PLATFORM_2FA_CODE_EMAIL_ENVOYE",
            type_cible="AUTH",
            acteur_email=user.email,
            acteur_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        # Commit AVANT l'envoi : un code recu doit exister en base quand
        # l'utilisateur le saisit, meme si l'envoi met du temps.
        await db.commit()

        envoye = await EmailService.code_connexion_2fa(user.email, code, DUREE_CODE_EMAIL_MINUTES)
        if not envoye:
            raise InvalidStateException(
                "L'e-mail n'a pas pu être envoyé. Réessayez ou utilisez une autre méthode.",
                code="ENVOI_EMAIL_ECHOUE",
            )
        return {
            "destinataire": masquer_email(user.email),
            "expiration_secondes": DUREE_CODE_EMAIL_MINUTES * 60,
        }

    @staticmethod
    async def _consommer_code_email(
        db: AsyncSession, user: UtilisateurPlateforme, contexte: str, code: str
    ) -> bool:
        """Consomme le code e-mail de ce contexte : `True` s'il etait valable."""
        from src.modules.platform.security import hacher_code_email

        code = (code or "").strip()
        if len(code) != 6 or not code.isdigit():
            return False
        ligne = (
            await db.execute(
                select(JetonUsageUnique).where(
                    JetonUsageUnique.hash_jeton == hacher_code_email(contexte, code),
                    JetonUsageUnique.usage == UsageJeton.CODE_2FA_EMAIL,
                    JetonUsageUnique.cible_id == str(user.id),
                    JetonUsageUnique.utilise.is_(False),
                    JetonUsageUnique.expire_le > _maintenant(),
                )
            )
        ).scalar_one_or_none()
        if ligne is None:
            return False
        ligne.utilise = True
        ligne.utilise_at = _maintenant()
        return True

    @staticmethod
    async def activer_second_facteur_par_email(
        db: AsyncSession, user: UtilisateurPlateforme, contexte: str, code: str
    ) -> List[str]:
        """
        Active le second facteur **par e-mail** et rend les codes de secours, une fois.

        Pendant de `activer_second_facteur` pour qui ne veut pas d'application :
        le code recu prouve la possession de la boite mail. Aucun secret TOTP
        n'est promu ; un secret prepare mais jamais scanne est efface, pour qu'il
        ne puisse pas etre active plus tard par une autre voie.
        """
        from src.modules.platform.security import (
            generer_codes_secours,
            hacher_codes_secours,
        )

        if user.deux_facteurs_actif:
            raise InvalidStateException(
                "Le second facteur est déjà actif.", code="DEUX_FACTEURS_DEJA_ACTIF"
            )
        if not await PlatformAuthService._consommer_code_email(db, user, contexte, code):
            raise AuthenticationException(
                "Code de vérification invalide.", code="CODE_2FA_INVALIDE"
            )

        user.secret_2fa_en_attente = None
        user.deux_facteurs_actif = True
        user.deux_facteurs_confirme_at = _maintenant()
        codes = generer_codes_secours()
        user.codes_secours_haches = hacher_codes_secours(codes)
        user.codes_secours_a_regenerer = False
        await db.flush()
        return codes

    @staticmethod
    async def regenerer_codes_secours(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        code: str,
        motif: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> List[str]:
        """
        Remplace les codes de secours d'un compte déjà enrôlé, en clair, une fois.

        **Préconditions strictes** — en cas de doute, refus :

        - la 2FA doit être **active** (on ne régénère pas les codes d'un compte
          qui n'a pas de second facteur : il s'enrôlera et en émerra) ;
        - un **TOTP valide sur le secret actif** doit être présenté : la
          possession du mot de passe et d'une session ne suffit pas ;
        - un **motif** est requis et journalisé — l'absence de motif rend
          l'opération injugeable a posteriori.

        La liste ancienne est **invalidée** en même temps que la nouvelle est
        écrite : aucune fenêtre ne subsiste où deux listes valent. Les dix
        nouveaux codes ne sont renvoyés qu'ici, et le journal ne contient que
        leur nombre — jamais leur valeur.
        """
        from src.modules.platform.security import (
            generer_codes_secours,
            hacher_codes_secours,
        )

        if not user.deux_facteurs_actif:
            raise AuthenticationException(
                "Code de vérification invalide.", code="CODE_2FA_INVALIDE"
            )

        secret = valider_secret_2fa(user.secret_2fa_chiffre)
        if secret is None or not verifier_code_totp(secret, code):
            raise AuthenticationException(
                "Code de vérification invalide.", code="CODE_2FA_INVALIDE"
            )

        codes = generer_codes_secours()
        # L'ancienne liste est remplacée dans la même transaction : invalider
        # d'abord, puis écrire, sans fenêtre intermédiaire.
        user.codes_secours_haches = hacher_codes_secours(codes)
        user.codes_secours_a_regenerer = False
        await JournalService.journaliser(
            db,
            action="PLATFORM_CODES_SECOURS_REGENERES",
            type_cible="AUTH",
            acteur_email=user.email,
            acteur_id=user.id,
            # **Jamais les codes.** Leur nombre suffit à l'audit : leur valeur
            # dans le journal rendrait la journalisation un canal d'accès.
            apres={"codes_secours_emis": len(codes)},
            motif=motif,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await db.flush()
        return codes

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
    async def _emettre_jeton_enrolement(
        db: AsyncSession,
        user: UtilisateurPlateforme,
        client_ip: Optional[str],
    ) -> str:
        """
        Jeton d'enrolement : n'ouvre que la preparation et l'activation.

        Un jeton de session aurait ete bien plus simple, et c'est exactement le
        piege : un jeton large sur un compte sans second facteur est une session
        sans second facteur. La restriction est portee par la colonne `usage`,
        lue par la dependance d'activation.
        """
        jeton = generer_jeton_opaque()
        db.add(
            JetonUsageUnique(
                usage=UsageJeton.ENROLEMENT_2FA,
                hash_jeton=hacher_jeton(jeton),
                cible_type="UTILISATEUR",
                cible_id=str(user.id),
                expire_le=_maintenant() + timedelta(minutes=DUREE_ENROLEMENT_2FA_MINUTES),
                ip_address=client_ip,
            )
        )
        await db.flush()
        return jeton

    async def _marquer_enrolement_consomme(db: AsyncSession, jeton: str) -> None:
        """Marque le jeton d'enrolement consomme : il ne vaut plus rien ensuite."""
        if not jeton:
            return
        from src.modules.platform.security import hacher_jeton

        ligne = (
            await db.execute(
                select(JetonUsageUnique).where(
                    JetonUsageUnique.hash_jeton == hacher_jeton(jeton),
                    JetonUsageUnique.usage == UsageJeton.ENROLEMENT_2FA,
                )
            )
        ).scalar_one_or_none()
        if ligne is not None:
            ligne.utilise = True
            ligne.utilise_at = _maintenant()
            await db.flush()

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
        # La réinitialisation est TOUJOURS une désactivation : le téléphone est
        # perdu, donc l'ancien secret ne doit plus ouvrir rien. La préparation
        # n'écrit plus que le secret en attente — elle ne désactive plus rien —
        # donc la réinitialisation le fait EXPLICITEMENT ici, comme le fait la
        # CLI `reinitialiser-2fa`.
        #
        # `null()` et non `None` : sur une colonne JSONB, `None` sérialise en
        # JSONB `null` — une *valeur* — et la contrainte
        # `ck_codes_secours_exigent_2fa`, qui teste `codes_secours_haches IS
        # NULL`, la rejette. (Même piège, même solution que `admin.py`.)
        from sqlalchemy import null

        user.deux_facteurs_actif = False
        user.deux_facteurs_confirme_at = None
        user.secret_2fa_chiffre = None
        user.codes_secours_haches = null()
        user.codes_secours_a_regenerer = False
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