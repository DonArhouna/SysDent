# 00 — État des lieux : que contient le backend SysDent Pro aujourd'hui ?

> **Étape 0 de la mission « couche plateforme (backoffice) backend ».**
> Document rédigé **avant** toute écriture de code, à partir de la lecture du code
> (`Backend/src`, `Backend/tests`, migrations Alembic) et de l'interrogation directe
> de la base de démonstration.
> Toutes les affirmations marquées ✅ ont été vérifiées par exécution ; les autres
> sont des lectures de code et sont référencées par `fichier:ligne`.

---

## 1. Méthode et périmètre

| Élément | Valeur |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 async (asyncpg) + Alembic (2 contextes) |
| Bases | 1 base **master** (`sysdent_master`) + **N bases tenant** (1 par cabinet) |
| Environnement vérifié | PostgreSQL 16.15 (conteneur Docker `sysdent_s0b`, port `55435`) |
| Entrées analysées | 12 modules métier, 18 443 lignes de `Backend/src`, 13 fichiers de tests |
| Hors périmètre | Frontend client (seuls les points d'intégration listés seront touchés) |

✅ **Environnement de base re joint.** Contrary to earlier assessments in this
project, the demo database **is** reachable from this shell (`localhost:55435`).
Consequence: the whole platform back-office, including its test suite, can be
executed for real. This is verified at §10.

---

## 2. Cartographie du backend

```
Backend/src
├── main.py                     FastAPI, middlewares, /health
├── api/v1/router.py            Assemble 12 sous-routeurs (⚠️ `tenants` NON câblé)
├── core/
│   ├── config.py               Settings (pydantic-settings) — .env
│   ├── database.py             master_engine + TenantDatabaseManager (LRU de pools)
│   ├── security.py             argon2/bcrypt, création JWT, Fernet
│   ├── rate_limit.py           RateLimiter en mémoire (fenêtre glissante)
│   ├── migrations.py           upgrade_master_to_head() / upgrade_tenant_to_head(url)
│   ├── exceptions.py           AppException + 9 sous-exceptions typées
│   ├── middleware.py           corrélation (X-Request-ID) + headers de sécurité
│   └── exception_handlers.py  unification des erreurs en `{success, error:{code,message}}`
├── common/                     permissions.py (catalogue tenant), pagination, schémas
└── modules/
    ├── master/                 ← **le seul embryon de plateforme existant**
    ├── auth/ cabinets/ patients/ consultations/ odontogramme/
    ├── ordonnances/ facturation/ rendezvous/ rbac/ audit/
    └── tenants/                modèles de la base tenant + models.py (1071 lignes)
```

Trois classes déclaratives distinctes, une par univers de données :

| Classe | Fichier | Base | Contenu |
|---|---|---|---|
| `Base` | `src/common/base_model.py:17` | `sysdent_master` | `societes`, `tenants_db`, `utilisateur_index`, `super_admins`, … |
| `TenantBase` | `src/common/base_model.py:22` | base du cabinet | patients, consultations, factures, `utilisateurs`, `audit_logs`… |
| `PlatformBase` | **à créer** | base plateforme | *inexistant à ce jour* |

`TenantBase` est séparée de `Base` précisément parce que les deux jeux de modèles
sont chargés dans le même process (`master/services.py` importe des modèles tenant)
et qu'un registre de métadonnées partagé ferait créer les tables au mauvais endroit
(`base_model.py:23-29`). **Ce raisonnement s'applique tel quel à une troisième base.**

---

## 3. Stratégie d'isolation réellement en place

### 3.1 Ce n'est PAS « un schéma par tenant » : c'est **une base PostgreSQL par tenant**

✅ Vérifié sur l'instance de démonstration :

```
$ psql -p 55435 -l
postgres, sysdent_master,
sysdent_tenant_clinique_cabinet_sn_2f36e8, sysdent_tenant_clinique_cabinet_sn_5bd215,
sysdent_tenant_clinique_cabinet_sn_cb3730, ... (19 bases tenants)
```

Le nom `_bootstrap_tenant_schema_and_admin` est **trompeur** : la fonction
(`master/services.py:63`) applique un schéma *dans* une base dédiée. Le vrai
prototype est `sanitize_db_name()` (`master/services.py:34`) :
`sysdent_tenant_{nom_slug}_{6 hex}`.

**Conséquence directe : « migrations sur l'ensemble des schémas tenants » se traduit
en réalité par « exécuter les migrations sur l'ensemble des *bases* tenants ».** La
Formulation de la mission reste valide, l'implémentation doit viser les bases.

### 3.2 Cycle de vie d'une base tenant

```
POST /master/societes
  └─ 1. INSERT societes + tenants_db(statut=PROVISIONING)  → COMMIT ✅
  └─ 2. CREATE DATABASE "<db_name>"      (connexion AUTOCOMMIT vers `postgres`)
  └─ 3. alembic upgrade head             (dans un thread : `asyncio.to_thread`)
  └─ 4. semis RBAC + formulaire médicaments + cabinet + admin + praticien
  └─ 5. UPDATE tenants_db.statut = ACTIVE + index email → COMMIT ✅
```

`CREATE DATABASE` ne peut pas s'exécuter dans une transaction : le commit de l'étape 1
précède donc l'étape 2. **Si l'étape 2 ou 3 échoue, la société reste en base avec le
statut `PROVISIONING`** (`master/services.py:432-448`) : c'est un état repris
manuellement, pas un rollback.

✅ **Cette situation existe déjà en démo : 6 sociétés sur 29 sont en `PROVISIONING`**
(cabinet créé, base jamais finalisée). C'est exactement le défaut que la Phase B doit
corriger par un provisionnement transactionnel avec reprise.

### 3.3 Où vit le registre des tenants

`sysdent_master`, tables (✅ vérifiées) :

| Table | Rôle |
|---|---|
| `societes` | identité du cabinet : nom, NINEA, contacts, `pays`, `actif` |
| `tenants_db` | **1 ligne par tenant** : `db_name`, `db_host/port/user`, `db_password` (**chiffré Fernet**), `statut` (`ACTIVE`/`PROVISIONING`/`SUSPENDED`/`ARCHIVED`), `schema_version` |
| `utilisateur_index` | routage `email → société_id` : rend le login tenant **O(1)** |
| `audit_logs_global` | journal maître (acteur email, action, cible, détails JSONB, IP) |

`db_password` est chiffré au repos par Fernet (`core/security.py:108`,
clé `TENANT_DB_ENCRYPTION_KEY`) ✅ — bon pattern, à conserver.

### 3.4 Comment le tenant est résolu à chaque requête

`auth/dependencies.py:48` (`get_tenant_db`) :

```
JWT (claim tenant_id)  ──ou──  header X-Tenant-ID
        ↓
uuid.UUID(tenant_id)                     # échec → 401 TENANT_ID_INVALIDE
        ↓
SELECT * FROM tenants_db
 WHERE societe_id = ? AND statut = 'ACTIVE'   # échec → 404 TENANT_NOT_FOUND
        ↓
tenant_db_manager.get_or_create_engine(...)   # pool LRU, 50 moteurs max
        ↓
AsyncSession sur la base du cabinet
```

Le statut `ACTIVE` de `tenants_db` est **déjà un point de coupure réel** : suspendre
un tenant coupe l'API (pas seulement le login). C'est un excellent point d'ancrage
pour la machine à états de la Phase B — mais il ne couvre **que** deux valeurs
(`ACTIVE` vs tout le reste) et il n'y a **aucune notion d'essai, de date d'expiration
ni d'historique**.

### 3.5 Périmètre de protection multi-tenant réel

✅ `POST /master/societes` est protégé (`master/router.py:151`) — un `CREATE DATABASE`
n'est plus déclenchable sans jeton Super Admin.
✅ Le login tenant résout via l'index avant d'ouvrir **une seule** base.
✅ Les tests d'isolation existants (`test_patients_isolation.py`,
`test_odontogramme_isolation.py`, `test_consultations_isolation.py`) prouvent
l'absence de fuite inter-tenant côté requête.

⚠️ **Angle mort** : la résolution accepte un header `X-Tenant-ID` lorsque le JWT n'en
porte pas (`auth/dependencies.py:42`). Sans jeton, `get_token_payload` lève une 401
avant, donc le header n'est aujourd'hui exploitable que par un porteur de jeton
valide — mais un jeton tenant valide pourrait demander la base **d'un autre cabinet**
si le compte existe dans les deux. *À durcir en Phase B* (le tenant doit venir du
JWT uniquement).

---

## 4. Authentification actuelle

### 4.1 Format des JWT

`core/security.py:29` — HS256, clé unique `SECRET_KEY` (⚠️ **la même pour tenants et
console master**).

| Claim access | Valeur |
|---|---|
| `sub` | `str(uuid)` utilisateur |
| `tenant_id` | uuid société (tenant) ou `null` (master) |
| `role` | nom du rôle, ex. `ADMIN_CABINET` / `SUPER_ADMIN` |
| `permissions` | liste `"MODULE:ACTION"` |
| `type` | `"access"` ou `"refresh"` |
| `iat`, `exp`, `nbf` | timestamps Unix |

| Claim refresh | Valeur |
|---|---|
| `sub`, `tenant_id`, `jti` | identifiant de session unique |
| `type` | `"refresh"` |

- **Durée** : access **15 min**, refresh **7 jours** (`config.py:27-28`).
- **Audience / `scope`** : ⚠️ **absents**. C'est le point faible structurel qui
  empêche aujourd'hui toute étanchéité forte entre mondes.
- **Rotation** : ✅ implémentée — l'ancien refresh est marqué `est_revoque` et un
  nouveau `jti` est créé (`auth/services.py`).
- **Révocation** : ✅ table `sessions_utilisateurs` (tenant) et `super_admin_sessions`
  (master).
- ⚠️ **Le refresh token est stocké en clair** en base (`sessions_utilisateurs.refresh_token`,
  colonne `unique`). Une fuite de la base d'un cabinet donne directement des refresh
  tokens rejouables. *Chiffré à l'instar de `db_password` — correction recommandée.*

### 4.2 Hachage des mots de passe

✅ Argon2 (memory_cost 65536, time_cost 3, parallelism 4) via `passlib`,
bcrypt en repli (`core/security.py:10`). `deprecated="auto"` : les hash bcrypt
existants sont migrés à la réauthentification. **Conforme.**

### 4.3 2FA

❌ **Cols existent, logique absente.** `utilisateurs.deux_facteurs` (bool) et
`utilisateurs.secret_2fa` (String(100)) sont déclarés
(`tenants/models.py:153-154`) mais **aucune ligne de code** ne les lit ou ne les
écrit : aucun TOTP, aucune vérification à la connexion. Le modèle promet une
fonctionnalité qui n'est pas implémentée — un écart à ne pas propager côté plateforme.

### 4.4 Limitation de débit

✅ `RateLimiter` à fenêtre glissante, en mémoire, clé `email|IP`,
5 tentatives / 5 min puis blocage 15 min (`core/rate_limit.py`). Appliqué au login
tenant (`auth/router.py:50`) et au login master (`master/router.py:62`).
⚠️ Limite assumée et documentée : en mémoire ⇒ non partagé entre workers/multi-instances.

### 4.5 Politique de mots de passe

❌ **Aucune.** `SocieteCreate.admin_password` impose seulement `min_length=8`
(`master/schemas.py:20`). Pas de exigence de complexité, pas d'historique, pas de
contrôle de similarité avec l'email. *La Phase A l'impose pour la plateforme.*

---

## 5. Ce qui existe déjà côté plateforme

| Attendu | Existant | Manquant |
|---|---|---|
| Modèle de tenant | ✅ `societes` + `tenants_db` | statut métier structuré (`essai/actif/suspendu/résilié`), dates d'essai, historique |
| Statuts | ⚠️ `tenants_db.statut` technique (`ACTIVE/PROVISIONING/SUSPENDED/ARCHIVED`) + `societes.actif` booléen | machine à états, motif obligatoire, horodatage |
| Plans / quotas | ❌ **rien** (`grep -ri "plan\|quota"` → 0 résultat métier) | tout |
| Abonnements / factures éditeur | ❌ rien | tout |
| Rôles « super admin » | ⚠️ `super_admins` : un rôle unique, **aucun RBAC**, `permissions=["*"]` en dur dans le JWT | 5 rôles métier, permissions `platform.*` |
| Routes d'administration | ⚠️ `/master/*` : auth (4), societes (CRUD + statut), statistiques — **non paginées** | registre paginé, filtres, exports |
| Audit plateforme | ⚠️ `audit_logs_global` (append-only par convention, **pas de garde SQL**, pas d'export) | immuabilité garantie, avant/après, motif, CSV |
| Jobs / tâches planifiées | ❌ **aucun** — `arq` est dans `requirements.txt` mais n'est importé nulle part ; Redis est configuré mais jamais utilisé | expiration d'essai, stats agrégées, export asynchrone |
| Statistiques | ⚠️ `GET /master/statistiques` — un `COUNT(*)` global | stats par tenant, agrégation planifiable |
| Notifications / annonces | ❌ rien | tout |
| Support / impersonation | ❌ rien | tout |

**Ce qui existe est un « outillage » (un seul super-admin technique qui provisionne),
pas une plateforme.** La granularité est binaire.

---

## 6. Diagnostic des deux anomalies vues dans le navigateur

### 6.1 `GET /api/v1/rbac/roles` → **500** — bug backend réel

**Cause racine** : `rbac/services.py:201`

```python
"nb_utilisateurs": len(role.utilisateurs or []),
```

La requête de `lister_roles` (`rbac/services.py:180-184`) ne charge que
`permission_roles → permission` via `selectinload`. La collection `utilisateurs`
**n'est pas chargée**. En SQLAlchemy async, un accès paresseux hors du greenlet
lève `MissingGreenlet`, qui remonte en 500.

Le projet **connaît déjà ce piège** : il est corrigé explicitement à deux endroits
avec le même commentaire — `master/services.py:479-483` (`societes`)
et `auth/services.py:29-36` (`_permissions_de`, « *un accès paresseux hors du
greenlet async échoue (MissingGreenlet)* »). `lister_roles` a été oublié.

**Correctif** : une requête de comptage explicite (un `select(func.count())`
groupé sur `role_id`) au lieu d'un accès paresseux. Un `selectinload` gaspillerait
une requête par rôle ; le `COUNT` groupé en coûte une seule.

Déjà consigné comme **B1** dans [`PLAN_RESTE_A_FAIRE.md`](../../PLAN_RESTE_A_FAIRE.md) §B1.

### 6.2 `GET /api/v1/utilisateurs?limit=50` → **404** — endpoint inexistant

✅ Vérifié : `grep -rn "@router" src/` → **aucun routeur `/utilisateurs`**. Le module
n'existe pas côté backend.

Mais le frontend est **entièrement prêt** : `Frontend/src/features/utilisateurs/`
(service `utilisateurs-api.ts` avec `list`/`create`/`update`/`resetPassword`/`remove`,
page `utilisateurs-page.tsx`, types, entrée de navigation). L'écran est donc
fonctionnellement mort : il affiche l'état d'erreur « indisponible » ajouté en
mission 1, sans état vide trompeur.

**Root cause** : fonctionnalité jamais livrée côté backend — déjà consigné comme
**B10** (P0) dans [`PLAN_RESTE_A_FAIRE.md`](../../PLAN_RESTE_A_FAIRE.md) §B10.

> **Décision à valider n°1.** La Phase C demande de brancher le quota « sur la limite
> d'utilisateurs déjà prévue dans la gestion des utilisateurs du tenant ». **Cette
> limite n'existe pas** (`grep -ri "illimit\|max_utilisateurs"` → 0 résultat) : il n'y
> a ni module ni valeur « illimitée par défaut ».
> **Recommandation :** livrer le **service de quotas central** + ses points d'appel,
> et traiter le module `/utilisateurs` comme le chantier **P0-5** déjà prévu par la
> feuille de route (hors périmètre de la mission plateforme). Le quota utilisateurs
> sera alors appliqué en une ligne au moment où ce module sera livré.
> *Alternative : livrer `/utilisateurs` dans cette mission — mais c'est une
> fonctionnalité de l'application cliente, pas de la plateforme, et cela doublerait
> le périmètre.*

### 6.3 Les 401 observés

✅ **Artificiels, pas un bug.** Les tours précédents ont injecté une fausse session
dans `localStorage` (`sysdent-auth` avec `token: "jeton-de-visualisation"`) pour
inspecter l'interface sans backend. Un tel jeton est rejeté à la signature → 401 sur
`/cabinets`, `/factures/journal-caisse`, puis `/auth/refresh` → « *La session a
expiré* » (`auth-store.ts:151`) → `/auth/logout`. **Comportement correct et
sécurisé.** Nettoyage du `localStorage` fait.

---

## 7. Écarts entre l'existant et la cible

| # | Cible | État | Écart | Phase |
|---|---|---|---|---|
| E1 | Identité plateforme dédiée, 5 rôles | `super_admins` mono-rôle, sans permission | **Total** | A |
| E2 | Clé de signature + audience distinctes | clé unique, pas d'audience | **Total** | A |
| E3 | 2FA TOTP obligatoire | colonnes vides, aucune logique | **Total** | A |
| E4 | Politique de mot de passe, IP whitelist | `min_length=8` seul | **Total** | A |
| E5 | Amorçage par CLI explicite | `init_db.py` lit `SUPER_ADMIN_EMAIL/PASSWORD` du `.env` | Partiel | A |
| E6 | Machine à états tenant | booléen `actif` + statut technique | **Total** | B |
| E7 | Provisionnement transactionnel avec rollback | commit avant `CREATE DATABASE` → orphelins | **Total** | B |
| E8 | Semis par gabarits versionnés | `RbacService` + `FORMULAIRE_DENTAIRE` **en dur dans le code** | **Total** | B |
| E9 | Migrations multi-tenants + état par tenant | inexistant | **Total** | B |
| E10 | Plans / quotas / abonnements | inexistant | **Total** | C |
| E11 | Accès support encadré | inexistant | **Total** | D |
| E12 | Journal plateforme immuable | `audit_logs_global` mutable par code | Partiel | E |
| E13 | Jobs planifiés | inexistant (`arq` installé, non utilisé) | **Total** | E/F |
| E14 | Onboarding public | inexistant | **Total** | F |
| E15 | Groupe OpenAPI « Platform » séparé | inexistant | **Total** | A→F |
| E16 | Emails derrière une interface | inexistant | **Total** | F |

---

## 8. Décisions d'architecture à valider

### D1 — Où stocker les utilisateurs plateforme ?

| Option | Description | Pour | Contre |
|---|---|---|---|
| **A. Base `sysdent_platform` dédiée** ✅ **retenue** | 3ᵉ base, 3ᵉ moteur, 3ᵉ contexte Alembic | Étanchéité maximale ; un rôle SQL plateforme n'a aucun droit sur les bases clients ; sauvegarde/restauration séparée ; les secrets 2FA et le journal immuable ne sont jamais dans une base lisible par le chemin de login client | Un 3ᵉ moteur à gérer ; la base doit être créée au déploiement |
| B. Schéma `platform` dans `sysdent_master` | Même moteur, `search_path` dédié | Moins de code, un seul point de connexion | Aucune barrière SQL entre plateforme et chemin d'authentification client ; le `search_path` est une convention, pas une garantie |

**Recommandation : A.** Le principe directeur « deux mondes étanches » est le
cœur de la mission ; l'option B ne crée qu'une *convention* là où A crée une
*garantie*. Le coût (une table de configuration de plus) est marginal devant le
risque. Le même raisonnement que `TenantBase` vs `Base` (`base_model.py:23-29`)
vaut pour `PlatformBase`.

### D2 — Stratégie de migrations multi-schemas (= multi-bases) tenants ?

| Option | Description | Pour | Contre |
|---|---|---|---|
| **A. Outil plateforme, boucle explicite sur le registre** ✅ **retenue** | Pour chaque tenant ACTIVE : lire son `alembic_version`, appliquer `upgrade head` dans un thread, enregistrer l'état ; endpoints Super Admin (appliquer sur tous / état / relancer / rapport) | Reprise sur échec individuel ; rapport ; pas de divergence silencieuse | Le temps de l'opération croît avec le nombre de tenants |

**Variante A' (retenue)** : avant/après chaque lot, **sauvegarde `pg_dump` du tenant
concerné** quand une migration destructrice est demandée ; le journal d'audit
plateforme conserve l'état avant/après de chaque tenant.

**Comment mesurer l'état ?** Deux options : (i) lire `alembic_version` directement
dans la base du tenant — valeur de vérité, sans table supplémentaire ;
(ii) table `migration_tenants` côté plateforme.
**Décision : les deux.** `(i)` est la source de vérité exposée par
`GET /platform/migrations` ; `(ii)` mémorise l'historique des *tentatives*
(quand, par qui, durée, erreur), que `alembic_version` ne peut pas contenir.

### D3 — Comment rendre l'isolation des jetons réelle ?

| Option | Description | Pour | Contre |
|---|---|---|---|
| **A. Clé distincte + claim `aud` + `scope`, vérifiés par une dépendance** ✅ **retenue** | `PLATFORM_SECRET_KEY` pour la plateforme ; chaque jeton porte `aud` (`sysdent-tenant`/`sysdent-platform`) et `scope` (`tenant`/`platform`/`support`) ; `decode_token_scoped(token, scope, aud)` | Défense en profondeur : si la fuite de clé survient, l'audience reste un frein ; testable | Le décodage doit rester tolérant pour les jetons déjà émis |
| B. Vérification par le rôle uniquement (état actuel) | comme `master/dependencies.py:42` | — | Un jeton forgeant `role=SUPER_ADMIN` passe ; aucune notion d'audience |

**Décision : A.** B est précisément ce que la mission interdit. Pour ne pas casser
les sessions en cours, `decode_token()` reste tolérant et **un nouveau**
`decode_token_scoped()` est utilisé par les dépendances : les jetons sans `aud`
(jusqu'au prochain login) sont acceptés côté tenant, mais **jamais** côté plateforme.

### D4 — Durée des jetons plateforme ?

Accès **10 min** (contre 15 côté client), refresh **8 h** avec rotation (contre 7 jours),
support **30 min** non renouvelable. Un compte plateforme contourne le RBAC client :
la surface doit être plus étroite et plus courte que celle du client.

### D5 — Deuxième facteur : bibliothèque ou stdlib ?

`pyotp` n'était pas installé. **Option retenue : `pyotp`** (dépendance ajoutée,
une ligne de `requirements.txt`) plutôt qu'une implémentation RFC 6238 maison — le
secret TOTP est un élément d'authentification, il ne doit pas être réécrit par nous.
Vérification du secret **hachée** en base (jamais le secret en clair), avec clé de
chiffrement dédiée.

### D6 — Modèle de semis : gabarits versionnés en base

`RbacService` (catalogue, matrice) et `FORMULAIRE_DENTAIRE` sont aujourd'hui du code.
**Option retenue :** table `gabarits_semis` côté plateforme, **versionnée**
(`code`, `version`, `contenu JSONB`, `active`), amorcée par la commande CLI puis
modifiable par l'équipe éditeur. Le provisionnement **copie** le gabarit actif.
Cela rend le §B6 réel au lieu de déplacer du code d'un fichier à un autre.

### D7 — Compatibilité de `super_admins` avec la nouvelle identité

Le modèle `SuperAdmin` et `/master/*` **restent en place et continuent de
fonctionner** (aucune route cliente ne les utilise : ✅ vérifié, le frontend
n'appelle que `/auth/*`). La nouvelle couche `/platform/*` est **additionnelle**.
Un script de **rattrapage** crée le premier `UtilisateurPlateforme` à partir du
Super Admin existant. Décision : **ne pas supprimer** `/master/*` dans cette mission
(eviter toute casse), mais le marquer déprécié.

---

## 9. Plan de migration des données existantes

Aucune donnée existante n'est modifiée. Trois ajouts **additifs** :

| Cible | Opération | Réversible |
|---|---|---|
| `sysdent_platform` (nouvelle base) | `CREATE DATABASE` + `alembic upgrade head` | `DROP DATABASE` |
| `sysdent_master.societes` / `tenants_db` | **+1 colonne** `statut_metier` (défaut `ACTIF`) si l'on veut porter l'état métier dans la base master | `DROP COLUMN` |
| tables tenants | inchangées | — |

**Script de rattrapage** (`platform:rattrapage`) : pour chaque `tenants_db` existant,
créer l'abonnement « plan par défaut », rattacher le statut `ACTIF`, et aligner
`schema_version`. **Testé sur une copie de la base avant exécution** (règle
« migrations touchant des données existantes »).

**Réversibilité :** toutes les migrations Alembic/platform fourniront un `downgrade()`.

---

## 10. Faisabilité de l'exécution réelle — vérifié

✅ Le blocage « base injoignable » qui figurait dans les comptes rendus précédents
**est levé** : le conteneur `sysdent_s0b` écoute sur `localhost:55435`.

```
$ docker ps
18b52b64984b  postgres:16-alpine  Up 6 hours  0.0.0.0:55435->5432/tcp  sysdent_s0b

$ psql -p 55435 -c "select version()"
PostgreSQL 16.15 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
```

✅ 29 sociétés, 23 `ACTIVE` / 6 `PROVISIONING` — un jeu de démonstration exploitable
pour les tests (cycle de vie, migrations multi-tenants, rollback).

Les tests existants créent une base jetable par test
(`tests/conftest.py:100`) : la suite est donc réellement exécutable.

---

## 11. Limites de cette analyse

- Analyse **statique + interrogative**, pas d'analyse de charge.
- Les 6 tenants en `PROVISIONING` n'ont pas été diagnostiqués individuellement.
- L'absence de TOTP côté tenant est constatée par recherche de code
  (`grep -rn "totp\|secret_2fa"`) : si un plan externe injectait le secret,
  ce serait hors de ce dépôt.
- Le rate limiter en mémoire n'a pas été mesuré sous concurrence.

---

## 12. Ce qui part en Phase A

Synthèse des décisions retenues (toutes **à valider** par le commanditaire) :

1. Base **`sysdent_platform` dédiée**, classe `PlatformBase`, Alembic `alembic_platform/`.
2. Clé `PLATFORM_SECRET_KEY` distincte + claims `aud`/`scope` vérifiés (`D3`).
3. 5 rôles `platform.*` semés par CLI, RBAC réel en base, aucun `permissions=["*"]`.
4. TOTP **obligatoire** via `pyotp`, secret **haché** en base (`D5`).
5. 2FA obligatoire dès le premier login : le bootstrap CLI affiche l'`otpauth://`
   une seule fois, à l'opérateur.
6. Le provisionnement Phase B devient **transactionnel** (création de base +
   application + semis atomiques, avec compensation explicite) et **factorisé** avec
   l'onboarding Phase F.
7. `/master/*` conservé (non cassant), `/platform/*` en ajout.