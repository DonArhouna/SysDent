# Tests SysDent Pro — quoi lancer, quand, et ce que ça prouve

Ce document existe parce que la suite complète était **impossible à lancer en
routine** : plus de 40 minutes, deux fois abandonnée avant la fin. Une suite qu'on
ne finit pas n'est pas une suite, c'est un décor.

---

## Les deux niveaux

### `rapide` — à lancer après **chaque** modification

```powershell
cd Backend
$env:MASTER_DB_HOST='127.0.0.1'; $env:MASTER_DB_PORT='55435'
$env:TENANT_DB_HOST='127.0.0.1';  $env:TENANT_DB_PORT='55435'
$env:PLATFORM_DB_HOST='127.0.0.1'; $env:PLATFORM_DB_PORT='55435'
.\.venv\Scripts\python.exe -m pytest tests/test_patients_dossier.py tests/test_consultations_workflow.py -q --tb=short
```

Couvre le cœur métier et le RBAC. **Ne vérifie pas** l'isolation inter-tenant, les
migrations, ni l'étanchéité plateforme/tenant.

### `complet` — avant de conclure une étape

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=line --durations=15
```

Tout : isolation inter-tenant, migrations, étanchéité plateforme/tenant, RBAC,
parcours de bout en bout. **C'est le seul niveau qui autorise à dire « rien n'est
cassé ».**

### Frontend

```powershell
cd Frontend
npm test          # Vitest
npx tsc -b --force
npx oxlint
```

`tsc -b --force` et non `tsc --noEmit -p tsconfig.json` : ce dernier ne type-checke
**rien**, `tsconfig.json` n'étant qu'un redirectionneur.

### Contrat de pagination

```powershell
.\.venv\Scripts\python.exe tests\inventaire_listes.py
```

Lit le spectre OpenAPI de l'application — ni mémoire, ni documentation — et sort en
code **1** si une liste volumineuse n'est pas paginée. À brancher en CI.

---

## Pourquoi la suite est passée de 40 min à moins de 15

| Correction | Effet mesuré |
|---|---|
| Schéma construit **une fois par session**, chaque test obtient sa base par `CREATE DATABASE … TEMPLATE` | setup : plusieurs secondes → **0,80 s** |
| Les 3 fichiers d'isolation ne rejouent plus 17 migrations **par base** (ils en créent 2 par test) | setup : **6–8,6 s → 0,80 s** |
| Hachage de mot de passe à coût réduit **en session de test** | 440 ms → **2,2 ms** par hachage |

### Ce qui n'a pas été affaibli

- **Aucun test supprimé, ignoré ni assoupli.** Le seul `skip` de la suite est
  inchangé.
- Chaque test garde **sa propre base physique**. L'isolation reste structurelle :
  elle est obtenue plus vite, pas approximée.
- `src/core/security.py` garde ses paramètres de production. Seul le nom lié dans
  chaque module est remplacé, pendant la seule session de test.
- Le hachage de test est un vrai KDF, salé et irréversible : les tests qui vérifient
  qu'un mauvais mot de passe est rejeté restent honnêtes.

---

## Prérequis

- Conteneur PostgreSQL démarré : `docker ps` doit montrer `sysdent_s0b` en `Up`.
  Il s'est arrêté **trois fois** sur ce poste ; c'est la cause la plus fréquente
  d'un échec qui n'a rien à voir avec le code.
- Toujours `127.0.0.1`, jamais `localhost`.
- Ne **jamais** `pg_terminate_backend` sur la base partagée.
- `pg_dump` / `psql` sont absents du venv : passer par
  `docker exec sysdent_s0b pg_dump` / `psql`.

---

## Pièges rencontrés, pour ne pas les rediscover

| Piège | Symptôme | Cause |
|---|---|---|
| `tests/platform/` masque le module standard `platform` | `AttributeError: module 'platform' has no attribute 'python_implementation'` | Python ajoute le dossier du script en tête de `sys.path` |
| Les routers inclus ne sont pas aplatis dans `app.routes` | l'inventaire des routes renvoie **0 route**, sans erreur | cette version de FastAPI conserve un nœud `_IncludedRouter` |
| `PaginationParams = Depends()` sur un modèle Pydantic | la pagination est inopérante **sans erreur** | `Depends()` n'analyse pas `__init__` : `page` et `limit` restent à 1/20 |
| Remplacer une fonction importée par son nom | le remplacement échoue **silencieusement** | comparer à `module.fonction` *pendant* la substitution : dès la première, plus rien ne correspond |
| `CREATE DATABASE … TEMPLATE` échoue | `source database "…" is being accessed by other users` | une connexion reste ouverte sur le modèle |