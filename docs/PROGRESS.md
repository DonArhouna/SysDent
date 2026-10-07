# SysDent Pro — journal de reprise

> **Usage** : ce fichier est le point de départ de toute session. Il dit où on en
> est, ce qui est **prouvé**, ce qui ne l'est pas, et par où reprendre.
> Mis à jour à la fin de chaque étape. Un commit atomique par étape.

---

## État à date : 2026-10-07 (session 2)

**Étape en cours : 2 — file d'attente.** Migration **écrite et testée sur copie**,
**pas encore appliquée** à la base de démo. Étape 1 close et prouvée.

---

## Étape 2 — File d'attente : migration prête, application en attente

### Ce qui est fait

| Livrable | État |
|---|---|
| `docs/corrections/06_FILE_ATTENTE.md` — plan d'exécution | écrit avant toute modification |
| Sauvegarde de la base de démo | `%LOCALAPPDATA%\Temp\opencode\sysdent_demo_avant_file_attente_20261007_2104.dump` (0,25 Mo) |
| Copie de test `sysdent_copie_file_attente` | créée, 8 rdv / 32 patients / 30 consultations restaurés |
| `e8b2c4a7d1e5_file_attente.py` | écrite, appliquée sur la copie, **aller-retour vérifié 2 fois** |

### Preuve sur copie

| Contrôle | Résultat |
|---|---|
| Table `file_attente` créée | oui |
| 11 index, dont les 3 uniques partiels | oui |
| **Deuxième arrivée du même patient** | **REFUSÉE** — `duplicate key value violates unique constraint "uq_file_attente_actif"` |
| Nouvelle arrivée après clôture du passage | acceptée |
| `downgrade` | table supprimée |
| Ré-application après `downgrade` | **échouait** — voir ci-dessous |
| Données préexistantes après aller-retour | 8 rdv / 32 patients / 30 consultations, intactes |

### Un défaut de réversibilité trouvé et corrigé

Le premier aller-retour a **échoué** : `op.drop_table` ne supprime pas le type énuméré
créé par `create_table`. La ré-application levait
`DuplicateObject: type "statutfileattenteenum" already exists`.

Une migration « réversible » sur le papier ne l'est pas si son aller-retour échoue :
c'est précisément ce que le test sur copie sert à attraper, et un `downgrade` qui
fonctionne une seule fois ne prouve rien. Corrigé par un `DROP TYPE IF EXISTS` dans
`downgrade()`, puis vérifié sur deux cycles complets.

> **À surveiller** : aucune autre migration de ce dépôt ne comporte de `DROP TYPE`
> (`grep` sur `alembic_tenant/versions/` : zéro occurrence). La même latence
> existe probablement ailleurs. À auditer à l'étape 7.

### Pourquoi la migration n'est pas encore appliquée

La suite complète backend tournait encore (20 % au moment de l'arrêt) : la règle
« non-régression verte avant de passer à l'étape suivante » n'est pas satisfaite.
La migration étant **purement additive** — elle crée une table et ne touche aucune
table ni aucune ligne existante — le risque de régression est faible, mais « faible »
n'est pas « prouvé », et la règle l'interdit.

### Reprise — ordre exact

1. `docker ps` → `sysdent_s0b` doit être `Up`
2. Reprendre la suite : `cd Backend`, poser `MASTER_DB_PORT=55435` et
   `TENANT_DB_PORT=55435`, puis `.\.venv\Scripts\python.exe -m pytest -q --tb=short`
   → doit être **verte**
3. Appliquer : poser
   `ALEMBIC_TENANT_DB_URL='postgresql+psycopg2://postgres:<pw>@127.0.0.1:55435/sysdent_tenant_clinique_cabinet_sn_5bd215'`
   puis `.\.venv\Scripts\python.exe -m alembic -c alembic_tenant.ini upgrade head`
4. Modèle ORM `FileAttente` + `StatutFileAttenteEnum` dans `src/modules/tenants/models.py`
5. Permissions `ATTENTE:READ/CREATE/UPDATE/CALL` dans `src/common/permissions.py`
   (matrice dans `06_FILE_ATTENTE.md` §4)
6. Module `src/modules/attente/` : services, router, schemas — 7 endpoints (§5 du plan)
7. Tests `tests/test_file_attente.py` — dont **concurrence** (§8 du plan)
8. Écrans `/attente` secrétaire + dentiste
9. Rejouer la suite complète

Le mot de passe de la base se lit dans `Backend/.env`, clé `TENANT_DB_PASSWORD`
(il n'est pas dans `.env.example` en clair). La copie `sysdent_copie_file_attente`
peut être supprimée : `docker exec sysdent_s0b psql -U postgres -c 'DROP DATABASE sysdent_copie_file_attente'`.

---

## Étape 0 — reprise

### Dépôt

| | |
|---|---|
| Branche | `main`, **arbre propre** (0 fichier modifié) |
| Dernier commit | `6d669e1` — *feat: add platform module, stock, caisse, utilisateurs, alembic platform migrations and full documentation* (2026-10-07 18:27, 147 fichiers) |
| Contrainte levée | La session précédente laissait ~73 fichiers non commités. C'est fini : tout est dans `6d669e1`. |
| Tête Alembic tenant | `d7f2a9c4b6e1` (17 migrations) |

### Infrastructure au contrôle

Les quatre conteneurs tournaient déjà : `sysdent_s0b` (55435), `sysdent_master_db` (5432), `sysdent_redis`, `emp_postgres`.

### Outillage frontend — gaps comblés

Le dépôt client **n'avait aucun outillage de test** : ni Vitest, ni jsdom, ni
Testing Library. Toute la vérification frontend reposait sur `tsc -b` et
`oxlint`, qui ne disent rien du comportement. Ajouté :

- `vitest@3.2.7` + `@vitest/coverage-v8@3.2.7` (épinglés : `@vitest/ui@3.2.7` était
  déjà présent et exige `vitest@3.2.7` — une installation non épinglée échoue en
  `ERESOLVE`)
- `jsdom`, `@testing-library/react`, `@testing-library/dom`, `@testing-library/jest-dom`
- `npm run test` / `npm run test:watch`
- **Pas de MSW** : les assertions portent sur le *nombre d'appels* et le *nombre de
  purges*, pas sur l'encodage HTTP. Un `fetch` piloté à la main prouve le
  mécanisme réel sans dépendance supplémentaire.
  → **décision à valider** : accepter un test sans intercepteur réseau ?

`npm install` exige `npm install-scripts approve esbuild` (npm 11+) sinon Vitest ne
trouve pas son binaire. Déjà fait sur ce poste ; à refaire sur un poste neuf.

---

## Étape 1 — correctif de session expirée : **PROUVÉ**

### Le défaut

Session expirée → 401 → échec du renouvellement → l'application **continuait
d'appeler l'API avec un jeton mort**. Cascade de 401 puis de 403 qui ne
parlaient d'aucune permission réelle : l'utilisateur cherchait une panne de droits
inexistante.

### Ce que les tests ont trouvé en plus du défaut connu

Trois défauts réels, découverts **par les tests** et non à la lecture :

| # | Défaut | Effet |
|---|---|---|
| 1 | **Cache React Query non vidé** à la déconnexion (S0-7) | Sur un poste partagé, la personne suivante voit les données de la précédente avant même que la première requête ne revienne. Fuite inter-utilisateurs. |
| 2 | **Site mémorisé jamais purgé** (`cabinet-store`, `localStorage: sysdent-cabinet-storage`) | Un identifiant de site = un identifiant de tenant. Le second utilisateur porte ses requêtes vers le site du premier. Le backend refuse (l'isolation tient), mais l'application demande une donnée qui n'est pas la sienne et affiche une erreur incompréhensible. **Trouvé par le test, pas par la relecture.** |
| 3 | **Aucun multi-onglets** | Le `localStorage` partagé ne met pas à jour un store déjà chargé : un onglet resté ouvert continue d'appeler l'API avec un jeton révoqué. |

Et un défaut dans le **correctif précédent lui-même** :

| # | Défaut | Cause |
|---|---|---|
| 4 | **Six purges au lieu d'une** | Le verrou « purge en cours » ne verrouillait rien : les six 401 arrivent **échelonnés**, chacun après la résolution de la promesse de renouvellement partagée. La première purge se termine avant que la suivante n'arrive. L'état correct est « cette session est **déjà morte** », pas « une purge est en cours ». |

### Couverture de la chasse à la fuite

| Emplacement | Verdict |
|---|---|
| `localStorage: sysdent-auth` | purgé (jetons + profil) |
| `localStorage: sysdent-cabinet-storage` | **purgé (correction)** |
| `localStorage: thème` | laissé — préférence non sensible, expressly autorisé |
| `sessionStorage` | aucune écriture dans le dépôt |
| IndexedDB | aucun usage |
| Service Worker / Cache API | absent (`public/` ne contient que deux SVG) |
| Brouillons de formulaires | aucun : les « brouillons » du code sont des **statuts** de documents (`BROUILLON`), pas de l'état local |
| Toasts | messages d'erreur backend, pas de donnée de santé structurée ; non purgés (arbitrage documenté) |

### Preuve

`Frontend/src/test/session-expiree.test.ts` — 6 tests.

**Avant correction : 3 échecs** (purge du site, multi-onglets, six purges).
**Après : 6/6 verts.** `tsc -b` propre, `oxlint` 0 erreur.

| Test | Prouve |
|---|---|
| purge unique, pas de rejeu, pas de cascade | 2 appels seulement (métier puis refresh) — c'est le défaut observé |
| six requêtes simultanées | 1 seul `POST /auth/refresh`, 7 appels au total, 1 purge |
| session valide survit | rejeu avec le **nouveau** jeton, 0 purge |
| second utilisateur ne voit rien | `client.clear()` **avant** toute navigation |
| site mémorisé purgé | store cabinet + `localStorage` |
| multi-onglets | l'onglet B est purgé **sans** que B ait déconnecté |

### Non vérifié

**Le rendu navigateur.** Aucun test de ce fichier n'observe ce qui s'affiche. Le
comportement visible reste à confirmer par l'utilisateur : laisser expirer la
session → redirection vers `/login`, **aucune** cascade 401/403.

---

## Reste à faire

| # | Étape | État |
|---|---|---|
| 2 | File d'attente (salle d'attente) | à faire — **démarre ici** |
| 3 | Historique clinique | à faire |
| 4 | Référentiels configurables | à faire |
| 5 | Fusion Praticien → Utilisateur | à faire — risque élevé, ne pas apply sans test sur copie |
| 6 | Rôle Médecin chef | à faire |
| 7 | Contrôle de dérive | à faire |
| 8 | État d'écart du cahier des charges | à faire, sans implémentation |

### Documents périmés

- `docs/corrections/RAPPORT_FINAL.md` — écrit avant les six derniers chantiers
- `docs/corrections/MATRICE_ROLES.md` — idem, à **régénérer depuis le code**
- `docs/audit/05_FEUILLE_DE_ROUTE.md` — **S0-7 à clore** (prouvé par le test
  « vide le cache React Query »)

---

## Décisions à valider

1. **Tests frontend sans MSW** (fetch piloté) — choix fait pour l'économie et la
   précision ; à confirmer.
2. **Toasts non purgés à la déconnexion** — un message d'erreur backend peut
   contenir un nom de patient ; il resterait à l'écran pour l'utilisateur suivant.
   Arbitrage : purge nécessaire ou surcoût injustifié ?
3. **`BroadcastChannel` sans repli `storage`** — disponible partout depuis 2022 ;
   pas de repli pour les navigateurs antérieurs.