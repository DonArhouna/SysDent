"""
Envoi d'e-mails par SMTP : choix du transport et chiffrement de la connexion.

Aucun serveur réel n'est contacté : `smtplib` est remplacé par un faux qui
enregistre ce que le code lui demande.
"""

import smtplib
from types import SimpleNamespace

import pytest

from src.modules.platform.services import notifications
from src.modules.platform.services.notifications import (
    ConsoleNotificationSender,
    Message,
    SmtpNotificationSender,
    configurer_sender_depuis_settings,
)


class FauxSMTP:
    instances: list["FauxSMTP"] = []

    def __init__(self, hote, port, timeout=None, context=None):
        self.hote, self.port = hote, port
        self.appels: list[str] = []
        self.identifiants = None
        self.envoyes = []
        FauxSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.appels.append("starttls")

    def login(self, utilisateur, mot_de_passe):
        self.appels.append("login")
        self.identifiants = (utilisateur, mot_de_passe)

    def send_message(self, courriel):
        self.appels.append("send")
        self.envoyes.append(courriel)


class FauxSMTPEnPanne(FauxSMTP):
    def login(self, utilisateur, mot_de_passe):
        raise smtplib.SMTPAuthenticationError(535, b"identifiants refuses")


@pytest.fixture(autouse=True)
def _reinitialiser(monkeypatch):
    FauxSMTP.instances = []
    precedent = notifications.obtenir_sender()
    yield
    notifications.definir_sender(precedent)


def _reglages(**valeurs):
    base = dict(
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        SMTP_USER="",
        SMTP_PASSWORD="",
        SMTP_FROM="",
        SMTP_FROM_NAME="SysDent Pro",
        SMTP_TIMEOUT_SECONDS=15,
        EMAIL_COPIE_CONSOLE=False,
        APP_ENV="development",
    )
    base.update(valeurs)
    return SimpleNamespace(**base)


def _sender(port=587):
    return SmtpNotificationSender(
        hote="smtp.example.test",
        port=port,
        utilisateur="expediteur@example.test",
        mot_de_passe="secret",
        expediteur="expediteur@example.test",
        nom_expediteur="SysDent Pro",
    )


def _message():
    return Message(destinataire="dest@example.test", sujet="Objet", corps_texte="Corps")


def test_sans_mot_de_passe_l_envoi_reste_sur_la_console():
    sender = configurer_sender_depuis_settings(_reglages(SMTP_USER="a@example.test"))
    assert isinstance(sender, ConsoleNotificationSender)
    assert notifications.obtenir_sender() is sender


def test_avec_identifiants_le_transport_smtp_est_actif():
    sender = configurer_sender_depuis_settings(
        _reglages(SMTP_USER="a@example.test", SMTP_PASSWORD="abcd efgh ijkl mnop")
    )
    assert isinstance(sender, SmtpNotificationSender)
    assert notifications.obtenir_sender() is sender
    # Les espaces du mot de passe d'application Gmail sont retirés.
    assert sender._mot_de_passe == "abcdefghijklmnop"
    assert sender.expediteur == "a@example.test"


async def test_port_587_passe_par_starttls_avant_l_authentification(monkeypatch):
    monkeypatch.setattr(notifications.smtplib, "SMTP", FauxSMTP)
    assert await _sender(587).envoyer(_message()) is True

    serveur = FauxSMTP.instances[0]
    assert serveur.appels == ["starttls", "login", "send"]
    courriel = serveur.envoyes[0]
    assert courriel["To"] == "dest@example.test"
    assert courriel["Subject"] == "Objet"
    assert "expediteur@example.test" in courriel["From"]


async def test_port_465_ouvre_une_connexion_tls_directe(monkeypatch):
    monkeypatch.setattr(notifications.smtplib, "SMTP_SSL", FauxSMTP)
    assert await _sender(465).envoyer(_message()) is True
    assert FauxSMTP.instances[0].appels == ["login", "send"]


async def test_un_echec_renvoie_faux_sans_journaliser_le_secret(monkeypatch, capsys):
    monkeypatch.setattr(notifications.smtplib, "SMTP", FauxSMTPEnPanne)
    assert await _sender(587).envoyer(_message()) is False
    sortie = capsys.readouterr()
    assert "secret" not in sortie.out + sortie.err
    assert "Corps" not in sortie.out + sortie.err


def test_copie_console_active_en_developpement():
    sender = configurer_sender_depuis_settings(
        _reglages(
            SMTP_USER="a@example.test", SMTP_PASSWORD="x",
            EMAIL_COPIE_CONSOLE=True, APP_ENV="development",
        )
    )
    assert isinstance(sender, notifications.CopieConsoleNotificationSender)
    assert sender.nom() == "smtp+console"


def test_copie_console_refusee_en_production():
    sender = configurer_sender_depuis_settings(
        _reglages(
            SMTP_USER="a@example.test", SMTP_PASSWORD="x",
            EMAIL_COPIE_CONSOLE=True, APP_ENV="production",
        )
    )
    assert isinstance(sender, SmtpNotificationSender)


async def test_copie_console_affiche_le_code_meme_si_le_smtp_echoue(monkeypatch, capsys):
    monkeypatch.setattr(notifications.smtplib, "SMTP", FauxSMTPEnPanne)
    sender = notifications.CopieConsoleNotificationSender(_sender(587))
    message = Message(destinataire="dest@example.test", sujet="Code", corps_texte="Code : 482913")
    assert await sender.envoyer(message) is False
    assert "482913" in capsys.readouterr().out
