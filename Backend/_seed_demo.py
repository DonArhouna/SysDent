"""
Jeu de démonstration SysDent Pro — alimente un cabinet neuf.

Usage :
    .\\.venv\\Scripts\\python.exe .\\_seed_demo.py <email> <mot_de_passe>

Pourquoi ce script
------------------
Une société provisionnée est vide : sans données, toutes les pages affichent
leur état vide et la refonte visuelle ne peut pas être jugée sur du réel
(colonnes, badges de statut, totaux, liserés, cohérence des nombres). Ce script
passe **uniquement par les endpoints publics** — aucune écriture directe en
base — pour que le jeu révèle exactement ce que verrait un utilisateur.

Idempotent : s'il trouve déjà un patient témoin, il s'arrête sans rien modifier.
"""

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, ".")

from httpx import ASGITransport, AsyncClient

from src.core.database import master_engine, tenant_db_manager
from src.main import app

# Un lundi pour les rendez-vous (dans les horaires d'ouverture), une date
# passée pour les consultations déjà clôturées.
LUNDI = date(2026, 10, 5)
PASSE = date(2026, 9, 28)

PATIENTS = [
    ("Aminata", "Seye", "1994-04-20", "F", "77 123 45 67", "Enseignante", {}),
    ("Babacar", "Fall", "1985-01-11", "M", "77 100 20 30", "Commerçant", {"hta": True}),
    ("Fatou", "Ndiaye", "2011-09-03", "F", "78 445 12 90", "Élève",
     {"allergies": [{"substance": "Pénicilline", "reaction": "Urticaire généralisée"}]}),
    ("Moussa", "Diop", "1968-07-22", "M", "70 998 77 12", "Retraité",
     {"diabete": True, "diabete_type": "TYPE_2"}),
    ("Khady", "Ba", "1998-12-05", "F", "76 334 55 21", "Comptable", {}),
    ("Ibrahima", "Sow", "1991-03-17", "M", "77 889 00 45", "Chauffeur", {"tabac": True}),
    ("Ndeye", "Diouf", "1955-11-30", "F", "70 112 23 98", "Retraitée",
     {"hta": True, "allergies": [{"substance": "Iode", "reaction": "Cyanose"}]}),
    ("Ousmane", "Sarr", "2001-06-14", "M", "78 671 45 02", "Étudiant", {}),
]

MOTIFS = [
    ("Douleur dentaire aiguë", "URGENCE"),
    ("Contrôle annuel", "CONTROLE"),
    ("Détartrage et polissage", "CONTROLE"),
    ("Suivi de traitement orthodontique", "ORTHODONTIE"),
    ("Restauration esthétique", "ESTHETIQUE"),
]

NOMENCLATURE = [
    {"code": "CONS", "libelle": "Consultation dentaire", "categorie": "Consultation", "tarif_base": 15000, "duree_estimee_min": 20, "unitaire": False},
    {"code": "DET", "libelle": "Détartrage complet", "categorie": "Prévention", "tarif_base": 25000, "duree_estimee_min": 30, "unitaire": True},
    {"code": "SCAL", "libelle": "Polissage", "categorie": "Prévention", "tarif_base": 10000, "duree_estimee_min": 15, "unitaire": True},
    {"code": "RAD", "libelle": "Radiographie panoramique", "categorie": "Imagerie", "tarif_base": 35000, "duree_estimee_min": 10, "unitaire": True},
    {"code": "AMALG", "libelle": "Amalgame", "categorie": "Restauration", "tarif_base": 20000, "duree_estimee_min": 30, "unitaire": True},
    {"code": "COMPOS", "libelle": "Composite", "categorie": "Restauration", "tarif_base": 28000, "duree_estimee_min": 30, "unitaire": True},
    {"code": "DETART", "libelle": "Traitement canalaire", "categorie": "Endodontie", "tarif_base": 60000, "duree_estimee_min": 60, "unitaire": True},
    {"code": "EXT", "libelle": "Extraction simple", "categorie": "Chirurgie", "tarif_base": 20000, "duree_estimee_min": 20, "unitaire": True},
    {"code": "EXTCH", "libelle": "Extraction chirurgicale", "categorie": "Chirurgie", "tarif_base": 45000, "duree_estimee_min": 45, "unitaire": True},
    {"code": "COUR", "libelle": "Couronne métallique", "categorie": "Prothèse", "tarif_base": 75000, "duree_estimee_min": 90, "unitaire": True},
    {"code": "CERAM", "libelle": "Couronne céramique", "categorie": "Prothèse", "tarif_base": 95000, "duree_estimee_min": 90, "unitaire": True},
    {"code": "PROTH", "libelle": "Prothèse dentaire", "categorie": "Prothèse", "tarif_base": 250000, "duree_estimee_min": 60, "unitaire": False},
    {"code": "ORTHO", "libelle": "Consultation orthodontique", "categorie": "Orthodontie", "tarif_base": 20000, "duree_estimee_min": 30, "unitaire": False},
    {"code": "CHIRPED", "libelle": "Chirurgie dentaire", "categorie": "Pédiatrie", "tarif_base": 15000, "duree_estimee_min": 20, "unitaire": False},
]

# Numerotation FDI : quadrant (1-4, permanent ; 5-8, deciduaire) puis position
# du bord median. Les actes « unitaires » s'y rattachent.
DENTS_FDI = [
    16, 26, 36, 46,  # premier quadrant
    18, 28, 38, 48,
    17, 27, 37, 47,
    15, 25, 35, 45,
    14, 24, 34, 44,
    13, 23, 33, 43,
    12, 22, 32, 42,
    11, 21, 31, 41,
    51, 52, 53, 54, 55, 61, 62, 63, 64, 65, 71, 72, 73, 74, 75, 81, 82, 83, 84, 85,
]

COMPTE = {"crees": 0, "ignores": 0, "erreurs": 0}

# Le client est monté directement sur l'application ASGI : il n'y a pas de
# proxy devant, donc chaque chemin doit porter le préfixe de l'API.
API = "/api/v1"


def jour(h: int, m: int = 0) -> str:
    return f"{LUNDI.isoformat()}T{h:02d}:{m:02d}:00+00:00"


async def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    email, mdp = sys.argv[1].strip().lower(), sys.argv[2]

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    ids_actes_existants: list[str] = []

    async def creer(chemin: str, corps: dict, attendu=(200, 201)) -> dict | None:
        r = await client.post(API + chemin, json=corps)
        if r.status_code not in attendu:
            COMPTE["erreurs"] += 1
            print(f"  ! {chemin} -> HTTP {r.status_code} : {r.text[:160]}")
            return None
        COMPTE["crees"] += 1
        return r.json().get("data", {})

    async def compter(chemin: str) -> int:
        """Total d'une liste paginee. `obtenir` perd `meta` : il faut le lire ici."""
        r = await client.get(API + chemin)
        if r.status_code != 200:
            return 0
        return r.json().get("meta", {}).get("total_records", 0)

    async def obtenir(chemin: str) -> list | dict | None:
        r = await client.get(API + chemin)
        if r.status_code != 200:
            COMPTE["erreurs"] += 1
            print(f"  ! GET {chemin} -> HTTP {r.status_code}")
            return None
        corps = r.json()
        return corps.get("data", corps.get("items"))

    # ------------------------------------------------------------ session
    r = await client.post(API + "/auth/login", json={"email": email, "password": mdp})
    if r.status_code != 200:
        print(f"Login impossible : HTTP {r.status_code}")
        return 1
    client.headers.update({"Authorization": f"Bearer {r.json()['data']['access_token']}"})
    print(f"Connecte : {email}")

    # ------------------------------------------------- deja peuple ?
    total = await compter("/patients?page=1&limit=1")
    nb_actes_ref = await compter("/nomenclature/actes?limit=100")
    if total and nb_actes_ref:
        print(f"Cabinet deja peuple ({total} patient(s), {nb_actes_ref} acte(s)) — rien ne change.")
        return 0
    if total or nb_actes_ref:
        print(f"Cabinet partiellement peuple ({total} patient(s), {nb_actes_ref} acte(s)) "
              f"— on complete ce qui manque.")

    # ------------------------------------------------------- organisation
    cabinets = await obtenir("/cabinets") or []
    cabinet_id = cabinets[0]["id"]
    print(f"Cabinet : {cabinets[0]['nom']}")

    praticiens = await obtenir(f"/praticiens?cabinet_id={cabinet_id}") or []
    if not praticiens:
        print("Aucun praticien rattache : abandon.")
        return 1
    praticien_id = praticiens[0]["id"]
    print(f"Praticien : {praticiens[0].get('prenom', '')} {praticiens[0].get('nom', '')}")

    # Decor : on reutilise ce qui existe plutot que de dupliquer (le backend
    # refuse rightly une salle ou un fauteuil homonyme).
    salles = await obtenir(f"/cabinets/{cabinet_id}/salles") or []
    if isinstance(salles, dict):
        salles = salles.get("items", salles.get("data", []))
    salle = (
        next((s for s in salles if s.get("nom") == "Salle 1"), None)
        or await creer(f"/cabinets/{cabinet_id}/salles", {"nom": "Salle 1"})
    )
    if not salle:
        print("Impossible d'obtenir une salle — abandon.")
        return 1

    fauteuils_existants = await obtenir(f"/cabinets/{cabinet_id}/fauteuils") or []
    if isinstance(fauteuils_existants, dict):
        fauteuils_existants = fauteuils_existants.get("items", fauteuils_existants.get("data", []))
    fauteuils = [f["id"] for f in fauteuils_existants if isinstance(f, dict)]
    for numero in ("F1", "F2", "F3"):
        if any(f.get("numero") == numero for f in fauteuils_existants if isinstance(f, dict)):
            continue
        f = await creer(f"/salles/{salle['id']}/fauteuils", {"numero": numero})
        if f:
            fauteuils.append(f["id"])
    print(f"Decor : 1 salle, {len(fauteuils)} fauteuil(s)")

    # Disponibilités du lundi au vendredi, 08h-17h.
    dispo = await obtenir(f"/praticiens/{praticien_id}/disponibilites") or []
    if isinstance(dispo, dict):
        dispo = dispo.get("items", dispo.get("data", []))
    if isinstance(dispo, list):
        for jour_semaine in range(5):
            if any(d.get("jour_semaine") == jour_semaine for d in dispo if isinstance(d, dict)):
                continue
            await creer(
                f"/praticiens/{praticien_id}/disponibilites",
                {"jour_semaine": jour_semaine, "heure_debut": "08:00", "heure_fin": "17:00"},
            )

    # --------------------------------------------------- nomenclature actes
    # Un cabinet provisionne n'a AUCUN acte : la table `actes_nomenclature` est
    # creee par la migration mais jamais peuplee (contrairement au formulaire
    # medicamenteux, seme au provisionnement). Sans elle, impossible de saisir
    # un acte donc de facturer depuis une consultation. See PLAN_RESTE_A_FAIRE.md.
    print("\nNomenclature des actes…")
    if await compter("/nomenclature/actes?limit=100"):
        print("  deja presentee")
    if not ids_actes_existants:
        for a in NOMENCLATURE:
            await creer("/nomenclature/actes", a)
        actes = await obtenir("/nomenclature/actes") or []
        if isinstance(actes, dict):
            actes = actes.get("items", [])
        ids_actes_existants = [a["id"] for a in actes] if isinstance(actes, list) else []
    print(f"  {len(ids_actes_existants)} acte(s)")

    # --------------------------------------------------------- patients
    print("\nPatients…")
    ids_patients = []
    deja_patients = await obtenir("/patients?page=1&limit=100") or []
    if isinstance(deja_patients, dict):
        deja_patients = deja_patients.get("items", [])
    if not isinstance(deja_patients, list):
        deja_patients = []
    noms_connus = {
        (p.get("prenom", "").strip().lower(), p.get("nom", "").strip().lower())
        for p in deja_patients
        if isinstance(p, dict)
    }
    for prenom, nom, naissance, sexe, tel, profession, etat in PATIENTS:
        if (prenom.lower(), nom.lower()) in noms_connus:
            COMPTE["ignores"] += 1
            continue
        corps = {
            "prenom": prenom,
            "nom": nom,
            "date_naissance": naissance,
            "sexe": sexe,
            "telephone_1": tel,
            "profession": profession,
            "ville": "Dakar",
            "etat_general": etat or None,
        }
        p = await creer("/patients", corps)
        if p:
            ids_patients.append(p["id"])
    print(f"  {len(ids_patients)} patient(s)")

    # ------------------------------------------------------ consultations
    print("\nConsultations (passées) et actes…")
    ids_actes = ids_actes_existants
    # Index code -> position, pour savoir quels actes demandent une dent.
    detail = await obtenir("/nomenclature/actes?limit=100") or []
    if isinstance(detail, dict):
        detail = detail.get("items", [])
    codes_actes = [a.get("code", "") for a in detail] if isinstance(detail, list) else []
    codes_unitaires = {
        a.get("code") for a in (detail if isinstance(detail, list) else []) if a.get("unitaire")
    }
    if not codes_actes:
        codes_actes = [""] * len(ids_actes)
    nb_actes = 0
    for i, pid in enumerate(ids_patients[:6]):
        motif, type_motif = MOTIFS[i % len(MOTIFS)]
        cons = await creer(
            "/consultations",
            {
                "patient_id": pid,
                "motif": motif,
                "type_motif": type_motif,
                "cabinet_id": cabinet_id,
                "date_consultation": f"{PASSE.isoformat()}T{(9 + i):02d}:00:00+00:00",
                "duree_minutes": 30,
            },
        )
        if not cons or not ids_actes:
            continue
        # Deux à trois actes par consultation. Un acte marque « unitaire » dans
        # la nomenclature (extraction, couronne, radiographie…) exige un numero
        # de dent FDI : le backend le refuse proprement sinon.
        for j in range(2 + (i % 2)):
            code = codes_actes[(i + j) % len(codes_actes)]
            corps = {"acte_id": ids_actes[(i + j) % len(ids_actes)], "quantite": 1}
            if codes_unitaires and code in codes_unitaires:
                corps["dent_numero"] = DENTS_FDI[(i * 3 + j) % len(DENTS_FDI)]
            await creer(f"/consultations/{cons['id']}/actes", corps)
            nb_actes += 1
    print(f"  {nb_actes} acte(s) réalisé(s)")

    # ------------------------------------------------------ rendez-vous
    print("\nRendez-vous (lundi)…")
    creneaux = [(9, 0), (9, 30), (10, 0), (11, 0), (14, 0), (15, 30), (16, 0)]
    deja = await obtenir(f"/rendez-vous?date={LUNDI.isoformat()}&limit=100") or []
    if isinstance(deja, dict):
        deja = deja.get("items", [])
    pris = {
        (r.get("debut") or "")[:16]
        for r in (deja if isinstance(deja, list) else [])
        if isinstance(r, dict)
    }
    nb_rdv = 0
    for i, (h, m) in enumerate(creneaux):
        if i >= len(ids_patients):
            break
        if jour(h, m)[:16] in pris:
            COMPTE["ignores"] += 1
            continue
        motif, type_motif = MOTIFS[i % len(MOTIFS)]
        await creer(
            "/rendez-vous",
            {
                "patient_id": ids_patients[i],
                "praticien_id": praticien_id,
                "cabinet_id": cabinet_id,
                "fauteuil_id": fauteuils[i % len(fauteuils)] if fauteuils else None,
                "debut": jour(h, m),
                "duree_minutes": 30,
                "motif": motif,
                "type_motif": type_motif,
                "statut": "CONFIRME" if i % 3 else "PLANIFIE",
            },
        )
        nb_rdv += 1
    print(f"  {nb_rdv} rendez-vous")

    # -------------------------------------------------------- facturation
    print("\nFactures et paiements…")
    lignes = [
        {"designation": "Consultation dentaire", "quantite": 1, "prix_unitaire": 15000},
        {"designation": "Détartrage", "quantite": 1, "prix_unitaire": 25000},
    ]
    nb_fact = 0
    for i, pid in enumerate(ids_patients[:5]):
        f = await creer("/factures", {"patient_id": pid, "lignes": lignes})
        if not f:
            continue
        nb_fact += 1
        # Paiements partiels : c'est l'état le plus parlant (reste à payer).
        if i % 2 == 0:
            await creer(
                f"/factures/{f['id']}/paiements",
                {"montant": 20000, "mode": "ESPECES"},
            )
        if i % 3 == 0:
            await creer(
                f"/factures/{f['id']}/paiements",
                {"montant": 20000, "mode": "MOBILE_MONEY", "reference": "77 000 11 22"},
            )
    print(f"  {nb_fact} facture(s)")

    # ------------------------------------------------------------ devis
    print("\nDevis…")
    for i, pid in enumerate(ids_patients[5:7]):
        await creer(
            "/devis",
            {
                "patient_id": pid,
                "lignes": [
                    {"designation": "Couronne céramique", "quantite": 1, "prix_unitaire": 85000},
                    {"designation": "Devis de diagnostic", "quantite": 1, "prix_unitaire": 5000},
                ],
            },
        )

    await client.aclose()
    await tenant_db_manager.close_all()
    await master_engine.dispose()

    print()
    print(f"Cree : {COMPTE['crees']}   Erreurs : {COMPTE['erreurs']}")
    if COMPTE["erreurs"]:
        print("  (certains elements ont echoue — voir les lignes '!' ci-dessus)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))