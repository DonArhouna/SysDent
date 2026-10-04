# SysDent Pro — Plan de travail restant

> État au **4 octobre 2026**, après refonte visuelle, audit des données en dur et
> **vérification visuelle réelle** de l'application (backend démarré, données
> réelles, captures dans les deux thèmes et sur trois formats d'écran).
>
> **Convention** : ✅ fait · 🟡 partiel · ❌ absent.
> Chaque ligne n'est marquée faite que si elle a été **vérifiée à l'exécution**,
> pas déduite de la lecture du code.

---

## 1. Synthèse par module

### Backend — 119 endpoints, 13 modules

| Module | État | Routes | Ce qui a été vérifié |
|---|---|---|---|
| `auth` (JWT, refresh, `/me`) | ✅ | 4 | login réel OK |
| `master` (console Super Admin) | 🟡 | 10 | provisioning OK **sauf** reprise (§2 B5) |
| `patients` (+ dossier, état général, antécédents) | ✅ | 13 | liste, filtres, archivage OK |
| `consultations` (+ actes, nomenclature) | 🟡 | 14 | **nomenclature vide sur cabinet neuf** (§2 B2) |
| `odontogramme` (+ charting) | ✅ | 11 | schéma, faces, historique OK |
| `ordonnances` (+ 14 médicaments) | ✅ | 10 | formulaire seedé au provisionnement |
| `rbac` | ❌ | 5 | **`GET /rbac/roles` renvoie 500** (§2 B1) |
| `rendez-vous` (agenda, créneaux, fauteuils) | ✅ | 12 | conflits praticien **et** fauteuil validés |
| `cabinets` (salles, fauteuils, praticiens, dispos) | ✅ | 24 | module le plus complet |
| `facturation` (factures, devis, caisse, échéancier) | ✅ | 14 | KPI page → faux hors page 1 (§2 B7) |
| `audit` | ✅ | 1 | paginé, filtre par action |
| **`stock`** | ❌ | — | **module entier absent** |
| **`notifications`** | ❌ | — | aucun endpoint |
| **`rapports`** | ❌ | — | aucun endpoint |
| **`stats` (tableau de bord)** | ❌ | — | 4 appels agrégés, non atomiques |

### Frontend — 18 routes, 97 fichiers, 0 donnée factice

| Écran | État | Vérifié |
|---|---|---|
| Layout flottant (sidebar/navbar/drawer) | ✅ | desktop 1440, tablette 834, mobile 390 |
| Tableau de bord | ✅ | données réelles, 4 états |
| Patients (liste + dossier) | ✅ | 13 dossiers réels |
| Consultations (liste + détail) | ✅ | |
| Odontogramme & charting | ✅ | deux thèmes, légende alignée sur les dents |
| Ordonnances | ✅ | |
| Agenda & RDV | 🟡 | pas de lien profond vers une date (`§4`) |
| Cabinets · Praticiens | ✅ | |
| Facturation (factures, devis, caisse) | ✅ | impression = print navigateur |
| Audit · RBAC | 🟡 | RBAC cassé côté backend (B1) |
| **Stock** | 🟡 | UI prête, endpoints inexistants — **état honnête affiché** |
| **`/stock/commandes`** | ❌ | route qui rend la page Produits |
| Rapports · Portail patient | ❌ | non commencés |

---

## 2. Écarts backend constatés

Priorité décroissante. Les trois premiers sont des **bloquants**.

### B1 — `GET /rbac/roles` renvoie 500 · **P0**
`src/modules/rbac/services.py:201`

```python
"nb_utilisateurs": len(role.utilisateurs or [])   # ligne 201
```

Le `selectinload` de la ligne 182 ne charge que `permission_roles → permission`.
`role.utilisateurs` déclenche donc un **lazy load asynchrone** hors contexte greenlet →
`MissingGreenlet`. Le `or []` ne l'empêche pas : l'attribut existe sur la classe, l'IO est
tenté quand même.

**Correctif** : ajouter `.selectinload(Role.utilisateurs)` à la requête de la ligne 180.

> La page d'administration des rôles est **inutilisable** aujourd'hui. Le plan précédent
> la marquait ✅ : c'est faux, et c'est le type d'erreur que seule l'exécution révèle.

### B2 — Un cabinet neuf n'a **aucun acte** dans sa nomenclature · **P0**
Table `actes_nomenclature` vide après provisionnement (mesuré : 0 ligne, 26 sociétés).

Le formulaire **médicamenteux** est bien semé au provisionnement
(`master/services.py:111` → `MedicamentService.semer_formulaire`, 14 molécules).
La nomenclature des actes, elle, n'est **jamais peuplée**.

**Conséquence en chaîne** : impossible de saisir un acte sur une consultation →
`GET /consultations/{id}/total` renvoie 0 → impossible de facturer depuis une
consultation. Le circuit de facturation n'est utilisable qu'en facture libre.

**Correctif** : symmetrical au formulaire médicamenteux — semer une nomenclature
par défaut au provisionnement, ou l'exposer en paramètre de création de société.

### B3 — `GET /nomenclature/actes?limit=201` renvoie 500 au lieu de 422 · **P1**
`src/modules/consultations/router.py:365` — `PaginationParams(page=page, limit=limit)`
construit **à la main** dans le handler. La `ValidationError` sort du circuit de
validation de FastAPI et devient une 500.

Mesuré sur les 10 routes paginées : 6 renvoient 422 (correct), 1 renvoie 500, 3
n'encadrent pas `limit`.

| Route | `limit=200` |
|---|---|
| `/patients`, `/consultations`, `/factures`, `/devis`, `/audit` | 422 ✅ |
| `/nomenclature/actes` | **500** ❌ |
| `/rendez-vous`, `/ordonnances` | 200 — `limit` non borné ⚠️ |

**Correctif** : déclarer `limit: int = Query(100, ge=1, le=100)` comme les autres
routes, et borner les deux restantes.

### B4 — Aucun endpoint de reprise du provisionnement · **P1**
Une société reste en statut `PROVISIONING` si la création de sa base échoue
(comportement **voulu et documenté**). Mais rien ne permet de relancer : le seul
chemin est de rejouer `POST /societes`, qui répond `EMAIL_DEJA_UTILISE`.

**Correctif** : `POST /master/societes/{id}/reprovisionner` (ADMIN).

### B5 — Blocage environnemental : `psycopg2` interdit par la politique Windows · **bloquant local**
```
ImportError: DLL load failed while importing _psycopg:
Une stratégie de contrôle d'application a bloqué ce fichier.
```

Alembic utilise une URL **synchrone** (`postgresql+psycopg2://`). Le runtime, lui,
utilise `asyncpg` et n'est pas touché. Conséquence : **aucun nouveau tenant ne peut
être provisionné** tant que le bloqueur est actif — même le provisioning qui a
fonctionné hier.

À traiter hors code : autoriser `_psycopg.pyd` auprès de la politique de contrôle
d'application, ou basculer les migrations tenant sur `psycopg` (v3) si le blocage
le vise spécifiquement.

### B10 — Aucun endpoint utilisateur : un cabinet ne peut pas recruter · **P0**
Constaté le 4 octobre 2026 sur le schéma OpenAPI : **ni route ni schéma**
`Utilisateur`. Un compte n'existe qu'implicitement, à la provisionnement d'une
société — un seul administrateur par cabinet.

Conséquence métier directe : pas de secrétaire, pas de comptable, pas de
deuxième praticien. Le cabinet ne peut pas fonctionner en équipe.

À livrer : `GET/POST /utilisateurs`, `PATCH /utilisateurs/{id}`,
`POST /utilisateurs/{id}/mot-de-passe`, `DELETE /utilisateurs/{id}` (désactivation,
jamais de suppression physique), permissions `ADMIN:USER:*`.

Le frontend est prêt : `features/utilisateurs/` (service, types, page) affiche un
état « module indisponible » qui liste précisément ce qui manque. **Le contrat
proposé doit être validé avant d'écrire le backend**, sinon l'écran et l'API
divergeront.

### B11 — Le renouvellement de session est impossible · **P0**
`POST /auth/refresh` déclare `tenant_db: AsyncSession = Depends(get_tenant_db)`
(`auth/router.py:106`). Cette dépendance résout le cabinet via
`get_current_tenant_id` → `get_token_payload` → `decode_token`, qui **rejette un
jeton d'accès expiré**.

Or c'est précisément le cas d'usage : l'endpoint ne fonctionne donc qu'avec un
jeton valide — celui qu'on cherche précisément à renouveler.

| Appel à `/auth/refresh` | Résultat (mesuré) |
|---|---|
| sans en-tête `Authorization` | 401 « Jeton d'accès manquant » |
| jeton **frais** | 200 |
| jeton **expiré** | 401 « La session a expirée » |

**Aucun contournement frontend.** La session meurt au bout de
`ACCESS_TOKEN_EXPIRE_MINUTES` (15 min).

*Correctif* : extraire le corps de `get_tenant_db` (`dependencies.py:59-89`) dans
un helper `ouvrir_session_tenant(tenant_id, master_db)`, puis, dans
`/auth/refresh`, lire `tenant_id` dans le **refresh token** — `renouveller_session`
le fait déjà (`services.py:205`) et le jeton étant signé, cette valeur est digne
de confiance. Le service est correct ; seule la dépendance de la route est fausse.

*Correctif complémentaire* : déposer un cookie `refresh_token` HttpOnly à la
connexion et rendre le champ du corps facultatif, pour que le frontend n'ait pas
à conserver un secret de 7 jours dans `localStorage`.

### B6 — Un homonyme n'empêche pas de créer un second dossier · **P2**
`creation_patient_doublon_detecte` est journalisé en `warning`, mais la création
poursuit. Deux « Test Unitaire » et trois homonymes ont coexisté pendant la
production du jeu de démonstration.

Les homonymes sont légitimes en clinique ; en revanche l creations devrait proposer
de fusionner ou de rattacher. **Décision métier à prendre** — je ne la tranche pas.

### B7 — KPI de facturation calculés sur la page courante · **P1**
`factures-list-page.tsx:132` (déjà commenté dans le code). Les totaux « ce mois »,
« en attente »… sont calculés sur les lignes de la page affichée : faux dès que la
pagination server change. **Correctif** : `GET /facturation/stats`.

### B8 — Endpoints absents, confirmés
| Manquant | Consommé par | Bloque |
|---|---|---|
| `GET/POST /stock/articles`, `GET/POST /stock/mouvements` | `stock-api.ts` | tout le module Stock |
| `GET /stock/alertes` | KPI seuil de réapprovisionnement | |
| `GET /notifications`, `PATCH /notifications/{id}/lu` | panneau de la navbar | |
| `GET /stats/dashboard` | tableau de bord (4 appels, non atomiques) | |
| `GET /facturation/stats` | KPI Factures | chiffres faux hors page 1 |
| `GET /rapports/{type}` | module Rapports | |
| `POST /ordonnances/{id}/pdf`, `POST /factures/{id}/pdf` | impression | documents non archivables |
| `GET /portail/patient/*` | portail patient | |
| CIM-10 structuré | saisie du diagnostic | texte libre aujourd'hui |

---

## 3. Reste frontend

| Tâche | Détail | P | Charge |
|---|---|---|---|
| `/stock/commandes` | route qui rend la page Produits, promut dans le menu | P1 | S |
| Lien profond agenda | `/agenda?date=` n'est pas lu : pas de partage d'une journée | P1 | S |
| Découpage du bundle | **662 ko** en un seul chunk | P1 | M |
| Tests | aucun test ; `tonStatutFacture` et le mapping d'états sont dupliqués | P1 | M |
| Piège de focus | absent dans le drawer ; pas de retour de focus à la fermeture | P2 | S |
| i18n | libellés de rôle et `ASTUCES` en constantes FR dans le code | P2 | M |
| Impression PDF | print navigateur → à basculer sur B8 | P2 | M |
| Mode hors-ligne / PWA | non commencé | P2 | L |
| Portail patient | non commencé | P2 | L |

---

## 4. Dépendances croisées

```
B1 (rbac/roles)      ──> écran /rbac entièrement inutilisable      AUCUNE dépendance
B2 (nomenclature)    ──> actes ──> total consultation ──> facturation depuis un soin
B3 (limit/422)       ──> indépendant, 1 ligne
B4 (reprovisionner)  ──> nationals B5 (blocage psycopg2)
B5 (psycopg2)        ──> BLOQUE tout nouveau tenant ──> bloque aussi la recette de démo
B6 (homonymes)       ──> décision métier
B7 (/facturation/stats) ──> KPI Factures
B8 /stock/*         ──> page Stock ──> retire l'état « non disponible »
   /notifications   ──> badge navbar
   /stats/dashboard ──> remplace 4 appels
   PDF              ──> impression facture + ordonnance

cloisonnement multi-tenant ──> À POSER AVANT tout nouveau module
   `src/modules/tenants/` expose 0 route dans `router.py`. Tant que la
   méthode n'est pas fixée (décorateur `CurrentTenant` ou discipline manuelle),
   chaque endpoint ajouté devra être corrigé après coup.
```

---

## 5. Priorités et charge

**S** ≈ 0,5 j · **M** ≈ 1–2 j · **L** ≈ 3–5 j

### P0 — bloquant
| # | Tâche | Charge |
|---|---|---|
| P0-1 | **B1** — `selectinload(Role.utilisateurs)`, rend l'écran RBAC | S |
| P0-2 | **B2** — semer la nomenclature des actes au provisionnement | M |
| P0-3 | **B5** — débloquer `_psycopg` (hors code) | S |
| P0-4 | **B11** — `/auth/refresh` : résoudre le tenant depuis le refresh token | S |
| P0-5 | **B10** — module Utilisateurs (schéma, CRUD, permissions `ADMIN:USER:*`) | L |

### P1 — important
| # | Tâche | Charge |
|---|---|---|
| P1-1 | **B3** — `limit` borné partout, 422 au lieu de 500 | S |
| P1-2 | **B4** — endpoint de reprise de provisionnement | S |
| P1-3 | **B7** + `/facturation/stats` — KPI justes hors page 1 | S |
| P1-4 | Module Stock (schéma, CRUD, permissions, câblage) | L |
| P1-5 | `/stats/dashboard` — 4 appels → 1 | M |
| P1-6 | Découpage du bundle par route | M |
| P1-7 | Tests sur les mappings de statut et d'état d'erreur | M |
| P1-8 | `/stock/commandes` + lien profond agenda | S |

### P2 — amélioration
| # | Tâche | Charge |
|---|---|---|
| P2-1 | `/notifications` + panneau branché | M |
| P2-2 | Génération PDF serveur | M |
| P2-3 | Module Rapports | L |
| P2-4 | CIM-10 structuré | M |
| P2-5 | Extraction des libellés vers l'i18n | M |
| P2-6 | PWA / hors-ligne | L |
| P2-7 | Portail patient | L |
| P2-8 | Piège de focus dans le drawer | S |

### Sprints proposés
- **Sprint 0** — P0-1, P0-3, P1-1, P1-2 (tous des corrections courtes ; débloque l'écran RBAC et le provisionnement).
- **Sprint 1** — P0-5 (Utilisateurs : sans eux le cabinet ne peut pas travailler en équipe), puis P0-2 et P1-4.
- **Sprint 2** — P1-3, P1-5, P1-6, P1-7, P1-8 : chiffres justes, performances, qualité.
- **Sprint 3+** — P2 par lots, en commençant par les PDF (P2-2), qui conditionnent l'archivage.

> **Le cloisonnement multi-tenant devrait précéder les nouveaux modules** (B-note du §4).
> C'est le seul point qui, s'il est mal posé, se paie sur *chaque* endpoint ajouté ensuite.

---

## 6. Risques

| Risque | Impact | Probabilité | Parade |
|---|---|---|---|
| Cloisonnement tenant contourné sur les nouveaux endpoints | **Fuite de données entre cabinets** | Moyenne | Tracer et tester l'isolation **avant** Sprint 1 |
| Nomenclature vide | Facturation depuis un soin inutilisable | **Élevée** (constaté) | P0-2 |
| KPI faux hors page 1 (Factures) | Chiffres faux en production | **Élevée** (latent) | P1-3 |
| Blocage `_psycopg` | Plus aucun nouveau tenant | **Élevée** (constaté) | P0-3 |
| Bundle 662 ko | Lent sur connexion mobile | Moyenne | P1-6 |
| Aucun test sur les mappings | Régression silencieuse à l'ajout d'un statut | Moyenne | P1-7 |
| Pas de PDF serveur | Documents non conformes à l'archivage | Moyenne | P2-2 |
| Formulaire médicamenteux non relu par un pharmacien | Prescription hors AMM | Moyenne | Revue avant tout usage réel |
| `retry: false` sur Stock | Perte d'erreur transitoire | Faible | Bouton « Réessayer » présent |

---

## 7. Limites de cette vérification

À signaler franchement, comme le plan précédent le faisait :

- **Le backend n'a pas été modifié.** Les corrections B1 à B7 sont décrites avec leur
  cause et leur correctif, mais **pas appliquées** : la mission portait sur le frontend.
- **Aucun test automatisé** : les constats viennent de l'exécution réelle
  (HTTP + captures), pas d'une suite de tests. C'est ce qui a permis de voir que
  `rbac` était cassé alors qu'il était marqué terminé.
- **Captures sans interação** : le harnais navigue et lit `localStorage`, il ne clique
  pas. Les modales, les onglets et les formulaires n'ont donc pas été ouverts — leur
  rendu est vérifié par le code et les tokens, pas à l'écran.
- **Le jeu de démonstration** (`Backend/_seed_demo.py`) passe uniquement par les
  endpoints publics. Il reste 5 dossiers en double sur la société `admin@cabinet.sn` :
  ils portent une consultation en cours, donc le backend refuse de les archiver
  (`PATIENT_HAS_ACTIVE_CONSULTATIONS` — règle correcte, mais qui empêche le nettoyage).
- **Capture headless** : le protocole CDP est piloté par un script temporaire, hors
  dépôt. `--screenshot` en mode headless classique ignore `--window-size` (viewport à
  764 px au lieu de 1440) et `--virtual-time-budget` épuise les retries de TanStack
  Query avant la première réponse réseau — d'où un faux « API injoignable ».

---

## 8. Arborescence et dépendances

```
SysDent Pro/
├── Backend/
│   ├── _create_cabinet.py        ← crée une société + son admin (console Master)
│   ├── _seed_demo.py             ← jeu de démonstration, endpoints publics uniquement
│   └── src/modules/              ← ❌ stock, notifications, rapports
├── Frontend/src/
│   ├── components/
│   │   ├── layout/               ← app-shell, sidebar, topbar, cabinet-selector
│   │   └── ui/                   ← page-header, status-badge, empty-state, toast, FAB…
│   ├── features/                 ← 11 domaines + stock (non branché)
│   ├── lib/                      ← client HTTP unique, formatage, navigation
│   └── providers/                ← theme-provider (mécanisme de thème intact)
└── PLAN_RESTE_A_FAIRE.md         ← ce document
```

**Dépendances techniques** : React 19 · Vite 8 · TypeScript 6 · Tailwind 3
(`darkMode: class`) · TanStack Query 5 · Zustand 5 · react-router 7 · lucide-react.
**Aucune dépendance ajoutée.**

### Point de vigilance dépôt

`Frontend/src/lib/` était **exclu de git** : le `.gitignore` racine contenait `lib/`
(motif setuptools, non ancré), qui attrapait le dossier à n'importe quelle profondeur.
Le dépôt ne contenait donc aucune couche de communication frontend — un `git clone`
donnait une application incapable de compiler. Corrigé : motif ancré `/lib/` et
garantie explicite `!/Frontend/src/lib/`.
