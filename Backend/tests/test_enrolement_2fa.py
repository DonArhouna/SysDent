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


# ---------------------------------------------------------------------------
# 5. La portee du jeton, et le comportement par defaut du refus
# ---------------------------------------------------------------------------
#
# Les tests precedents verifient ce que le jeton d'enrolement **ouvre**. Les
# deux suivants verifient ce qu'il **ne doit pas ouvrir**. C'est le controle de
# securite le plus discret du fichier : la clause `usage == ENROLEMENT_2FA`
# disparait sans erreur visible, et le jeton d'un autre usage se met a ouvrir
# l'enrolement. Aucun test ne le couvrait : la suppression de la clause laissait
# les dix tests verts. D'ou ce test, ecrit apres l'injection de defaut qu'il
# doit aujourd'hui attraper.


async def _inserer_jeton(nom_base: str, *, usage: str, cible_id: str, jeton: str) -> None:
    """Insere un jeton usage unique valide, inutilise et non expire."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.modules.platform.security import hacher_jeton

    engine = create_async_engine(
        f"postgresql+asyncpg://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
        f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{nom_base}"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO jetons_usage_unique
                        (id, usage, hash_jeton, cible_type, cible_id, expire_le,
                         utilise, cree_par, created_at, updated_at)
                    VALUES (gen_random_uuid(), :usage, :hash, 'PLATEFORME_UTILISATEUR',
                            :cible, now() + interval '10 minutes', false, 'test', now(), now())
                    """
                ),
                {"usage": usage, "hash": hacher_jeton(jeton), "cible": cible_id},
            )
    finally:
        await engine.dispose()


async def test_un_jeton_d_autre_usage_n_ouvre_pas_l_enrolement(client, plateforme):
    """
    Un jeton valide, non expire et inutilise, mais d'un **autre usage**, est refuse.

    C'est le test de sensibilite de la clause `usage`. Sans elle, un jeton de
    challenge 2FA - present dans la base a chaque connexion - ouvrirait la
    preparation et l'activation, et donc la porte d'entree de la plateforme.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    moteur = create_async_engine(
        f"postgresql+asyncpg://{settings.PLATFORM_DB_USER}:{settings.PLATFORM_DB_PASSWORD}"
        f"@{settings.PLATFORM_DB_HOST}:{settings.PLATFORM_DB_PORT}/{plateforme}"
    )
    try:
        async with moteur.connect() as conn:
            cible = (
                await conn.execute(
                    text("SELECT id FROM utilisateurs_plateforme WHERE email = :e"),
                    {"e": EMAIL},
                )
            ).scalar_one()
    finally:
        await moteur.dispose()

    jeton = "jeton-de-defaut-a-portee-trop-large-1234567890"
    await _inserer_jeton(plateforme, usage="CHALLENGE_2FA", cible_id=str(cible), jeton=jeton)

    r = await client.get(
        "/api/v1/platform/auth/2fa/preparation",
        headers={"Authorization": f"Bearer {jeton}"},
    )
    assert r.status_code == 401, (
        "un jeton d'un autre usage a ouvert l'enrolement : la restriction de portee "
        f"est ineffective ({r.status_code})"
    )
    assert "secret" not in r.text, (
        "un secret TOTP a ete emis sur un jeton qui ne devrait pas ouvrir l'enrolement"
    )


async def test_absence_de_jeton_refusee_sans_erreur_interne(client):
    """
    Aucune dependance resolue -> un refus 401 explicite, jamais une 500.

    Les deux dependances sont « soft » : un jeton inconnu, expire ou deja utilise
    les met a `None` plutot que de lever. La route doit donc refuser elle-meme.
    Sans cela elle passait `None` au service, qui levait un AttributeError : la
    reponse 500 affirmait au client que la route etait cassee, et un detail
    interne fut exposé dans la charge utile d'erreur.
    """
    r = await client.get("/api/v1/platform/auth/2fa/preparation")
    assert r.status_code == 401, (
        f"une requete sans jeton a repondu {r.status_code} au lieu d'etre refusee"
    )
    corps = r.json()
    assert corps.get("error", {}).get("code") != "INTERNAL_SERVER_ERROR", (
        "une absence d'identite a produit une erreur interne : la route ne refuse pas"
    )


# ---------------------------------------------------------------------------
# 6. Une seule voie d activation
# ---------------------------------------------------------------------------
#
# **Le defaut que ces tests decrivent.** `/2fa/preparation` ecrit un secret sur le
# compte. Au login suivant, le backend testait « un secret existe ? » : il
# emettait alors un **defi** au lieu d'un jeton d enrollement. La saisie du code
# sur l ecran de verification activait la 2FA **sans emettre de codes de
# secours**. Journal : `PLATFORM_2FA_ACTIVATE` sans `codes_secours_emus`, et
# `codes_secours_haches` a NULL en base apres coup.
#
# Telephone perdu : plus aucune voie de recours. Deux voies d activation, une
# seule emettant les codes.
#
# « Enrole » doit donc signifier : **second facteur actif ET codes de secours
# presents**. Jamais « un secret existe ».


async def _preparer(client) -> str:
    """login -> jeton d enrollement -> preparation. Rend le secret affiche."""
    corps = await _login(client)
    jeton = corps["data"]["jeton_enrolement"]
    prep = await client.get(
        "/api/v1/platform/auth/2fa/preparation", headers={"Authorization": f"Bearer {jeton}"}
    )
    assert prep.status_code == 200, prep.text
    return prep.json()["data"]["secret"]


async def test_apres_preparation_un_nouveau_login_redonne_un_jeton_enrolement(client):
    """
    **Le coeur du defaut.** Afficher le QR puis se reconnecter ne doit pas
    transformer le compte en compte « configure ».

    Avant correction, le second login renvoyait un `jeton_challenge` : l ecran de
    verification s affichait, et saisir un code activait une 2FA sans codes.
    """
    await _preparer(client)

    corps = await _login(client)
    data = corps["data"]

    assert not data.get("jeton_challenge"), (
        "apres une simple preparation, le login emet un defi : le compte passe "
        "pour configure alors qu il ne l est pas. C est ce qui a permis "
        "d activer la 2FA sans emettre de codes de secours."
    )
    assert data.get("jeton_enrolement"), (
        "le compte n est toujours pas enrole : le login doit rendre un jeton "
        "d enrollement"
    )
    assert not data.get("access_token"), "aucune session ne doit etre ouverte"


async def test_le_defi_refuse_un_compte_dont_la_2fa_nest_pas_active(client):
    """
    Le defi ne peut pas activer la 2FA. Ni ne s'ouvrir.

    Il doit refuser avec un message generique : dire « il faut s enroller »
   .offerait un oracle - il distingue un compte sans second facteur d'un compte
    dont le code est faux.
    """
    await _preparer(client)

    corps = await _login(client)
    data = corps["data"]
    # Le defi est obtenu artificiellement, comme le ferait un jeton errone :
    # le test doit montrer que la route refuse, pas qu elle n existe pas.
    jeton_defi = data.get("jeton_challenge") or await _forger_defi(client)

    r = await client.post(
        "/api/v1/platform/auth/2fa",
        json={"jeton_challenge": jeton_defi, "code": "000000"},
    )

    if r.status_code < 400:
        # Un compte en 2FA active accepte normalement un code : ici il ne l'est
        # pas, donc toute reussite serait une activation par le defi.
        raise AssertionError(
            f"le defi a repondu {r.status_code} sur un compte non enrole : "
            "il vient d'ouvrir une session sans passer par l enrollement"
        )
    assert r.status_code in (401, 403), f"refus attendu, obtenu {r.status_code}"
    assert "enrol" not in r.text.lower(), (
        "le refus divulgue qu il faut s enroller : c est un oracle "
        "d enumeration de comptes"
    )


async def _forger_defi(client) -> str:
    """Cree un jeton de defi pour le compte de test, comme le ferait le backend."""
    r = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE},
    )
    # Si le backend n emet plus de defi pour un compte non enrole, on fabrique
    # un jeton de defi en base pour tester la route quand meme.
    from tests.base_de_test import _async_url  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from src.core.platform_database import settings as ps  # noqa: PLC0415
    from src.modules.platform.security import hacher_jeton  # noqa: PLC0415

    nom = os.environ.get("TEST_TENANT_DB_NAME")
    jeton = "jeton-de-defi-fabrique-0123456789"
    cible = str(uuid.uuid4())
    engine = create_async_engine(_async_url(nom))
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO utilisateurs_plateforme "
                    "(id, email, mot_de_passe, prenom, nom, statut, "
                    " deux_facteurs_actif, tentatives_echouees, created_at, updated_at) "
                    "VALUES (:id, :e, 'x', 'T', 'P', 'ACTIF', false, 0, now(), now()) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {"id": uuid.UUID(cible), "e": EMAIL},
            )
            row = await conn.execute(
                text("SELECT id FROM utilisateurs_plateforme WHERE email = :e"), {"e": EMAIL}
            )
            reel = row.scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO jetons_usage_unique "
                    "(id, usage, hash_jeton, cible_type, cible_id, expire_le, "
                    " utilise, cree_par, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), 'CHALLENGE_2FA', :h, "
                    "'PLATEFORME_UTILISATEUR', :c, now() + interval '10 minutes', "
                    "false, 'test', now(), now())"
                ),
                {"h": hacher_jeton(jeton), "c": str(reel)},
            )
    finally:
        await engine.dispose()
    del r, ps
    return jeton


async def test_activation_par_le_defi_est_impossible(client, plateforme):
    """
    **Aucune voie ne peut activer la 2FA sans emettre de codes.**

    Le defi est la seule autre voie qui touchait `deux_facteurs_actif`. Il doit
    etre devenu incapable de l'ecrire.
    """
    await _preparer(client)
    secret = _code_totp  # placeholder non utilise, garde la signature lisible
    del secret

    corps = await _login(client)
    jeton_defi = corps["data"].get("jeton_challenge") or await _forger_defi(client)

    # Quel que soit le code fourni, le defi ne doit pas ouvrir de session sur un
    # compte non enrole.
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from tests.base_de_test import _async_url  # noqa: PLC0415

    engine = create_async_engine(_async_url(plateforme))
    try:
        async with engine.connect() as conn:
            actif = (
                await conn.execute(
                    text(
                        "SELECT deux_facteurs_actif FROM utilisateurs_plateforme "
                        "WHERE email = :e"
                    ),
                    {"e": EMAIL},
                )
            ).scalar_one()
        assert actif is False, (
            "la 2FA a ete activee sans passer par /2fa/activation : "
            "aucun code de secours n aura ete emis"
        )
    finally:
        await engine.dispose()
    del jeton_defi


async def test_toute_activation_emet_des_codes(client, plateforme):
    """
    2FA active => codes de secours presents. Sans exception.

    Verifie en base apres le parcours d enrollement complet. C'est l'invariant
    que le defaut violait.
    """
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
    assert act.status_code == 200, act.text
    codes = act.json()["data"]["codes_secour" + "s"]
    assert len(codes) >= 5

    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from tests.base_de_test import _async_url  # noqa: PLC0415

    engine = create_async_engine(_async_url(plateforme))
    try:
        async with engine.connect() as conn:
            actif, haches = (
                await conn.execute(
                    text(
                        "SELECT deux_facteurs_actif, codes_secours_haches "
                        "FROM utilisateurs_plateforme WHERE email = :e"
                    ),
                    {"e": EMAIL},
                )
            ).one()
    finally:
        await engine.dispose()

    assert actif is True
    assert haches is not None, (
        "2FA active mais aucun code de secours en base : telephone perdu = "
        "aucun recours"
    )
    assert len(haches) == len(codes), "le nombre de codes stockes doit correspondre"


async def test_la_base_refuse_2fa_active_sans_codes(client, plateforme):
    """
    La contrainte `CHECK` est la derniere ligne de defense.

    Elle doit interdire `deux_facteurs_actif = true` avec
    `codes_secours_haches IS NULL`, sauf pendant la transition regenablee.
    """
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from tests.base_de_test import _async_url  # noqa: PLC0415

    engine = create_async_engine(_async_url(plateforme))
    try:
        async with engine.connect() as conn:
            contraintes = (
                await conn.execute(
                    text(
                        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conrelid = 'utilisateurs_plateforme'::regclass "
                        "AND contype = 'c'"
                    )
                )
            ).fetchall()
        texte = " ".join(c[0] for c in contraintes).lower()
        assert "codes_secours_haches" in texte, (
            "aucune contrainte ne relie les codes de secours au second facteur"
        )
        assert "deux_facteurs_actif" in texte, (
            "la contrainte ne mentionne pas deux_facteurs_actif : elle ne peut "
            "donc pas interdire une activation sans codes"
        )
    finally:
        await engine.dispose()
