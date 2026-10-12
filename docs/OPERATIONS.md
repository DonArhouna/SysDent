# Opérations

## Alembic : trois chaînes, trois fichiers, une seule commande par base

Le dépôt contient **trois chaînes de migrations indépendantes**, chacune avec son
fichier `.ini` et son dossier de versions. Les mélanger ne lève pas d'erreur
claire : Alembic répond *« Can't locate revision »*, alors que la révision
demandée existe — dans une autre chaîne.

C'est exactement ce qui est arrivé le 10/10/2026, en cherchant à mesurer l'écart
de schéma d'une base de cabinet :

```
alembic history -r c6d1e8f5a4b7:3c2a49eaec83
→ FAILED: Can't locate revision identified by 'c6d1e8f5a4b7'
```

`c6d1e8f5a4b7` appartient à la chaîne **tenant**, `3c2a49eaec83` est la tête de
la chaîne **master**. On interrogeait la mauvaise chaîne. Le message ne dit pas
qu'une autre chaîne existe.

### La correspondance

| Base | Fichier de configuration | Dossier de versions | Tête | Migrations | Base visée |
|---|---|---|---|---|---|
| **Master** — sociétés, `tenants_db`, `utilisateur_index`, super-admins | `alembic.ini` | `alembic/` | `3c2a49eaec83` | 2 | `sysdent_master` |
| **Plateforme** — console, quotas, annonces, audit | `alembic_platform.ini` | `alembic_platform/` | `f2c9e5d7a3b1` | 5 | `sysdent_platform` |
| **Cabinets (tenant)** — patients, consultations, facturation, salle d'attente | `alembic_tenant.ini` | `alembic_tenant/` | `e8b2c4a7d1e5` | 18 | une base par cabinet |

Le chemin d'exécution est **asynchrone** (`asyncpg`) dans les trois cas. Une URL
`postgresql+psycopg2://` est convertie avant tout chargement de pilote ; ne
jamais supposer que le pilote demandé est celui qui sera chargé.

### La commande qu'il faut

Toutes se lancent depuis le dossier `Backend/`.

```bash
# Base master — à appliquer rarement, sur sysdent_master
python -m alembic -c alembic.ini upgrade head

# Base plateforme — console et console d'administration
python -m alembic -c alembic_platform.ini upgrade head

# Base d'un cabinet — une base, une commande
ALEMBIC_TENANT_DB_URL='postgresql+asyncpg://...' \
  python -m alembic -c alembic_tenant.ini upgrade head
```

`ALEMBIC_TENANT_DB_URL` n'est jamais écrit dans un shell traced ni dans un
historique : le chemin prévu par le code est l'appel programmatique
`src.core.migrations.upgrade_tenant_to_head(url)`, qui transmet l'URL par
`config.attributes` et ne la fait apparaître sur aucune ligne de commande.

### Lire l'état d'une base de cabinet

```sql
SELECT version_num FROM alembic_version;
```

Une base **sans** cette table n'est pas migrée du tout — c'est un état distinct
de « en retard », et non une base cassée. La page de santé
(`GET /platform/sante`, contrôle `schemas_tenants`) distingue les deux, et
indique le nombre de migrations manquantes par cabinet.

### Vérifier les trois chaînes avant de toucher à quoi que ce soit

```bash
python -m alembic -c alembic.ini          heads
python -m alembic -c alembic_platform.ini  heads
python -m alembic -c alembic_tenant.ini    heads
```

Une seule tête par chaîne. Plusieurs têtes signifient deux branches de
migrations : « être à jour » n'a alors plus de sens, et il faut le résoudre avant
toute application.

## Le contrat OpenAPI ne garantit pas les bornes numériques

À lire avant d'écrire un client, ou un test de contrat, contre une API qui
comporte des `Decimal`.

### Ce que le document promet, et ce qu'il ne promet pas

Pydantic produit, pour un `Decimal` borné, un `anyOf` : une branche `number` avec
`minimum` et `maximum`, et une branche `string` contrainte par un **motif de
forme**. Ce motif vérifie qu'une chaîne ressemble à un nombre décimal. Il ne
vérifie pas sa valeur.

Conséquence mesurée sur la tarification : le motif du taux de prise en charge
accepte `'101.00'` et `'-1.00'`. Un client qui ne valide que par le document
OpenAPI laisse donc passer des valeurs que le serveur refusera.

```text
Backend/scripts/exporter_openapi.py  ->  Backoffice/openapi.json
```

Le document est la source du test `Frontend/src/test/contrat-tarification.test.ts`
- il sert à vérifier **la forme** des corps, pas leurs bornes.

### Où les bornes sont réellement garanties

Trois fois, et il faut les trois :

1. **Le formulaire**, par une validation testée.
   `Frontend/src/features/tarification/components/validation.ts`,
   vérifié par `Frontend/src/test/validation-tarification.test.ts`.

2. **Pydantic**, qui applique `ge`/`le` après conversion en `Decimal`. Un taux
   à 101 est refusé avec un **422** et un message nommé, quelle que soit la
   forme reçue.

3. **La base**, par un `CHECK` : `taux_prise_en_charge BETWEEN 0 AND 100`,
   `montant >= 0`. Le dernier rempart, pour ce qui passerait par une autre
   porte qu'un formulaire ou qu'un appel HTTP.

### Le test qui fixe cette limite

```text
Frontend/src/test/contrat-tarification.test.ts
  « le schema ne porte PAS la borne 0-100 sur la forme chaine »
```

Il vérifie que le motif accepte `'101.00'`. S'il échoue un jour, c'est que le
schéma s'est durci : la borne est peut-être devenue vérifiable par le contrat,
et il faut alors re-écrire ce qu'il dit. **Ce test n'est pas un constat
figé** : c'est une mesure, rejouée à chaque exécution.

### Corollaire : ne jamais faire confiance au document seul

Un test de contrat qui valide un corps contre `openapi.json` prouve que le
corps est *de la bonne forme*. Pour les bornes, il faut soit lire le schéma
Pydantic, soit tester la validation du formulaire. Écrire « le taux est refusé »
en s'appuyant uniquement sur `openapi.json` serait un test faux.

### Sur une base jetable, jamais sur un cabinet réel

Une migration se valide par aller-retour sur une **copie jetable** d'une base
existante, nommée `jetable_*`, puis supprimée :

```
création → restauration d'un dump → upgrade head → downgrade → upgrade head
```

Une migration validée ainsi puis appliquée à un cabinet réel est une migration
réessayable. Une migration écrite puis appliquée directement au cabinet est un
ticket de production. Le test d'aller-retour est automatisé dans
`Backend/tests/test_configuration_alembic.py` pour la structure des chaînes, et
le contrôle d'intégrité (`Backend/scripts/controle_integrite.py`) refuse de
laisser passer une chaîne à plusieurs têtes ou illisible.