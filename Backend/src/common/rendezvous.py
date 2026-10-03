"""
Vocabulaire et règles de cycle de vie des rendez-vous (D2B).

Ce module est la grammaire partagée entre le module Rendez-vous et le module
Consultations (D1B). Le statut d'un rendez-vous et le statut d'une consultation
sont deux notions distinctes mais solidaires : passer un rendez-vous « en
consultation » ouvre une consultation, et la clore termine le rendez-vous.

Découpage volontaire : les *statuts* et les *transitions* vivent ici, le *stockage*
et la *détection de conflits* dans le module. Ajouter un statut se fait à un seul
endroit, et les deux modules restent cohérents.
"""

from datetime import datetime, timedelta
from typing import Dict, FrozenSet, Optional, Tuple

# ---------------------------------------------------------------------------
# STATUTS
# ---------------------------------------------------------------------------
# Repris du CDC : Planifié, Confirmé, En salle d'attente, En consultation,
# Terminé, Annulé, Absent.

PLANIFIE = "PLANIFIE"
CONFIRME = "CONFIRME"
EN_SALLE_ATTENTE = "EN_SALLE_ATTENTE"
EN_CONSULTATION = "EN_CONSULTATION"
TERMINEE = "TERMINEE"
ANNULE = "ANNULE"
ABSENT = "ABSENT"

STATUTS: Tuple[str, ...] = (
    PLANIFIE,
    CONFIRME,
    EN_SALLE_ATTENTE,
    EN_CONSULTATION,
    TERMINEE,
    ANNULE,
    ABSENT,
)

LIBELLES_STATUT: Dict[str, str] = {
    PLANIFIE: "Planifié",
    CONFIRME: "Confirmé",
    EN_SALLE_ATTENTE: "En salle d'attente",
    EN_CONSULTATION: "En consultation",
    TERMINEE: "Terminé",
    ANNULE: "Annulé",
    ABSENT: "Absent",
}

#: Statuts qui **occupent encore** la ressource : le créneau est pris, la
#: présence est attendue ou en cours.
STATUTS_ACTIFS: FrozenSet[str] = frozenset(
    {PLANIFIE, CONFIRME, EN_SALLE_ATTENTE, EN_CONSULTATION}
)

#: Statuts terminaux : le rendez-vous a eu lieu, ou n'aura pas lieu.
#:
#: ⚠️ ANNULE et ABSENT sont EXCLUS des conflits. Un rendez-vous annulé ou manqué
#: ne réserve plus le créneau : c'est ce qui permet à la base de libérer la
#: place sans qu'aucune requête ne soit nécessaire.
STATUTS_TERMINAUX: FrozenSet[str] = frozenset({TERMINEE, ANNULE, ABSENT})

#: Ce que la contrainte d'exclusion PostgreSQL doit ignorer. Definie ici et pas
#: dans la migration : la règle « un rendez-vous annulé ne bloque pas » doit se
#: lire au même endroit que les statuts.
STATUTS_EXCLUS_DU_CONFLIT: FrozenSet[str] = STATUTS_TERMINAUX


# ---------------------------------------------------------------------------
# TRANSITIONS
# ---------------------------------------------------------------------------
# Un rendez-vous suit un chemin unique. Les transitions libres donneraient au
# secrétariat la possibilité de « dé-terminer » une consultation déjà clôturée,
# ou de rouvrir un rendez-vous annulé.

_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    PLANIFIE: frozenset({CONFIRME, EN_SALLE_ATTENTE, ANNULE, ABSENT}),
    CONFIRME: frozenset({EN_SALLE_ATTENTE, ANNULE, ABSENT}),
    EN_SALLE_ATTENTE: frozenset({EN_CONSULTATION, ANNULE, ABSENT}),
    EN_CONSULTATION: frozenset({TERMINEE, ANNULE}),
    TERMINEE: frozenset(),
    ANNULE: frozenset(),
    ABSENT: frozenset(),
}


class TransitionInterdite(ValueError):
    """Changement de statut non permis. Le message s'adresse au secrétariat."""

    def __init__(self, depuis: str, vers: str):
        self.depuis = depuis
        self.vers = vers
        self.code = "TRANSITION_INTERDITE"
        self.message = _message(depuis, vers)
        super().__init__(self.message)


def transitions_possibles(statut: str) -> FrozenSet[str]:
    return _TRANSITIONS.get(statut, frozenset())


def transition_possible(depuis: str, vers: str) -> bool:
    return vers in _TRANSITIONS.get(depuis, frozenset())


def verifier_transition(depuis: str, vers: str) -> None:
    """Lève `TransitionInterdite` si le changement de statut n'est pas permis."""
    if depuis == vers:
        # Idempotence : re-confirmer un rendez-vous déjà confirmé, ou
        # double-cliquer sur « annuler », ne doit pas échouer.
        return
    if not transition_possible(depuis, vers):
        raise TransitionInterdite(depuis, vers)


def _message(depuis: str, vers: str) -> str:
    if depuis in STATUTS_TERMINAUX:
        return (
            f"Un rendez-vous « {LIBELLES_STATUT.get(depuis, depuis).lower()} » est "
            "définitif : on ne le rouvre pas. Créez un nouveau rendez-vous si le "
            "patient doit revenir."
        )
    possibles = transitions_possibles(depuis)
    if not possibles:
        return (
            f"Aucun changement de statut n'est possible depuis "
            f"« {LIBELLES_STATUT.get(depuis, depuis)} »."
        )
    liste = " ou ".join(f"« {LIBELLES_STATUT[p]} »" for p in sorted(possibles))
    return (
        f"Impossible de passer un rendez-vous de "
        f"« {LIBELLES_STATUT.get(depuis, depuis)} » à "
        f"« {LIBELLES_STATUT.get(vers, vers)} ». Depuis cet état, on ne peut que : "
        f"{liste}."
    )


def est_transition_morte(statut: str) -> bool:
    """Un rendez-vous annulé ne redevient jamais planifié, mais peut être rejoué."""
    return statut in (ANNULE, ABSENT, TERMINEE)


# ---------------------------------------------------------------------------
# MOTIFS DE BLOCAGE D'UN FAUTEUIL
# ---------------------------------------------------------------------------

#: Le fauteuil est occupé par CE rendez-vous. Motif le plus fréquent.
BLOCAGE_RENDEZ_VOUS = "RENDEZ_VOUS"

#: Le fauteuil est retiré du service pour cause technique.
BLOCAGE_MAINTENANCE = "MAINTENANCE"

#: Réparation en cours, immobilisation plus longue.
BLOCAGE_REPARATION = "REPARATION"

#: Réservé à un usage interne (stérilisation, accueil d'un groupe scolaire).
BLOCAGE_RESERVATION = "RESERVATION"

MOTIFS_BLOCAGE: Tuple[str, ...] = (
    BLOCAGE_RENDEZ_VOUS,
    BLOCAGE_MAINTENANCE,
    BLOCAGE_REPARATION,
    BLOCAGE_RESERVATION,
)

LIBELLES_MOTIF_BLOCAGE: Dict[str, str] = {
    BLOCAGE_RENDEZ_VOUS: "Rendez-vous",
    BLOCAGE_MAINTENANCE: "Maintenance",
    BLOCAGE_REPARATION: "Réparation",
    BLOCAGE_RESERVATION: "Réservation interne",
}

#: Motifs qui sont des indisponibilités du fauteuil, pas des rendez-vous.
MOTIFS_INDISPONIBILITE = frozenset(
    {BLOCAGE_MAINTENANCE, BLOCAGE_REPARATION, BLOCAGE_RESERVATION}
)


# ---------------------------------------------------------------------------
# DURÉES
# ---------------------------------------------------------------------------
# 30 minutes est le créneau par défaut de D2A (`DUREE_CRENEAU_MINUTES`). Le
# rendez-vous le reprend pour que le secrétariat n'ait rien à choisir.

DUREE_PAR_DEFAUT_MINUTES = 30

#: Bornes défensives. Une saisie de 8h le matin ou de 23h le soir est presque
#: toujours une faute de frappe ; on la refuse plutôt que de créer un créneau
#: impossible à retrouver dans l'agenda.
HEURE_OUVERTURE = 6
HEURE_FERMETURE = 23

DUREE_MIN_MINUTES = 5
DUREE_MAX_MINUTES = 480  # 8 h : une journée entière de prothèse en cabinetswap
DUREE_MINUTES_POSSIBLES = (15, 20, 30, 45, 60, 90, 120)


def duree_minutes(debut: datetime, fin: datetime) -> int:
    """Durée en minutes entre deux instants, arrondie à la minute."""
    return int((fin - debut).total_seconds() // 60)


def borne_horaire(debut: datetime, fin: datetime) -> Optional[str]:
    """
    Renvoie un motif de refus si le créneau est hors bornes, `None` sinon.

    `datetime.tzinfo` n'est pas consulté : on raisonne en heure locale du
    cabinet, ce qui correspond à ce que voit le secrétariat sur l'agenda.
    """
    if debut.hour < HEURE_OUVERTURE:
        return (
            f"Créneau avant l'ouverture ({HEURE_OUVERTURE:02d}h) : "
            f"début à {debut:%H:%M}."
        )
    if fin.date() != debut.date():
        # Un rendez-vous qui traverse minuit est presque toujours une erreur de
        # date (le secrétariat a changé de jour sans s'en apercevoir). Il
        # faudrait alors deux rendez-vous.
        return (
            f"Le créneau traverse minuit (du {debut:%d/%m} au {fin:%d/%m}). "
            "Un rendez-vous ne peut pas s'étendre sur deux jours : déclarez deux "
            "rendez-vous, ou vérifiez la date saisie."
        )
    if fin.hour > HEURE_FERMETURE or (fin.hour == HEURE_FERMETURE and fin.minute > 0):
        return (
            f"Créneau après la fermeture ({HEURE_FERMETURE:02d}h) : "
            f"fin à {fin:%H:%M}."
        )
    return None


def chevauchent(
    debut_a: datetime, fin_a: datetime, debut_b: datetime, fin_b: datetime
) -> bool:
    """
    Deux créneaux se chevauchent-ils ? Bornes ouvertes en fin, comme partout.

    09:00-09:30 et 09:30-10:00 ne se chevauchent PAS : deux rendez-vous
    consécutifs dans le même fauteuil doivent pouvoir s'enchaîner.
    """
    return debut_a < fin_b and debut_b < fin_a


def formater_creneau(debut: datetime, fin: datetime) -> str:
    """Rendu lisible pour les messages d'erreur et l'affichage."""
    return f"{debut:%d/%m/%Y %H:%M} - {fin:%H:%M}"
