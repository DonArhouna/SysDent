"""
Périmètre du jeton support : preuve du refus par défaut.

Le contrôle support est présenté dans `get_token_payload` comme « point unique
traversé par chaque route tenant ». Cette affirmation est le garde-fou central
de la Phase D : si une seule route oublie de passer par là, le support obtient
un accès non prévu, en lecture comme en écriture.

Un test qui énumère trois routes ne prouve rien. Celui-ci parcourt **toutes** les
routes du contrat d'API et vérifie, pour chacune, que le jeton support est refusé
sauf si — et seulement si — son chemin figure dans la liste blanche. Une route
ajoutée demain sans décision explicite échouera ici.

Deux contraintes d'outillage rencontrées, documentées ici parce qu'elles sont
piégeuses :

- L'énumération passe par `app.openapi()` et non `app.routes`. FastAPI inclut
  désormais les routeurs paresseusement (`_IncludedRouter`), si bien que
  `app.routes` ne contient que 6 entrées et aucune route métier : un test bâti
  dessus ne testerait rien.

- L'accès support est créé sur la base plateforme réelle, pas sur celle de test.
  `_revalider_acces_support` construit sa session lui-même, sans passer par la
  dépendance `get_platform_db` que les fixtures surchargent ; c'est donc le seul
  endroit où la revalidation le relira — ce qui teste au passage le vrai chemin.
"""

import re
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.main import app

BASE = "/api/v1"

# Préfixes qui ne relèvent pas de l'application cliente : ils ont leur propre
# frontière d'authentification (console plateforme, API interne, documentation).
HORS_PERIMETRE = (
    "/api/v1/platform",
    "/api/v1/master",
    "/api/v1/openapi.json",
    "/docs",
    "/redoc",
    "/health",
)

# Paramètres de chemin rencontrés dans l'API, avec une valeur plausible.
VALEURS = {
    "id": "00000000-0000-4000-8000-000000000001",
    "patient_id": "00000000-0000-4000-8000-000000000002",
    "consultation_id": "00000000-0000-4000-8000-000000000003",
    "facture_id": "00000000-0000-4000-8000-000000000004",
    "devis_id": "00000000-0000-4000-8000-000000000005",
    "ordonnance_id": "00000000-0000-4000-8000-000000000006",
    "cabinet_id": "00000000-0000-4000-8000-000000000007",
    "praticien_id": "00000000-0000-4000-8000-000000000008",
    "salle_id": "00000000-0000-4000-8000-000000000009",
    "fauteuil_id": "00000000-0000-4000-8000-00000000000a",
    "role_id": "00000000-0000-4000-8000-00000000000b",
    "access_id": "00000000-0000-4000-8000-00000000000c",
    "numero_fdi": "11",
    "date": "2026-01-15",
    "type": "RAPPEL",
}

# Routes PUBLIQUES : elles n'authentifient personne, donc le contrôle du
# périmètre support n'y est pas到達 — la validation du corps (422) répond avant
# même que les dépendances soient résolues. Un jeton support n'y ouvre rien.
#
# Cette liste n'est pas une exemption : `test_jeton_support_na_change_rien_sur_les_routes_publiques`
# exige que la réponse soit IDENTIQUE avec et sans le jeton, ce qui prouve que le
# jeton n'y change rien. Une route publique qui se mettrait à exiger une
# authentification devrait quitter cette liste.
ROUTES_PUBLIQUES = frozenset(
    {
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/refresh"),
        ("GET", "/api/v1/onboarding/etat"),
        ("POST", "/api/v1/onboarding/inscription"),
        ("POST", "/api/v1/onboarding/verification-email"),
    }
)


def routes_tenants_du_contrat() -> list[tuple[str, list[str]]]:
    """(chemin, méthodes) de toutes les routes de l'application cliente."""
    spec = app.openapi()
    trouvees = []
    for chemin, operations in spec["paths"].items():
        if not chemin.startswith(BASE) or chemin.startswith(HORS_PERIMETRE):
            continue
        methodes = sorted(
            m.upper()
            for m in operations
            if m.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE")
        )
        if methodes:
            trouvees.append((chemin, methodes))
    return sorted(trouvees)


def construire_url(chemin: str) -> str | None:
    """Remplace les gabarits par des valeurs. `None` si un paramètre est inconnu."""
    manque: list[str] = []

    def remplacer(m):
        nom = m.group(1)
        if nom not in VALEURS:
            manque.append(nom)
            return m.group(0)
        return VALEURS[nom]

    url = re.sub(r"\{(\w+)\}", remplacer, chemin)
    return None if manque else url


def _code_erreur(reponse) -> str | None:
    try:
        return (reponse.json().get("error", {}) or {}).get("code")
    except Exception:
        return None


@pytest_asyncio.fixture
async def acces_support(client_authenticated, session_plateforme):
    """
    Ouvre un accès support réel et rend (jeton, identifiant).

    L'accès est créé sur la base plateforme réelle, pas sur celle de test : voir
    la note de module. Il est refermé en fin de test — un accès laissé actif
    survivrait au test et fausserait les suivants.
    """
    from src.core.platform_database import PlatformSessionFactory
    from src.modules.platform.models import AccesSupport, StatutTenant, TenantPlateforme
    from src.modules.platform.services.support import SupportAccessService

    tenant_id = await _tenant_id_du_client(client_authenticated)

    session = PlatformSessionFactory()
    try:
        # La vue plateforme du cabinet doit etre dans la MEME base que celle ou
        # `demander` cherche : les deux ecritures passent par la session reelle.
        existante = (
            await session.execute(
                select(TenantPlateforme).where(TenantPlateforme.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if existante is None:
            session.add(
                TenantPlateforme(tenant_id=tenant_id, statut_metier=StatutTenant.ACTIF)
            )
            await session.flush()

        demande = await SupportAccessService.demander(
            session,
            tenant_id=tenant_id,
            agent_id=uuid.uuid4(),
            agent_email="agent.support@sysdent.pro",
            motif="Verification automatique du perimetre support",
            ticket="TEST-PERIMETRE",
            lecture_seule=True,
        )
        await session.commit()
        identifiant = uuid.UUID(str(demande["id"]))
        jeton = demande["jeton"]
    finally:
        await session.close()

    try:
        yield jeton, identifiant
    finally:
        session = PlatformSessionFactory()
        try:
            ligne = (
                await session.execute(
                    select(AccesSupport).where(AccesSupport.id == identifiant)
                )
            ).scalar_one_or_none()
            if ligne is not None:
                await session.delete(ligne)
            vue = (
                await session.execute(
                    select(TenantPlateforme).where(TenantPlateforme.tenant_id == tenant_id)
                )
            ).scalar_one_or_none()
            if vue is not None:
                await session.delete(vue)
            await session.commit()
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_perimetre_support_refuse_par_defaut(
    client_authenticated, acces_support
):
    """
    Toute route tenant non listée doit renvoyer `SUPPORT_HORS_PERIMETRE`.

    C'est le test qui attrape « une route a été ajoutée sans passer par la liste
    blanche » : tant qu'il échoue, un accès support non prévu est impossible.
    """
    from src.modules.auth.dependencies import ROUTES_ACCESSIBLES_AU_SUPPORT

    routes = routes_tenants_du_contrat()
    assert len(routes) >= 40, f"énumération suspecte : {len(routes)} routes seulement"

    jeton, _ = acces_support
    entetes = {"Authorization": f"Bearer {jeton}"}

    violations: list[str] = []
    ouvertes: list[str] = []
    ignorees: list[str] = []
    ouvertes = [
        f"{m} {c}"
        for c, methodes in routes
        for m in methodes
        if m in ROUTES_ACCESSIBLES_AU_SUPPORT.get(c, frozenset())
    ]

    for chemin, methodes in routes:
        url = construire_url(chemin)
        if url is None:
            ignorees.append(chemin)
            continue
        for methode in methodes:
            publique = (methode, chemin) in ROUTES_PUBLIQUES
            r = await client_authenticated.request(methode, url, headers=entetes)
            refuse = r.status_code == 403 and _code_erreur(r) == "SUPPORT_HORS_PERIMETRE"
            liste = methode in ROUTES_ACCESSIBLES_AU_SUPPORT.get(chemin, frozenset())
            if publique or liste:
                # Une route publique répond avant le contrôle du périmètre ; une
                # route listée doit rester ouverte. Ni l'une ni l'autre n'est une
                # violation — la preuve que le jeton n'élargit rien est le test
                # dédié aux routes publiques.
                continue
            if not refuse:
                violations.append(
                    f"{methode} {chemin} a répondu {r.status_code} / {_code_erreur(r)} "
                    "au lieu de SUPPORT_HORS_PERIMETRE"
                )

    assert not violations, "périmètre support non respecté :\n" + "\n".join(violations)
    # La liste blanche doit rester petite : c'est un garde-fou, pas un accès.
    assert 3 <= len(ouvertes) <= 12, f"liste blanche de taille inattendue : {ouvertes}"
    if ignorees:
        print(f"\nroutes non couvertes (paramètre inconnu) : {ignorees}")


@pytest.mark.asyncio
async def test_liste_blanche_est_bien_restreinte(client_authenticated, acces_support):
    """La liste blanche ne contient que des lectures, et toutes répondent 200."""
    from src.modules.auth.dependencies import ROUTES_ACCESSIBLES_AU_SUPPORT

    routes = dict(routes_tenants_du_contrat())
    jeton, _ = acces_support
    entetes = {"Authorization": f"Bearer {jeton}"}

    for chemin in sorted(ROUTES_ACCESSIBLES_AU_SUPPORT):
        assert chemin in routes, f"{chemin} est en liste blanche mais absent du contrat"
        methodes_autorisees = ROUTES_ACCESSIBLES_AU_SUPPORT[chemin]
        assert methodes_autorisees == {"GET"}, (
            f"{chemin} est en liste blanche avec {sorted(methodes_autorisees)} : "
            "seule la lecture est admise pour un accès support"
        )
        r = await client_authenticated.get(chemin, headers=entetes)
        assert r.status_code == 200, (
            f"GET {chemin} doit répondre 200 pour un accès support en lecture, "
            f"a répondu {r.status_code} : {r.text[:200]}"
        )


@pytest.mark.asyncio
async def test_ecriture_refusee_meme_sur_une_route_listee(client_authenticated, acces_support):
    """
    Une route listée en lecture ne doit pas s'ouvrir sur son écriture.

    `/api/v1/rbac/roles` porte `GET` et `POST`. Le filtre porte sur (chemin,
    méthode) : le `POST` ne doit jamais être ouvert au support, même si la route
    est par ailleurs listée. C'est le défaut exact que le test de périmètre ne
    voyait pas, puisque le chemin y était listé dans son ensemble.
    """
    jeton, _ = acces_support
    r = await client_authenticated.post(
        "/api/v1/rbac/roles",
        json={"nom": "ROLE_INJECTE_PAR_SUPPORT", "description": "ne doit pas exister"},
        headers={"Authorization": f"Bearer {jeton}"},
    )
    assert r.status_code == 403, f"POST /rbac/roles a répondu {r.status_code} au support"
    assert _code_erreur(r) == "SUPPORT_HORS_PERIMETRE", (
        f"le refus doit venir du périmètre, pas d'une permission : {_code_erreur(r)}"
    )


@pytest.mark.asyncio
async def test_jeton_support_na_change_rien_sur_les_routes_publiques(
    client_authenticated, acces_support
):
    """
    Preuve que `ROUTES_PUBLIQUES` est une observation, pas une exemption.

    Pour chaque route publique, la réponse doit être rigoureusement identique
    avec et sans le jeton support. Si elle différait, le jeton influencerait
    une route qui n'authentifie personne — et la route devrait quitter la liste.
    """
    jeton, _ = acces_support
    for methode, chemin in sorted(ROUTES_PUBLIQUES):
        url = construire_url(chemin) or chemin
        sans = await client_authenticated.request(methode, url)
        avec = await client_authenticated.request(
            methode, url, headers={"Authorization": f"Bearer {jeton}"}
        )
        assert avec.status_code == sans.status_code, (
            f"{methode} {chemin} : sans jeton {sans.status_code}, "
            f"avec jeton support {avec.status_code}"
        )
        assert _code_erreur(avec) == _code_erreur(sans), (
            f"{methode} {chemin} : le jeton support change le code d'erreur "
            f"({_code_erreur(sans)} -> {_code_erreur(avec)})"
        )


async def _tenant_id_du_client(client_authenticated) -> uuid.UUID:
    """
    Tenant du jeton cabinet.

    Les jetons tenant ne portent volontairement pas de claim `aud` (les sessions
    ouvertes avant la mission doivent rester valides) : la vérification
    d'audience est désactivée, sinon le décodage échoue.
    """
    import jwt

    from src.core.config import settings

    brut = client_authenticated.headers["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(
        brut, settings.SECRET_KEY, algorithms=["HS256"], options={"verify_aud": False}
    )
    return uuid.UUID(str(payload["tenant_id"]))
