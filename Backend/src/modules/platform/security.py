"""
Sécurité de la console PLATEFORME : politique de mot de passe, second facteur
TOTP, liste blanche d'IP, et primitives de hachage.

Ce module ne connaît pas FastAPI : ce sont des fonctions pures, testables sans
base ni application.
"""

import base64
import hashlib
import hmac
import ipaddress
import re
import secrets
from typing import List, Optional, Tuple

import structlog

from src.core.config import resoudre_fernet_platform, settings

logger = structlog.get_logger(__name__)


# ==============================================================================
# JETONS À USAGE UNIQUE (vérification e-mail, invitation admin)
# ==============================================================================


def generer_jeton_opaque(longueur: int = 32) -> str:
    """
    Jeton aléatoire URL-safe (256 bits de bande passante cryptographique).

    Le jeton en clair ne quitte jamais le serveur : il est remis à l'utilisateur
    par e-mail, et la base n'en conserve que le SHA-256. Une fuite de la base
    permet de voir QUELS jetons ont été émis, pas les utiliser.
    """
    return secrets.token_urlsafe(longueur)


def hacher_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def comparer_jeton(jeton_en_clair: str, hash_stocke: str) -> bool:
    """Comparaison à temps constant, pour ne pas fuir le préfixe correct."""
    return hmac.compare_digest(hacher_jeton(jeton_en_clair), hash_stocke)


def hacher_refresh(jeton: str) -> str:
    """Hash de refresh token de session (SHA-256 hex)."""
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


# ==============================================================================
# CHIFFREMENT DES SECRETS 2FA
# ==============================================================================


def chiffrer_secret_2fa(secret: str) -> str:
    return resoudre_fernet_platform().encrypt(secret.encode("utf-8")).decode()


def dechiffrer_secret_2fa(chiffre: str) -> str:
    return resoudre_fernet_platform().decrypt(chiffre.encode("utf-8")).decode("utf-8")


# ==============================================================================
# POLITIQUE DE MOTS DE PASSE (Phase A.4)
# ==============================================================================

_ERREURS_POLITIQUE = {
    "longueur": "Le mot de passe doit contenir au moins {n} caractères.",
    "majuscule": "Le mot de passe doit contenir au moins une majuscule.",
    "minuscule": "Le mot de passe doit contenir au moins une minuscule.",
    "chiffre": "Le mot de passe doit contenir au moins un chiffre.",
    "symbole": "Le mot de passe doit contenir au moins un caractère spécial.",
    "similaire_email": "Le mot de passe ne doit pas contenir votre adresse email.",
}


def verifier_mot_de_passe(
    mot_de_passe: str,
    email: str = "",
    mot_de_passe_precedent: Optional[str] = None,
) -> List[str]:
    """
    Applique la politique de mot de passe et retourne la liste des manquements.

    Le format de retour est une LISTE de règles violées, jamais un booléen :
    l'écran de création peut alors cocher les cases fautives au lieu d'afficher
    « mot de passe invalide ».
    """
    manquements: List[str] = []
    longueur = settings.PLATFORM_PASSWORD_MIN_LENGTH

    if len(mot_de_passe) < longueur:
        manquements.append(_ERREURS_POLITIQUE["longueur"].format(n=longueur))
    if not re.search(r"[A-Z]", mot_de_passe):
        manquements.append(_ERREURS_POLITIQUE["majuscule"])
    if not re.search(r"[a-z]", mot_de_passe):
        manquements.append(_ERREURS_POLITIQUE["minuscule"])
    if not re.search(r"[0-9]", mot_de_passe):
        manquements.append(_ERREURS_POLITIQUE["chiffre"])
    if not re.search(r"[^A-Za-z0-9]", mot_de_passe):
        manquements.append(_ERREURS_POLITIQUE["symbole"])

    if email:
        local = email.split("@")[0].lower()
        if local and len(local) >= 3 and local in mot_de_passe.lower():
            manquements.append(_ERREURS_POLITIQUE["similaire_email"])

    if mot_de_passe_precedent and hmac.compare_digest(mot_de_passe, mot_de_passe_precedent):
        manquements.append("Le nouveau mot de passe doit être différent de l'ancien.")

    return manquements


def mot_de_passe_valide(mot_de_passe: str, email: str = "") -> bool:
    return not verifier_mot_de_passe(mot_de_passe, email)


# ==============================================================================
# SECOND FACTEUR TOTP (RFC 6238) — OBLIGATOIRE
# ==============================================================================


def generer_secret_totp() -> str:
    """Secret base32 de 160 bits, le format attendu par les applications TOTP."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def uri_otpauth(secret: str, email: str) -> str:
    """URI `otpauth://` à encoder en QR Code par l'interface."""
    return (
        f"otpauth://totp/{settings.PLATFORM_2FA_ISSUER}:{email}"
        f"?secret={secret}&issuer={settings.PLATFORM_2FA_ISSUER}"
        f"&digits={settings.PLATFORM_2FA_TOTP_DIGITS}&period={settings.PLATFORM_2FA_TOTP_INTERVAL}"
    )


def _hotp(secret: str, compteur: int, digits: int) -> str:
    cle = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(cle, compteur.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def codes_totp(secret: str, instant: Optional[float] = None) -> Tuple[str, str]:
    """Code du pas de temps courant et du pas précédent (tolérance d'horloge)."""
    import time

    if instant is None:
        instant = time.time()
    pas = instant // settings.PLATFORM_2FA_TOTP_INTERVAL
    return _hotp(secret, int(pas), settings.PLATFORM_2FA_TOTP_DIGITS), _hotp(
        secret, int(pas) - 1, settings.PLATFORM_2FA_TOTP_DIGITS
    )


def verifier_code_totp(secret: str, code: str, fenetre: int = 1) -> bool:
    """
    Vérifie un code TOTP.

    `fenetre=1` tolère le pas précédent, ce qui absorbe le décalage d'horloge
    entre le poste de l'agent et le serveur sans ouvrir de fenêtre de rejeu
    significative (30 s).
    """
    if not code or not code.isdigit():
        return False
    import time

    maintenant = time.time()
    pas = int(maintenant // settings.PLATFORM_2FA_TOTP_INTERVAL)
    for decalage in range(-fenetre, fenetre + 1):
        attendu = _hotp(secret, pas + decalage, settings.PLATFORM_2FA_TOTP_DIGITS)
        if hmac.compare_digest(attendu, code):
            return True
    return False


def valider_secret_2fa(secret_chiffre: Optional[str]) -> Optional[str]:
    """Déchiffre un secret 2FA, en tolérant une clé de chiffrement changée."""
    if not secret_chiffre:
        return None
    try:
        return dechiffrer_secret_2fa(secret_chiffre)
    except Exception:  # noqa: BLE001 - une clé changée ne doit pas casser le serveur
        logger.error("secret_2fa_illisible", hint="PLATFORM_SECRET_ENCRYPTION_KEY a changé")
        return None


# ==============================================================================
# LISTE BLANCHE D'IP (Phase A.4)
# ==============================================================================


def ip_autorisee(ip: Optional[str]) -> Tuple[bool, str]:
    """
    Vérifie une IP contre la liste blanche configurée.

    Vide = aucune restriction (configuration par défaut en développement).
    Accepte une adresse exacte ou un réseau CIDR, ce qui permet d'ouvrir la
    console à un bureau sans ouvrir le monde entier.
    """
    liste = settings.ip_whitelist_platform
    if not liste:
        return True, "aucune liste blanche configurée"

    if not ip:
        return False, "adresse IP absente de la requête"

    try:
        adresse = ipaddress.ip_address(ip)
    except ValueError:
        return False, "adresse IP illisible"

    for entree in liste:
        entree = entree.strip()
        if not entree:
            continue
        try:
            if "/" in entree:
                if adresse in ipaddress.ip_network(entree, strict=False):
                    return True, f"réseau autorisé {entree}"
            elif adresse == ipaddress.ip_address(entree):
                return True, f"adresse autorisée {entree}"
        except ValueError:
            logger.warning("entree_liste_blanche_invalide", entree=entree)
    return False, "adresse non autorisée"