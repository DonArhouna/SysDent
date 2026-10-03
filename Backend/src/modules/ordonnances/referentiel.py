"""
Formulaire médicamenteux de départ pour un cabinet dentaire.

AVERTISSEMENT CLINIQUE. Ce formulaire est un point de départ technique, pas une
base pharmacopée. Il couvre les molécules les plus courantes en odontologie au
Sénégal et au Maghreb, avec les contre-indications usuelles. Il doit être revu
et complété par un pharmacien avant tout usage sur des patients réels.

Chaque entrée porte ses règles sous forme de données : compléter le formulaire
est une mise à jour de la base, pas une modification de code.

Les posologies sont exprimées pour l'adulte. L'ordonnance ne gère pas la
posologie pédiatrique : pour un enfant, le praticien saisit la posologie en
clair.
"""

from typing import Dict, List


def _interdit(condition: str, message: str) -> Dict:
    return {"condition": condition, "gravite": "INTERDIT", "message": message}


def _precaution(condition: str, message: str) -> Dict:
    return {"condition": condition, "gravite": "PRECAUTION", "message": message}


#: Formes disponibles (alignées sur la colonne `medicaments.forme`).
FORMES = (
    "COMPRIME",
    "SIROP",
    "GELE",
    "BADEROUCHE",
    "POMMADE",
    "CAROUCHE",
    "SACHET",
)

#: Molécules du formulaire initial.
FORMULAIRE_DENTAIRE: List[Dict] = [
    # ------------------------------------------------------------- antibiotiques
    {
        "nom_commercial": "Amoxicilline",
        "dci": "Amoxicilline",
        "forme": "COMPRIME",
        "dosage": "500mg",
        "classe_therapeutique": "ANTIBIOTIQUE_BETA_LACTAME",
        "posologie_adulte": "500 mg, 3 fois par jour, 7 jours",
        "precautions": "Au cours du repas, pour limiter l'irritation gastrique.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_PENICILLINE",
                "Allergie à la pénicilline : une bêta-lactamine est formellement "
                "interdite. Substituer par une molécule d'une autre famille "
                "(macrolide, métronidazole).",
            ),
            _interdit(
                "ALLERGIE_AMOXICILLINE",
                "Allergie à l'amoxicilline déclarée : administration interdite.",
            ),
            _precaution(
                "GROSSESSE",
                "Amoxicilline et grossesse : à éviter au 1er trimestre. Utilisable sur "
                "avis médical si le bénéfice l'emporte. Demander une justification.",
            ),
            _precaution(
                "ALLAITEMENT",
                "Amoxicilline et allaitement : passage dans le lait maternel. À éviter "
                "tant que l'enfant est nouveau-né. Demander une justification.",
            ),
        ],
    },
    {
        "nom_commercial": "Amoxicilline / Acide clavulanique",
        "dci": "Amoxicilline + Acide clavulanique",
        "forme": "SACHET",
        "dosage": "1g",
        "classe_therapeutique": "ANTIBIOTIQUE_BETA_LACTAME",
        "posologie_adulte": "1 sachet, 2 fois par jour, 7 jours",
        "precautions": "Réhydratation abondante (risque de diarrhée).",
        "contre_indications": [
            _interdit(
                "ALLERGIE_PENICILLINE",
                "Allergie à la pénicilline : bêta-lactamine interdite.",
            ),
            _interdit(
                "ALLERGIE_ACIDECLAVULANIQUE",
                "Allergie à l'acide clavulanique déclarée : administration interdite.",
            ),
            _precaution(
                "GROSSESSE",
                "Association amoxicilline-acide clavulanique et grossesse : à éviter au "
                "1er trimestre. Demander une justification.",
            ),
        ],
    },
    {
        "nom_commercial": "Azithromycine",
        "dci": "Azithromycine",
        "forme": "COMPRIME",
        "dosage": "500mg",
        "classe_therapeutique": "ANTIBIOTIQUE_MACROLIDE",
        "posologie_adulte": "500 mg, 1 fois par jour, 3 jours",
        "precautions": "À prendre à distance des antiacides. Troubles digestifs fréquents.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_AZITHROMYCINE",
                "Allergie à l'azithromycine : macrolide interdit.",
            ),
            _precaution(
                "ANTICOAGULANT",
                "Macrolide et anticoagulant : risque d'interaction, contrôler l'INR.",
            ),
        ],
    },
    {
        "nom_commercial": "Métronidazole",
        "dci": "Métronidazole",
        "forme": "COMPRIME",
        "dosage": "500mg",
        "classe_therapeutique": "ANTIBIOTIQUE_BETA_LACTAME",
        "posologie_adulte": "500 mg, 3 fois par jour, 7 jours",
        "precautions": (
            "Proscrire toute consommation d'alcool pendant le traitement et les 48 h "
            "qui suivent (effet antablasse). Goût métallique fréquent."
        ),
        "contre_indications": [
            _interdit(
                "GROSSESSE",
                "Métronidazole et grossesse : contre-indiqué au 1er trimestre "
                "(risque mutagène sans bénéfice démontré).",
            ),
            _interdit(
                "ALLERGIE_METRONIDAZOLE",
                "Allergie au métronidazole : administration interdite.",
            ),
        ],
    },
    # --------------------------------------------------------------- antalgiques
    {
        "nom_commercial": "Paracétamol",
        "dci": "Paracétamol",
        "forme": "COMPRIME",
        "dosage": "1g",
        "classe_therapeutique": "ANALGESIQUE",
        "posologie_adulte": "1 g, 3 fois par jour, maximum 3 g par jour",
        "precautions": "Ne pas dépasser 3 g par jour (risque d'hépatotoxicité).",
        "contre_indications": [
            _interdit(
                "ALLERGIE_PARACETAMOL",
                "Allergie au paracétamol : administration interdite.",
            ),
            _interdit(
                "INSUFFISANCE_HEPATIQUE",
                "Insuffisance hépatique sévère : paracétamol contre-indiqué à la dose "
                "standard sans surveillance biologique.",
            ),
            _precaution(
                "ALLAITEMENT",
                "Paracétamol et allaitement : passage faible dans le lait, "
                "généralement compatible.",
            ),
        ],
    },
    {
        "nom_commercial": "Ibuprofène",
        "dci": "Ibuprofène",
        "forme": "COMPRIME",
        "dosage": "400mg",
        "classe_therapeutique": "AINS",
        "posologie_adulte": "400 mg, 3 fois par jour, au cours des repas, 5 jours",
        "precautions": "Au cours du repas. Ne pas associer à un autre AINS.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_IBUPROFENE",
                "Allergie à l'ibuprofène ou à un autre AINS : administration interdite.",
            ),
            _interdit(
                "GROSSESSE",
                "AINS et grossesse : contre-indiqués à partir du 6e mois (fermeture "
                "prématurée du canal artériel). INTERDIT.",
            ),
            _interdit(
                "ALLERGIE_ASPIRINE",
                "Allergie à l'aspirine : l'ibuprofène est un AINS de la même famille, "
                "une allergie croisée est probable.",
            ),
            _interdit(
                "INSUFFISANCE_RENALE",
                "Insuffisance rénale : AINS contre-indiqués (risque d'insuffisance "
                "rénale aiguë).",
            ),
            _interdit(
                "ASTHME",
                "Asthme sensible à l'aspirine : risque de bronchospasme sévère.",
            ),
            _precaution(
                "ANTICOAGULANT",
                "AINS et anticoagulant : risque hémorragique majoré. Préférer le "
                "paracétamol.",
            ),
            _precaution(
                "HTA",
                "AINS et hypertension : rétention hydrosodée, risque de "
                "décompensation tensionnelle.",
            ),
        ],
    },
    {
        "nom_commercial": "Diclofénac",
        "dci": "Diclofénac",
        "forme": "COMPRIME",
        "dosage": "50mg",
        "classe_therapeutique": "AINS",
        "posologie_adulte": "50 mg, 3 fois par jour, 5 jours",
        "precautions": "Au cours du repas. Réservé aux douleurs aiguës courtes.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_DICLOFENAC",
                "Allergie au diclofénac : AINS interdit.",
            ),
            _interdit(
                "GROSSESSE",
                "AINS et grossesse : contre-indiqué à partir du 6e mois. INTERDIT.",
            ),
            _interdit(
                "INSUFFISANCE_RENALE",
                "Insuffisance rénale : AINS contre-indiqués.",
            ),
            _interdit(
                "ASTHME",
                "Asthme sensible à l'aspirine : risque de bronchospasme.",
            ),
        ],
    },
    {
        "nom_commercial": "Tramadol",
        "dci": "Tramadol",
        "forme": "GELE",
        "dosage": "2,5%",
        "classe_therapeutique": "ANALGESIQUE",
        "posologie_adulte": "Application locale sur la zone douloureuse",
        "precautions": "Usage externe. Dépendance non concernée par la voie locale.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_TRAMADOL",
                "Allergie au tramadol : administration interdite.",
            ),
            _interdit(
                "ASTHME",
                "Tramadol et asthme sévère : risque de bronchospasme.",
            ),
        ],
    },
    # -------------------------------------------------------------- antiseptiques
    {
        "nom_commercial": "Chlorhexidine 0,12%",
        "dci": "Chlorhexidine",
        "forme": "BADEROUCHE",
        "dosage": "0,12%",
        "classe_therapeutique": "ANTISEPTIQUE",
        "posologie_adulte": "Bain de bouche 2 fois par jour pendant 7 jours, sans avaler",
        "precautions": "Ne pas avaler. Coloration transitoire des dents et du palais. "
                      "Utiliser au moins 30 minutes après un bain de bouche acide.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_CHLORHEXIDINE",
                "Allergie à la chlorhexidine : antiseptique interdit.",
            ),
        ],
    },
    {
        "nom_commercial": "Eau oxygénée 3%",
        "dci": "Eau oxygénée",
        "forme": "GELE",
        "dosage": "3%",
        "classe_therapeutique": "ANTISEPTIQUE",
        "posologie_adulte": "Application locale sur la zone concernée",
        "precautions": "Usage externe uniquement. Ne pas appliquer sur une plaie profonde.",
        "contre_indications": [],
    },
    {
        "nom_commercial": "Fluorure de sodium",
        "dci": "Fluorure de sodium",
        "forme": "GELE",
        "dosage": "5%",
        "classe_therapeutique": "ANTISEPTIQUE",
        "posologie_adulte": "Application professionnelle au fauteuil",
        "precautions": "Réservé au professionnel. Protection buccale et gants obligatoires.",
        "contre_indications": [],
    },
    # -------------------------------------------------------------- antifongiques
    {
        "nom_commercial": "Fluconazole",
        "dci": "Fluconazole",
        "forme": "COMPRIME",
        "dosage": "150mg",
        "classe_therapeutique": "ANTIFONGIQUE",
        "posologie_adulte": "150 mg, dose unique",
        "precautions": "Bilan hépatique recommandé si le traitement est répété.",
        "contre_indications": [
            _interdit(
                "GROSSESSE",
                "Fluconazole et grossesse : contre-indiqué.",
            ),
            _interdit(
                "ALLERGIE_FLUCONAZOLE",
                "Allergie au fluconazole : administration interdite.",
            ),
            _precaution(
                "INSUFFISANCE_HEPATIQUE",
                "Insuffisance hépatique : surveillance du bilan hépatique.",
            ),
        ],
    },
    # --------------------------------------------------------- anesthésie locale
    {
        "nom_commercial": "Articaine + Adrénaline",
        "dci": "Articaine + Adrénaline",
        "forme": "CAROUCHE",
        "dosage": "40mg/ml + 0,005%",
        "classe_therapeutique": "ANESTHESIE_LOCALE",
        "posologie_adulte": "Usage professionnel au fauteuil, dose minimale efficace",
        "precautions": "Vérifier l'absence de pathologie cardiaque. Aspiration "
                      "obligatoire. Ne jamais injecter en zone vasculaire.",
        "contre_indications": [
            _interdit(
                "ANTICOAGULANT",
                "Anesthésique à l'adrénaline et anticoagulant : risque d'hémorragie "
                "au site de ponction.",
            ),
            _interdit(
                "ALLERGIE_ADRENALINE",
                "Allergie à l'adrénaline ou aux sulfites : anesthésie locale interdite.",
            ),
            _precaution(
                "HTA",
                "Adrénaline et hypertension non contrôlée : réduire la dose, "
                "contrôler la tension avant injection.",
            ),
            _precaution(
                "DIABETE",
                "Adrénaline et diabète : risque d'hyperglycémie, surveiller.",
            ),
        ],
    },
    {
        "nom_commercial": "Lidocaïne",
        "dci": "Lidocaïne",
        "forme": "CAROUCHE",
        "dosage": "2%",
        "classe_therapeutique": "ANESTHESIE_LOCALE",
        "posologie_adulte": "Usage professionnel au fauteuil, dose minimale efficace",
        "precautions": "Respecter la dose maximale de 4 mg/kg sans adrénaline.",
        "contre_indications": [
            _interdit(
                "ALLERGIE_LIDOCAINE",
                "Allergie à la lidocaïne : anesthésique local interdit.",
            ),
        ],
    },
]
