"""Preuve HTTP reelle du correctif d'enrolement 2FA.

Tourne CONTRE UNE COPIE de la base plateforme (`sysdent_copie_enrolement`), avec
un compte cree pour la preuve. Ni `rhonekane@gmail.com` ni aucun compte reel
n'est lu, modifie ou reinitialise.

Aucun secret, code ou jeton n'est imprime : seuls les libelles d'etape, les
codes d'etat HTTP et les comptes (longueurs, presences) sont affiches.

**Rejouer la preuve.** Les commandes suivantes recreent la copie — la base
reelle n'est QUE LUE, jamais modifiee :

    docker exec sysdent_s0b psql -U postgres -c "DROP DATABASE IF EXISTS sysdent_copie_enrolement WITH (FORCE)" -c "CREATE DATABASE sysdent_copie_enrolement"
    docker exec sysdent_s0b sh -c "pg_dump -U postgres -Fc -d sysdent_platform -f /tmp/copie.dump && pg_restore -U postgres -d sysdent_copie_enrolement /tmp/copie.dump && rm /tmp/copie.dump"
    cd Backend
    $env:PLATFORM_DB_NAME = "sysdent_copie_enrolement"; .\\.venv\\Scripts\\python.exe -m alembic -c alembic_platform.ini upgrade head
    .\\.venv\\Scripts\\python.exe scripts\\preuve_enrolement_2fa.py

Retour attendu : `BILAN : 16/16 etapes conformes`.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# AVANT tout import de `src` : la base cible est la copie, jamais la reelle.
os.environ["PLATFORM_DB_NAME"] = "sysdent_copie_enrolement"
# `scripts/` vit sous `Backend/` : la racine se deduit du fichier lui-meme, pas
# d'un chemin ecrit a la main.
BACKEND = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, BACKEND)

# `settings` lit `.env` depuis le repertoire de travail : on s'y place pour que
# la cle de chiffrement et les autres reglages soient les memes qu'en service.
os.chdir(BACKEND)

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, null, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.platform_database import platform_engine  # noqa: E402
from src.core.security import get_password_hash  # noqa: E402
from src.main import app  # noqa: E402
from src.modules.platform.models import (  # noqa: E402
    JetonUsageUnique,
    SessionPlateforme,
    StatutUtilisateurPlateforme,
    UtilisateurPlateforme,
)
from src.modules.platform.security import codes_totp, generer_secret_totp  # noqa: E402
from src.modules.platform.services.auth import PlatformAuthService  # noqa: E402

EMAIL = "preuve-enrolement@sysdent-exemple.fr"
# **Aucun secret en dur.** Le mot de passe du compte de preuve est lu dans
# l'environnement ; faute de variable, un mot de passe aleatoire est genere et
# (re)affecte au compte de preuve que CE script possede — jamais a un compte
# reel. Un literal dans le source serait un secret commite.
import os
import secrets as _secrets

MOT_DE_PASSE = os.environ.get("MOT_DE_PASSE_PREUVE_ENROLEMENT") or (
    "Pre-" + _secrets.token_urlsafe(24)
)
MOT_DE_PASSE_IMPOSE = os.environ.get("MOT_DE_PASSE_PREUVE_ENROLEMENT") is None
API = "/api/v1/platform/auth"

facteur = async_sessionmaker(bind=platform_engine, expire_on_commit=False)

resultats: list[tuple[str, bool]] = []


def noter(libelle: str, ok: bool, detail: str = "") -> None:
    resultats.append((libelle, ok))
    suffixe = f"  [{detail}]" if detail else ""
    print(f"{'OK    ' if ok else 'ECHEC '}{libelle}{suffixe}", flush=True)


async def _compte(db) -> UtilisateurPlateforme:
    return (
        await db.execute(
            select(UtilisateurPlateforme).where(UtilisateurPlateforme.email == EMAIL)
        )
    ).scalar_one()


async def _remettre_a_zero(db, utilisateur_id) -> None:
    """Ramene le compte de preuve a l'etat « jamais enrole » (copie jetable)."""
    await db.execute(
        delete(SessionPlateforme).where(SessionPlateforme.utilisateur_id == utilisateur_id)
    )
    await db.execute(
        delete(JetonUsageUnique).where(JetonUsageUnique.cible_id == str(utilisateur_id))
    )
    compte = (
        await db.execute(
            select(UtilisateurPlateforme).where(
                UtilisateurPlateforme.id == utilisateur_id
            )
        )
    ).scalar_one()
    compte.deux_facteurs_actif = False
    compte.secret_2fa_chiffre = None
    compte.secret_2fa_en_attente = None
    compte.deux_facteurs_confirme_at = None
    compte.codes_secours_haches = null()
    compte.codes_secours_a_regenerer = False
    compte.tentatives_echouees = 0
    compte.verrouille_jusqua = None
    await db.commit()


async def main() -> int:
    async with platform_engine.begin() as connexion:
        await connexion.execute(text("SELECT 1"))

    # ── Compte de preuve (cree pour la preuve, jamais un compte reel) ─────────
    async with facteur() as db:
        existant = (
            await db.execute(
                select(UtilisateurPlateforme).where(
                    UtilisateurPlateforme.email == EMAIL
                )
            )
        ).scalar_one_or_none()
        if existant is not None:
            utilisateur_id = existant.id
            await _remettre_a_zero(db, utilisateur_id)
            if MOT_DE_PASSE_IMPOSE:
                # Le mot de passe aleatoire change a chaque execution : on le
                # remet sur le compte de preuve — et seulement sur lui.
                existant.mot_de_passe = get_password_hash(MOT_DE_PASSE)
                await db.commit()
        else:
            compte = UtilisateurPlateforme(
                email=EMAIL,
                mot_de_passe=get_password_hash(MOT_DE_PASSE),
                prenom="Preuve",
                nom="Enrolement",
                statut=StatutUtilisateurPlateforme.ACTIF,
                deux_facteurs_actif=False,
            )
            db.add(compte)
            await db.flush()
            utilisateur_id = compte.id
            await db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://preuve.local"
    ) as client:
        login_json = {"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}

        # 1. Login d'un compte sans 2FA active -> jeton d'enrolement, JAMAIS de session
        r = await client.post(f"{API}/login", json=login_json)
        donnees = r.json().get("data") or {}
        jeton_enrolement = donnees.get("jeton_enrolement")
        noter(
            "1. login sans 2FA active -> jeton d'enrolement, aucune session",
            r.status_code == 200
            and bool(jeton_enrolement)
            and not donnees.get("access_token")
            and not donnees.get("jeton_challenge"),
            f"statut={r.status_code}",
        )

        # 2. Preparation avec ce jeton -> secret affiche une fois
        r = await client.get(
            f"{API}/2fa/preparation",
            headers={"Authorization": f"Bearer {jeton_enrolement}"},
        )
        preparation = r.json().get("data") or {}
        secret_connue = preparation.get("secret") or ""
        noter(
            "2. preparation (jeton d'enrolement) -> secret affiche une fois",
            r.status_code == 200 and len(secret_connue) > 10,
            f"statut={r.status_code}",
        )

        # 3. Login A PREPARATION : toujours un jeton d'enrolement, jamais un defi
        r = await client.post(f"{API}/login", json=login_json)
        donnees = r.json().get("data") or {}
        jeton_enrolement = donnees.get("jeton_enrolement")
        noter(
            "3. login apres preparation -> toujours un jeton d'enrolement, jamais un defi",
            r.status_code == 200
            and bool(jeton_enrolement)
            and not donnees.get("jeton_challenge"),
            f"statut={r.status_code}",
        )

        # 4. Un defi provoque sur ce compte NON enrole -> refuse, et n'active RIEN
        async with facteur() as db:
            compte = await _compte(db)
            jeton_defi = await PlatformAuthService._emettre_challenge(
                db, compte, client_ip="127.0.0.1", user_agent="preuve-http"
            )
            await db.commit()
        # Code VALIDE au sens TOTP, calcule sur le secret en attente : meme le
        # bon code ne doit pas passer, puisque le compte n'est pas enrole.
        code_valide = codes_totp(secret_connue)[0]
        r = await client.post(
            f"{API}/2fa", json={"jeton_challenge": jeton_defi, "code": code_valide}
        )
        corps = r.text.lower()
        async with facteur() as db:
            compte = await _compte(db)
            etat = (
                compte.deux_facteurs_actif,
                compte.secret_2fa_chiffre,
                compte.codes_secours_haches,
            )
        noter(
            "4. defi sur compte non enrole -> 401 generique, 2FA jamais activee",
            r.status_code == 401
            and "enrol" not in corps
            and "deux facteurs" not in corps
            and etat == (False, None, None),
            f"statut={r.status_code}",
        )

        # 5. Activation -> 10 codes affiches UNE fois + session complete
        code_valide = codes_totp(secret_connue)[0]
        r = await client.post(
            f"{API}/2fa/activation",
            headers={"Authorization": f"Bearer {jeton_enrolement}"},
            json={"code": code_valide},
        )
        donnees = r.json().get("data") or {}
        codes = donnees.get("codes_secours") or []
        jeton_session = donnees.get("access_token")
        entetes_session = {"Authorization": f"Bearer {jeton_session}"}
        noter(
            "5. activation (TOTP sur le secret en attente) -> 10 codes + session",
            r.status_code == 200 and len(codes) == 10 and bool(jeton_session),
            f"statut={r.status_code}, codes={len(codes)}",
        )

        # 6. /auth/me -> 2FA active, indicateur de regeneration a False
        r = await client.get(f"{API}/me", headers=entetes_session)
        donnees = r.json().get("data") or {}
        noter(
            "6. /auth/me -> deux_facteurs_actif true, indicateur a false",
            r.status_code == 200
            and donnees.get("deux_facteurs_actif") is True
            and donnees.get("codes_secours_a_regenerer") is False,
            f"statut={r.status_code}",
        )

        # 7. Reconnexion -> defi TOTP -> session
        r = await client.post(f"{API}/login", json=login_json)
        donnees = r.json().get("data") or {}
        jeton_defi = donnees.get("jeton_challenge")
        code_valide = codes_totp(secret_connue)[0]
        r2 = await client.post(
            f"{API}/2fa", json={"jeton_challenge": jeton_defi, "code": code_valide}
        )
        noter(
            "7. reconnexion -> defi TOTP -> session ouverte",
            r.status_code == 200
            and bool(jeton_defi)
            and not donnees.get("jeton_enrolement")
            and r2.status_code == 200
            and bool((r2.json().get("data") or {}).get("access_token")),
            f"login={r.status_code}, defi={r2.status_code}",
        )

        # 8. Un code de secours ouvre la session... (usage 1/1)
        ancien_code = codes[0]
        r = await client.post(f"{API}/login", json=login_json)
        jeton_defi = (r.json().get("data") or {}).get("jeton_challenge")
        r2 = await client.post(
            f"{API}/2fa", json={"jeton_challenge": jeton_defi, "code": ancien_code}
        )
        noter(
            "8. code de secours -> accepte la premiere fois",
            r2.status_code == 200,
            f"statut={r2.status_code}",
        )

        # 9. ... et refuse des la deuxieme (usage unique)
        r = await client.post(f"{API}/login", json=login_json)
        jeton_defi = (r.json().get("data") or {}).get("jeton_challenge")
        r2 = await client.post(
            f"{API}/2fa", json={"jeton_challenge": jeton_defi, "code": ancien_code}
        )
        noter(
            "9. meme code de secours -> refuse la deuxieme fois",
            r2.status_code == 401,
            f"statut={r2.status_code}",
        )

        # 10. Le jeton d'enrolement est consomme : il ne sert plus a rien
        code_valide = codes_totp(secret_connue)[0]
        r = await client.post(
            f"{API}/2fa/activation",
            headers={"Authorization": f"Bearer {jeton_enrolement}"},
            json={"code": code_valide},
        )
        noter(
            "10. jeton d'enrolement rejoue apres activation -> refuse",
            r.status_code in (401, 403),
            f"statut={r.status_code}",
        )

        # ── Phase B : etat legacy simule (2FA active, aucun code) ────────────
        # Exactement l'etat du compte Super Admin reel, reproduit sur le compte
        # de preuve : la base reelle n'est pas touchee.
        async with facteur() as db:
            compte = await _compte(db)
            compte.deux_facteurs_actif = True
            compte.codes_secours_haches = null()
            compte.codes_secours_a_regenerer = True
            await db.commit()

        r = await client.post(f"{API}/login", json=login_json)
        donnees = r.json().get("data") or {}
        jeton_defi = donnees.get("jeton_challenge")
        code_valide = codes_totp(secret_connue)[0]
        r2 = await client.post(
            f"{API}/2fa", json={"jeton_challenge": jeton_defi, "code": code_valide}
        )
        entetes_session = {
            "Authorization": f"Bearer {(r2.json().get('data') or {}).get('access_token')}"
        }
        r3 = await client.get(f"{API}/me", headers=entetes_session)
        donnees_me = r3.json().get("data") or {}
        noter(
            "11. 2FA active sans codes -> /auth/me signale codes_secours_a_regenerer",
            donnees_me.get("codes_secours_a_regenerer") is True,
            f"statut={r3.status_code}",
        )

        # 12. Regeneration : un mauvais TOTP est refuse...
        pas_de_temps = time.time() - settings.PLATFORM_2FA_TOTP_INTERVAL * 100
        code_faux = codes_totp(secret_connue, instant=pas_de_temps)[0]
        r = await client.post(
            f"{API}/2fa/codes-secours/regenerer",
            headers=entetes_session,
            json={"code": code_faux, "motif": "preuve http enrollement"},
        )
        noter(
            "12. regeneration avec un TOTP expire -> refuse (401)",
            r.status_code == 401,
            f"statut={r.status_code}",
        )

        # 13. ... puis TOTP valide + motif -> dix nouveaux codes, indicateur a False
        code_valide = codes_totp(secret_connue)[0]
        r = await client.post(
            f"{API}/2fa/codes-secours/regenerer",
            headers=entetes_session,
            json={"code": code_valide, "motif": "preuve http enrollement"},
        )
        nouveaux_codes = (r.json().get("data") or {}).get("codes_secours") or []
        r_me = await client.get(f"{API}/me", headers=entetes_session)
        me = r_me.json().get("data") or {}
        noter(
            "13. regeneration -> 10 nouveaux codes (lot different), indicateur a False",
            r.status_code == 200
            and len(nouveaux_codes) == 10
            and set(nouveaux_codes).isdisjoint(set(codes))
            and me.get("codes_secours_a_regenerer") is False,
            f"statut={r.status_code}, nouveaux={len(nouveaux_codes)}",
        )

        # 14. L'ancien lot est invalide apres regeneration
        r = await client.post(f"{API}/login", json=login_json)
        jeton_defi = (r.json().get("data") or {}).get("jeton_challenge")
        r2 = await client.post(
            f"{API}/2fa", json={"jeton_challenge": jeton_defi, "code": ancien_code}
        )
        noter(
            "14. ancien code de secours apres regeneration -> refuse",
            r2.status_code == 401,
            f"statut={r2.status_code}",
        )

    # 15. Le journal ne contient AUCUN code (ni ancien, ni nouveau)
    async with facteur() as db:
        lignes = (
            await db.execute(
                text(
                    "SELECT action || ' ' || COALESCE(motif, '') || ' ' "
                    "|| COALESCE(avant::text, '') || ' ' || COALESCE(apres::text, '') "
                    "FROM journal_audit_plateforme"
                )
            )
        ).scalars().all()
    bloc = "\n".join(lignes)
    fuites = [c for c in codes + nouveaux_codes if c in bloc]
    noter(
        "15. journal d'audit : aucun code de secours n'y figure",
        not fuites,
        f"{len(fuites)} fuite(s)",
    )
    noter(
        "16. journal d'audit : le motif de regeneration est consigne",
        "preuve http enrollement" in bloc,
    )

    # Le compte de preuve est remis a zero : la copie ne garde aucun etat utile.
    async with facteur() as db:
        await _remettre_a_zero(db, utilisateur_id)

    await platform_engine.dispose()

    total = len(resultats)
    bons = sum(1 for _, ok in resultats if ok)
    print(f"\nBILAN : {bons}/{total} etapes conformes", flush=True)
    return 0 if bons == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
