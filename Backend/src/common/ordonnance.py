"""
Vocabulaire et moteur des contre-indications médicamenteuses.

Principe : les règles sont des DONNÉES, pas du code. Un médicament déclare
quelles conditions l'interdisent ou l'inquiètent ; l'ordonnance translated l'état
clinique du patient en un ensemble de conditions, puis on confronte les deux.

Découpage volontaire : le référentiel (`MedicamentReferentiel`) porte les règles,
ce module ne connaît QUE la grammaire des conditions. Ajouter une règle
médicamenteuse est une mise à jour de données, sans redéploiement.

⚠️ Le référentiel fourni au seed est un **point de départ**, pas une base
pharmacopée. Il doit être revu et complété par un pharmacien avant un usage réel
(voir README du module `ordonnances`).
"""

from typing import Dict, Iterable, List, Optional, Set

# ---------------------------------------------------------------------------
# GRAVITÉ D'UNE CONTRE-INDICATION
# ---------------------------------------------------------------------------

#: Le médicament est formellement interdit. La ligne est refusée.
INTERDIT = "INTERDIT"

#: Risque modifié sans interdiction formelle. La ligne n'est acceptée que si le
#: praticien en justifie explicitement (ex : amoxicilline en fin de grossesse).
PRECAUTION = "PRECAUTION"

GRAVITES = (INTERDIT, PRECAUTION)

# ---------------------------------------------------------------------------
# CONDITIONS CLINIQUES
#
# Codes stables : ils apparaissent dans le référentiel et dans le journal. Un
# libellé lisible accompagne le code pour l'affichage.
# ---------------------------------------------------------------------------

# Grossesse et allaitement (RG08)
GROSSESSE = "GROSSESSE"
ALLAITEMENT = "ALLAITEMENT"

# Terrain (RG08)
DIABETE = "DIABETE"
INSUFFISANCE_RENALE = "INSUFFISANCE_RENALE"
INSUFFISANCE_HEPATIQUE = "INSUFFISANCE_HEPATIQUE"
HTA = "HTA"
ASTHME = "ASTHME"
ANTICOAGULANT = "ANTICOAGULANT"

# Allergies (RG07)
ALLERGIE = "ALLERGIE"  # allergie déclarée, substance non précisée

LIBELLES_CONDITIONS = {
    GROSSESSE: "Grossesse",
    ALLAITEMENT: "Allaitement",
    DIABETE: "Diabète",
    INSUFFISANCE_RENALE: "Insuffisance rénale",
    INSUFFISANCE_HEPATIQUE: "Insuffisance hépatique",
    HTA: "Hypertension artérielle",
    ASTHME: "Asthme",
    ANTICOAGULANT: "Traitement anticoagulant",
    ALLERGIE: "Allergie déclarée",
}

#: Préfixe des conditions d'allergie par substance : ALLERGIE_PENICILLINE,
#: ALLERGIE_LATEX... La substance est normalisée en majuscules sans séparateur.
PREFIXE_ALLERGIE = "ALLERGIE_"


def condition_allergie(substance: str) -> str:
    """
    Construit le code de condition d'une allergie : « Pénicilline » ->
    ``ALLERGIE_PENICILLINE``.

    La normalisation (casse, accents, espaces et tirets) est délibérée : le
    praticien saisit librement, le référentiel doit pouvoir comparer sans
    connaître toutes les graphies possibles.
    """
    normalise = (
        substance.strip()
        .upper()
        .replace("É", "E")
        .replace("È", "E")
        .replace("Ê", "E")
        .replace("À", "A")
        .replace("Ç", "C")
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )
    return f"{PREFIXE_ALLERGIE}{normalise}"


def libelle_condition(code: str) -> str:
    """Libellé lisible d'une condition, y compris pour les allergies par substance."""
    if code in LIBELLES_CONDITIONS:
        return LIBELLES_CONDITIONS[code]
    if code.startswith(PREFIXE_ALLERGIE):
        return f"Allergie : {code[len(PREFIXE_ALLERGIE):].lower()}"
    return code.replace("_", " ").capitalize()


# ---------------------------------------------------------------------------
# NORMALISATION DES SUBSTANCES
# ---------------------------------------------------------------------------
#
# Permet de rapprocher « amoxicilline », « Amoxicilline » et « AMOXICILLINE »
# sans connaître toutes les graphies. Sert aux allergies ET aux interactions
# entre médicaments (DCI).

_ACCENTS = {
    "É": "E", "È": "E", "Ê": "E", "Ë": "E",
    "À": "A", "Â": "A", "Ä": "A",
    "Ç": "C", "Î": "I", "Ï": "I", "Ô": "O", "Ö": "O", "Û": "U", "Ù": "U",
}


def normaliser_dci(dci: str) -> str:
    """
    Normalise une dénomination commune internationale pour comparaison.

    « Acide clavulanique » et « acide-clavulanique » donnent la même clé. Les
    sels et associations sont aussi ramenés à leur molécule porteuse
    (« amoxicilline + acide clavulanique » -> «AMOXICILLINE »), car c'est la
    molécule qui porte le risque allergique et l'interaction.
    """
    texte = dci.strip()
    # On garde la première molécule d'une association.
    for separateur in ("+", " et ", "/"):
        if separateur in texte:
            texte = texte.split(separateur)[0]
    brut = texte.upper()
    for accent, remplacement in _ACCENTS.items():
        brut = brut.replace(accent, remplacement)
    return brut.replace(" ", "").replace("-", "").replace("_", "")


#: Classes thérapeutiques utilisées par le référentiel pour les interactions
#: (deux médicaments d'une même classe partagent leurs risques).
CLASSES = {
    "AINS": "Anti-inflammatoire non stéroïdien",
    "ANTIBIOTIQUE_BETA_LACTAME": "Antibiotique β-lactamine",
    "ANTIBIOTIQUE_MACROLIDE": "Macrolide",
    "ANTISEPTIQUE": "Antiseptique buccal",
    "ANALGESIQUE": "Antalgique",
    "ANTIFONGIQUE": "Antifongique",
    "ANTICOAGULANT": "Anticoagulant",
}

#: Interactions médicamenteuses connues, exprimées par paires de DCI normalisées.
#: Clé = couple trié, valeur = description de la vigilance.
#: Volontairement restrictif : mieux vaut manquer une interaction signalée qu'en
#: afficher une fausse qui décrédibiliserait l'outil.
INTERACTIONS_CONNUES: Dict[tuple, str] = {
    ("ASPIRINE", "IBUPROFENE"): "Association d'AINS : risque hémorragique digestif majoré.",
    ("DICLOFENAC", "IBUPROFENE"): "Association d'AINS : risque hémorragique digestif majoré.",
    ("ASPIRINE", "DICLOFENAC"): "Association d'AINS : risque hémorragique digestif majoré.",
    ("ASPIRINE", "WARFARINE"): "Antiagrégant et anticoagulant : risque hémorragique majeur.",
    ("IBUPROFENE", "WARFARINE"): "AINS et anticoagulant : risque hémorragique majeur.",
    ("DICLOFENAC", "WARFARINE"): "AINS et anticoagulant : risque hémorragique majeur.",
    ("METRONIDAZOLE", "WARFARINE"): "Inhibition du métabolisme de l'anticoagulant : INR à contrôler.",
    ("METRONIDAZOLE", "ALCOOL"): "Effet antablasse : association à proscrire pendant le traitement.",
}


# ---------------------------------------------------------------------------
# MOTEUR DE CONTRE-INDICATION
# ---------------------------------------------------------------------------

class AlerteMedicament:
    """
    Alerte produite par le contrôle d'une ligne d'ordonnance.

    Objet simple plutôt que schéma Pydantic : il est construit par le moteur,
    puis sérialisé dans l'audit et renvoyé au frontend tel quel.
    """

    def __init__(self, code: str, gravite: str, message: str, condition: str):
        self.code = code
        self.gravite = gravite
        self.message = message
        self.condition = condition

    def __repr__(self) -> str:  # pragma: no cover - confort de débogage
        return f"<AlerteMedicament {self.gravite} {self.condition}: {self.message}>"

    def model_dump(self) -> dict:
        return {
            "code": self.code,
            "gravite": self.gravite,
            "message": self.message,
            "condition": self.condition,
        }


def conditions_pour_contre_indications(
    *,
    grossesse: bool = False,
    grossesse_terme: Optional[str] = None,
    allaitement: bool = False,
    diabete: bool = False,
    hta: bool = False,
    allergies: Optional[Iterable[dict]] = None,
    antecedents: Optional[Iterable] = None,
) -> Dict[str, str]:
    """
    Traduit l'état clinique du patient en conditions actives.

    Retourne un dictionnaire ``code_condition -> détail lisible``. La clé est
    celle que le référentiel médicamenteux compare.

    Les antécédents complètent l'état général : c'est courant en pratique d'avoir
    un antécédent « cardiovasculaire » qui n'a jamais été recopié dans l'état
    général. Ignorer les antécédents laisserait passer des prescriptions
    dangereuses.
    """
    conditions: Dict[str, str] = {}

    def ajouter(code: str, detail: str) -> None:
        conditions.setdefault(code, detail)

    if grossesse:
        terme = f" ({grossesse_terme})" if grossesse_terme else ""
        ajouter(GROSSESSE, f"Patiente enceinte{terme}")
    if allaitement:
        ajouter(ALLAITEMENT, "Allaitement en cours")
    if diabete:
        ajouter(DIABETE, "Diabète connu")
    if hta:
        ajouter(HTA, "Hypertension artérielle")

    # Allergies : une condition générique plus une condition par substance.
    for allergie in allergies or []:
        if not isinstance(allergie, dict):
            continue
        substance = (allergie.get("substance") or "").strip()
        if not substance:
            ajouter(ALLERGIE, "Allergie déclarée sans substance précisée")
            continue
        reaction = allergie.get("reaction")
        detail = f"Allergie déclarée : {substance}"
        if reaction:
            detail += f" ({reaction})"
        ajouter(ALLERGIE, "Allergie déclarée")
        ajouter(condition_allergie(substance), detail)

    # Antécédents : on ne connaît que les types reconnus.
    for antecedent in antecedents or []:
        type_antecedent = (getattr(antecedent, "type_antecedent", "") or "").upper()
        en_cours = bool(getattr(antecedent, "en_cours", False))
        description = getattr(antecedent, "description", "") or ""
        if not en_cours:
            continue
        if type_antecedent in ("ASTHME", "RESPIRATOIRE"):
            ajouter(ASTHME, f"Antécédent respiratoire : {description}")
        elif type_antecedent in ("CARDIO", "CARDIAQUE", "HTA"):
            ajouter(HTA, f"Antécédent cardiovasculaire : {description}")
        elif type_antecedent in ("RENAL", "INSUFFISANCE_RENALE"):
            ajouter(INSUFFISANCE_RENALE, f"Antécédent rénal : {description}")
        elif type_antecedent in ("HEPATIQUE", "INSUFFISANCE_HEPATIQUE"):
            ajouter(INSUFFISANCE_HEPATIQUE, f"Antécédent hépatique : {description}")
        elif type_antecedent == "ANTICOAGULANT":
            ajouter(ANTICOAGULANT, f"Anticoagulant en cours : {description}")
        elif type_antecedent == "ALLERGIE":
            substance = description.strip()
            if substance:
                ajouter(condition_allergie(substance), f"Antécédent allergique : {substance}")
            ajouter(ALLERGIE, "Antécédent allergique en cours")

    return conditions


def evaluer_contre_indications(
    *,
    dci: str,
    contre_indications: Optional[Iterable[dict]],
    conditions_actives: Dict[str, str],
) -> List[AlerteMedicament]:
    """
    Confronte les règles d'un médicament aux conditions du patient.

    `contre_indications` est une liste du référentiel :
    ``[{"condition": "GROSSESSE", "gravite": "PRECAUTION", "message": "..."}]``
    """
    alertes: List[AlerteMedicament] = []
    regles = contre_indications or []

    for regle in regles:
        if not isinstance(regle, dict):
            continue
        condition = (regle.get("condition") or "").strip().upper()
        if not condition or condition not in conditions_actives:
            continue
        gravite = (regle.get("gravite") or INTERDIT).strip().upper()
        if gravite not in GRAVITES:
            gravite = INTERDIT
        message = regle.get("message") or (
            f"{dci} : {libelle_condition(condition)} — contre-indication"
            f"{' formelle' if gravite == INTERDIT else ' (précaution)'}."
        )
        alertes.append(
            AlerteMedicament(
                code=f"CONTRE_INDICATION_{gravite}",
                gravite=gravite,
                message=message,
                condition=condition,
            )
        )

    return alertes


def detecter_interactions(dcis_lignes: Iterable[str]) -> List[dict]:
    """
    Détecte les interactions médicamenteuses entre les lignes d'une ordonnance.

    L'ordre des lignes est sans importance : chaque paire n'est examinée qu'une
    fois, dans un seul sens.
    """
    alertes: List[dict] = []
    normalises: List[str] = []
    for dci in dcis_lignes:
        cle = normaliser_dci(dci)
        if cle and cle not in normalises:
            normalises.append(cle)

    for i in range(len(normalises)):
        for j in range(i + 1, len(normalises)):
            couple = tuple(sorted((normalises[i], normalises[j])))
            description = INTERACTIONS_CONNUES.get(couple)
            if description:
                alertes.append(
                    {
                        "code": "INTERACTION_MEDICAMENTEUSE",
                        "gravite": PRECAUTION,
                        "message": description,
                        "medicaments": list(couple),
                    }
                )
    return alertes


def interactions_speciales(dcis_lignes: Iterable[str]) -> List[dict]:
    """
    Interactions qui ne sont pas des paires mais des états du patient.

    Cas retenu : le métronidazole et l'alcool. Ce n'est pas une interaction
    entre deux médicaments mais une contre-indication liée à la consommation,
    trop fréquente pour être ignorée dans un cabinet.
    """
    normalises = {normaliser_dci(d) for d in dcis_lignes}
    alertes: List[dict] = []
    if "METRONIDAZOLE" in normalises:
        alertes.append(
            {
                "code": "INTERACTION_ALCOOL",
                "gravite": PRECAUTION,
                "message": (
                    "Métronidazole : proscrire toute consommation d'alcool pendant le "
                    "traitement et les 48 h qui suivent (effet antablasse)."
                ),
            }
        )
    return alertes
