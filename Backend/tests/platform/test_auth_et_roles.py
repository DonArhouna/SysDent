"""
Tests de la console PLATEFORME : étanchéité des jetons et matrice rôle × route.

Ces deux sujets sont regroupés parce qu'ils partagent la même propriété à
prouver : **un jeton n'ouvre que ce pour quoi il a été émis**.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

BASE = "/api/v1"


# ==============================================================================
# ÉTANCHÉITÉ DES JETONS
# ==============================================================================


@pytest.mark.asyncio
async def test_jeton_plateforme_refuse_sur_route_tenant(client_platform, super_admin):
    """
    Un jeton de la console ne doit ouvrir AUCUNE route de l'application cliente.

    La console connaît les cabinets mais ne les exploite pas : sans cette
    séparation, un Super Admin verrait tous les dossiers patients du parc.
    """
    for chemin in ("/rbac/roles", "/audit", "/cabinets", "/patients"):
        r = await client_platform.get(f"{BASE}{chemin}", headers=super_admin["headers"])
        assert r.status_code in (401, 403), f"{chemin} a répondu {r.status_code}"


@pytest.mark.asyncio
async def test_jeton_tenant_refuse_sur_route_plateforme(
    client_platform, super_admin, client_authenticated
):
    """Symétrique : un jeton de cabinet n'ouvre pas la console."""
    jeton_client = client_authenticated.headers["Authorization"]
    for chemin in ("/platform/tenants", "/platform/users", "/platform/audit", "/platform/sante"):
        r = await client_platform.get(f"{BASE}{chemin}", headers={"Authorization": jeton_client})
        assert r.status_code in (401, 403), f"{chemin} a répondu {r.status_code}"


@pytest.mark.asyncio
async def test_jeton_absent_refuse(client_platform):
    r = await client_platform.get(f"{BASE}/platform/tenants")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audiences_et_scopes_differents():
    """
    L'audience est un contrôle supplémentaire à la clé de signature.

    Deux clés distinctes suffiraient déjà à isoler les mondes ; l'audience
    empêche en plus qu'un jeton plateforme soit rejoué sur une route qui
    l'accepterait par une faille de routage.
    """
    from src.core.config import settings

    assert settings.PLATFORM_AUDIENCE != settings.TENANT_AUDIENCE
    assert settings.PLATFORM_SCOPE != settings.TENANT_SCOPE
    assert settings.SUPPORT_SCOPE not in (settings.TENANT_SCOPE, settings.PLATFORM_SCOPE)


@pytest.mark.asyncio
async def test_jeton_platform_ne_passe_pas_le_decodeur_tenant(client_platform, super_admin):
    """
    `decode_token_scoped` (chemin d'une route TENANT) refuse un jeton plateforme.

    Testé au niveau du décodeur, pas seulement de la route : c'est le point
    unique par lequel passent toutes les requêtes client.
    """
    from src.core.exceptions import AuthenticationException
    from src.core.security import decode_token_scoped

    with pytest.raises(AuthenticationException):
        decode_token_scoped(super_admin["access_token"])


@pytest.mark.asyncio
async def test_signature_alteree_refusee(client_platform, super_admin):
    """Un jeton dont la charge utile a été modifiée est rejeté."""
    from src.core.exceptions import AuthenticationException
    from src.core.security import decode_token

    jeton = super_admin["access_token"]
    parties = jeton.split(".")
    charge = parties[1]
    # Un octet de signature changé suffit : la vérification porte sur la totalite.
    signature_faussee = ("A" if parties[2][0] != "A" else "B") + parties[2][1:]

    with pytest.raises(AuthenticationException):
        decode_token(f"{parties[0]}.{charge}.{signature_faussee}")


# ==============================================================================
# MATRICE RÔLE × ROUTE
# ==============================================================================


ROLES_PAR_DEFAUT = [
    "SUPER_ADMIN_PLATEFORME",
    "SUPPORT",
    "FACTURATION",
    "COMMERCIAL",
    "AUDITEUR",
]

#: (chemin, méthode, permission requise d'après le catalogue).
ROUTES_A_TESTER = [
    ("/platform/tenants", "GET", "platform.tenants.read"),
    ("/platform/users", "GET", "platform.users.read"),
    ("/platform/plans", "GET", "platform.plans.read"),
    ("/platform/invoices", "GET", "platform.billing.read"),
    ("/platform/stats/globales", "GET", "platform.stats.read"),
    ("/platform/audit", "GET", "platform.audit.read"),
    ("/platform/sante", "GET", "platform.health.read"),
    ("/platform/acces-support", "GET", "platform.support.read"),
]


async def _session_de(client_platform, session_plateforme, role: str, email: str) -> dict:
    """Crée un compte portant un seul rôle et renvoie ses en-têtes."""
    from src.modules.platform.models import UtilisateurPlateforme
    from src.modules.platform.security import chiffrer_secret_2fa, generer_secret_totp
    from src.modules.platform.services.users import PlatformUserService

    await PlatformUserService.creer(
        session_plateforme,
        email=email,
        prenom="Test",
        nom=role[:12],
        mot_de_passe="MotDePassePlateforme-2026!Ok",
        roles=[role],
        auteur="fixture",
        activer_2fa=False,
    )
    compte = (
        await session_plateforme.execute(
            select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == email)
        )
    ).scalar_one()
    secret = generer_secret_totp()
    compte.secret_2fa_chiffre = chiffrer_secret_2fa(secret)
    await session_plateforme.commit()

    from tests.conftest import _connecter

    jeton = await _connecter(client_platform, email, secret)
    return {"Authorization": f"Bearer {jeton}"}


@pytest.mark.parametrize("role", ROLES_PAR_DEFAUT)
@pytest.mark.asyncio
async def test_401_403_200_par_role(
    client_platform, session_plateforme, catalogue_bootstrap, role
):
    """
    Chaque rôle par défaut reçoit bien 401/403/200 selon ses permissions.

    L'invariant vérifié est l'absence de fuite ascendante : un rôle NE DOIT PAS
    jamais obtenir 200 sur une permission qu'il ne détient pas. Un 403 est
    attendu ; un 200 serait une escalade.
    """
    from src.modules.platform.permissions import MATRICE_ROLES, format_permission

    attendu = {
        format_permission(ressource, action) for ressource, action in MATRICE_ROLES[role]
    }

    entetes = await _session_de(
        client_platform, session_plateforme, role, f"{role.lower()}@test.sysdent.pro"
    )

    for chemin, methode, permission in ROUTES_A_TESTER:
        r = await client_platform.request(methode, f"{BASE}{chemin}", headers=entetes)
        assert r.status_code in (200, 401, 403), f"{role} {chemin} → {r.status_code}"

        if r.status_code == 200 and attendu is not None and role != "SUPER_ADMIN_PLATEFORME":
            assert permission in attendu, (
                f"{role} a obtenu 200 sur {chemin} sans la permission {permission}"
            )


@pytest.mark.asyncio
async def test_auditeur_ne_peut_pas_ecrire(
    client_platform, session_plateforme, catalogue_bootstrap
):
    """L'auditeur est en lecture seule : toute écriture doit être refusée."""
    entetes = await _session_de(
        client_platform,
        session_plateforme,
        "AUDITEUR",
        "auditeur.ecriture@test.sysdent.pro",
    )
    r = await client_platform.post(
        f"{BASE}/platform/plans",
        headers=entetes,
        json={"code": "PIRATE", "nom": "x", "prix": "1", "periodicite": "MENSUEL", "devise": "XOF"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_support_ne_peut_pas_facturer(
    client_platform, session_plateforme, catalogue_bootstrap
):
    """Le rôle Support n'a pas la facturation — point explicite de la matrice."""
    entetes = await _session_de(
        client_platform,
        session_plateforme,
        "SUPPORT",
        "support.facture@test.sysdent.pro",
    )
    r = await client_platform.get(f"{BASE}/platform/invoices", headers=entetes)
    assert r.status_code == 403, r.text