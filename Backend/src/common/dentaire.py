"""
Vocabulaire dentaire partagé : numérotation FDI, faces, états d'une dent.

Référentiel unique utilisé par les modules Consultations et Odontogramme. La
numérotation FDI est le langage commun du dossier dentaire : la partager évite
que deux modules valident différemment la même dent.

Numérotation FDI
----------------
  Quadrant 1 : 11-18  (définitives supérieures droites)
  Quadrant 2 : 21-28  (définitives supérieures gauches)
  Quadrant 3 : 31-38  (définitives inférieures gauches)
  Quadrant 4 : 41-48  (définitives inférieures droites)
  Quadrants 5-8 : 51-85 (dentition de lait, 20 dents)

Numérotation Universal : 1 à 32, dans l'ordre, de la 3e molaire supérieure
droite à la 3e molaire inférieure gauche.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# FDI
# ---------------------------------------------------------------------------

DENTS_PERMANENTES_ADULTE = [
    # Quadrant 1 : supérieur droit, de la molaire à la incisive centrale
    18, 17, 16, 15, 14, 13, 12, 11,
    # Quadrant 2 : supérieur gauche
    21, 22, 23, 24, 25, 26, 27, 28,
    # Quadrant 3 : inférieur gauche
    31, 32, 33, 34, 35, 36, 37, 38,
    # Quadrant 4 : inférieur droit
    48, 47, 46, 45, 44, 43, 42, 41,
]

# Dentition deciduous : 20 dents, 5 par quadrant.
DENTS_LAIT_ENFANT = [
    55, 54, 53, 52, 51,
    61, 62, 63, 64, 65,
    75, 74, 73, 72, 71,
    85, 84, 83, 82, 81,
]

_FDI_PERMANENTE_RE = re.compile(r"^(1[1-8]|2[1-8]|3[1-8]|4[1-8])$")
_FDI_LAIT_RE = re.compile(r"^(5[1-5]|6[1-5]|7[1-5]|8[1-5])$")

# Correspondance FDI -> Universal (1 à 32).
_FDI_VERS_UNIVERSAL = {
    18: 1, 17: 2, 16: 3, 15: 4, 14: 5, 13: 6, 12: 7, 11: 8,
    21: 9, 22: 10, 23: 11, 24: 12, 25: 13, 26: 14, 27: 15, 28: 16,
    38: 17, 37: 18, 36: 19, 35: 20, 34: 21, 33: 22, 32: 23, 31: 24,
    48: 25, 47: 26, 46: 27, 45: 28, 44: 29, 43: 30, 42: 31, 41: 32,
}

FDI_DENTS_LAIT = tuple(DENTS_LAIT_ENFANT)


def est_dent_permanente(numero_fdi: int) -> bool:
    return numero_fdi in _FDI_VERS_UNIVERSAL


def est_dent_de_lait(numero_fdi: int) -> bool:
    return 51 <= numero_fdi <= 85 and numero_fdi % 10 != 0


def valider_numero_dent(numero: Optional[int]) -> Optional[int]:
    """
    Valide un numéro FDI. Lève une ValueError explicite sinon.

    Le message nomme les fourchettes attendues : un praticien qui saisit 99 doit
    comprendre ce qui ne va pas sans consulter la documentation.
    """
    if numero is None:
        return None

    n = str(numero)
    if _FDI_PERMANENTE_RE.match(n):
        return numero
    if _FDI_LAIT_RE.match(n):
        return numero

    raise ValueError(
        f"Numéro de dent FDI invalide : {numero}. "
        "Attendu : 11-48 (dents définitives) ou 51-85 (dents de lait)."
    )


def vers_universal(numero_fdi: int) -> Optional[int]:
    """Convertit un numéro FDI en numérotation Universal (1-32). None si lait."""
    return _FDI_VERS_UNIVERSAL.get(numero_fdi)


# ---------------------------------------------------------------------------
# FACES
# ---------------------------------------------------------------------------

FACE_MESIAL = "MESIAL"
FACE_DISTAL = "DISTAL"
FACE_VESTIBULAIRE = "VESTIBULAIRE"
FACE_LINGUAL_PALATIN = "LINGUAL_PALATIN"
FACE_OCCLUSAL_INCISAL = "OCCLUSAL_INCISAL"

FACES_DENT = (
    FACE_MESIAL,
    FACE_DISTAL,
    FACE_VESTIBULAIRE,
    FACE_LINGUAL_PALATIN,
    FACE_OCCLUSAL_INCISAL,
)

# Libellés courts utilisés par le composant SVG (audit log, exports).
FACES_COURTES = {
    FACE_MESIAL: "M",
    FACE_DISTAL: "D",
    FACE_VESTIBULAIRE: "V",
    FACE_LINGUAL_PALATIN: "L",
    FACE_OCCLUSAL_INCISAL: "O",
}


def valider_face(face: Optional[str]) -> Optional[str]:
    if face is None:
        return None
    normalise = face.strip().upper()
    if normalise not in FACES_DENT:
        raise ValueError(
            f"Face invalide : {face}. Valeurs acceptées : {', '.join(FACES_DENT)}."
        )
    return normalise


# ---------------------------------------------------------------------------
# ÉTATS D'UNE DENT
#
# Liste du dictionnaire de données (analyse §5.1). Volontairement une constante
# Python plutôt qu'un ENUM PostgreSQL : ajouter un état odontologique est une
# évolution courante, alors que `ALTER TYPE ... ADD VALUE` est bloqué dans une
# transaction et pénible en production. La contrainte est appliquée côté
# applicatif et vérifiée par tests.
# ---------------------------------------------------------------------------

ETAT_SAINE = "SAINE"

ETATS_DENT = (
    # Dents absentes / non éIPLantées
    "ABSENTE_EXTRACTEE",
    "ABSENTE_CONGENITALE",
    "INCLUSE",
    "SUPERNUMERAIRE",
    # Caries
    "CARIE_DEBUTANTE",
    "CARIE_AVANCEE",
    "CARIE_PROFONDE",
    "CARIE_SOUS_PLOMBAGE",
    # Restaurations
    "OBTURATION_AMALGAME",
    "OBTURATION_COMPOSITE",
    "OBTURATION_CVI",
    "INLAY",
    "ONLAY",
    # Couronnes et prothèses
    "COURONNE",
    "TCR",
    "REPRISE_TCR",
    "APEXIFICATION",
    "COURONNE_METAL",
    "COURONNE_CERAMIQUE",
    "BRIDGE_PILIER",
    "BRIDGE_INTERMEDIAIRE",
    "PROTHESE_PARTIELLE",
    "PROTHESE_TOTALE",
    "STELLITE",
    # Implantologie
    "IMPLANT_POSE",
    "COURONNE_SUR_IMPLANT",
    "ATTENTE_OSTEOINTEGRATION",
    # Chirurgie / endodontie
    "EXTRACTION_PLANIFIEE",
    "EXTRACTION_REALISEE",
    "RESECTION_APICALE",
    # Orthodontie et esthétique
    "BAGUE",
    "BRACKET",
    "CONTENTION",
    "FACETTE",
    "BLANCHIMENT",
    # Autres
    ETAT_SAINE,
    "A_TRAITER",
)

#: États qui justifient une alerte visuelle forte côté praticien.
ETATS_ATTENTION = {
    "CARIE_DEBUTANTE",
    "CARIE_AVANCEE",
    "CARIE_PROFONDE",
    "INCLUSE",
    "EXTRACTION_PLANIFIEE",
    "REPRISE_TCR",
    "ATTENTE_OSTEOINTEGRATION",
}

#: États correspondant à une dent soignée (affichage « bleu » dans le CDC).
ETATS_SOIGNES = {
    "OBTURATION_AMALGAME",
    "OBTURATION_COMPOSITE",
    "OBTURATION_CVI",
    "INLAY",
    "ONLAY",
    "COURONNE",
    "TCR",
    "APEXIFICATION",
    "COURONNE_METAL",
    "COURONNE_CERAMIQUE",
    "FACETTE",
    "IMPLANT_POSE",
    "RESECTION_APICALE",
}


def valider_etat_dent(etat: Optional[str]) -> Optional[str]:
    if etat is None:
        return ETAT_SAINE
    normalise = etat.strip().upper()
    if normalise not in ETATS_DENT:
        raise ValueError(
            f"État de dent inconnu : {etat}. "
            f"Valeurs acceptées : {len(ETATS_DENT)} (voir src/common/dentaire.py)."
        )
    return normalise


# ---------------------------------------------------------------------------
# CHARTING PARODONTAL
# ---------------------------------------------------------------------------

#: Six sites de sondage par dent (3 vestibulaires, 3 linguo-palatins).
SITES_SONDAGE = ("MV", "V", "DV", "ML", "L", "DL")

#: Plage de profondeur de sondage en millimètres (sonde periodontale).
PROFONDEUR_SONDAGE_MIN = 0
PROFONDEUR_SONDAGE_MAX = 15


def valider_site_sondage(site: Optional[str]) -> Optional[str]:
    if site is None:
        return None
    normalise = site.strip().upper()
    if normalise not in SITES_SONDAGE:
        raise ValueError(
            f"Site de sondage invalide : {site}. Valeurs acceptées : {', '.join(SITES_SONDAGE)}."
        )
    return normalise
