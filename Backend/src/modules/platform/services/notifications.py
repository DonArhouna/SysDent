"""
Envoi de messages — abstrait derrière une interface (Phase F.5).

Aucun fournisseur d'e-mail n'est branché dans cette mission. Plutôt que
d'appeler `smtplib` en dur depuis les services (ce qui obligerait à tout
refactorer le jour où un fournisseur arrive), tout passe par l'interface
`NotificationSender`.

L'implémentation active en développement est `ConsoleNotificationSender` : elle
écrit le message dans les logs structurés. Le corps du message peut contenir un
jeton de vérification — c'est précisément ce qu'un journal d'application ne
devrait PAS contenir (règle transverse : « aucune donnée de santé ni secret dans
les logs »). Le corps n'est donc PAS journalisé : seuls le destinataire, le
sujet et le type de message le sont. Le corps complet est écrit sur la sortie
standard du serveur, qui n'est pas un journal de données.
"""

import abc
import sys
from dataclasses import dataclass, field
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


#: Expéditeur actif, remplacé au démarrage par un fournisseur réel le jour venu.
_sender: NotificationSender = ConsoleNotificationSender()


def definir_sender(sender: NotificationSender) -> None:
    global _sender
    _sender = sender


def obtenir_sender() -> NotificationSender:
    return _sender


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