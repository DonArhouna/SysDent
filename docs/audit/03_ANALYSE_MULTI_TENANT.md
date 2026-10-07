# 03 — Analyse d'écart : le modèle multi-tenant validé

> **Date** : 4 octobre 2026 · **Décisions validées** : (1) un espace isolé par
> cabinet, (2) un parcours d'onboarding, (3) un futur Backoffice sur le même
> backend, (4) l'admin de cabinet gère ses utilisateurs, rôles et permissions.
>
> **Règle de lecture** — chaque affirmation porte la mention **[constaté]** quand
> elle est vérifiée dans le code (fichier et ligne), **[recommandé]** quand c'est
> mon avis d'expert. Les schémas proposés sont des recommandations, pas de
> l'existant.

---

## Synthèse en une page

| Décision | État actuel | Verdict |
|---|---|---|
| **1. Isolation par cabinet** | **Base de données physique par société**, résolue à chaque requête | 🟢 **Le bon choix est déjà fait** — à consolider, pas à refaire |
| **2. Onboarding** | Provisionnement technique complet côté plateforme ; **aucune UI**, aucun assistant de configuration | 🟡 Socle solide, parcours produit inexistant |
| **3. Séparation plateforme / tenant** | **Deux bases et deux games d'authentification existent déjà** (`/api/v1/*` vs `/api/v1/master/*`) | 🟢 Structure déjà correcte — à **documenter et verrouiller** |
| **4. Admin de cabinet gère ses utilisateurs** | Rôles **personnalisables** ✅ mais **aucun endpoint utilisateur** ❌, et l'admin ne peut **pas** restreindre ses propres droits | 🔴 **Le volet le plus en retard** |

**Le message central :** le backend a été conçu en multi-tenant **avant** que la
décision ne soit actée, et il l'a bien fait. Le retard n'est pas
architectural — il est **fonctionnel** : il manque des endpoints (utilisateurs,
nomenclature d'actes), une couche RBAC à 2 dimensions (site), et toute la
surface produit de l'onboarding.

---

## B1 — Multi-tenancy et isolation des données

### B1.1 Ce qui existe [constaté]

#### La stratégie d'isolation en place : **une base physique par société**

`Backend/src/modules/master/services.py:39` — `_create_physical_database()` crée
une base PostgreSQL dédiée. La table `tenants_db` (base **master**) associe à
chaque société son `db_name`, son hôte, son port, son utilisateur et son mot de
passe **chiffré** (`decrypt_secret`).

Le nom de base est dérivé d'un slug : `sysdent_tenant_clinique_cabinet_sn_5bd215`
(vérifié en base sur la société de démonstration).

**Conséquence mesurée sur le modèle : 30 tables sur 36 ne portent aucune colonne
`tenant_id` ni `cabinet_id`.** Ce n'est pas un oubli — c'est **la conséquence
correcte** du choix database-per-tenant : une table qui n'existe que dans la base
du cabinet n'a pas besoin d'être filtrée.

```
MASTER (plateforme)                    TENANT (par société)
─────────────────────                  ────────────────────
societes                               utilisateurs · cabinets · salles
tenants_db          ←── isole ──→     fauteuils · praticiens · patients
utilisateur_index                        dossiers_medicaux · dents · actes_realises
super_admins                            rendez_vous · factures · paiements …
super_admin_sessions                    prescriptions · devis · audit_logs
audit_logs_global
```

#### Résolution du tenant [constaté]

`src/modules/auth/dependencies.py:37-89` :

```python
async def get_current_tenant_id(x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")):
    tenant_id = payload.get("tenant_id") or x_tenant_id   # JWT d'abord, en-tête en repli
    if not tenant_id:
        raise AuthenticationException(...)
    return str(tenant_id)

async def get_tenant_db(tenant_id = Depends(get_current_tenant_id), master_db = Depends(get_master_db)):
    uuid_tenant = uuid.UUID(str(tenant_id))              # doit être un UUID
    stmt = select(TenantDB).where(TenantDB.societe_id == uuid_tenant,
                                  TenantDB.statut == "ACTIVE")
```

Quatre points forts, tous vérifiés :

1. **Le JWT porte le `tenant_id`** (`security.py:43`) : le client ne choisit pas
   sa base, il ne fait que présenter celle qu'on lui a donnée à la connexion.
2. **Suspension immédiate** : le filtre `statut == "ACTIVE"` rend la base
   inatteignable dès qu'une société est suspendue, **sans supprimer ses données**.
3. **Mot de passe de base chiffré** au repos dans la table master.
4. **Validation UUID stricte** : un identifiant arbitraire ne peut pas ouvrir une
   session par devinette — commentaire explicite dans le code.

#### Résolution de l'utilisateur [constaté]

Table `utilisateur_index` dans la base master : `(email, societe_id,
utilisateur_id, actif, derniere_connexion)`. À la connexion, l'email est cherché
dans l'index → il donne le `societe_id` et l'`utilisateur_id` → le `tenant_id`
entre dans le JWT. Un utilisateur **d'un seul cabinet** ; un même email dans deux
cabinets = deux entrées d'index.

### B1.2 Les 4 stratégies — avantages, inconvénients, et ma recommandation

| Stratégie | Isolation | Coût d'exploitation | Migrations | Requêtes inter-tenant | Adapté au contexte PME/Afrique |
|---|---|---|---|---|---|
| **Colonne `tenant_id` + filtre systématique** | 🔶 faible — dépend de la vigilance du développeur | 🟢 faible | 🟢 1 fois | 🟢 trivial | 🔶 risqué |
| **Row-Level Security PostgreSQL** | 🟢 forte (base) | 🟡 moyen (session à poser par requête) | 🟢 1 fois | 🟡 possible | 🟡 |
| **Schéma par tenant** | 🟢 forte | 🟡 moyen | 🟡 par tenant | 🔶 complexe | 🟡 |
| **Base par tenant** *(actuel)* | 🟢🟢 **maximale** | 🔶 1 base par client | 🔶 N fois | 🔶 impossible | 🟢 |

**Ma recommandation : ne rien changer.** [recommandé]

L'argument est le risque d'oubli. En colonne `tenant_id`, **une seule requête
sans filtre expose les données d'un autre cabinet** — et ce bug ne se voit pas en
recette, il se découvre en production, un jour, sur la liste des patients. En
base par tenant, la même requête échoue bruyamment : la table n'existe pas dans
cette base. L'échec est **spectaculaire au lieu d'être silencieux**. Pour une
application de santé multi-tenant dont la première qualité attendue est
« les données d'un cabinet ne sont jamais visibles par un autre », c'est le bon
arbitrage.

Et cela colle au contexte déclaré : PME, connexion instable, ~50 utilisateurs
simultanés. Le pool de connexions est **par tenant** (`tenant_db_manager`), donc
un pic de trafic dans un cabinet ne sature pas les autres.

**Le coût à assumer en toute connaissance de cause :**

| Coût | Mesure | Acceptable ? |
|---|---|---|
| Une migration = N exécutions | `upgrade_tenant_to_head` en boucle de provisioning | 🟢 26 sociétés aujourd'hui, ~500 attendues |
| Pas de statistique inter-tenant depuis le tenant | `GET /master/statistiques` existe déjà pour ça | 🟢 assumé |
| 26 (→ 500) bases | PostgreSQL gère 5 000+ bases sans difficulté | 🟢 |
| Sauvegarde par base, multiplicative | `pg_dump` par base, ou `pg_basebackup` + restauration ciblée | 🟡 à automatiser |

### B1.3 Recommandation : RLS en **couche de défense**, pas en substitution [recommandé]

Si l'isolation par base est garantie, la menace restante est **opérationnelle** :
un `psql` lancé sur la mauvaise base, un script de maintenance oublié,
une migration écrite deux fois. Le RLS coûte peu et attrape l'erreur humaine :

```sql
-- Sur les tables sensibles d'une base tenant, en défense en profondeur
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
CREATE POLICY patients_isole ON patients USING (true);  -- neutre : la base EST la frontière
```

À appliquer **seulement** sur `patients`, `dossiers_medicaux`, `consultations`,
`prescriptions`, `factures`, `audit_logs`. Priorité P2 — ce n'est pas un correctif,
c'est une ceinture sur un costume déjà fermé.

### B1.4 Fuite inter-tenant — l'audit des 6 vecteurs

| Vecteur | État | Constat |
|---|---|---|
| **Requêtes sans filtre tenant** | ✅ **éliminé par construction** | La base est la frontière ; il n'y a pas de requête « entre bases » possible depuis une session tenant |
| **Cache Redis non cloisonné** | ✅ **non Applicable** | **Aucun Redis dans le backend** (recherche sur tout `src/` : 0 occurrence). Pas de cache applicatif, donc rien à cloisonner |
| **Fichiers / radios sans préfixe tenant** | 🟡 **à construire** | **Aucune implémentation de stockage de fichiers n'existe.** `logo_url` et `signature_url` sont de simples chaînes (≤ 500 car.) stockées en base — aucune API d'upload. Voir B1.5 |
| **Logs** | 🟡 **à vérifier** | Le logger ajoute `request_id`, `client_ip`, `path` — je n'ai pas vérifié ligne par ligne l'absence d'identifiant patient dans les messages |
| **Exports** | 🟡 **partiel** | `ACTION_EXPORT` existe pour `PATIENTS`, `FACTURATION`, `AUDIT`. À auditer endpoint par endpoint quand le module imagerie arrivera |
| **Recherche globale / jobs planifiés** | ✅ **sans objet aujourd'hui** | Aucune tâche de fond (SMS/email) n'existe dans le code |
| **Cache navigateur / React Query** | 🔴 **à corriger** | Voir ci-dessous |

#### Le vrai risque restant n'est pas le backend : c'est le cache du frontend 🔴

React Query garde en mémoire les réponses pendant `staleTime`. Sur un poste
partagé (écran d'accueil en salle d'attente, tablette de l'accueil), si un second
utilisateur se connecte **sans rechargement complet**, il peut briefly voir les
données du précédent.

**[recommandé]** `queryClient.clear()` à la déconnexion **et** au changement
d'utilisateur, plus `refetchOnWindowFocus` déjà actif. Coût : 3 lignes. C'est
le seul point du système où une fuite inter-tenant est plausible aujourd'hui, et
il est entièrement côté client.

### B1.5 Décision à valider 🟡 — « Site » ou « Cabinet » ?

Le modèle validé dit **Tenant (le cabinet client) → Sites/agences → Fauteuils →
Praticiens**.

**[constaté]** Aujourd'hui la table `cabinets` est **à l'intérieur** de la base
tenant, et un tenant = une société = un cabinet (le provisioning crée un premier
cabinet d'office : `master/services.py:88`, « Un cabinet sans enregistrement ne
peut ni consulter ni facturer »).

Pour une **SEULE base par société**, un groupe de 3 cliniques n'existe pas :
chaque clinique = une société = une base.

**2 options :**

**Option A — une société = un tenant, plusieurs `cabinets` dedans** (fidèle à la
décision)
- ✅ Une seule base par groupe, une seule migration, un seul jeu de rôles.
- ✅ Le backoffice gère une seule ligne par client, quelle que soit sa taille.
- ✅ Le chiffre d'affaires se consolide par client sans requête inter-base.
- 🔶 Il faut une **hiérarchie de rôles à 2 dimensions** (rôle global + restriction
  par site) — c'est le vrai chantier, pas le modèle de données.

**Option B — un tenant = un site** (ce qui est fait aujourd'hui)
- ✅ Aucune ambiguïté sur « le cabinet » : un site, une base.
- 🔶 Un groupe de 3 sites = 3 fiches client, 3 bases, 3 abonnements, et la
  consolidation est impossible sans requête inter-base.

**Ma recommandation : Option A.** Elle est conforme à la décision validée, et le
surcoût est contenu et connu : une colonne `site_id` (ou `cabinet_id`) sur les
tables métier, déjà présente sur 6 d'entre elles (`salles`, `disponibilites`,
`consultations`, `rendez_vous`, `factures`, `devis`), à propager aux 24 autres,
plus le RBAC à deux dimensions décrit en B4.4.

**Décision à valider** : est-ce qu'une société peut être multi-sites dès le
premier jour ? Si oui, Option A. Si non, on peut **différer** l'implémentation
en notant que la propagation de `cabinet_id` sur les 24 tables est d'autant plus
douloureuse plus tard. **Ma recommandation est de traiter ce point au Sprint 1
plutôt qu'au Sprint 4.**

---

## B2 — Onboarding

### B2.1 Ce qui existe [constaté]

Le provisionnement technique est **complet et bien conçu** :
`create_societe_and_provision_tenant` (`master/services.py:358`) enchaîne :

| Étape | Ligne | Détail |
|---|---|---|
| 1. Créer la base physique | `:39` | `_create_physical_database` |
| 2. Migrer le schéma | `:82` | `upgrade_tenant_to_head` dans un thread (Alembic est synchrone) |
| 3. Créer le moteur | `:85` | pool dédié au tenant |
| 4. Créer le **premier cabinet** | `:88` | « Un cabinet sans enregistrement ne peut ni consulter ni facturer » |
| 5. Semer le **RBAC** | `:107` | `RbacService.bootstrap_complet` — permissions, rôles, matrice |
| 6. Semer le **formulaire médicaments** | `:108` | `MedicamentService.semer_formulaire` (14 molécules) |
| 7. Créer l'**admin** + son profil praticien | `:114` | rôle `ADMIN_CABINET`, rôle **récupéré** et non recréé (contrainte UNIQUE) |

La gestion d'échec est propre : `statut` reste `PROVISIONING`, le tenant est
**visible et identifiable**, le motif est journalisé
(`tenant_provisioning_failed`), le client reçoit
`TENANT_PROVISIONING_FAILED`. Une suspension bascule `societe.actif` **et**
`tenant_db.statut` (`ACTIVE` ↔ `SUSPENDED`) — les données restent.

### B2.2 Ce qui manque

| Manque | Gravité | Constat |
|---|---|---|
| **Aucune UI de provisioning** | 🔴 P0 | Les 10 routes `/master/*` ont **0 %** de consommation frontend (doc 01, A3). Un Super Admin ne peut créer un cabinet que via un script Python (`_create_cabinet.py`) |
| **Pas de vérification email/téléphone** | 🔴 P0 | Rien n'est vérifié : l'admin est créé avec l'email fourni, actif immédiatement |
| **Pas d'assistant de configuration initiale** | 🔴 P0 | Aucun écran « informations du cabinet, sites, horaires, fauteuils, tarifs » |
| **Nomination d'actes vide à la provision** | 🔴 P0 | `master/services.py:106-108` sème les **médicaments** mais **pas** `ActeNomenclature`. Un cabinet neuf **ne peut rien facturer** : le module Facturation est inutilisable jusqu'à une saisie manuelle de la nomenclature |
| **Aucun endpoint de reprise** | 🟠 P1 | Un tenant bloqué en `PROVISIONING` n'a **aucune** route pour le relancer : il faut réexécuter le script |
| **Pas d'import de données existantes** | 🟠 P1 | Un cabinet qui migre depuis un autre logiciel repart de zéro |
| **Pas d'image du tenant** | 🟡 P2 | Aucune sauvegarde ni restauration par société |

### B2.3 Flux d'onboarding recommandé [recommandé]

```
                    ┌──────────────────────────────────────────┐
   Plateforme       │  Backoffice (futur) :  Nouvelle société    │
                    │  nom, pays, plan, contacts, NINEA          │
                    └──────────────────┬───────────────────────┘
                                       │ POST /platform/tenants
                                       ▼
                            PROVISIONING (technique, ~30 s)
                    ┌──────────────────────────────────────────┐
                    │  provision_tenant() — déjà existant       │
                    │  base · migrations · RBAC · formule ·     │
                    │  cabinet · admin · PRÉ-REQUIS : acte     │
                    └──────────────────┬───────────────────────┘
                                       ▼
                            ACTIF_SANS_EMAIL_VERIFIE
                    ┌──────────────────────────────────────────┐
   Cabinet          │  1. Vérifier l'email  →  lien signé 24 h   │
   (dans l'app      │  2. Définir mot de passe définitif       │
    client)         │  3. Assistant configuration (7 étapes)    │
                    └──────────────────┬───────────────────────┘
                                       ▼
                            ACTIF_CONFIGURÉ  →  saisie réelle
```

**L'assistant de configuration en 7 étapes** [recommandé] — chaque étape
écrit dans le tenant, aucune n'est bloquante (le cabinet reste utilisable avec
seules les étapes 1 et 2) :

| # | Étape | Écriture | Pourquoi cette étape est là |
|---|---|---|---|
| 1 | Identité | `cabinets` | nom, adresse, ville, téléphone, **logo** |
| 2 | Sites | `cabinets` + `salles` | au moins une salle — sans quoi aucun fauteuil |
| 3 | Équipements | `fauteuils` | nombre par salle ; le fauteuil est l'unité de contrainte du planning |
| 4 | Équipe | `praticiens` + rattachement | sans praticien, aucun RDV possible |
| 5 | Horaires | `disponibilites` | **préalable à toute recherche de créneau** |
| 6 | Tarifs | `actes_nomenclature` | **préalable à toute facturation** |
| 7 | Paiements & documents | `caisse` (modes), modèles d'ordonnance/facture | Wave, Orange Money, espèces, carte |

Les étapes 5 et 6 sont la cause racine de B2.2 : sans elles, le tenant démarre
« configuré » mais **incapable de fonctionner**. C'est le premier correctif à
faire.

### B2.4 États d'un tenant — [constaté] vs [recommandé]

**States réels** (`tenants_db.statut`) : `PROVISIONING` · `ACTIVE` ·
`SUSPENDED`. Plus `societes.actif` (booléen), redondant avec `statut`.

**States recommandés** :

| État | today | Proposé | Règle |
|---|---|---|---|
| `PROVISIONING` | ✅ | ✅ | Provisionnement technique en cours |
| `PENDING_VERIFICATION` | ❌ | 🆕 | Créé, email non vérifié, **accès refusés** |
| `TRIAL` | ❌ | 🆕 | Période d'essai, quotas réduits |
| `ACTIVE` | ✅ | ✅ | Exploite normalement |
| `SUSPENDED` | ✅ | ✅ | Accès refusé, **données conservées** |
| `MIGRATING` | ❌ | 🆕 | Sauvegarde/restauration ou migration de données en cours |
| `CANCELLED` | ❌ | 🆕 | Résilié — **conservation légale** pendant la durée du obligation de conservation du dossier médical |
| `DELETED` | ❌ | 🆕 | Purge, après expiration de la période de conservation |

**Décision à valider** 🟡 : la suppression définitive d'un tenant est un sujet de
**droit**, pas de produit. Le dossier médical de santé se conserve des années.
Ma recommandation : **ne jamais supprimer une base de données de façon
irréversible** — anonymiser le tenant, conserver les factures (obligation
comptable), et ne purger le nominatif qu'après l'échéance légale.

---

## B3 — Séparation plateforme / tenant

### B3.1 Ce qui existe [constaté] — et c'est déjà la bonne structure

Le backend a **deux frontières d'authentification distinctes**, sur deux bases :

| | **Niveau tenant** | **Niveau plateforme** |
|---|---|---|
| Préfixe | `/api/v1/*` | `/api/v1/master/*` |
| Base | base du cabinet | base **master** |
| Identité | `utilisateurs` (par tenant) | `super_admins` (**table séparée**) |
| Sessions | `sessions_utilisateurs` | `super_admin_sessions` |
| JWT | `sub` = `utilisateur_id`, claim `tenant_id` | `sub` = `super_admin_id`, **sans** `tenant_id` |
| Rôles | RBAC `require_permissions(...)` | **aucun RBAC** — rôle unique |
| Audit | `audit_logs` (par tenant) | `audit_logs_global` |
| Routes | 109 | 10 |
| Refresh | `POST /auth/refresh` | `POST /master/auth/refresh` |

**Les points saillants :**

- **`super_admins` est une table distincte de `utilisateurs`.** Ce n'est pas un
  rôle dans la même table avec un drapeau — c'est une identité d'une autre
  nature, dans une autre base, avec ses propres sessions. C'est exactement ce que
  la décision 3 demande, et c'est déjà fait.
- **`audit_logs_global` est séparé de `audit_logs`.** Un journal de plateforme ne
  peut pas être confondu avec le journal d'un cabinet.
- **Le Super Admin n'a pas de permission RBAC.** Il n'est pas « administrateur de
  tous les tenants » : c'est un rôle d'éditeur, avec un périmètre différent. La
  séparation des pouvoirs est réelle.

**Ce qui manque :** la frontière existe dans le code mais n'est **ni documentée ni
protégée par construction**. Un Super Admin peut, aujourd'hui, appeler
`GET /api/v1/patients` ? **Non** — son JWT n'a pas de `tenant_id`, donc
`get_tenant_db` lève `TENANT_ID_INVALIDE`. La séparation tient par l'**absence
d'un claim**, pas par une vérification explicite. C'est fragile : le jour où on
ajoute un claim pour une raison légitime, la barrière tombe en silence.

### B3.2 Endpoints « plateforme » à prévoir [recommandé] — sans les implémenter

```
/api/v1/platform/
├── tenants                     CRUD cabinet, recherche, filtres par plan/statut
├── tenants/{id}/statut         suspension / réactivation (immuable : cf. audit)
├── tenants/{id}/provisioning   RELANCE  ← comble B2.2
├── plans                       abonnements : catalogue, prix, limites
├── tenants/{id}/abonnement     changement de plan, dates, quota
├── tenants/{id}/quota          nb utilisateurs / stockage / bande passante
├── usage                       consommation par tenant et par période (facturation éditeur)
├── support                     tickets, historique de conversation
├── impersonation               session support ENCADRÉE (impérativement : voir ci-dessous)
└── journal                     audit_logs_global, filtré, exportable
```

**Sur l'impersonation** — c'est le point le plus sensible de tout le backoffice.
[recommandé] Si l'équipe de support doit voir l'écran d'un cabinet, ne jamais
réutiliser le token du Super Admin. Émettre un **jeton d'impersonation distinct**,
valable 15 minutes, portant `impersonated_by`, journalisé **avant** l'accès,
affiché de façon visible dans l'UI backoffice (« vous consultez le cabinet X »),
et **révoqué** à la déconnexion. Le Super Admin doit être capable d'agir *sur* un
tenant (suspendre, facturer, importer) sans jamais *être* un utilisateur de ce
tenant. Sinon la séparation des pouvoirs disparaît en un clic.

### B3.3 Structure d'API — recommandation [recommandé]

**Préfixe `/platform/*`, et garder le tenant inchangé.**

```
/api/v1/patients          → inchangé. Zéro migration de 109 routes.
/api/v1/platform/tenants  → nouveau préfixe explicite, non ambigu.
/api/v1/master/*          →renommé /api/v1/platform/*
```

Pourquoi ne **pas** mettre les endpoints plateforme sous `/api/*` sans
préfixe ? Parce que « même préfixe, filtres différents » est exactement la
configuration qui produit un jour une fuite de 3 lignes. Le préfixe distinct rend
l'erreur visible au premier `grep`, permet de brancher une **autre politique
d'authentification** sur `/platform/*` sans toucher au reste, et laisse au
backoffice un espace d'URLs qui lui appartient.

**Versionnement** — la décision est à ne pas versionner maintenant :

| Option | Avantage | Inconvénient | Verdict |
|---|---|---|---|
| `/api/v1` (actuel) | Simple | Un changement cassant = `/api/v2` et une seconde base de code | ✅ **conserver** |
| `/api/v1` + header `Accept: …; version=2` | Pas de duplication d'URL | Opaque, difficile à déboguer | ❌ |
| Version par header `X-API-Version` | Explicite | 2 versions vivantes à maintenir | 🟡 si le public API arrive |

**Décision à valider** 🟡 : ne versionner que le jour où le **backoffice ou une API
publique tiers** devient un client externe identifié. Les 109 routes internes
peuvent évoluer sous le contrôle du même dépôt — le versionnement n'apporte rien
à un client unique qui se met à jour en même temps que le serveur.

---

## B4 — Gestion des utilisateurs, rôles et permissions par cabinet

C'est le volet **le plus en retard**. Je le traite en détail parce que c'est la
décision 4.

### B4.1 État actuel du RBAC [constaté]

#### Le modèle de permissions est bon

`src/common/permissions.py` — format `MODULE:ACTION`, **12 modules × 6 actions**
(`READ`, `CREATE`, `UPDATE`, `DELETE`, `EXPORT`, `SIGN`) = **45 permissions**.
La séparation `AGENDA` / `DISPONIBILITES` est documentée et justifiée :

> « AGENDA = prendre un rendez-vous avec un patient (secrétariat) ;
> DISPONIBILITES = dire quand un praticien travaille (praticien). Confondre les
> deux donnerait au secrétariat le droit de modifier l'agenda de travail des
> dentistes. »

C'est le niveau de maturité attendu d'un RBAC en santé.

#### Le double source de vérité est assumé et expliqué

> « Pourquoi une table de permissions dans la base ET une matrice ici ? La table
> permet au Super Admin d'accorder une permission à un rôle sans redéployer le
> code ; la matrice ci-dessous sert au seed initial et de garde-fou. »

**Bonne décision.** Le catalogue vit en base, la matrice sert de graine et de
plancher.

#### Les 6 rôles semés

`ADMIN_CABINET` · `PRATICIEN` · `ASSISTANT` · `SECRETAIRE` · `COMPTABLE` ·
`GESTIONNAIRE_STOCK`, avec une matrice rédigée en commentaires qui explique le
pourquoi de chaque carve-out. Le rôle `SECRETAIRE` est explicitement privé de
dossier médical — règle clinique correcte.

#### Les permissions sont appliquées côté serveur — [constaté] ✅

`require_permissions("PATIENTS:CREATE")` est une dépendance FastAPI sur les
routes. Le frontend reçoit les permissions dans `GET /auth/me` et s'en sert
**uniquement pour afficher ou masquer** un bouton (doc 02, § 4). Un utilisateur
sans le droit ne peut pas contourner l'UI : la route refuse. **C'est le seul
comportement acceptable et il est respecté.**

#### Les endpoints RBAC

| Route | Effet |
|---|---|
| `GET /rbac/roles` | lister 🔴 **500** (bug B2, doc 01) |
| `POST /rbac/roles` | **créer un rôle personnalisé** ✅ |
| `POST /rbac/roles/{id}/permissions` | accorder ✅ |
| `DELETE /rbac/roles/{id}/permissions` | retirer ✅ (refusé sur `ADMIN_CABINET`) |
| `GET /rbac/permissions` | catalogue ✅ |
| **Supprimer un rôle** | ❌ **n'existe pas** |
| **Assigner un rôle à un utilisateur** | ❌ **n'existe pas** (aucun endpoint utilisateur) |

### B4.2 Cinq lacunes, par gravité

#### 🔴 L1 — Aucun endpoint `Utilisateur` : la décision 4 est inopérante

Il n'existe **aucune route, aucun schéma, aucun service** pour les utilisateurs.
Vérifié : `GET /utilisateurs` → **404**.

Conséquence concrète : **un cabinet ne peut pas recruter.** Ni secrétaire, ni
comptable, ni deuxième praticien. Le RBAC est intégralement écrit, la matrice est
élégante, les rôles personnalisés sont créables — **et il n'y a personne à qui
les attribuer.** C'est le trou le plus coûteux du système : 6 rôles et 45
permissions ne valent rien sans une table d'utilisateurs.

Le frontend a déjà été construit contre un contrat *proposé* (service, types,
page `/utilisateurs` avec état « module indisponible » honnête). Il est prêt à
être branché.

#### 🔴 L2 — `ADMIN_CABINET` échappe à **tout** contrôle de permission

```python
ROLES_SANS_CONTROLE_PERMISSIONS = {"ADMIN_CABINET", "SUPER_ADMIN"}
# « Ils sont court-circuités dans require_permissions : ne pas essayer de
#  restreindre ces rôles via le RBAC. »
```

Combiné au garde-fou de `retirer_permission`, cela donne un rôle d'administrateur
**absolument incontrôlable** : ni par lui-même, ni par personne.

C'est défendable en partie — un admin qui peut se verrouiller lui-même hors de
son propre cabinet est un piège. Mais cela contredit la décision 4 : « ajuste les
permissions ». today un cabinet peut créer « Secrétaire restreint » (rôle
personnalisé) ✅, mais **ne peut pas** faire un « Administrateur délégué qui gère
les utilisateurs sans facturer » ❌.

**[recommandé]** Transformer `ADMIN_CABINET` en rôle à permissions
**matérialisées** (les 45 lignes sont insérées en base à la création du rôle, au
lieu d'un court-circuit), avec **une seule** exception maintenue :
`ADMIN_CABINET` ne peut pas retirer `ADMIN:UPDATE` à lui-même. On garde le
garde-fou, on perd la magical box.

#### 🟠 L3 — Un rôle peut être créé, jamais supprimé

`POST /rbac/roles` existe, **pas de `DELETE`**. Un cabinet qui crée
« Remplaçant gardien » ne pourra jamais s'en défaire ; le catalogue de rôles
s'enflera indéfiniment et la matrice de permissions deviendra illisible.

Le modèle gère déjà le cas difficile — `retirer_permission` refuse sur
`ADMIN_CABINET` avec un message explicite (« c'est le rôle de secours d'un
cabinet »). La même prudence s'applique à la suppression.

#### 🟠 L4 — Un utilisateur = un seul rôle, un seul cabinet

`utilisateur_index` est indexé sur `(email, societe_id)` et `utilisateurs.role_id`
est une clé étrangère simple. Un praticien qui travaille dans **deux cabinets**
n'existe pas. Pour un groupe de cliniques, c'est bloquant. Modèle cible :
n-u1-tiers **n-u1-utilisateurs** (un compte, plusieurs rattachements), chaque
rattachement portant son rôle et son périmètre de sites.

#### 🟡 L5 — Pas de journalisation des changements de droits

`audit_logs` existe et `GET /audit` est consommé. Mais je n'ai **pas vérifié**
que l'octroi et le retrait d'une permission y sont écrits. **À vérifier** — si
l'audit ne couvre pas les changements de droits, il ne couvre pas l'essentiel.

### B4.3 Modèle cible — permissions atomiques → rôles → utilisateurs [recommandé]

```
        PERMISSIONS (45, atomiques, catalogue global en lecture seule)
        PATIENTS:READ   PATIENTS:CREATE   FACTURATION:EXPORT …
                    ▲
                    │  many-to-many, matérialisé par tenant
        RÔLES         │
        ├─ système (ADMIN_CABINET, PRATICIEN, ASSISTANT, SECRETAIRE,
        │            COMPTABLE, GESTIONNAIRE_STOCK) — non supprimable, non figé
        └─ personnalisés par tenant — supprimables librement s'ils sont vides
                    ▲
                    │  many-to-many via UTILISATEUR_CABINET
        UTILISATEUR  │
        ├─ rôle  (position 1 : le rôle principal)
        ├─ rôle  (position 2 : multijoueur — ex. praticien + comptable)
        └─ périmètre : { cabinet_id: [site A, site C] }  ← multi-site
```

**L'ajout clé par rapport à aujourd'hui : le rattachement devient une table
d'association, pas une colonne.** C'est ce qui permet le multi-cabinet (L4) et
la restriction par site (B1.5) **sans jamais redessiner le reste**.

```
UTILISATEUR                RATTACHEMENT              ROLE
────────────────────       ────────────────────     ────────────────────
id                         id                       id
email (unique global)      utilisateur_id ──┐       nom
mot_de_passe (haché)       role_id ──────────┼──►    permissions ──► PERMISSION
prenom, nom                cabinet_id           │    est_systeme
actif                      actif                 │    supprime
derniere_connexion         date_debut/date_fin    │
2FA (futur)                cree_par               │

                          + RATTACHEMENT_SITES    │
                            rattachement_id        │
                            cabinet_id             │
```

### B4.4 RBAC à deux dimensions — le seul vrai point dur du multi-site

Un utilisateur peut avoir un rôle **global** et un périmètre **par site**.
L'évaluation d'une permission devient :

```
accordé  ⟺   (rôle porte la permission)
         AND (utilisateur actif sur le site de la ressource)
         AND (le site est dans le périmètre du rattachement, ou périmètre = tous)
```

**Décision à valider** 🟡 : est-ce que l'admin de cabinet reste
`ADMIN_CABINET` sur **tous** ses sites, ou peut-il être `ADMIN_CABINET` sur le
site A et simple `PRATICIEN` sur le site B ? La seconde option est beaucoup plus
puissante mais ajoute un `AND` à **toutes** les requêtes du RBAC. Si un groupe
n'a qu'un seul administrateur pour tous ses sites, la première option suffit et
on gagne beaucoup de complexité perdue. **Question à poser aux futurs clients
avant de coder.**

### B4.5 Garde-fous [recommandé] — état vérifié

| Garde-fou | État | Note |
|---|---|---|
| Ne pas supprimer le dernier admin | ❌ **à créer** | Devient possible dès que les endpoints utilisateurs existent |
| Ne pas s'octroyer de droits plateforme | ✅ **structurel** | `super_admins` est une autre table, dans l'autre base |
| Journaliser tout changement de droits | 🟡 **à vérifier** | `audit_logs` existe, la couverture des changements de droits est à confirmer |
| Limiter le nombre d'utilisateurs par plan | ❌ **à créer** | Aucun plan, aucun quota — cf. doc 04 |
| Mot de passe provisoire + activation | ❌ **à créer** | Pas de flux d'invitation |
| 2FA | ❌ **à créer** | `super_admins` a déjà `tentatives_echouees` et `verrouille_jusqua` — **le mécanisme existe, il n'est pas sur les utilisateurs du tenant** |
| Verrouillage après échecs | 🟡 **partiel** | Géré pour le Super Admin ; à vérifier pour le tenant |
| Sessions actives listables / révoquables | 🟡 **partiel** | `sessions_utilisateurs` existe ; l'endpoint de listing n'est pas dans les 119 routes → **à créer** |
| Expiration de session | ✅ oui | JWT + refresh |

**Recommandation prioritaire** : porter `tentatives_echouees` / `verrouille_jusqua`
sur `utilisateurs` — le modèle de verrouillage est **déjà écrit et testé** pour
le Super Admin. Le porter sur le tenant est du travail déjà half-done, pas un
développement nouveau.

### B4.6 Points d'attention sécurité

1. **Le refresh token en `localStorage`** — dette assumée et documentée dans le
   code : `POST /auth/refresh` l'exige dans le corps de la requête et le backend
   ne pose aucun cookie de refresh. Conséquence : **une faille XSS donne la
   session**. Correctif structurel : cookie `httpOnly` + `SameSite=Strict` +
   route de refresh qui ne se sert pas du token du client. C'est une décision
   backend, à planifier.
2. **L'en-tête `X-Tenant-ID` en repli** — `get_current_tenant_id` accepte un
   tenant par en-tête si le JWT n'en porte pas. today cela **n'est pas
   exploitable** (cette dépendance n'est utilisée que par `get_tenant_db`, et un
   attaquant sans JWT valide n'arrive pas jusqu'à elle). Mais c'est une
   **dépendance unnecessary et dangereuse par conception**. **[recommandé]** :
   supprimer le repli sur l'en-tête, ou exiger explicitement un claim. Défense en
   profondeur contre un futur endpoint qui oublierait de valider l'utilisateur.
3. **Impersonation support** — cf. B3.2. Si elle est créée sans jeton distinct et
   journalisé, la séparation plateforme/tenant s'effondre.
4. **Révocation** — la rotation des refresh tokens existe et fonctionne
   (c'est la cause du bug B3 de la session de 15 min : `1 sur N`.refreshements
   concurrents réussit). Un endpoint « révoquer toutes les sessions » est
   nécessaire en cas de vol d'ordinateur.

---

## Ce qui manque, résumé honnête

Sur les quatre décisions validées :

| Décision | Ce qui existe | Ce qui manque |
|---|---|---|
| **1. Isolation** | Base par tenant,JWT, suspension, chiffrement, validation UUID | RBAC par site, `queryClient.clear()` à la déconnexion, RLS en défense |
| **2. Onboarding** | Provisionnement technique complet et robuste | UI, vérification email, assistant 7 étapes, **nomenclature d'actes**, reprise d'un `PROVISIONING` |
| **3. Plateforme / tenant** | Deux bases, deux tables d'identité, deux journals, préfixe distinct | Préfixe `/platform/*`, endpoints tenants/plans/quotas/usage, impersonation encadrée |
| **4. Utilisateurs & rôles** | 45 permissions, 6 rôles, rôles personnalisés créables, application **serveur** | **Endpoints utilisateurs**, suppression de rôle, rattachement multi-cabinet, RBAC par site, garde-fous |
