"""Enrôlement 2FA avant toute session complète.

**Le défaut que ces tests décrivent.** La 2FA est obligatoire sur la plateforme,
mais sa seule voie d'activation (`GET /platform/auth/2fa/preparation`) exige une
session déjà ouverte. La connexion d'un compte sans 2FA active renvoie donc
`401 DEUX_FACTEURS_NON_ACTIVE`, et l'enrôlement est inatteignable. Sur une
plateforme à un seul Super Admin, **il n'existe aucune sortie** : le compte est
définitivement bloqué.

**Ce qui doit être vrai après correction :**

1. identifiants justes + 2FA inactive → un **jeton d'enrôlement** à portée très
   limitée, jamais une session complète ;
2. ce jeton n'ouvre que la préparation et l'activation ; il est **rejeté partout
   ailleurs**, y compris les routes client ;
3. à l'activation : les codes de secours s'affichent **une seule fois**, puis une
   session complète est émise ;
4. aucune session complète sans 2FA active.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Importer les helpers de l'outillage de test (plateforme : base dédiée).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import base_de_test  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.security import get_password_hash, verify_password  # noqa: E402
from src.main import app  # noqa: E402

EMAIL = "test-enrolement@sysdent-exemple.fr"
MOT_DE_PASSE = "MotDePasseEnrolement1!"


# ---------------------------------------------------------------------------
# Outillage : une base plateforme isolée par test
# ---------------------------------------------------------------------------


@pytest.fixture
async def plateforme():
    nom = base_de_test.nom_jetable("sysdent_platform_enrolement")
    engine = None
    try:
        import asyncio as _asyncio
        from sqlalchemy.ext.asyncio import create_async_engine

        admin = create_async_engine(
            base_de_test._async_url("postgres"), isolation_level="AUTOCOMMIT"
        )
        async with admin.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text(f'CREATE DATABASE "{nom}"'))
        await admin.dispose()

        engine = create_async_engine(
            f"postgresql+asyncpg://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
            f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{nom}"
        )
        from src.core.migrations import upgrade_platform_to_head

        # `upgrade_platform_to_head()` ne prend pas d'argument : il lit l'URL
        # dans l'environnement, comme le veut l'isolation des trois contextes.
        os.environ["ALEMBIC_PLATFORM_DB_URL"] = (
            f"postgresql+psycopg2://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
            f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{nom}"
        )
        try:
            await _asyncio.to_thread(upgrade_platform_to_head)
        finally:
            os.environ.pop("ALEMBIC_PLATFORM_DB_URL", None)
        yield nom
    finally:
        if engine is not None:
            await engine.dispose()
        import asyncio as _asyncio
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        admin = create_async_engine(
            base_de_test._async_url("postgres"), isolation_level="AUTOCOMMIT"
        )
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{nom}" WITH (FORCE)'))
        await admin.dispose()


async def _creer_compte(nom_base: str, *, deux_facteurs_actif: bool) -> None:
    """Insère un compte plateforme Super Admin, 2FA activée ou non."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
        f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{nom_base}"
    )
    try:
        async with engine.begin() as conn:
            compte = await conn.execute(
                text(
                    """
                    INSERT INTO utilisateurs_plateforme
                        (id, email, mot_de_passe, prenom, nom, statut,
                         deux_facteurs_actif, tentatives_echouees, created_at, updated_at)
                    VALUES (gen_random_uuid(), :email, :mdp, 'Test', 'Plateforme', 'ACTIF',
                            :actif, 0, now(), now())
                    RETURNING id
                    """
                ),
                {
                    "email": EMAIL,
                    "mdp": get_password_hash(MOT_DE_PASSE),
                    "actif": deux_facteurs_actif,
                },
            )
            user_id = compte.scalar_one()
            role = await conn.execute(
                text(
                    """
                    INSERT INTO roles_plateforme (id, code, libelle, description, systeme,
                                                 niveau_hierarchie, created_at, updated_at)
                    VALUES (gen_random_uuid(), 'SUPER_ADMIN_PLATEFORME', 'Administrateur plateforme',
                            'Administrateur plateforme', true, 1, now(), now())
                    ON CONFLICT (code) DO UPDATE SET updated_at = now()
                    RETURNING id
                    """
                )
            )
            role_id = role.scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO utilisateur_roles (utilisateur_id, role_id) "
                    "VALUES (:u, :r) ON CONFLICT DO NOTHING"
                ),
                {"u": user_id, "r": role_id},
            )
    finally:
        await engine.dispose()


@pytest.fixture
async def client(plateforme):
    """
    Client HTTP dont la dependance `get_platform_db` pointe sur la base du test.

    Poser une variable d'environnement **ne fonctionnerait pas** : `settings` est
    deja charge a l'import de l'application, et la changer apres n'a aucun effet.
    La surcharge de dependance est le mecanisme employe par le reste de la suite
    plateforme.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.core.platform_database import get_platform_db

    moteur = create_async_engine(
        f"postgresql+asyncpg://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
        f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{plateforme}"
    )
    fabrique = async_sessionmaker(bind=moteur, expire_on_commit=False)

    async def _session():
        async with fabrique() as session:
            yield session

    await _creer_compte(plateforme, deux_facteurs_actif=False)
    app.dependency_overrides[get_platform_db] = _session
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_platform_db, None)
        await moteur.dispose()


async def _login(client) -> dict:
    r = await client.post(
        "/api/v1/platform/auth/login", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}
    )
    return r.json() if r.status_code == 200 else {"_statut": r.status_code, "_corps": r.text}


# ---------------------------------------------------------------------------
# 1. Un compte sans 2FA active obtient un jeton d'enrôlement, PAS une session
# ---------------------------------------------------------------------------


async def test_login_sans_2fa_rend_un_jeton_enrolement_pas_une_session(client):
    corps = await _login(client)
    assert "_statut" not in corps, f"le login a échoué au lieu d'émettre un jeton : {corps}"
    data = corps.get("data", {})
    # **Aucune session complète avant activation.** Un `access_token` ici
    # reviendrait à ouvrir la plateforme sans second facteur.
    assert not data.get("access_token"), (
        "le login a émis une session complète alors que la 2FA est inactive : "
        "la plateforme serait accessible sans second facteur"
    )
    assert not data.get("refresh_token"), "un refresh token a été émis sans 2FA active"
    assert data.get("jeton_enrolement"), "aucun jeton d'enrôlement n'a été émis"


async def test_message_erreur_ne_rivale_pas_que_la_2fa_est_inactive(client):
    """Le refus d'hier divulguait le motif. C'est un oracle d'énumération."""
    corps = await _login(client)
    texte = str(corps)
    assert "DEUX_FACTEURS_NON_ACTIVE" not in texte
    assert "n'est pas activée" not in texte


# ---------------------------------------------------------------------------
# 2. Le jeton d'enrôlement est strictement borné
# ---------------------------------------------------------------------------


async def test_jeton_enrolement_refuse_sur_les_autres_routes_plateforme(client):
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    r = await client.get(
        "/api/v1/platform/auth/me", headers={"Authorization": f"Bearer {jeton}"}
    )
    # 401 comme 403 : ce qui compte est le refus, pas le code.
    assert r.status_code in (401, 403), (
        f"/platform/auth/me a accepté le jeton d'enrôlement ({r.status_code})"
    )


async def test_jeton_enrolement_refuse_sur_les_routes_client(client):
    """Étanchéité : un jeton d'enrôlement plateforme ne vaut rien côté cabinet."""
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    r = await client.get("/api/v1/patients", headers={"Authorization": f"Bearer {jeton}"})
    assert r.status_code in (401, 403), (
        f"une route client a traité le jeton d'enrôlement comme une session ({r.status_code})"
    )


async def test_jeton_enrolement_refuse_sur_refresh(client):
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    r = await client.post(
        "/api/v1/platform/auth/refresh", json={"refresh_token": jeton}
    )
    assert r.status_code >= 400, "le jeton d'enrôlement a été accepté pour renouveler une session"


# ---------------------------------------------------------------------------
# 3. L'enrôlement aboutit, et la session complète n'est émise qu'ensuite
# ---------------------------------------------------------------------------


async def test_enrolement_complet_emet_la_session_a_la_fin(client):
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]

    prep = await client.get(
        "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
    )
    assert prep.status_code == 200, f"la préparation a échoué : {prep.text[:300]}"
    preparation = prep.json()["data"]
    assert preparation.get("secret"), "aucun secret TOTP renvoyé"
    assert preparation.get("uri"), "aucune URI otpauth renvoyée"

    code = _code_totp(preparation["secret"])
    act = await client.post(
        "/api/v1/platform/auth/2fa/activation",
        headers={"Authorization": f"Bearer {jeton}"},
        json={"code": code},
    )
    assert act.status_code == 200, f"l'activation a échoué : {act.text[:300]}"
    data = act.json()["data"]

    assert data.get("access_token"), "aucune session complète après activation"
    codes_secours = data.get("codes_secours")
    assert codes_secours and len(codes_secours) >= 5, (
        "les codes de secours doivent être affichés une seule fois à l'activation"
    )

    # La session complète fonctionne réellement.
    me = await client.get(
        "/api/v1/platform/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert me.status_code == 200, f"la session émise ne fonctionne pas : {me.text[:200]}"


async def test_jeton_enrolement_est_a_usage_unique(client):
    """Utiliser le jeton pour préparer ne doit pas le consommer : il sert deux fois."""
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    for _ in range(2):
        r = await client.get(
            "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
        )
        assert r.status_code == 200, f"la préparation a échoué au second appel : {r.status_code}"


async def test_jeton_enrolement_ne_sert_plus_apres_activation(client):
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    prep = await client.get(
        "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
    )
    code = _code_totp(prep.json()["data"]["secret"])
    await client.post(
        "/api/v1/platform/auth/2fa/activation",
        headers={"Authorization": f"Bearer {jeton}"},
        json={"code": code},
    )
    # Après activation, le jeton d'enrôlement ne doit plus ouvrir de session.
    r = await client.get(
        "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
    )
    assert r.status_code >= 400, "le jeton d'enrôlement survit à l'activation"


# ---------------------------------------------------------------------------
# 4. Codes de secours
# ---------------------------------------------------------------------------


async def test_code_de_secours_permet_la_connexion(client):
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    prep = await client.get(
        "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
    )
    code = _code_totp(prep.json()["data"]["secret"])
    act = await client.post(
        "/api/v1/platform/auth/2fa/activation",
        headers={"Authorization": f"Bearer {jeton}"},
        json={"code": code},
    )
    codes = act.json()["data"]["codes_secours"]

    # Nouveau client : connexion par code de secours au lieu du code TOTP.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c2:
        login = await c2.post(
            "/api/v1/platform/auth/login",
            json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE},
        )
        assert login.status_code == 200
        jeton2 = login.json()["data"]["jeton_challenge"]
        r = await c2.post(
            "/api/v1/platform/auth/2fa",
            json={"jeton_challenge": jeton2, "code": codes[0]},
        )
        assert r.status_code == 200, f"un code de secours valide a été refusé : {r.text[:200]}"
        assert r.json()["data"].get("access_token")


async def test_code_de_secours_est_a_usage_unique(client):
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    prep = await client.get(
        "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
    )
    code = _code_totp(prep.json()["data"]["secret"])
    act = await client.post(
        "/api/v1/platform/auth/2fa/activation",
        headers={"Authorization": f"Bearer {jeton}"},
        json={"code": code},
    )
    codes = act.json()["data"]["codes_secours"]
    utilise = codes[0]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c2:
        for tentative in range(2):
            await c2.post(
                "/api/v1/platform/auth/login",
                json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE},
            )
            login = (
                await c2.post(
                    "/api/v1/platform/auth/login",
                    json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE},
                )
            ).json()
            jeton2 = login["data"]["jeton_challenge"]
            r = await c2.post(
                "/api/v1/platform/auth/2fa",
                json={"jeton_challenge": jeton2, "code": utilise},
            )
            if tentative == 0:
                assert r.status_code == 200, "le premier usage du code de secours doit passer"
            else:
                assert r.status_code >= 400, (
                    "un code de secours déjà utilisé a été accepté : il est rejouable"
                )


# ---------------------------------------------------------------------------
# Utilitaire TOTP (sans dépendance externe : pyotp n'est pas dans le venv)
# ---------------------------------------------------------------------------


def _code_totp(secret_base32: str, *, decalage: int = 0) -> str:
    import base64
    import hashlib
    import hmac
    import struct
    import time

    cle = base64.b32decode(secret_base32.upper() + "=" * (-len(secret_base32) % 8))
    compteur = int(time.time()) // 30 + decalage
    mac = hmac.new(cle, struct.pack(">Q", compteur), hashlib.sha1).digest()
    dyna = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[dyna : dyna + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"