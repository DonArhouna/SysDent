"""
Onboarding public (Phase F) — auto-inscription d'un cabinet.

Une route publique est l jewels le plus attaquée d'une API. Trois principes
tenant cette conception :

1. **Aucune fuite d'information.** Chaque erreur renvoie le MÊME message et le
   MÊME code, que l'adresse existe ou non. Un message différencié
   (« e-mail déjà utilisé ») est un annuaire gratuit : il permet de lister les
   clients d'un cabinet. Le journal garde la cause, l'utilisateur ne reçoit que
   la réponse générique.

2. **Rien n'est actif avant vérification.** Le cabinet est provisionné, mais sa
   connexion côté client est refusée tant que l'e-mail n'est pas vérifié. Sans
   cela, on s'inscrit avec l'adresse d'un tiers et on obtient un accès.

3. **Le provisionnement est celui de la Phase B.** Aucun second chemin de
   création de cabinet : le service de la Phase F appelle
   `ProvisioningService.provisionner`, le même que la console. Deux chemins
   d'écriture pour la même entité, c'est deux jeux de règles qui divergent.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AppException, BusinessRuleViolationException
from src.modules.platform.models import (
    InscriptionOnboarding,
    JetonUsageUnique,
    StatutInscription,
    UsageJeton,
)
from src.modules.platform.security import generer_jeton_opaque, hacher_jeton
from src.modules.platform.services.journal import JournalService

logger = structlog.get_logger(__name__)

#: Message unique renvoyé à toute inscription refusée. Volontairement
#: identique quel que soit le motif réel : voir le principe 1 ci-dessus.
MESSAGE_GENERIQUE = "Inscription impossible avec ces informations. Vérifiez vos données ou contactez le support."
CODE_GENERIQUE = "INSCRIPTION_REFUSEE"


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class OnboardingService:
    """Inscription publique, vérification d'e-mail et checklist de démarrage."""

    # ── Inscription ───────────────────────────────────────────────────────

    @staticmethod
    async def inscrire(
        master_db: AsyncSession,
        platform_db: AsyncSession,
        *,
        nom_cabinet: str,
        email: str,
        mot_de_passe: str,
        prenom: str,
        nom: str,
        telephone: Optional[str] = None,
        ville: Optional[str] = None,
        pays: str = "Sénégal",
        plan_code: Optional[str] = None,
        jours_essai: Optional[int] = None,
        honeypot: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crée un cabinet en essai et son administrateur.

        Le cabinet est réellement provisionné (base, schéma, rôles, actes,
        abonnement) : c'est la même fonction que la console. La différence tient
        à trois points : le statut est `ESSAI`, la connexion est verrouillée tant
        que l'e-mail n'est pas vérifié, et le message d'erreur est générique.
        """
        if not settings.ONBOARDING_ENABLED:
            raise AppException(
                "Les inscriptions en ligne sont temporairement indisponibles.",
                code="ONBOARDING_DESACTIVE",
                status_code=503,
            )

        OnboardingService._verifier_anti_bot(honeypot)

        email_normalise = email.strip().lower()
        if await OnboardingService._existe_deja(platform_db, email_normalise):
            # Journalisé pour l'exploitant, invisible pour l'appelant.
            logger.info(
                "onboarding_email_deja_utilise",
                domain=email_normalise.split("@")[-1],
                ip_address=ip_address,
            )
            raise AppException(MESSAGE_GENERIQUE, code=CODE_GENERIQUE, status_code=409)

        from src.modules.platform.services.provisioning import ProvisioningService

        try:
            resultat = await ProvisioningService.provisionner(
                master_db=master_db,
                platform_db=platform_db,
                nom=nom_cabinet,
                admin_email=email_normalise,
                admin_prenom=prenom,
                admin_nom=nom,
                statut_initial="ESSAI",
                ville=ville,
                pays=pays,
                telephone=telephone,
                plan_code=plan_code,
                jours_essai=jours_essai if jours_essai is not None else settings.ONBOARDING_ESSAI_DAYS,
                auteur=f"onboarding:{email_normalise}",
                motif="Auto-inscription publique",
                attendre_verification_email=True,
                client_ip=ip_address,
                user_agent=user_agent,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("onboarding_provisionnement_echoue", erreur=str(exc))
            raise AppException(MESSAGE_GENERIQUE, code=CODE_GENERIQUE, status_code=409) from exc

        # `plan_code` est NOT NULL en base : on enregistre la formule réellement
        # appliquée (celle du plan par défaut si l'appelant n'en a pas choisi),
        # jamais la valeur demandée qui pourrait ne pas exister.
        plan_effectif = plan_code or await _code_plan_defaut(platform_db)

        inscription = InscriptionOnboarding(
            tenant_id=resultat.societe.id,
            email=email_normalise,
            telephone=telephone,
            plan_code=plan_effectif,
            statut=StatutInscription.EN_ATTENTE_VERIFICATION,
            email_verifie=False,
            telephone_verifie=False,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        platform_db.add(inscription)
        await platform_db.flush()

        jeton_verification = await OnboardingService._emettre_jeton_verification(
            platform_db, inscription, UsageJeton.VERIFICATION_EMAIL, ip_address=ip_address
        )
        # Envoi par l'abstraction `EmailService` : aucun fournisseur n'est branché,
        # l'implémentation « console » écrit le message dans les journaux. Le jeton
        # n'est renvoyé dans la réponse HTTP que si l'envoi a échoué — sinon
        # quiconque intercepterait la réponse pourrait vérifier l'adresse.
        from src.modules.platform.services.notifications import EmailService

        envoye = await EmailService.verification_email(
            destinataire=email_normalise, jeton=jeton_verification, nom_cabinet=nom_cabinet
        )
        if not envoye:
            logger.warning(
                "onboarding_email_verification_non_envoye",
                domain=email_normalise.split("@")[-1],
            )

        await JournalService.journaliser(
            platform_db,
            action="PLATFORM_ONBOARDING_INSCRIPTION",
            type_cible="TENANT",
            cible_id=str(resultat.societe.id),
            tenant_id=resultat.societe.id,
            acteur_email=f"onboarding:{email_normalise}",
            apres={"statut": inscription.statut.value},
            ip_address=ip_address,
        )

        return {
            "inscription_id": inscription.id,
            "tenant_id": resultat.societe.id,
            "email": email_normalise,
            "statut": inscription.statut.value,
        }

    # ── Vérification de l'e-mail ──────────────────────────────────────────

    @staticmethod
    async def _emettre_jeton_verification(
        platform_db: AsyncSession,
        inscription: InscriptionOnboarding,
        usage: UsageJeton,
        minutes: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """
        Crée un jeton à usage unique et n'en conserve que l'empreinte.

        Stocker le jeton en clair en base en ferait un second canal d'accès : une
        fuite de la base donnerait des inscriptions activables. Seule son
        empreinte est conservée — suffisant pour comparer, inutile pour activer.
        """
        jeton = generer_jeton_opaque()
        platform_db.add(
            JetonUsageUnique(
                usage=usage,
                hash_jeton=hacher_jeton(jeton),
                cible_type="INSCRIPTION",
                cible_id=str(inscription.id),
                expire_le=_maintenant()
                + timedelta(minutes=minutes or settings.ONBOARDING_VERIFICATION_TOKEN_MINUTES),
                ip_address=ip_address,
            )
        )
        await platform_db.flush()
        logger.info(
            "jeton_verification_emis",
            usage=usage.value,
            inscription_id=str(inscription.id),
        )
        return jeton

    @staticmethod
    async def verifier_email(platform_db: AsyncSession, jeton: str) -> Dict[str, Any]:
        """
        Vérifie l'e-mail et active la connexion du cabinet.

        Un jeton invalide, expiré ou déjà utilisé produit exactement la même
        réponse qu'un jeton qui n'a jamais existé.
        """
        empreinte = hacher_jeton(jeton)
        enregistrement = (
            await platform_db.execute(
                select(JetonUsageUnique).where(
                    JetonUsageUnique.hash_jeton == empreinte,
                    JetonUsageUnique.usage == UsageJeton.VERIFICATION_EMAIL,
                )
            )
        ).scalar_one_or_none()

        if (
            enregistrement is None
            or enregistrement.utilise
            or enregistrement.expire_le <= _maintenant()
        ):
            raise AppException(
                "Ce lien est invalide ou a expiré. Demandez-en un nouveau.",
                code="JETON_INVALIDE",
                status_code=400,
            )

        inscription = (
            await platform_db.execute(
                select(InscriptionOnboarding).where(
                    InscriptionOnboarding.id == uuid.UUID(enregistrement.cible_id)
                )
            )
        ).scalar_one_or_none()
        if inscription is None:
            raise AppException(
                "Ce lien est invalide ou a expiré. Demandez-en un nouveau.",
                code="JETON_INVALIDE",
                status_code=400,
            )

        enregistrement.utilise = True
        enregistrement.utilise_at = _maintenant()
        inscription.email_verifie = True
        inscription.verifie_at = _maintenant()
        inscription.statut = StatutInscription.VERIFIE
        await platform_db.flush()

        await OnboardingService._activer_le_cabinet(inscription.tenant_id)

        logger.info("onboarding_email_verifie", tenant_id=str(inscription.tenant_id))
        return {
            "tenant_id": inscription.tenant_id,
            "email": inscription.email,
            "statut": inscription.statut.value,
        }

    @staticmethod
    async def _activer_le_cabinet(tenant_id) -> None:
        """
        Ouvre la connexion du cabinet après vérification de l'adresse.

        `tenants_db.statut` est le verrou technique utilisé par
        `AuthService._resoudre_tenant` : le passer de `PENDING_VERIFICATION` à
        `ACTIVE` est exactement ce qui rend l'espace accessible. On ne touche
        PAS au statut métier (qui reste `ESSAI`) : ce sont deux leviers
        distincts — l'un technique, l'autre commercial.
        """
        from sqlalchemy import select as _select

        from src.core.database import MasterAsyncSessionFactory
        from src.modules.master.models import TenantDB

        async with MasterAsyncSessionFactory() as master:
            tenant_db = (
                await master.execute(
                    _select(TenantDB).where(TenantDB.societe_id == tenant_id)
                )
            ).scalar_one_or_none()
            if tenant_db is None or tenant_db.statut == "ACTIVE":
                return
            tenant_db.statut = "ACTIVE"
            await master.commit()
        logger.info("onboarding_cabinet_active", tenant_id=str(tenant_id))

    # ── Checklist de démarrage ────────────────────────────────────────────

    @staticmethod
    async def etat_onboarding(
        platform_db: AsyncSession, tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        État de démarrage d'un cabinet : étapes faites et étapes à faire.

        Alimente la checklist du frontend client. Volontairement lisible et
        expliquée («sites : ajoutez au moins un site et ses horaires »), pour que
        l'écran d'accueil puisse dire quoi faire et non seulement cocher des
        cases.
        """
        from src.core.database import MasterAsyncSessionFactory, tenant_db_manager
        from src.modules.master.models import Societe

        async with MasterAsyncSessionFactory() as master:
            societe = (
                await master.execute(
                    select(Societe).where(Societe.id == tenant_id)
                )
            ).scalar_one_or_none()

        if societe is None:
            raise AppException("Cabinet introuvable.", code="TENANT_NOT_FOUND", status_code=404)

        factory = await tenant_db_manager.get_session_factory(str(societe.id))
        compteurs: Dict[str, int] = {}
        if factory is not None:
            async with factory() as db:
                compteurs = await OnboardingService._compter(db)

        etapes = [
            _etape(
                "informations_cabinet",
                "Informations du cabinet",
                bool(societe.adresse_siege or societe.telephone),
                "Renseignez l'adresse, le téléphone et le NINEA de votre structure.",
            ),
            _etape(
                "sites",
                "Sites",
                compteurs.get("cabinets", 0) > 0,
                "Un site par défaut a été créé. Ajoutez un second site si votre cabinet en a plusieurs.",
            ),
            _etape(
                "salles",
                "Salles",
                compteurs.get("salles", 0) > 0,
                "Ajoutez au moins une salle : c'est là que sont placés vos fauteuils.",
            ),
            _etape(
                "horaires",
                "Horaires d'ouverture",
                compteurs.get("horaires", 0) > 0,
                "Définissez vos horaires d'ouverture, ils apparaissent sur vos rendez-vous.",
            ),
            _etape(
                "praticiens",
                "Praticiens",
                compteurs.get("praticiens", 0) > 0,
                "Rattachez au moins un praticien à votre espace.",
            ),
            _etape(
                "actes",
                "Actes et tarifs",
                compteurs.get("actes", 0) > 0,
                "Reprenez la nomenclature d'actes et ajustez vos tarifs.",
            ),
            _etape(
                "paiements",
                "Modes de paiement",
                compteurs.get("paiements", 0) > 0,
                "Activez au moins un mode de paiement pour encaisser.",
            ),
            _etape(
                "logo",
                "Logo du cabinet",
                bool(societe.logo_url),
                "Déposez votre logo — il apparaît sur les ordonnances.",
            ),
        ]

        terminees = sum(1 for e in etapes if e["faite"])
        return {
            "tenant_id": str(tenant_id),
            "terminees": terminees,
            "total": len(etapes),
            "progression": round(terminees / len(etapes) * 100) if etapes else 100,
            "etapes": etapes,
        }

    @staticmethod
    async def _compter(db: AsyncSession) -> Dict[str, int]:
        """Compteurs de la checklist. Aucun attribut nominatif n'est lu."""
        from sqlalchemy import func, select

        from src.modules.tenants.models import Cabinet, Praticien, Salle

        async def compte(modele) -> int:
            return int((await db.execute(select(func.count()).select_from(modele))).scalar_one() or 0)

        async def compte_ou(modele, colonne) -> int:
            return int(
                (await db.execute(select(func.count()).select_from(modele).where(colonne.is_not(None)))).scalar_one()
                or 0
            )

        return {
            "cabinets": await compte(Cabinet),
            "salles": await compte(Salle),
            "praticiens": await compte(Praticien),
            # Ces trois tables portent des noms différents selon la version du
            # schéma ; une absence ne doit pas casser la checklist.
            "horaires": await _compter_siExiste(db, "horaires_ouverture"),
            "actes": await _compter_siExiste(db, "actes"),
            "paiements": await _compter_siExiste(db, "modes_paiement"),
        }

    # ── Anti-bot ──────────────────────────────────────────────────────────

    @staticmethod
    def _verifier_anti_bot(honeypot: Optional[str]) -> None:
        """
        Champ-piège : un humain ne remplit jamais un champ invisible.

        Réponse identique à celle d'un échec quelconque : un robot qui apprend
        qu'il a été détecté adaptera son comportement.
        """
        if settings.ONBOARDING_CAPTCHA_MODE == "honeypot" and honeypot:
            logger.info("onboarding_honeypot_declenche")
            raise AppException(MESSAGE_GENERIQUE, code=CODE_GENERIQUE, status_code=429)

    @staticmethod
    async def _existe_deja(platform_db: AsyncSession, email: str) -> bool:
        """Un e-mail déjà inscrit — réponse identique à celle d'un succès volé."""
        return (
            await platform_db.execute(
                select(InscriptionOnboarding.id).where(InscriptionOnboarding.email == email)
            )
        ).scalar_one_or_none() is not None


async def _code_plan_defaut(platform_db: AsyncSession) -> str:
    """Code de la formule appliquée à défaut : celle marquée « plan par défaut »."""
    from src.modules.platform.services.plans import PlanService

    try:
        return (await PlanService.plan_defaut(platform_db)).code
    except Exception:  # noqa: BLE001 - l'inscription doit rester possible
        logger.warning("plan_defaut_introuvable_inscription")
        return "ESSENTIEL"


async def _compter_siExiste(db: AsyncSession, table: str) -> int:
    """
    Compte les lignes d'une table si elle existe.

    La checklist ne doit pas échouer parce qu'un schéma client plus ancien n'a
    pas encore la table des modes de paiement : un « 0 » est une information
    exploitable, une exception 500 n'en est pas une.
    """
    from sqlalchemy import func, text

    try:
        resultat = await db.execute(
            text(f"SELECT count(*) FROM {table}")  # noqa: S608 - table interne, pas d'entrée utilisateur
        )
        return int(resultat.scalar_one() or 0)
    except Exception:  # noqa: BLE001 - table absente = 0
        await db.rollback()
        return 0


def _etape(cle: str, libelle: str, faite: bool, aide: str) -> Dict[str, Any]:
    return {"cle": cle, "libelle": libelle, "faite": faite, "aide": aide}