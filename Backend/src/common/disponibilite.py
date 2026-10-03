"""
Vocabulaire et règles des disponibilités praticien (D2A).

Ce module est la grammaire partagée entre le présent module et le module Agenda
(D2B). Il ne fait aucun accès base : il manipule des heures et des jours, ce
qui le rend testable sans PostgreSQL et réutilisable tel quel par la
détection de conflits.

Découpage volontaire : la *définition* d'une plage vit en base
(`Disponibilite`), le *calcul* de ce qu'on peut en faire vit ici.

Deux notions distinctes, à ne jamais confondre :
  - les horaires d'OUVERTURE d'un cabinet : quand le bâtiment est ouvert ;
  - les DISPONIBILITÉS d'un praticien : quand ce praticien travaille.

Un créneau proposable au patient doit être dans les deux. `creneaux_proposables`
fait cette intersection ; le module Agenda s'appuiera dessus.
"""

from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# JOURS DE LA SEMAINE
# ---------------------------------------------------------------------------
# 0 = lundi … 6 = dimanche. Convention posée par le MLD (`disponibilites`).
# Elle diverge de `date.weekday()` (0 = lundi) : ici elle coïncide, ce qui rend
# la conversion immédiate, mais le choix est explicite pour éviter qu'un lecteur
# suppose l'inverse.

LUNDI, MARDI, MERCREDI, JEUDI, VENDREDI, SAMEDI, DIMANCHE = range(7)

JOURS_SEMAINE: Tuple[str, ...] = (
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
)

JOURS_COURTS: Tuple[str, ...] = ("LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM")


def libelle_jour(index: int) -> str:
    """Nom lisible d'un index de semaine (0-6). Hors bornes : description exacte."""
    if 0 <= index <= 6:
        return JOURS_SEMAINE[index]
    return f"jour {index}"


def jour_de_la_semaine(jour: date) -> int:
    """Index de semaine d'une date, dans la convention ci-dessus."""
    return jour.weekday()


# ---------------------------------------------------------------------------
# TYPES DE PLAGE
# ---------------------------------------------------------------------------

#: Créneau où le praticien reçoit et où l'on peut proposer un rendez-vous.
CONSULTATION = "CONSULTATION"

#: Créneau réservé aux urgences : non proposable sur l'agenda, mais il
#: n'est pas une indisponibilité — on ne le réserve pas à l'avance.
URGENCE = "URGENCE"

#: Indisponibilité déclarée (congé, formation, remplacement). Retiré des
#: créneaux proposables.
BLOCKING = "BLOCKING"

TYPES_PLAGE = (CONSULTATION, URGENCE, BLOCKING)

LIBELLES_TYPE_PLAGE = {
    CONSULTATION: "Consultations",
    URGENCE: "Urgences",
    BLOCKING: "Indisponibilité",
}


def est_bloquante(type_plage: str) -> bool:
    """Une plage `BLOCKING` retire des créneaux, les autres en créent ou les réservent."""
    return type_plage == BLOCKING


# ---------------------------------------------------------------------------
# DURÉE DE CRÉNEAU
# ---------------------------------------------------------------------------
# 30 minutes est le pas le plus courant en odontologie. La valeur est une
# constante et non un paramètre : la changer affecterait tous les cabinets d'un
# coup, et le module Agenda a besoin d'une référence stable.

DUREE_CRENEAU_MINUTES = 30
DUREE_CRENEAU_SECONDS = DUREE_CRENEAU_MINUTES * 60


# ---------------------------------------------------------------------------
# VALIDATION D'UNE PLAGE
# ---------------------------------------------------------------------------

class PlageInvalide(ValueError):
    """
    Plage horaire incohérente.

    Porte deux attributs : `message`, destiné au praticien via l'API, et `code`,
    destiné au frontend qui doit pouvoir brancher sur la cause sans lire le
    texte. `message` est un attribut explicite parce que `ValueError` ne le
    conserve pas sous ce nom.
    """

    def __init__(self, message: str, code: str = "PLAGE_INVALIDE"):
        super().__init__(message)
        self.message = message
        self.code = code


def valider_plage(
    *,
    heure_debut: time,
    heure_fin: time,
    jour_semaine: Optional[int],
    date_specifique: Optional[date],
    type_plage: str,
) -> None:
    """
    Vérifie qu'une plage est exploitable. Lève `PlageInvalide` sinon.

    Les règles portent des messages en français : ce sont les textes que le
    praticien verra dans l'UI quand sa saisie sera refusée.
    """
    if heure_debut >= heure_fin:
        raise PlageInvalide(
            f"L'heure de début ({heure_debut:%H:%M}) doit précéder l'heure de fin "
            f"({heure_fin:%H:%M}). Une plage ne peut pas traverser minuit : déclarez "
            "deux plages si le service dépasse 00:00.",
            code="PLAGE_INVERSEE",
        )

    if jour_semaine is None and date_specifique is None:
        raise PlageInvalide(
            "Indiquez un jour de semaine (récurrence) ou une date précise "
            "(exception).",
            code="PLAGE_SANS_JOUR",
        )

    if jour_semaine is not None and not (0 <= jour_semaine <= 6):
        raise PlageInvalide(
            f"Le jour de semaine doit être compris entre 0 (lundi) et 6 (dimanche), "
            f"et non {jour_semaine}.",
            code="JOUR_INVALIDE",
        )

    if type_plage not in TYPES_PLAGE:
        raise PlageInvalide(
            f"Type de plage inconnu : {type_plage}. Attendu parmi {TYPES_PLAGE}.",
            code="TYPE_PLAGE_INCONNU",
        )


# ---------------------------------------------------------------------------
# CHEVAUCHEMENT DE PLAGES
# ---------------------------------------------------------------------------

def minutes_de(h: time) -> int:
    """Une heure `time` exprimée en minutes depuis minuit."""
    return h.hour * 60 + h.minute


def heures_de(m: int) -> time:
    """L'inverse de `minutes_de`."""
    return time(hour=m // 60, minute=m % 60)


def chevauche(a_debut: time, a_fin: time, b_debut: time, b_fin: time) -> bool:
    """
    Deux plages se chevauchent-elles ?

    Les bornes sont **fermées en début, ouvertes en fin** : 09:00-10:00 et
    10:00-11:00 ne se chevauchent PAS. C'est ce qui permet à deux rendez-vous
    de s'enchaîner sans trou, et c'est la convention du module Agenda.
    """
    return a_debut < b_fin and b_debut < a_fin


def confliter(
    candidates: Iterable[Tuple[int, int]],
    nouvelle_debut: int,
    nouvelle_fin: int,
) -> Optional[Tuple[int, int]]:
    """
    Première plage chevauchant `[nouvelle_debut, nouvelle_fin]`, ou `None`.

    Les bornes sont des minutes depuis minuit (voir `minutes_de`), ce qui rend
    le test purement arithmétique. Le module Agenda s'en servira pour la
    détection de conflits sur les rendez-vous comme sur les disponibilités.
    """
    for debut, fin in candidates:
        if nouvelle_debut < fin and debut < nouvelle_fin:
            return (debut, fin)
    return None


# ---------------------------------------------------------------------------
# GÉNÉRATION DE CRÉNEAUX
# ---------------------------------------------------------------------------

def decouper_en_creneaux(
    heure_debut: time,
    heure_fin: time,
    duree_minutes: int = DUREE_CRENEAU_MINUTES,
) -> List[Tuple[time, time]]:
    """
    Découpe une plage en créneaux de durée fixe.

    Le dernier créneau est **écourté** si la plage ne tombe pas juste : une
    plage 09:00-09:50 avec un pas de 30 minutes donne 09:00-09:30 puis
    09:30-09:50, pas un créneau qui déborde sur 10:00.
    """
    if duree_minutes <= 0:
        raise PlageInvalide(
            f"La durée d'un créneau doit être strictement positive (reçu : {duree_minutes}).",
            code="DUREE_INVALIDE",
        )

    debut = minutes_de(heure_debut)
    fin = minutes_de(heure_fin)
    if fin <= debut:
        raise PlageInvalide(
            f"L'heure de début ({heure_debut:%H:%M}) doit précéder l'heure de fin "
            f"({heure_fin:%H:%M}).",
            code="PLAGE_INVERSEE",
        )

    creneaux: List[Tuple[time, time]] = []
    curseur = debut
    while curseur < fin:
        suivant = min(curseur + duree_minutes, fin)
        creneaux.append((heures_de(curseur), heures_de(suivant)))
        curseur = suivant
    return creneaux


def creneaux_proposables(
    disponibilites: Iterable,
    jour: date,
    duree_minutes: int = DUREE_CRENEAU_MINUTES,
) -> List[Tuple[time, time]]:
    """
    Créneaux qu'on peut proposer au patient pour une date donnée.

    `disponibilites` est un iterable d'objets portant `jour_semaine`,
    `date_specifique`, `heure_debut`, `heure_fin`, `type_plage` et `actif`
    (donc des lignes `Disponibilite`, mais aussi n'importe quel objet conforme).

    Trois règles, appliquées dans cet ordre :
      1. une plage `date_specifique` qui ne concerne pas ce jour est ignorée ;
      2. les plages `BLOCKING` actives sont **retirées** des créneaux ;
      3. les créneaux restants sont fusionnés puis découpés.

    La fusion évite de proposer deux fois un créneau couvert par deux plages
    qui se chevauchent (amplitude 08:00-12:00 + 08:00-10:00, cas réel quand
    quelqu'un declare ses disponibilites en deux fois).
    """
    jour_cible = jour_de_la_semaine(jour)
    incluses: List[Tuple[int, int]] = []
    exclusions: List[Tuple[int, int]] = []

    for dispo in disponibilites:
        if not getattr(dispo, "actif", True):
            continue

        date_spec = getattr(dispo, "date_specifique", None)
        if date_spec is not None and date_spec != jour:
            continue

        # La colonne s'appelle `type` (nom du MLD) ; on lit l'attribut tel quel.
        type_plage = getattr(dispo, "type", CONSULTATION)

        plage = (minutes_de(dispo.heure_debut), minutes_de(dispo.heure_fin))
        if est_bloquante(type_plage):
            exclusions.append(plage)
            continue

        # Une plage qui ne porte ni jour récurrent ni date ne sert à rien :
        # `valider_plage` l'interdit à l'écriture, on l'ignore à la lecture.
        if date_spec is None and getattr(dispo, "jour_semaine", None) != jour_cible:
            continue

        incluses.append(plage)

    if not incluses:
        return []

    # 2. Fusion des plages incluses : on retient la plus petite borne basse et
    #    la plus grande borne haute de chaque groupe connecté.
    fusionnees = _fusionner(incluses)

    # 3. Retrait des exclusions.
    restantes: List[Tuple[int, int]] = []
    for debut, fin in fusionnees:
        # On découpe la plage par les exclusions qui la traversent.
        trous: List[Tuple[int, int]] = [
            (max(debut, d), min(fin, f))
            for d, f in exclusions
            if chevauche(heures_de(debut), heures_de(fin), heures_de(d), heures_de(f))
        ]
        if not trous:
            restantes.append((debut, fin))
            continue
        trous.sort()
        curseur = debut
        for d, f in trous:
            if d > curseur:
                restantes.append((curseur, d))
            curseur = max(curseur, f)
        if curseur < fin:
            restantes.append((curseur, fin))

    creneaux: List[Tuple[time, time]] = []
    for debut, fin in restantes:
        creneaux.extend(decouper_en_creneaux(heures_de(debut), heures_de(fin), duree_minutes))
    return creneaux


def _fusionner(plages: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Fusionne des plages qui se touchent ou se recouvrent (minutes depuis minuit).

    08:00-10:00 et 10:00-12:00 donnent 08:00-12:00 : aucun trou n'est réel,
    le praticien travaille sans interruption.
    """
    if not plages:
        return []

    triees = sorted(plages)
    resultat = [list(triees[0])]
    for debut, fin in triees[1:]:
        if debut <= resultat[-1][1]:
            resultat[-1][1] = max(resultat[-1][1], fin)
        else:
            resultat.append([debut, fin])
    return [(d, f) for d, f in resultat]


# ---------------------------------------------------------------------------
# RENDU COMPACT POUR L'UI
# ---------------------------------------------------------------------------

def compacter(plages: Iterable[Tuple[time, time]]) -> List[Tuple[str, str]]:
    """
    Transforme des paires d'heures en chaînes `HH:MM`, pour l'affichage.

    Le frontend n'a ainsi pas à reformater les `time` Python sérialisés par
    FastAPI en `"HH:MM:SS"`, et un créneau de 09:00 s'affiche `09:00` et non
    `09:00:00`.
    """
    return [(d.strftime("%H:%M"), f.strftime("%H:%M")) for d, f in plages]
