"""
Jeu de démonstration complet : remplit **toutes** les rubriques du frontend.

Usage (depuis `Backend/`, venv activé) :

    python _seed_complet.py --email admin@cabinet.sn

Complète `_seed_demo.py` (patients, actes, consultations, factures, devis) avec
ce qu'il ne couvre pas :

- équipe : secrétaire, assistant, comptable, gestionnaire de stock, second praticien ;
- tarification : catégories de patients, organismes, droits de prise en charge ;
- agenda autour d'aujourd'hui : passé terminé (consultation, actes, facture,
  paiement), absences, annulations, journée en cours, semaines à venir ;
- ordonnances (signées ou non), odontogrammes ;
- stock : fournisseurs, produits (dont alertes de seuil et de péremption),
  mouvements, commandes à tous les stades, réception.

Comme `_seed_demo.py`, tout passe par l'API publique. La session est ouverte
directement en base (outil interne, qui a déjà accès aux bases) : le mot de
passe n'est demandé nulle part. Les comptes de l'équipe sont créés sans mot de
passe, donc sans invitation ni e-mail : ils restent inertes tant qu'un
administrateur ne les invite pas.

Relancé, chaque section vérifie ce qui existe et ne duplique rien.
"""

import argparse
import asyncio
import random
import sys
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, ".")

from httpx import ASGITransport, AsyncClient

import _seed_demo
from src.core.database import master_engine, tenant_db_manager
from src.main import app

API = "/api/v1"
AUJOURDHUI = date.today()
# Graine fixe : deux exécutions sur une base vide produisent le même jeu.
ALEA = random.Random(2026)

COMPTE = {"crees": 0, "erreurs": 0}

EQUIPE = [
    ("Mariama", "Kane", "SECRETAIRE", "77 210 33 44"),
    ("Cheikh", "Mbaye", "ASSISTANT", "77 455 66 01"),
    ("Astou", "Gaye", "COMPTABLE", "76 820 14 77"),
    ("Pape", "Thiam", "GESTIONNAIRE_STOCK", "78 301 92 63"),
    ("Mame Diarra", "Faye", "PRATICIEN", "77 640 08 15"),
]

PATIENTS_SUPPLEMENTAIRES = [
    ("Awa", "Cissé", "1989-02-14", "F", "77 512 40 11", "Infirmière", {}),
    ("Mamadou", "Gueye", "1976-08-02", "M", "77 333 21 09", "Ingénieur", {"hta": True}),
    ("Coumba", "Mbengue", "2015-05-27", "F", "78 902 11 34", "Élève", {}),
    ("Abdoulaye", "Ndao", "1960-12-19", "M", "70 455 88 20", "Retraité", {"diabete": True, "diabete_type": "TYPE_2"}),
    ("Rokhaya", "Diagne", "1993-07-08", "F", "76 118 45 90", "Avocate", {}),
    ("Lamine", "Camara", "1982-10-30", "M", "77 274 63 52", "Mécanicien", {"tabac": True}),
    ("Sokhna", "Lô", "2003-03-21", "F", "78 640 22 71", "Étudiante",
     {"allergies": [{"substance": "Latex", "reaction": "Eczéma de contact"}]}),
    ("Modou", "Seck", "1971-01-05", "M", "70 803 19 44", "Commerçant", {}),
    ("Adama", "Touré", "1999-09-12", "M", "77 965 30 18", "Développeur", {}),
    ("Yacine", "Wade", "1987-06-25", "F", "76 507 82 36", "Pharmacienne", {}),
    ("Serigne", "Niang", "1958-04-03", "M", "70 221 74 05", "Imam", {"hta": True}),
    ("Bineta", "Sy", "2009-11-16", "F", "78 377 59 62", "Élève", {}),
]

MOTIFS = [
    ("Douleur dentaire aiguë", "DOULEUR"),
    ("Contrôle annuel", "CONTROLE"),
    ("Détartrage et polissage", "CONTROLE"),
    ("Suivi de traitement canalaire", "SUIVI"),
    ("Pose de couronne", "PROTHESE"),
    ("Suivi orthodontique", "ORTHODONTIE"),
    ("Blanchiment", "ESTHETIQUE"),
    ("Abcès, gonflement de la joue", "URGENCE"),
]

DIAGNOSTICS = [
    ("Carie dentinaire profonde", "Composite après curetage, contrôle à 6 mois.", "K02.1"),
    ("Gingivite chronique", "Détartrage, enseignement de l'hygiène, bain de bouche 10 jours.", "K05.1"),
    ("Pulpite irréversible", "Traitement canalaire en deux séances puis couronne.", "K04.0"),
    ("Parodontite modérée", "Surfaçage radiculaire par quadrant.", "K05.3"),
    ("Dent de sagesse incluse", "Extraction chirurgicale sous anesthésie locale.", "K01.1"),
]

ORGANISMES = [
    ("IPM-FP", "IPM de la Fonction publique", "MUTUELLE"),
    ("MUT-ENS", "Mutuelle des enseignants", "MUTUELLE"),
    ("ASP", "Assurance Santé Plus", "ASSURANCE"),
]

CATEGORIES = [
    ("ASSURE", "Assuré / mutualiste", 2),
    ("ENTREPRISE", "Convention entreprise", 3),
]

FOURNISSEURS = [
    ("Dental Afrique Distribution", "Ousmane Kébé", "33 821 45 67", "commandes@dental-afrique.example.com", "Zone industrielle, Dakar"),
    ("Médi-Stock Sénégal", "Fatim Sall", "33 864 12 90", "contact@medi-stock.example.com", "Rue 10, Médina, Dakar"),
    ("Pharma Dentaire Pro", "Jean Mendy", "33 957 30 44", "ventes@pharma-dentaire.example.com", "Avenue Bourguiba, Dakar"),
    ("Labo Prothèse Thiès", "Aliou Diatta", "33 951 08 26", "atelier@labo-thies.example.com", "Quartier Escale, Thiès"),
]

# code, désignation, catégorie, unité, stock, seuil, prix d'achat, péremption (jours), emplacement
ARTICLES = [
    ("GANT-M", "Gants nitrile taille M (boîte de 100)", "Consommables", "boîte", 42, 10, 4500, None, "Réserve A1"),
    ("GANT-S", "Gants nitrile taille S (boîte de 100)", "Consommables", "boîte", 6, 10, 4500, None, "Réserve A1"),
    ("MASQ", "Masques chirurgicaux (boîte de 50)", "Consommables", "boîte", 25, 8, 3000, None, "Réserve A2"),
    ("COMP-A2", "Composite photopolymérisable A2", "Restauration", "seringue", 14, 5, 18000, 240, "Armoire soins"),
    ("COMP-A3", "Composite photopolymérisable A3", "Restauration", "seringue", 3, 5, 18000, 25, "Armoire soins"),
    ("CVI", "Ciment verre ionomère", "Restauration", "kit", 7, 3, 22000, 300, "Armoire soins"),
    ("ANES-ART", "Articaïne 4 % adrénalinée (50 carpules)", "Anesthésie", "boîte", 9, 4, 35000, 18, "Armoire sécurisée"),
    ("ANES-LID", "Lidocaïne 2 % (50 carpules)", "Anesthésie", "boîte", 2, 4, 28000, 400, "Armoire sécurisée"),
    ("LIME-K", "Limes K assorties 15-40", "Endodontie", "boîte", 18, 6, 12000, None, "Tiroir endo"),
    ("HYPO", "Hypochlorite de sodium 2,5 %", "Endodontie", "flacon", 11, 4, 3500, 150, "Tiroir endo"),
    ("GUTTA", "Cônes de gutta-percha", "Endodontie", "boîte", 4, 5, 9000, None, "Tiroir endo"),
    ("ALGIN", "Alginate pour empreintes (sachet 450 g)", "Prothèse", "sachet", 20, 6, 7500, 365, "Réserve B1"),
    ("FIL-SUT", "Fil de suture résorbable 4/0", "Chirurgie", "unité", 30, 10, 2500, 500, "Tiroir chirurgie"),
    ("COMPR", "Compresses stériles 5x5 (paquet)", "Consommables", "paquet", 60, 20, 1500, None, "Réserve A3"),
    ("FLUOR", "Vernis fluoré", "Prévention", "tube", 8, 3, 15000, 12, "Armoire soins"),
]

MEDICAMENTS = [
    ("Amoxicilline 1 g", "1 comprimé matin et soir", "7 jours", 14),
    ("Paracétamol 1 g", "1 comprimé toutes les 6 heures si douleur", "5 jours", 20),
    ("Ibuprofène 400 mg", "1 comprimé 3 fois par jour pendant le repas", "3 jours", 9),
    ("Chlorhexidine 0,12 % bain de bouche", "Bain de bouche 2 fois par jour", "10 jours", 1),
    ("Métronidazole 500 mg", "1 comprimé 3 fois par jour", "7 jours", 21),
]

ETATS_ODONTO = [
    "CARIE_DEBUTANTE", "CARIE_AVANCEE", "OBTURATION_COMPOSITE", "OBTURATION_AMALGAME",
    "COURONNE_CERAMIQUE", "TCR", "ABSENTE_EXTRACTEE", "A_TRAITER", "EXTRACTION_PLANIFIEE",
]
DENTS_ADULTE = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 31, 32, 33, 34, 35, 36, 37, 41, 42, 43, 44, 45, 46, 47]


def iso(jour: date, h: int, m: int = 0) -> str:
    return datetime.combine(jour, time(h, m), tzinfo=timezone.utc).isoformat()


def jours_ouvres(debut: date, fin: date) -> list[date]:
    jours, j = [], debut
    while j <= fin:
        if j.weekday() < 5:
            jours.append(j)
        j += timedelta(days=1)
    return jours


class Api:
    """Client ASGI : chaque appel est compté, chaque refus est affiché."""

    def __init__(self, jeton: str):
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {jeton}"},
        )

    async def ecrire(self, methode: str, chemin: str, corps: dict | None = None, params: dict | None = None,
                     silencieux: bool = False):
        r = await self.client.request(methode, API + chemin, json=corps, params=params)
        if r.status_code not in (200, 201):
            if not silencieux:
                COMPTE["erreurs"] += 1
                print(f"  ! {methode} {chemin} -> HTTP {r.status_code} : {r.text[:200]}")
            return None
        COMPTE["crees"] += 1
        return r.json().get("data") or {}

    async def lire(self, chemin: str, params: dict | None = None):
        r = await self.client.get(API + chemin, params=params)
        if r.status_code != 200:
            print(f"  ! GET {chemin} -> HTTP {r.status_code} : {r.text[:160]}")
            return []
        data = r.json().get("data", r.json())
        if isinstance(data, dict):
            data = data.get("items", data.get("data", data))
        return data

    async def total(self, chemin: str, params: dict | None = None) -> int:
        r = await self.client.get(API + chemin, params=params)
        if r.status_code != 200:
            return 0
        corps = r.json()
        meta = corps.get("meta") or {}
        if "total_records" in meta:
            return meta["total_records"]
        data = corps.get("data")
        return len(data) if isinstance(data, list) else 0

    async def fermer(self):
        await self.client.aclose()


# ------------------------------------------------------------------ sections

async def section_equipe(api: Api, cabinet_id: str, domaine: str) -> list[str]:
    """Comptes de l'équipe ; renvoie les praticiens disponibles (profil praticien)."""
    print("\nÉquipe…")
    existants = {u.get("email") for u in await api.lire("/utilisateurs", {"limit": 100}) if isinstance(u, dict)}
    for prenom, nom, role, tel in EQUIPE:
        email = f"{prenom.split()[0].lower()}.{nom.lower()}@{domaine}"
        if email in existants:
            continue
        u = await api.ecrire("POST", "/utilisateurs", {
            "email": email, "prenom": prenom, "nom": nom, "role": role,
            "telephone": tel, "cabinet_id": cabinet_id,
        })
        if u and role == "PRATICIEN":
            # Le profil praticien peut déjà avoir été créé avec le compte.
            p = await api.ecrire("POST", "/praticiens", {
                "utilisateur_id": u["id"], "titre": "Dr", "specialite": "Orthodontie",
                "numero_ordre": "ONCD-2187", "cabinet_id": cabinet_id,
            }, silencieux=True)
            if p:
                await api.ecrire("POST", f"/cabinets/{cabinet_id}/praticiens/{p['id']}/rattachement", {},
                                 silencieux=True)

    praticiens = [p for p in await api.lire("/praticiens", {"cabinet_id": cabinet_id}) if isinstance(p, dict)]
    for p in praticiens:
        dispo = await api.lire(f"/praticiens/{p['id']}/disponibilites")
        jours_pris = {d.get("jour_semaine") for d in dispo if isinstance(d, dict)}
        for js in range(5):
            if js not in jours_pris:
                await api.ecrire("POST", f"/praticiens/{p['id']}/disponibilites",
                                 {"jour_semaine": js, "heure_debut": "08:00", "heure_fin": "17:00"})
    print(f"  {len(praticiens)} praticien(s)")
    return [p["id"] for p in praticiens]


async def section_patients(api: Api) -> list[dict]:
    print("\nPatients supplémentaires…")
    connus = {
        (p.get("prenom", "").lower(), p.get("nom", "").lower())
        for p in await api.lire("/patients", {"page": 1, "limit": 100}) if isinstance(p, dict)
    }
    for prenom, nom, naissance, sexe, tel, profession, etat in PATIENTS_SUPPLEMENTAIRES:
        if (prenom.lower(), nom.lower()) in connus:
            continue
        await api.ecrire("POST", "/patients", {
            "prenom": prenom, "nom": nom, "date_naissance": naissance, "sexe": sexe,
            "telephone_1": tel, "profession": profession, "ville": ALEA.choice(["Dakar", "Pikine", "Rufisque", "Thiès"]),
            "etat_general": etat or None,
        })
    patients = [p for p in await api.lire("/patients", {"page": 1, "limit": 100}) if isinstance(p, dict)]
    print(f"  {len(patients)} patient(s) au total")
    return patients


async def section_tarification(api: Api, patients: list[dict]) -> None:
    print("\nTarification et prise en charge…")
    categories = {c.get("code") for c in await api.lire("/tarification/categories") if isinstance(c, dict)}
    for code, libelle, ordre in CATEGORIES:
        if code not in categories:
            await api.ecrire("POST", "/tarification/categories", {"code": code, "libelle": libelle, "ordre": ordre})

    # Tarif conventionné : 10 % de moins que le tarif de base, par catégorie.
    actes = [a for a in await api.lire("/tarification/actes", {"limit": 100}) if isinstance(a, dict)]
    for a in actes:
        base = float(a.get("tarif_base") or 0)
        if not base:
            continue
        for code, _, _ in CATEGORIES:
            await api.ecrire("PUT", f"/tarification/actes/{a['id']}/tarifs",
                             {"categorie_code": code, "montant": round(base * 0.9, -2)}, silencieux=True)

    organismes = {o.get("code"): o for o in await api.lire("/tarification/organismes") if isinstance(o, dict)}
    for code, nom, type_org in ORGANISMES:
        if code not in organismes:
            o = await api.ecrire("POST", "/tarification/organismes", {"code": code, "nom": nom, "type_organisme": type_org})
            if o:
                organismes[code] = o

    ids_org = [o["id"] for o in organismes.values() if o.get("id")]
    nb = 0
    for i, p in enumerate(patients[:8]):
        if not ids_org or await api.total(f"/tarification/patients/{p['id']}/droits"):
            continue
        r = await api.ecrire("POST", f"/tarification/patients/{p['id']}/droits", {
            "organisme_id": ids_org[i % len(ids_org)],
            "numero_police": f"POL-{2026}{1000 + i}",
            "taux_prise_en_charge": [80, 70, 50][i % 3],
        })
        nb += bool(r)
    print(f"  {len(organismes)} organisme(s), {nb} droit(s) ajouté(s)")


async def section_stock(api: Api, cabinet_id: str) -> None:
    print("\nStock…")
    fournisseurs = [f for f in await api.lire("/stock/fournisseurs") if isinstance(f, dict)]
    noms = {f.get("nom") for f in fournisseurs}
    for nom, contact, tel, email, adresse in FOURNISSEURS:
        if nom not in noms:
            f = await api.ecrire("POST", "/stock/fournisseurs",
                                 {"nom": nom, "contact": contact, "telephone": tel, "email": email, "adresse": adresse})
            if f:
                fournisseurs.append(f)

    articles = [a for a in await api.lire("/stock/articles", {"cabinet_id": cabinet_id, "limit": 100}) if isinstance(a, dict)]
    codes = {a.get("code") for a in articles}
    nouveaux = []
    for code, designation, categorie, unite, qte, seuil, prix, peremption, emplacement in ARTICLES:
        if code in codes:
            continue
        corps = {
            "code": code, "designation": designation, "categorie": categorie, "unite": unite,
            "quantite_stock": qte, "seuil_alerte": seuil, "prix_achat": prix, "emplacement": emplacement,
            "motif_initial": "Inventaire d'ouverture",
        }
        if peremption is not None:
            corps["date_peremption"] = (AUJOURDHUI + timedelta(days=peremption)).isoformat()
        a = await api.ecrire("POST", "/stock/articles", corps, params={"cabinet_id": cabinet_id})
        if a:
            articles.append(a)
            nouveaux.append(a)

    # Consommation des dernières semaines, sur les produits tout juste créés.
    for a in nouveaux[:8]:
        await api.ecrire("POST", "/stock/mouvements", {
            "article_id": a["id"], "cabinet_id": cabinet_id, "type_mouvement": "SORTIE_CONSULTATION",
            "quantite": 1 + ALEA.randint(0, 2), "motif": "Utilisé en soins",
        }, silencieux=True)

    if await api.total("/stock/commandes") or not fournisseurs or not articles:
        print(f"  {len(fournisseurs)} fournisseur(s), {len(articles)} produit(s) ; commandes déjà présentes")
        return

    par_code = {a.get("code"): a for a in articles}

    def lignes(*codes_qte):
        return [
            {"article_id": par_code[c]["id"], "quantite": q, "prix_unitaire": float(par_code[c].get("prix_achat") or 0)}
            for c, q in codes_qte if c in par_code
        ]

    # Reçue : on la passe ENVOYEE puis on réceptionne tout.
    recue = await api.ecrire("POST", "/stock/commandes", {
        "fournisseur_id": fournisseurs[0]["id"], "notes": "Réassort mensuel",
        "lignes": lignes(("GANT-M", 20), ("MASQ", 10), ("COMPR", 30)),
    })
    if recue:
        await api.ecrire("PATCH", f"/stock/commandes/{recue['id']}", {"statut": "ENVOYEE"})
        detail = await api.lire(f"/stock/commandes/{recue['id']}")
        lignes_cmd = detail.get("lignes", []) if isinstance(detail, dict) else []
        if lignes_cmd:
            await api.ecrire("POST", "/stock/receptions", {
                "notes": "Livraison complète",
                "lignes": [{"ligne_commande_id": l["id"], "quantite_recue": l["quantite"]} for l in lignes_cmd],
            }, params={"commande_id": recue["id"], "site_id": cabinet_id})

    envoyee = await api.ecrire("POST", "/stock/commandes", {
        "fournisseur_id": fournisseurs[2 % len(fournisseurs)]["id"], "notes": "Produits sous le seuil",
        "lignes": lignes(("GANT-S", 15), ("ANES-LID", 6), ("COMP-A3", 8), ("GUTTA", 6)),
    })
    if envoyee:
        await api.ecrire("PATCH", f"/stock/commandes/{envoyee['id']}", {"statut": "ENVOYEE"})

    await api.ecrire("POST", "/stock/commandes", {
        "fournisseur_id": fournisseurs[1 % len(fournisseurs)]["id"], "notes": "À valider par le praticien",
        "lignes": lignes(("CVI", 3), ("ALGIN", 10)),
    })
    print(f"  {len(fournisseurs)} fournisseur(s), {len(articles)} produit(s), 3 commande(s)")


async def section_agenda(api: Api, cabinet_id: str, praticiens: list[str], patients: list[dict],
                         fauteuils: list[str], actes: list[dict]) -> list[dict]:
    """
    Rendez-vous de J-10 à J+14 (jours ouvrés). Les passés sont menés jusqu'au
    bout : salle d'attente, consultation, actes, clôture, facture, paiement.
    Renvoie les consultations terminées (pour les ordonnances).
    """
    print("\nAgenda autour d'aujourd'hui…")
    debut, fin = AUJOURDHUI - timedelta(days=14), AUJOURDHUI + timedelta(days=14)
    deja = await api.total("/rendez-vous", {"du": iso(debut, 0), "au": iso(fin, 23, 59), "limit": 1})
    if deja >= 20:
        print(f"  {deja} rendez-vous déjà présents sur la période — rien ne change")
        return []

    actes_simples = [a for a in actes if not a.get("unitaire")]
    actes_dent = [a for a in actes if a.get("unitaire")]
    creneaux = [(8, 30), (9, 15), (10, 0), (11, 0), (11, 45), (14, 0), (15, 0), (16, 0)]
    terminees: list[dict] = []
    nb_rdv = 0

    for jour in jours_ouvres(debut, fin):
        delta = (jour - AUJOURDHUI).days
        for k, pid in enumerate(praticiens):
            for h, m in ALEA.sample(creneaux, ALEA.randint(3, 5)):
                patient = ALEA.choice(patients)
                motif, type_motif = ALEA.choice(MOTIFS)
                rdv = await api.ecrire("POST", "/rendez-vous", {
                    "patient_id": patient["id"], "praticien_id": pid, "cabinet_id": cabinet_id,
                    "fauteuil_id": fauteuils[k % len(fauteuils)] if fauteuils else None,
                    "debut": iso(jour, h, m), "duree_minutes": 30 if type_motif != "PROTHESE" else 60,
                    "motif": motif, "type_motif": type_motif, "statut": "CONFIRME" if ALEA.random() < 0.6 else "PLANIFIE",
                }, silencieux=True)
                if not rdv:
                    continue  # créneau en conflit : normal avec un tirage aléatoire
                nb_rdv += 1
                heure_passee = delta < 0 or (delta == 0 and h < datetime.now().hour)
                if not heure_passee:
                    continue

                tirage = ALEA.random()
                if tirage < 0.08:
                    await api.ecrire("POST", f"/rendez-vous/{rdv['id']}/statut", params={"statut": "ABSENT"})
                    continue
                if tirage < 0.15:
                    await api.ecrire("POST", f"/rendez-vous/{rdv['id']}/statut",
                                     params={"statut": "ANNULE", "motif": "Empêchement du patient"})
                    continue

                cons = await mener_consultation(api, rdv, actes_simples, actes_dent)
                if cons:
                    terminees.append(cons)

    print(f"  {nb_rdv} rendez-vous, {len(terminees)} consultation(s) menée(s) jusqu'à la facture")
    return terminees


async def mener_consultation(api: Api, rdv: dict, actes_simples: list[dict], actes_dent: list[dict]) -> dict | None:
    await api.ecrire("POST", f"/rendez-vous/{rdv['id']}/statut", params={"statut": "EN_SALLE_ATTENTE"})
    cons = await api.ecrire("POST", f"/rendez-vous/{rdv['id']}/consultation")
    if not cons:
        return None
    cons_id = cons.get("id") or cons.get("consultation_id")
    if not cons_id:
        return None

    choix = []
    if actes_simples:
        choix.append(ALEA.choice(actes_simples))
    if actes_dent:
        choix += ALEA.sample(actes_dent, min(len(actes_dent), ALEA.randint(1, 2)))
    for a in choix:
        corps = {"acte_id": a["id"], "quantite": 1}
        if a.get("unitaire"):
            corps["dent_numero"] = ALEA.choice(DENTS_ADULTE)
        await api.ecrire("POST", f"/consultations/{cons_id}/actes", corps)

    diag, plan, cim = ALEA.choice(DIAGNOSTICS)
    await api.ecrire("POST", f"/consultations/{cons_id}/terminer", {
        "diagnostic_principal": diag, "plan_traitement": plan, "codes_cim10": [cim],
        "recommandations": "Brossage 3 fois par jour, brosse souple.",
    })
    # Le rendez-vous suit la consultation ; s'il ne le fait pas seul, on le clôt.
    await api.ecrire("POST", f"/rendez-vous/{rdv['id']}/statut", params={"statut": "TERMINEE"}, silencieux=True)

    facture = await api.ecrire("POST", f"/factures/consultation/{cons_id}", {})
    if facture:
        total = float(facture.get("montant_total") or facture.get("total_ttc") or facture.get("montant_ttc") or 0)
        tirage = ALEA.random()
        if total and tirage < 0.55:
            await api.ecrire("POST", f"/factures/{facture['id']}/paiements",
                             {"montant": total, "mode": ALEA.choice(["ESPECES", "MOBILE_MONEY", "CARTE_BANCAIRE"])})
        elif total and tirage < 0.8:
            await api.ecrire("POST", f"/factures/{facture['id']}/paiements",
                             {"montant": round(total / 2, -2) or total, "mode": "MOBILE_MONEY", "reference": "WAVE-" + str(ALEA.randint(10000, 99999))})
    return {"id": cons_id, "patient_id": rdv["patient_id"]}


async def section_ordonnances(api: Api, consultations: list[dict]) -> None:
    print("\nOrdonnances…")
    if await api.total("/ordonnances", {"limit": 1}) >= 5 or not consultations:
        print("  déjà présentes ou aucune consultation")
        return
    referentiel = [m for m in await api.lire("/ordonnances/medicaments", {"limit": 100}) if isinstance(m, dict)]
    nb = 0
    for i, cons in enumerate(consultations[:12]):
        lignes = []
        for nom, poso, duree, qte in ALEA.sample(MEDICAMENTS, 2):
            ref = next((m for m in referentiel if nom.split()[0].lower() in (m.get("dci") or m.get("nom_commercial") or "").lower()), None)
            ligne = {"posologie": poso, "duree": duree, "quantite": qte}
            if ref:
                ligne["medicament_id"] = ref["id"]
            else:
                ligne["medicament_texte"] = nom
            lignes.append(ligne)
        o = await api.ecrire("POST", "/ordonnances", {
            "patient_id": cons["patient_id"], "consultation_id": cons["id"], "lignes": lignes,
            "notes_generales": "À prendre après les repas.",
        })
        if o:
            nb += 1
            if i % 3 != 2:
                await api.ecrire("POST", f"/ordonnances/{o['id']}/signer")
    print(f"  {nb} ordonnance(s)")


async def section_odontogrammes(api: Api, patients: list[dict], praticien_id: str) -> None:
    print("\nOdontogrammes…")
    nb = 0
    for p in patients[:12]:
        existant = await api.lire(f"/odontogramme/patients/{p['id']}")
        dents = existant.get("dents", []) if isinstance(existant, dict) else []
        if any(d.get("etat_actuel") not in (None, "SAINE") for d in dents if isinstance(d, dict)):
            continue
        if not existant:
            await api.ecrire("POST", f"/odontogramme/patients/{p['id']}", {}, silencieux=True)
        lot = [
            {"numero_fdi": n, "etat": ALEA.choice(ETATS_ODONTO), "praticien_id": praticien_id}
            for n in ALEA.sample(DENTS_ADULTE, ALEA.randint(3, 7))
        ]
        if await api.ecrire("PATCH", f"/odontogramme/patients/{p['id']}/dents",
                            {"dents": lot, "praticien_id": praticien_id}):
            nb += 1
    print(f"  {nb} odontogramme(s) renseigné(s)")


async def section_devis(api: Api, patients: list[dict], actes: list[dict]) -> None:
    print("\nDevis…")
    if await api.total("/devis", {"limit": 1}) >= 6:
        print("  déjà présents")
        return
    chers = sorted([a for a in actes if a.get("tarif_base")], key=lambda a: -float(a["tarif_base"]))[:5]
    statuts = ["ENVOYE", "ACCEPTE", "REFUSE", None, "ENVOYE", "ACCEPTE"]
    for i, statut in enumerate(statuts):
        p = patients[(i * 3) % len(patients)]
        lignes = [
            {"acte_id": a["id"], "designation": a["libelle"], "quantite": 1, "prix_unitaire": float(a["tarif_base"]),
             **({"dent_numero": ALEA.choice(DENTS_ADULTE)} if a.get("unitaire") else {})}
            for a in ALEA.sample(chers, min(2, len(chers)))
        ]
        d = await api.ecrire("POST", "/devis", {
            "patient_id": p["id"], "lignes": lignes,
            "date_validite": (AUJOURDHUI + timedelta(days=30)).isoformat(),
        })
        if d and statut:
            if statut != "ENVOYE":
                await api.ecrire("POST", f"/devis/{d['id']}/statut", {"statut": "ENVOYE"}, silencieux=True)
            await api.ecrire("POST", f"/devis/{d['id']}/statut",
                             {"statut": statut, "signature_patient": statut == "ACCEPTE"})


# ---------------------------------------------------------------------- main

async def main(email: str, avec_base: bool) -> int:
    jeton = await _seed_demo._session_directe(email)

    if avec_base:
        print("=== Socle (_seed_demo.py) ===")
        await _seed_demo.peupler(email, None, fermer=False, jeton=jeton)

    print("\n=== Compléments ===")
    api = Api(jeton)
    try:
        cabinets = await api.lire("/cabinets")
        if not cabinets:
            print("Aucun cabinet : abandon.")
            return 1
        cabinet_id = cabinets[0]["id"]
        domaine = email.split("@")[1] if email.endswith(".sn") else "demo-cabinet.example.com"

        praticiens = await section_equipe(api, cabinet_id, domaine)
        patients = await section_patients(api)
        await section_tarification(api, patients)
        await section_stock(api, cabinet_id)

        actes = [a for a in await api.lire("/tarification/actes", {"limit": 100}) if isinstance(a, dict)]
        fauteuils = [f["id"] for f in await api.lire(f"/cabinets/{cabinet_id}/fauteuils") if isinstance(f, dict)]
        # Une session de caisse ouverte est requise pour encaisser.
        await api.ecrire("POST", "/caisse/sessions", {"cabinet_id": cabinet_id, "ouverture_especes": 50000},
                         silencieux=True)

        consultations = await section_agenda(api, cabinet_id, praticiens, patients, fauteuils, actes)
        await section_ordonnances(api, consultations)
        if praticiens:
            await section_odontogrammes(api, patients, praticiens[0])
        await section_devis(api, patients, actes)
    finally:
        await api.fermer()
        await tenant_db_manager.close_all()
        await master_engine.dispose()

    print(f"\nCompléments — créés : {COMPTE['crees']}   erreurs : {COMPTE['erreurs']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--email", required=True, help="E-mail d'un administrateur du cabinet à remplir.")
    parser.add_argument("--sans-socle", action="store_true", help="Ne pas relancer _seed_demo.py d'abord.")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.email.strip().lower(), not args.sans_socle)))
