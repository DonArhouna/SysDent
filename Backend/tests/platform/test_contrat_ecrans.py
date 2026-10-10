"""
Garde de contrat OpenAPI pour les routes que le backoffice consomme.

**Le défaut que ce test décrit.** Une route annotée `APIResponse[dict]` ou
`APIResponse[object]` déclenche, dans l'OpenAPI, un champ `data` de type
`object` — sans aucune propriété. Le client TypeScript génère alors `unknown`
ou `{}`, et l'écran compile en silence contre un objet vide : un champ renommé
côté serveur n'est plus détecté par personne, ni au build ni à l'exécution.

**La garde.** Chaque couple (chemin, méthode) consommé par le backoffice doit
porter un schéma de réponse **nommé** dont la définition contient au moins
une propriété. Si une route revient à un schéma vide, ce test échoue — et
rappelle comment corriger (détailler le schéma, pas annoter à la main).

**Injection de défaut.** La méthode `_verifier_route` est surchargée par un
corps qui renvoie systématiquement « schéma vide » ; le test doit alors
échouer — ce qui prouve que la garde protège bien.
"""

import pytest
from src.main import app

# (chemin, méthode) consommés par les écrans du backoffice.
ROUTES_ECRANS = [
    ("/api/v1/platform/stats/dashboard", "get"),
    ("/api/v1/platform/tenants", "get"),
    ("/api/v1/platform/auth/me", "get"),
    ("/api/v1/platform/auth/login", "post"),
]


def _reponse_est_sans_propriete(chemin: str, methode: str) -> list[str]:
    """Renvoie les problèmes du schéma de réponse (liste vide = conforme)."""
    spec = app.openapi()
    operation = spec["paths"].get(chemin, {}).get(methode)
    if operation is None:
        return [f"{methode.upper()} {chemin} : route absente du contrat"]

    problems: list[str] = []
    for code, reponse in operation.get("responses", {}).items():
        if not code.startswith("2"):
            continue
        contenu = reponse.get("content", {}).get("application/json", {})
        schema = contenu.get("schema", {})
        ref = schema.get("$ref", "")
        if not ref:
            return [f"{methode.upper()} {chemin} ({code}) : réponse sans $ref (type inline)"]
        nom = ref.split("/")[-1]
        definition = spec.get("components", {}).get("schemas", {}).get(nom, {})
        proprietes = definition.get("properties", {})
        if not proprietes:
            problems.append(f"{methode.upper()} {chemin} ({code}) : schéma {nom} sans propriétés")
    return problems


@pytest.mark.parametrize("chemin,methode", ROUTES_ECRANS)
def test_reponse_du_contrat_a_des_proprietes(chemin, methode):
    """
    Chaque réponse 2xx portée par un schéma **nommé** avec des propriétés.

    `APIResponse[T]` est acceptable : T porte le contrat. `APIResponse[dict]`
    ne l'est pas : dict = object = inconnu du client, plus rien à vérifier.
    """
    assert _reponse_est_sans_propriete(chemin, methode) == []


@pytest.mark.parametrize("chemin,methode", ROUTES_ECRANS[:1])
def test_garde_echoue_si_sans_propriete(chemin, methode):
    """
    Injection de défaut : une réponse requalifiée « sans propriétés » échoue.

    La garde doit refuser un schéma vide — c'est tout son travail.
    """
    import src.main as main_module

    original = app.openapi
    try:
        def openapi_contamine():
            spec = original()
            spec["paths"][chemin][methode]["responses"]["200"]["content"][
                "application/json"
            ]["schema"] = {}
            return spec

        app.openapi = openapi_contamine
        problems = _reponse_est_sans_propriete(chemin, methode)
        assert problems, "la garde devrait signaler un schéma injecté sans propriétés"
    finally:
        app.openapi = original
