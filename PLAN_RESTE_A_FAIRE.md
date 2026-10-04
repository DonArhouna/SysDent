# SysDent Pro — Plan de travail restant

> État au 4 octobre 2026, après la refonte visuelle, l'audit des données en dur
> et la mise en place des états d'erreur honnêtes.
>
> **Convention de lecture** : ✅ fait · 🟡 partiel · ❌ non commencé / absent.
> La colonne « Manque » ne liste que ce qui est réellement vérifié manquant —
> aucune supposition n'est notée comme un acquis.

---

## 1. Synthèse par module

### Backend (FastAPI, multi-tenant)

| Module | État | Routes | Manque |
|---|---|---|---|
| `auth` | ✅ | 4 | — (login, refresh, `/auth/me`) |
| `master` | ✅ | 10 | référentiels & données de base |
| `audit` | ✅ | 1 | — (GET paginé avec filtres, permissions `AUDIT:READ`) |
| `patients` | ✅ | 13 | dossier complet, état général, antécédents, archivage |
| `consultations` (+ nomenclature) | ✅ | 14 | CIM-10 : le frontend ne saisit qu'un texte libre (P2) |
| `odontogramme` (+ référentiel) | ✅ | 11 | — |
| `ordonnances` (+ médicaments, contrôle) | ✅ | 10 | — |
| `rbac` | ✅ | 5 | — |
| `rendezvous` (+ agenda, créneaux, blocage) | ✅ | 12 | — |
| `cabinets` (+ salles, fauteuils, praticiens, dispos) | ✅ | 24 | — (module le plus complet) |
| `facturation` (+ devis, journal, paiements, échéancier) | ✅ | 14 | pas d'endpoint de **statistiques** (§2) |
| `tenants` | 🟡 | 0 dans `router.py` | décorateur / multi-tenant, cf. §5 |
| **`stock`** | ❌ | — | **module entier absent** (P0) |
| **`notifications`** | ❌ | — | aucun endpoint (P1) |
| **`rapports`** | ❌ | — | aucun endpoint (P2) |
| **`stats` dashboard** | ❌ | — | aucun endpoint dédié (P1) |
| **`portail patient`** | ❌ | — | aucun endpoint (P2) |

### Frontend (React 19 / Vite 8)

| Écran | État | Manque |
|---|---|---|
| Layout flottant (sidebar / navbar / drawer) | ✅ | — refonte 2026-10, thèmes clair & sombre |
| Tableau de bord | 🟡 | aggrège 4 appels existants au lieu d'un `/stats` (P1) |
| Patients (liste + dossier) | ✅ | — |
| Consultations (liste + détail) | ✅ | — |
| Odontogramme | ✅ | couleurs d'état désormais sur tokens (P1 : épingler le référentiel) |
| Ordonnances | ✅ | — |
| Agenda & RDV | ✅ | — |
| Cabinets | ✅ | — |
| Praticiens | ✅ | — |
| Facturation (factures, devis, caisse, détail) | ✅ | impression = **print navigateur**, pas de PDF serveur (P2) |
| Audit | ✅ | — |
| RBAC | ✅ | — |
| **Stock** | 🟡 | UI complète + états honnêtes, **branchée sur des endpoints inexistants** (P0) |
| **`/stock/commandes`** | ❌ | route qui rend la même page Stock : soit on la retire, soit on la traite en P1 |
| Page de stats / rapports | ❌ | non commencée (P2) |
| Portail patient | ❌ | non commencé (P2) |

---

## 2. Endpoints backend manquants

| # | Endpoint attendu | consommé par | Manque pourquoi |
|---|---|---|---|
| E1 | `GET/POST /stock/articles`<br>`GET/PUT/DELETE /stock/articles/{id}` | `stock-api.ts`, page Stock | module absent du backend |
| E2 | `GET/POST /stock/mouvements`<br>`PUT /stock/mouvements/{id}` | onglet Mouvements | idem |
| E3 | `GET /stock/alertes` (seuils + péremptions) | tuile KPI « stock critique » | aujourd'hui calculé **côté client** sur la page courante : faux si la pagination server change |
| E4 | `GET /notifications` (+ `PATCH /notifications/{id}/lu`) | panneau notifications de la navbar | aucun flux exposé |
| E5 | `GET /stats/dashboard` | tableau de bord | 4 requêtes + `limit=1` pour lire `total_records` ; coûteux et non atomique |
| E6 | `GET /rapports/{type}?debut&fin` | module Rapports | aucun module |
| E7 | `GET /facturation/stats` | tuiles KPI de la page Factures | KPI calculées sur **la page courante** (commenté en `factures-list-page.tsx:132`) |
| E8 | `GET /portail/patient/*` | futur portail patient | aucun module |
| E9 | `POST /ordonnances/{id}/pdf` | impression ordonnance | print navigateur seul |

> **Règle appliquée dans le code** : tant qu'un endpoint manque, la page affiche
> un état vide ou d'erreur explicite et porte un commentaire
> `// TODO(backend)`. Aucun mock silencieux.

---

## 3. Reste frontend

| Tâche | Détail | P |
|---|---|---|
| Retirer ou implémenter `/stock/commandes` | route identique à `/stock`, promu dans le menu | P1 |
| Épingler le référentiel odontogramme | les couleurs viennent du backend, donc du texte libre : risque de couleurs hors tokens | P1 |
| Découper le bundle | 662 kB (un seul chunk) — `React.lazy` sur les pages de détail | P1 |
| Accessibilité clavier | `Cmd+K` OK ; manque un piège de focus dans le drawer et le focus retour | P2 |
| Tests | aucun test automatisé ; la duplication du mapping `statut → tone` justifie `describe` | P1 |
| i18n | `ASTUCES` et les libellés de rôle sont des constantes FR dans le code | P2 |
| Impression PDF | `facture-print-modal` utilise le print ; à basculer sur E9 | P2 |
| PWA / hors-ligne | non commencé | P2 |

---

## 4. Priorités, charge et sprints

Charge : **S** ≈ 0,5 j · **M** ≈ 1–2 j · **L** ≈ 3–5 j

### P0 — Débloquer le module Stock
| # | Tâche | Charge | Endpoint |
|---|---|---|---|
| P0-1 | Schéma SQL + migration : `articles`, `mouvements_stock` | M | — |
| P0-2 | CRUD `/stock/articles` (recherche, catégorie, seuil d'alerte, péremption, prix) | L | E1 |
| P0-3 | CRUD `/stock/mouvements` (entrée/sortie, type, motif, auteur) | M | E2 |
| P0-4 | Permissions `STOCK:READ/CREATE/UPDATE/DELETE` dans la matrice RBAC | S | — |
| P0-5 | Câblage frontend : supprimer l'état « module indisponible » | S | E1/E2 |

### P1 — Fiabilité et cohérence
| # | Tâche | Charge |
|---|---|---|
| P1-1 | `GET /notifications` + panneau branché | M |
| P1-2 | `GET /stats/dashboard` + tableau de bord simplifié | M |
| P1-3 | `GET /stock/alertes` (fin du calcul client) | S |
| P1-4 | `GET /facturation/stats` (fin des KPI page-courante) | S |
| P1-5 | Découpage du bundle par route | M |
| P1-6 | Tests sur les mappings de statut et les états d'erreur | M |
| P1-7 | Résoudre `/stock/commandes` | S |

### P2 — Extensions
| # | Tâche | Charge |
|---|---|---|
| P2-1 | Module Rapports (P&L, encaissements, activité praticien) | L |
| P2-2 | Génération PDF serveur (facture, ordonnance) | M |
| P2-3 | Portail patient (rendez-vous + documents) | L |
| P2-4 | CIM-10 structuré + recherche de codes | M |
| P2-5 | Extraction des libellés FR vers l'i18n | M |
| P2-6 | PWA | L |

### Sprints proposés
- **Sprint 1** — P0 complet (Stock utilisable de bout en bout).
- **Sprint 2** — P1-1 à P1-4 (stats et notifications : moins d'appels, KPI justes).
- **Sprint 3** — P1-5 à P1-7 (qualité, bundle, tests, routes orphelines).
- **Sprint 4+** — P2 par lots, en commençant par les PDF.

---

## 5. Dépendances croisées

```
Stock (E1,E2) ──> permissions RBAC (P0-4) ──> menu + garde ProtectedRoute
              └─> /stock/alertes (E3) ─────> KPI page Stock

/stats/dashboard (E5) ──> remplace 4 appels ──> patients, factures, devis, caisse
/notifications (E4) ─────> topbar ──────────> badge de notifications

/facturation/stats (E7) ──> KPI Factures (aujourd'hui faux hors page 1)

PDF (E9) ──> facture-print-modal + ordonnance-print-modal
Rapports (E6) ──> nouveau module + nouvelle page (nécessite E7 en amont)

multi-tenant (tenants) ──> filtre tenant_id sur TOUS les modules ci-dessus
                           ⚠️ à poser avant E1..E8, sinon à reprendre partout
```

**Point d'attention** : le dossier `Backend/src/modules/tenants/` existe mais
expose 0 route dans `router.py`. Avant d'ajouter cinq nouveaux endpoints, il faut
clarifier si le cloisonnement multi-tenant est appliqué par décorateur
(`CurrentTenant`) ou manuellement module par module — sinon chaque endpoint
nouveau devra être corrigé après coup.

---

## 6. Risques

| Risque | Impact | Probabilité | Parade |
|---|---|---|---|
| Contournement du cloisonnement tenant sur les nouveaux endpoints | **Fuite de données entre cabinets** | Moyenne | Tracer et tester l'isolation avant E1..E8 |
| KPI faux quand la pagination server change (Stock, Factures) | Chiffres faux en production | **Élevée** (latent) | E3 + E7 en P1 |
| Bundle 662 kB non découpé | Lent sur connexion mobile, Objective-C fails | Moyenne | P1-5 |
| Aucun test sur les mappings statut → teinte | Régression silencieuse à l'ajout d'un statut | Moyenne | P1-6 |
| Absence de PDF serveur | Documents non conformes à l'archivage | Moyenne | P2-2 |
| `retry: false` sur Stock | Perte d'erreur transitoire sans nouvelle tentative | Faible | Acceptable : le bouton « Réessayer » est présent |
| Écrans non revus sur navigateur réel | Écarts de rendu non détectés | — | Les captures automatisées n'ont pas fonctionné ici (§7) |

---

## 7. Limites de cette vérification

À signaler franchement, car cela conditionne la confiance dans les livrables :

- **Le backend n'a jamais été démarré** (base Docker sur le port 55435
  inaccessible depuis l'environnement d'exécution). Le branchement réel des
  endpoints `stock` et `notifications` **n'est donc pas validé en HTTP** : il
  repose sur la lecture des routes déclarées.
- **Les écrans ont été inspectés via l'arbre d'accessibilité et les styles
  calculés**, pas par capture d'image : le panneau de prévisualisation ne
  produisait pas de frames. Les rayons (24 px sidebar, 20 px navbar), le flou
  d'arrière-plan et le liseré coloré des KPI (4 px) sont **confirmés par les
  styles calculés**, mais un contrôle visuel humain reste souhaitable.
- Les états d'erreur ont été.validés avec le backend coupé (réseau) et avec une
  réponse 404 simulée pour le chemin « endpoint absent ».

---

## 8. Arborescence et dépendances

```
SysDent Pro/
├── Backend/src/
│   ├── api/v1/router.py        ← 12 modules enregistrés
│   └── modules/                 ← ❌ stock, notifications, rapports
├── Frontend/src/
│   ├── components/
│   │   ├── layout/              ← sidebar, topbar, app-shell (layout flottant)
│   │   └── ui/                  ← page-header, status-badge, empty-state, FAB…
│   ├── features/                ← 11 domaines + stock (non branché)
│   ├── lib/                     ← api.ts (client unique), navigation.ts
│   └── providers/               ← theme-provider (mécanisme de thème intact)
└── PLAN_RESTE_A_FAIRE.md        ← ce document
```

Dépendances techniques du frontend : **React 19 · Vite 8 · TypeScript 6 ·
Tailwind 3 (`darkMode: class`) · TanStack Query 5 · Zustand 5 ·
react-router 7 · lucide-react**. Aucune dépendance ajoutée pendant la refonte.