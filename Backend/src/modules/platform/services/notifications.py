"""
Envoi de messages — abstrait derrière une interface (Phase F.5).

Plutôt que d'appeler `smtplib` en dur depuis les services, tout passe par
l'interface `NotificationSender`. Au démarrage, `configurer_sender_depuis_settings`
branche `SmtpNotificationSender` si SMTP_USER et SMTP_PASSWORD sont renseignés.

Sans identifiants SMTP, l'implémentation active est `ConsoleNotificationSender` : elle
écrit le message dans les logs structurés. Le corps du message peut contenir un
jeton de vérification — c'est précisément ce qu'un journal d'application ne
devrait PAS contenir (règle transverse : « aucune donnée de santé ni secret dans
les logs »). Le corps n'est donc PAS journalisé : seuls le destinataire, le
sujet et le type de message le sont. Le corps complet est écrit sur la sortie
standard du serveur, qui n'est pas un journal de données.
"""

import abc
import asyncio
import smtplib
import ssl
import sys
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Message:
    destinataire: str
    sujet: str
    corps_texte: str
    corps_html: Optional[str] = None
    variables: Dict[str, str] = field(default_factory=dict)


class NotificationSender(abc.ABC):
    """
    Contrat d'envoi. Implémenter cette classe suffit à brancher un fournisseur
    (SendGrid, SES, Mailgun, SMTP interne) sans toucher au code appelant.
    """

    @abc.abstractmethod
    async def envoyer(self, message: Message) -> bool: ...

    @abc.abstractmethod
    def nom(self) -> str: ...


class ConsoleNotificationSender(NotificationSender):
    """
    Implémentation de développement : le message part sur la sortie standard.

    Choix assumé — le corps n'est PAS écrit dans les logs structurés parce qu'il
    porte le jeton de vérification d'e-mail. Ce serait un secret en clair dans
    une trace d'observabilité, exactement ce que la mission interdit.
    """

    def __init__(self, afficher_corps: bool = True) -> None:
        self.afficher_corps = afficher_corps
        self.historique: List[Message] = []

    async def envoyer(self, message: Message) -> bool:
        self.historique.append(message)
        logger.info(
            "email_envoye",
            transport=self.nom(),
            destinataire=message.destinataire,
            sujet=message.sujet,
        )
        if self.afficher_corps:
            print(
                "\n"
                + "=" * 72
                + f"\n  E-MAIL [{self.nom()}] -> {message.destinataire}"
                + f"\n  Objet : {message.sujet}\n"
                + "-" * 72
                + f"\n{message.corps_texte}\n"
                + "=" * 72,
                file=sys.stdout,
            )
        return True

    def nom(self) -> str:
        return "console"


class FichierNotificationSender(NotificationSender):
    """
    Implémentation de test : écrit les messages dans une liste en mémoire.

    Utilisée par la suite de tests pour vérifier « un e-mail de vérification a
    bien été envoyé à cette adresse » sans dépendre de la sortie standard.
    """

    def __init__(self) -> None:
        self.messages: List[Message] = []

    async def envoyer(self, message: Message) -> bool:
        self.messages.append(message)
        return True

    def nom(self) -> str:
        return "memoire"

    def dernier_jeton(self, usage: str) -> Optional[str]:
        """Dernier jeton émis pour un usage donné (utilisé par les tests)."""
        for message in reversed(self.messages):
            jeton = message.variables.get(usage)
            if jeton:
                return jeton
        return None


class SmtpNotificationSender(NotificationSender):
    """
    Envoi réel par SMTP (Gmail ou tout serveur SMTP authentifié).

    Le port 465 ouvre une connexion TLS directe ; tout autre port passe par
    STARTTLS, et l'envoi échoue si le serveur ne le propose pas : un mot de
    passe d'application ne doit jamais circuler en clair. `smtplib` étant
    bloquant, l'envoi tourne dans un thread pour ne pas figer la boucle asyncio.

    Comme pour l'envoi console, le corps n'est jamais journalisé. Une erreur
    n'est journalisée que par son type : le message d'une exception SMTP peut
    reprendre la réponse du serveur, voire l'identifiant.
    """

    def __init__(
        self,
        hote: str,
        port: int,
        utilisateur: str,
        mot_de_passe: str,
        expediteur: str,
        nom_expediteur: str = "",
        delai_secondes: int = 15,
    ) -> None:
        self.hote = hote
        self.port = port
        self.utilisateur = utilisateur
        self._mot_de_passe = mot_de_passe
        self.expediteur = expediteur
        self.nom_expediteur = nom_expediteur
        self.delai_secondes = delai_secondes

    def _construire(self, message: Message) -> EmailMessage:
        courriel = EmailMessage()
        courriel["Subject"] = message.sujet
        courriel["From"] = formataddr((self.nom_expediteur, self.expediteur))
        courriel["To"] = message.destinataire
        courriel.set_content(message.corps_texte)
        if message.corps_html:
            courriel.add_alternative(message.corps_html, subtype="html")
        return courriel

    def _envoyer_bloquant(self, courriel: EmailMessage) -> None:
        contexte = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(
                self.hote, self.port, timeout=self.delai_secondes, context=contexte
            ) as serveur:
                serveur.login(self.utilisateur, self._mot_de_passe)
                serveur.send_message(courriel)
            return
        with smtplib.SMTP(self.hote, self.port, timeout=self.delai_secondes) as serveur:
            serveur.starttls(context=contexte)
            serveur.login(self.utilisateur, self._mot_de_passe)
            serveur.send_message(courriel)

    async def envoyer(self, message: Message) -> bool:
        try:
            await asyncio.to_thread(self._envoyer_bloquant, self._construire(message))
        except Exception as erreur:
            logger.error(
                "email_echec",
                transport=self.nom(),
                destinataire=message.destinataire,
                sujet=message.sujet,
                erreur=type(erreur).__name__,
            )
            return False
        logger.info(
            "email_envoye",
            transport=self.nom(),
            destinataire=message.destinataire,
            sujet=message.sujet,
        )
        return True

    def nom(self) -> str:
        return "smtp"


class CopieConsoleNotificationSender(NotificationSender):
    """
    Développement uniquement : envoie par le transport principal, puis affiche
    le message sur la sortie standard, même si l'envoi a échoué. Le code reste
    lisible sans ouvrir la boîte mail. Jamais branché en production (cf.
    `configurer_sender_depuis_settings`).
    """

    def __init__(self, principal: NotificationSender) -> None:
        self.principal = principal
        self.console = ConsoleNotificationSender()

    async def envoyer(self, message: Message) -> bool:
        envoye = await self.principal.envoyer(message)
        # La console ne journalise que destinataire et sujet, jamais le corps.
        await self.console.envoyer(message)
        return envoye

    def nom(self) -> str:
        return f"{self.principal.nom()}+console"


#: Expéditeur actif : console par défaut, SMTP si `configurer_sender_depuis_settings`
#: trouve des identifiants au démarrage.
_sender: NotificationSender = ConsoleNotificationSender()


def definir_sender(sender: NotificationSender) -> None:
    global _sender
    _sender = sender


def obtenir_sender() -> NotificationSender:
    return _sender


def configurer_sender_depuis_settings(settings) -> NotificationSender:
    """
    Choisit l'expéditeur au démarrage : SMTP si l'identifiant et le mot de passe
    sont renseignés, console sinon. Le mot de passe n'est jamais journalisé.

    Avec EMAIL_COPIE_CONSOLE, chaque e-mail SMTP est aussi affiché sur la
    console, mais seulement hors production : en production, la sortie
    standard finit dans les journaux de l'hébergeur, et les codes avec.
    """
    if settings.SMTP_USER.strip() and settings.SMTP_PASSWORD.strip():
        sender: NotificationSender = SmtpNotificationSender(
            hote=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            utilisateur=settings.SMTP_USER.strip(),
            # Gmail affiche le mot de passe d'application par groupes de quatre
            # séparés par des espaces : on les retire pour un copier-coller tel quel.
            mot_de_passe=settings.SMTP_PASSWORD.replace(" ", ""),
            expediteur=(settings.SMTP_FROM or settings.SMTP_USER).strip(),
            nom_expediteur=settings.SMTP_FROM_NAME,
            delai_secondes=settings.SMTP_TIMEOUT_SECONDS,
        )
        if settings.EMAIL_COPIE_CONSOLE:
            if settings.APP_ENV == "production":
                logger.warning("email_copie_console_ignoree", raison="production")
            else:
                sender = CopieConsoleNotificationSender(sender)
    else:
        sender = ConsoleNotificationSender()
    definir_sender(sender)
    logger.info("email_transport_configure", transport=sender.nom())
    return sender


class EmailService:
    """Messages transactionnels de la plateforme (facade au-dessus du sender)."""

    @staticmethod
    async def verification_email(destinataire: str, jeton: str, nom_cabinet: str) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet="Confirmez votre adresse e-mail — SysDent Pro",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"Vous avez demandé la création du cabinet « {nom_cabinet} ».\n"
                    f"Confirmez votre adresse en saisissant ce code dans l'application :\n\n"
                    f"    {jeton}\n\n"
                    f"Le code est valable 60 minutes et ne sert qu'une seule fois.\n"
                    f"Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n"
                ),
                variables={"jeton_verification": jeton},
            )
        )

    @staticmethod
    async def code_connexion_2fa(destinataire: str, code: str, minutes: int) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet="Votre code de connexion — SysDent Pro Plateforme",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"Votre code de vérification pour la console SysDent :\n\n"
                    f"    {code}\n\n"
                    f"Il est valable {minutes} minutes et ne sert qu'une seule fois.\n"
                    f"Si vous n'êtes pas à l'origine de cette connexion, changez votre "
                    f"mot de passe : quelqu'un le connaît.\n"
                ),
                variables={"code_2fa_email": code},
            )
        )

    @staticmethod
    async def activation_compte_cabinet(
        destinataire: str, prenom: str, lien: str, nom_cabinet: str, heures: int
    ) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet=f"Activez votre compte {nom_cabinet} — SysDent Pro",
                corps_texte=(
                    f"Bonjour {prenom},\n\n"
                    f"Un compte a été créé pour vous sur SysDent Pro ({nom_cabinet}).\n"
                    f"Choisissez votre mot de passe en ouvrant ce lien :\n\n"
                    f"    {lien}\n\n"
                    f"Le lien est valable {heures} heures et ne sert qu'une seule fois.\n"
                    f"Si vous n'attendiez pas ce message, ignorez-le : sans ce lien, le compte reste inutilisable.\n"
                ),
                variables={"lien_activation": lien},
            )
        )

    @staticmethod
    async def code_connexion_cabinet(destinataire: str, code: str, minutes: int) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet="Votre code de connexion — SysDent Pro",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"Votre code de vérification :\n\n"
                    f"    {code}\n\n"
                    f"Il est valable {minutes} minutes et ne sert qu'une seule fois.\n"
                    f"Si vous n'êtes pas à l'origine de cette connexion, changez votre mot de passe.\n"
                ),
                variables={"code_connexion": code},
            )
        )

    @staticmethod
    async def rendez_vous_contact(
        destinataire: str,
        evenement: str,
        titre: str,
        type_libelle: str,
        quand: str,
        duree: int,
        lieu: Optional[str],
        lien_visio: Optional[str],
        avec: Optional[str],
        motif_annulation: Optional[str] = None,
    ) -> bool:
        entetes = {
            "cree": ("Rendez-vous confirmé", "Votre rendez-vous avec l'équipe SysDent Pro est planifié :"),
            "modifie": ("Rendez-vous modifié", "Votre rendez-vous avec l'équipe SysDent Pro a changé :"),
            "annule": ("Rendez-vous annulé", "Votre rendez-vous avec l'équipe SysDent Pro est annulé :"),
        }
        sujet, intro = entetes.get(evenement, entetes["cree"])
        lignes = [f"    {type_libelle} — {titre}", f"    Le {quand}, durée {duree} minutes"]
        if avec:
            lignes.append(f"    Pour : {avec}")
        if lieu:
            lignes.append(f"    Lieu : {lieu}")
        if lien_visio:
            lignes.append(f"    Visioconférence : {lien_visio}")
        if evenement == "annule" and motif_annulation:
            lignes.append(f"    Motif : {motif_annulation}")
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet=f"{sujet} — SysDent Pro",
                corps_texte="Bonjour,\n\n" + intro + "\n\n" + "\n".join(lignes) + "\n\nL'équipe SysDent Pro\n",
                variables={"evenement_rdv": evenement},
            )
        )

    @staticmethod
    async def invitation_admin(destinataire: str, jeton: str, nom_cabinet: str) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet=f"Vous êtes administrateur de « {nom_cabinet} » — SysDent Pro",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"Vous avez été désigné administrateur du cabinet « {nom_cabinet} ».\n"
                    f"Définissez votre mot de passe avec ce lien :\n\n"
                    f"    {jeton}\n\n"
                    f"Le lien est à usage unique et expire rapidement.\n"
                ),
                variables={"jeton_invitation": jeton},
            )
        )

    @staticmethod
    async def notification_acces_support(destinataire: str, agent: str, motif: str, ticket: str) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet="Un accès de support a été ouvert sur votre espace",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"L'équipe SysDent a ouvert un accès de LECTURE sur votre espace "
                    f"pour traiter le ticket {ticket or '(sans référence)'}.\n\n"
                    f"    Intervenant : {agent}\n"
                    f"    Motif      : {motif}\n\n"
                    f"Aucune donnée de vos patients n'est accessible en écriture.\n"
                ),
                variables={"agent": agent, "motif": motif},
            )
        )

    @staticmethod
    async def expiration_essai(destinataire: str, nom_cabinet: str, jours_restants: int) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet="Votre période d'essai se termine",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"La période d'essai de « {nom_cabinet} » se termine.\n"
                    f"Il vous reste {jours_restants} jour(s) avant la suspension de l'accès.\n"
                ),
                variables={"jours_restants": str(jours_restants)},
            )
        )

    @staticmethod
    async def invitation_plateforme(destinataire: str, jeton: str) -> bool:
        return await _sender.envoyer(
            Message(
                destinataire=destinataire,
                sujet="Votre accès à la console SysDent",
                corps_texte=(
                    f"Bonjour,\n\n"
                    f"Un accès à la console d'administration SysDent a été créé.\n"
                    f"Terminez votre inscription et activez la double authentification :\n\n"
                    f"    {jeton}\n\n"
                    f"L'activation du second facteur est obligatoire pour la console.\n"
                ),
                variables={"jeton_invitation": jeton},
            )
        )