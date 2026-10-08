# Backoffice SysDent Pro — plan du frontend

> Le backend plateforme est **largement construit** : 44 endpoints `/platform/*`
> existent déjà, avec permissions, rôles et étanchéité. Le manque est le frontend.
> Ce plan porte donc sur ce qui n'existe pas encore, et sur les rares trous côté
> backend.

---

## 1. Décision de cadrage — partage de code

**Option A (retenue, recommandée) — copier les tokens et les composants de base
dans `Backoffice/`.**

**Option B — package partagé (workspaces npm) pour les tokens et composants UI.**

### Pourquoi A pour démarrer

1. **Zéro risque de régression sur l'application client.** Le client est en
   production et couvert par 12 tests frontend. Un package partagé impose de faire
   évoluer les deux锁 en même temps : toute erreur de version casse le client.
2. **Le design system du client est encore en mouvement.** Les tokens, la bascule
   de thème et les composants (`PageHeader`, `KpiCard`, `StatusBadge`,
   `DataTable`, `Pagination`, `EmptyState`) viennent d'être créés ou modifiés. Un
   package figerait un état transitoire.
3. Le backoffice a une **identité visuelle distincte** (badge « Plateforme », accent
   propre). Un token partagé est utile ; un composant partagé l'est moins.

**Coût assumé** : la duplication des composants de base. Consigné comme évolution :
quand le design system du client se stabilise (fin des lots 4 et 6), extraire un
package `@sysdent/ui` est un travail mécanique et sans risque, à faire **avec** les
deux applications sous test.

### Ce qui est réellement copié, et non réécrit

Tokens de thème, primitives de boutons/cartes/modales/tableaux, `Pagination`,
`EmptyState`, `StatusBadge`, `PageHeader`, `KpiCard`, `ErrorBoundary`, mécanisme de
bascule sombre/clair. Le code est repris tel quel : il a été écrit pour être lu.

---

## 2. Stack — identique au client, sans écart gratuit

Reprise à l'identique du `Frontend/package.json` :

React 19.2, Vite 8.3, TypeScript 6.0, react-router-dom 7.18, Tailwind 3.4,
Zustand 5, TanStack Query 5.104, lucide-react, Vitest 3.2 + Testing Library,
oxlint.

**Ajouts justifiés :**

| Ajout | Pourquoi |
|---|---|
| `openapi-typescript` | génère les types depuis le schéma du backend |
| `openapi-fetch` | client typé, donc plus de paramètre écrit à la main |

---

## 3. Contrat frontend ↔ backend — décision 7

**Décision 7 : OUI**, appliquée **d'abord au backoffice**, sans coût de migration.

- Les types sont générés depuis l'OpenAPI **du groupe Platform**.
- Le client HTTP unique s'appuie sur `openapi-fetch`, typé : un paramètre non
  déclaré devient une erreur de compilation, pas un 422 à l'exécution.
- Le middleware `UnknownQueryParamMiddleware` du backend refuse déjà les paramètres
  inconnus en 422 : la défense est donc à deux niveaux.

**Pour l'application client, migration progressive** : les types sont générés et
utilisés pour les **nouveaux** écrans ; l'existant n'est pas migré maintenant.

Script CI `contrat:verifier` : régénère les types et échoue si le diff n'est pas
vide. C'est ce qui empêche la dérive entre le contrat publié et le contrat codé.

---

## 4. Tableau « écran → endpoints »

Lu dans le code, pas de mémoire. **44 endpoints `/platform/*` existent déjà.**

### Lot 1 — Socle et tableau de bord

| Écran | Endpoint | État |
|---|---|---|
| Connexion | `POST /platform/auth/login` | **existe** |
| 2FA — code | `POST /platform/auth/2fa` | **existe** |
| 2FA — préparation | `GET /platform/auth/2fa/preparation` | **existe** |
| 2FA — confirmation | `POST /platform/auth/2fa/confirmation` | **existe** |
| Profil | `GET /platform/auth/me` | **existe** |
| Déconnexion | `POST /platform/auth/logout` | **existe** |
| Renouvellement | `POST /platform/auth/refresh` | **existe** |
| KPI globaux | `GET /platform/stats/globales` | **existe** |
| Santé | `GET /platform/sante` | **existe** |
| Annonces récentes | `GET /platform/annonces` | **existe** |
| Audit récent | `GET /platform/audit` | **existe** (paginé) |

**Manque** : un endpoint d'**agrégats du tableau de bord** regroupant ce dont
l'écran a besoin en une requête. `stats/globales` existe mais son contenu n'a pas
été vérifié comme couvrant le tableau de bord ; à confirmer avant de l'utiliser.
→ **décision à valider** : ajouter `GET /platform/stats/dashboard`, ou composer
depuis les endpoints existants au prix de N requêtes.

### Lot 2 — Cabinets

| Écran | Endpoint | État |
|---|---|---|
| Liste paginée | `GET /platform/tenants` | **existe** (paginé) |
| Transitions autorisées | `GET /platform/tenants/transitions` | **existe** |
| Création | `POST /platform/tenants` | **existe** |
| Fiche | `GET` / `PATCH /platform/tenants/{id}` | **existe** |
| Historique des statuts | `GET /platform/tenants/{id}/historique` | **existe** |
| Quotas | `GET /platform/tenants/{id}/quotas` | **existe** |
| Simulation de quota | `GET /platform/tenants/{id}/quotas/simulation` | **existe** |
| Statistiques d'usage | `GET /platform/stats/tenants/{id}` | **existe** |
| Suspension | `POST /platform/tenants/{id}/suspension` | **existe** |
| Réactivation | `POST /platform/tenants/{id}/reactivation` | **existe** |
| Résiliation | `POST /platform/tenants/{id}/resiliation` | **existe** |
| Archivage | `POST /platform/tenants/{id}/archivage` | **existe** |
| Accès support du cabinet | `POST /platform/tenants/{id}/acces-support` | **existe** |
| **Renvoi d'invitation** | — | **MANQUE** |
| **Remplacement de l'administrateur initial** | — | **MANQUE** |
| **Export des données du cabinet** (tâche asynchrone) | — | **MANQUE** |
| **Liste des accès support actifs d'un cabinet** | `GET /platform/acces-support` | existe, mais filtrage par cabinet à vérifier |

### Lots 3 à 6

Les endpoints existent pour `plans`, `subscriptions`, `invoices`, `annonces`,
`acces-support`, `audit`, `users`, `permissions`, `roles`.

| Écran | Manque |
|---|---|
| Feature flags par plan / par cabinet | **MANQUE** |
| Statistiques d'usage par cabinet agrégées | existe (`stats/tenants/{id}`), contenu à vérifier |
| File de tâches / jobs planifiés | **MANQUE** (la santé existe, le détail non) |
| Relance des migrations d'un cabinet | **MANQUE** |
| Configuration du serveur de notifications | **MANQUE** |
| Gabarits de semis | **MANQUE** |

---

## 5. Arborescence

```
Backoffice/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── .env.example
├── public/
├── scripts/
│   └── generer-types.ts          openapi-typescript
└── src/
    ├── main.tsx                  ThemeProvider > QueryProvider > BrowserRouter
    ├── App.tsx                   routes
    ├── index.css                 tokens + primitives (copiés du client)
    ├── lib/
    │   ├── types-gen.d.ts        TYPES GÉNÉRÉS — ne pas éditer à la main
    │   ├── client.ts             openapi-fetch : client unique
    │   └── cn.ts
    ├── stores/
    │   ├── auth-store.ts         jetons, purge idempotente, multi-onglets
    │   └── toast-store.ts
    ├── providers/
    │   ├── theme-provider.tsx    bascule sombre/clair
    │   └── query-provider.tsx
    ├── guards/
    │   ├── route-guard.tsx       session + permission
    │   └── can.tsx               <Can> + usePermission
    ├── components/
    │   ├── layout/               sidebar et navbar flottantes, arrondies
    │   └── ui/                   boutons, cartes, modales, tableaux, Pagination…
    ├── features/
    │   ├── auth/                 connexion, 2FA, première configuration
    │   ├── dashboard/            tableau de bord global
    │   ├── tenants/              liste, création, fiche, actions de cycle de vie
    │   ├── plans/  subscriptions/  invoices/
    │   ├── support/  audit/  stats/  health/  announcements/
    │   └── platform-users/
    └── pages/
```

---

## 6. Différenciation obligatoire avec l'application client

Une erreur de destination serait grave : un accès support donne accès à **tous** les
cabinets. Toute confusion entre les deux interfaces est un incident de sécurité.

| Moyen | Mise en œuvre |
|---|---|
| Badge « Plateforme » | permanent dans la navbar |
| Accent distinct | token `--color-accent-plateforme`, aucun accent du client réutilisé |
| Titre d'onglet | « SysDent Pro – Backoffice » |
| Favicon | propre |
| Port de développement | distinct (5174 par défaut) |
| CORS backend | origine du backoffice en liste blanche, jamais `*` |

---

## 7. Confidentialité — le backoffice ne montre aucun contenu clinique

Ni diagnostics, ni dossiers, ni odontogramme, ni ordonnances, ni documents. À
vérifier **dans les types générés autant que dans l'interface** : c'est le filet
technique, l'interface seule pouvant être contournée par une URL.

---

## 8. Règle sur les nouvelles listes — décision 8 reportée

Les 12 routes non semables restent au registre, dans `docs/TESTS.md`. D'ici là :

> **Toute nouvelle route de liste, y compris celles du backoffice, doit être
> semable et couverte par le test de contrat comportemental dès sa création. Le
> stock ne doit pas augmenter.**

---

## 9. Ordre de réalisation

1. **Lot 1** — socle, 2FA, layout, navigation par rôle, tableau de bord
2. **Lot 2** — cabinets : liste, création, fiche, actions de cycle de vie
3. Lots 3 → 6 dans l'ordre

Chaque lot : backend si nécessaire → frontend → tests → non-régression → commit.

---

## 10. Décisions à valider

| # | Décision | Recommandation |
|---|---|---|
| A | Copier les composants plutôt que package partagé | **Appliquer A** pour démarrer, extraire `@sysdent/ui` quand le design system se stabilise |
| B | Endpoint d'agrégats pour le tableau de bord | **Ajouter** `GET /platform/stats/dashboard` : 9 requêtes au chargement sont un défaut, pas une optimisation |
| C | Stockage du jeton plateforme | cookie `httpOnly` si le backend le pose ; sinon mémoire + refresh — **à vérifier** |
| D | Codes de secours 2FA | le backend似乎 ne les prévoit pas ; à ajouter si le propriétaire les veut |

---

## 11. État à date — 2026-10-08

### Socle écrit et vérifié

| Contrôle | Résultat |
|---|---|
| `npx tsc -b --force` | **propre** |
| `npm run build` | **réussi** |
| Structure | 34 fichiers TS/TSX |

### Réserves ouvertes

| Réserve | Détail |
|---|---|
| **`oxlint` ne s'exécute pas** | le binding natif n'est pas résolu (`Cannot find native binding`) : l'installation a dû passer par `--legacy-peer-deps`, qui **saute les dépendances optionnelles**. Le build et le type-check passent ; le lint est donc **non vérifié** sur ce projet. À reprendre. |
| **`openapi-typescript@7` exige TypeScript 5**, le projet est en TS 6. Écart de peer accepté : l'outil ne fait que **générer** des types à la construction, il n'est jamais chargé à l'exécution. **Décision à valider.** |
| **`baseUrl` déprécié en TS 6** | retiré ; les `paths` relatifs suffisent. |
| CORS backend | l'origine `http://127.0.0.1:5174` doit être ajoutée à la liste blanche du backend — **non fait**. |

### Fichiers écrits

**Configurations** : `package.json`, `vite.config.ts` (port 5174), `tsconfig.{json,app,node}`,
`tailwind.config.js` (+ accent plateforme), `postcss.config.js`, `.env.example`,
`index.html`, `src/vite-env.d.ts`.

**Design system** : 20 composants copiés depuis l'application client — `button`, `card`,
`modal`, `drawer`, `dialog`, `table`, `tabs`, `pagination`, `empty-state`, `status-badge`,
`page-header`, `kpi-card`, `data-table`, `confirm-dialog`, `select`, `input`, `label`,
`textarea`, `badge`, `avatar`, `skeleton`, `toast`, `floating-action-button`,
`error-boundary`. Plus `theme-provider` et `toast-store`.

**Écrit pour le backoffice** :

| Fichier | Rôle |
|---|---|
| `src/lib/api.ts` | client HTTP unique, déduplication du renouvellement, refus de rejouer avec un jeton mort |
| `src/stores/auth-store.ts` | session plateforme, **2FA obligatoire**, purge idempotente, propagation multi-onglets |
| `src/stores/tenant-store.ts` | cabinet consulté, purgé à la déconnexion |
| `src/providers/query-provider.tsx` | cache vidé à la purge — **sans `useNavigate`**, le composant étant au-dessus du routeur |
| `src/guards/can.tsx` | `<Can>` et `usePermission`, pilotés par `/platform/auth/me` |
| `src/guards/route-guard.tsx` | garde de session et de permission |
| `src/features/auth/login-page.tsx` | connexion + saisie du code TOTP, message d'erreur unique |
| `src/pages/{forbidden,not-found}.tsx` | 403 et 404 |

### Non fait

Écrans des Lots 1 et 2 (tableau de bord, cabinets), types OpenAPI générés, layout
(sidebar et navbar flottantes), `GET /platform/stats/dashboard`, et les 5 endpoints
manquants relevés au tableau.

### Parcours à vérifier manuellement

Aucun rendu n'a pu être observé : **il n'y a pas de navigateur dans cette session**.
- `npm run dev` dans `Backoffice/` — l'écran de connexion s'affiche, badge « Plateforme »
  visible, thème sombre et clair.
- Erreur de connexion : un seul message, quelle que soit la cause.
- Flux 2FA : compte sans 2FA → écran de code ; mauvais code → refus.
