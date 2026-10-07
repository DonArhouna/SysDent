"""
Limitation de débit pour les endpoints sensibles (login Master et login tenant).

Implémentation volontairement en mémoire et par fenêtre glissante : le backend
tourne en un seul process (uvicorn), le coût est nul et il n'y a pas de dépendance
à Redis pour sécuriser le login — le premier point d'entrée du système.

Si le backend est un jour déployé sur plusieurs workers ou plusieurs instances,
ce module devra être remplacé par un compteur Redis partagé. Un limiteur
local à chaque worker reviendrait à multiplier la limite réelle par le nombre de
workers. La constante ci-dessous documente cette limite.
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple
import structlog

logger = structlog.get_logger(__name__)

# Nombre maximal de tentatives par fenêtre, par clé (email + IP).
DEFAULT_MAX_TENTATIVES = 5
DEFAULT_FENETRE_SECONDES = 300  # 5 minutes
# Durée de blocage après dépassement de la fenêtre.
DUREE_BLOCAGE_SECONDES = 900  # 15 minutes


class RateLimiter:
    """Limiteur à fenêtre glissante, en mémoire."""

    def __init__(
        self,
        max_tentatives: int = DEFAULT_MAX_TENTATIVES,
        fenetre_secondes: int = DEFAULT_FENETRE_SECONDES,
        duree_blocage_secondes: int = DUREE_BLOCAGE_SECONDES,
    ):
        self.max_tentatives = max_tentatives
        self.fenetre_secondes = fenetre_secondes
        self.duree_blocage_secondes = duree_blocage_secondes
        # clé -> (timestamps des tentatives, debut du blocage)
        self._tentatives: Dict[str, Deque[float]] = defaultdict(deque)
        self._bloques: Dict[str, float] = {}

    def _purger(self, cle: str, maintenant: float) -> None:
        """Retire les tentatives hors fenêtre et les blocages expirés."""
        if cle in self._bloques and self._bloques[cle] <= maintenant:
            del self._bloques[cle]
            self._tentatives.pop(cle, None)
            return
        if cle in self._tentatives:
            limite = maintenant - self.fenetre_secondes
            while self._tentatives[cle] and self._tentatives[cle][0] < limite:
                self._tentatives[cle].popleft()

    def est_bloque(self, cle: str) -> int:
        """
        Retourne le nombre de secondes restantes de blocage (0 si non bloqué).
        """
        maintenant = time.monotonic()
        self._purger(cle, maintenant)
        if cle in self._bloques:
            return max(1, int(self._bloques[cle] - maintenant))
        return 0

    def tenter(self, cle: str) -> None:
        """
        Enregistre une tentative. Lève TooManyRequestsException si la limite est
        atteinte ou si la clé est bloquée.
        """
        from src.core.exceptions import TooManyRequestsException

        maintenant = time.monotonic()
        self._purger(cle, maintenant)

        if cle in self._bloques:
            restantes = max(1, int(self._bloques[cle] - maintenant))
            logger.warning("rate_limit_bloque", cle=cle, secondes_restantes=restantes)
            raise TooManyRequestsException(
                "Trop de tentatives de connexion. Réessayez dans quelques minutes.",
                retry_after_seconds=restantes,
            )

        tentatives = self._tentatives[cle]
        tentatives.append(maintenant)

        if len(tentatives) > self.max_tentatives:
            self._bloques[cle] = maintenant + self.duree_blocage_secondes
            logger.warning(
                "rate_limit_declenche",
                cle=cle,
                tentatives=len(tentatives),
                duree_blocage=self.duree_blocage_secondes,
            )
            raise TooManyRequestsException(
                "Trop de tentatives de connexion. Réessayez dans quelques minutes.",
                retry_after_seconds=self.duree_blocage_secondes,
            )

    def reussite(self, cle: str) -> None:
        """Remet le compteur à zéro après une authentification réussie."""
        self._tentatives.pop(cle, None)
        self._bloques.pop(cle, None)

    def reinitialiser(self) -> None:
        self._tentatives.clear()
        self._bloques.clear()


def cle_login(email: str, ip: str) -> str:
    """
    Clé de limitation.

    L'email ET l'IP sont combinés volontairement : limiter sur le seul email
    permettrait un déni de service (bloquer le compte d'un utilisateur légitime en
    se connectant maladroitement depuis une autre IP) ; limiter sur la seule IP
    laisserait un attaquant passer par un nouveau compte à chaque tentative.
    """
    return f"{email.strip().lower()}|{ip or 'unknown'}"


# Limiteurs par surface d'authentification.
# Une instance PAR surface : partager le compteur entre le client et la console
# permettrait de verrouiller le compte d'un praticien en s'acharnant sur la console
# (et l'inverse). `Cle` est préfixée par la surface dans chaque service.
login_tenant_limiter = RateLimiter()
login_master_limiter = RateLimiter()
login_platform_limiter = RateLimiter(max_tentatives=5, fenetre_secondes=300, duree_blocage_secondes=900)
onboarding_limiter = RateLimiter(max_tentatives=5, fenetre_secondes=3600, duree_blocage_secondes=3600)
