# Travail à deux agents — règles de coexistence

> **Pourquoi ce document.** Deux assistants travaillent sur ce dépôt. Sans règles
> écrites, la coordination ne peut passer que par la parole — et il n'y a aucun
> canal entre nous. Tout ce qui suit est donc dans le fichier, pour être lu par
> le premier qui arrive.

## Les trois risques réels

### 1. La chaîne de migrations est linéaire — une seule tête

Tête actuelle : **`c6d1e8f5a4b7`**.

Deux migrations écrites en parallèle depuis cette tête produisent **deux têtes**,
et `alembic upgrade head` échoue. C'est le risque le plus élevé : il ne se voit
qu'au moment d'appliquer, après avoir déjà raté la migration.

**Règle** : un seul agent écrit dans `Backend/alembic_tenant/versions/`. L'autre
n'en écrit pas. Si vous devez une migration, dites-le au lieu de l'écrire.

### 2. Une seule base pour nous deux

Serveur : `127.0.0.1:55435` (conteneur `sysdent_s0b`).

- base démo : `sysdent_tenant_clinique_cabinet_sn_5bd215`
- base plateforme : `sysdent_master`

**Interdit** : `pg_terminate_backend`, `DROP DATABASE`, et toute commande
bloquant une connexion ouverte. J'ai fait l'erreur pendant une vérification de
migration aujourd'hui — cela aurait détruit le travail de l'autre agent.

Le conteneur s'est déjà arrêté deux fois (code 255). Le redémarrer est sans
risque ; en revanche ne pas l'arrêter.

### 3. Les suites de tests se disputent les mêmes noms

Chaque exécution crée des bases `sysdent_test_*` sur le même serveur. Deux suites
en parallèle peuvent entrer en collision.

**Règle** : une seule suite complète à la fois (≈ 33 min).

## Répartition en cours

| Périmètre | Agent | Pourquoi |
|---|---|---|
| Backend, migrations, base, tests, documents | **OpenCode** | propriétaire de la chaîne Alembic |
| Frontend (`Frontend/src`) | **FreeBuff** | aucun recouvrement avec le backend, aucune migration |

Tant que les périmètres sont respectés, aucun conflit de fichier n'est possible :
les deux agents écrivent dans des répertoires disjoints.

## Frontières de fichiers

| Chemin | Agent |
|---|---|
| `Backend/**` | OpenCode |
| `Frontend/**` | FreeBuff |
| `docs/**` | OpenCode — sauf `docs/corrections/03_CONSULTATION_PRATICIEN.md` si FreeBuff le lit |
| `docker-compose*.yml`, `.env` | ni l'un ni l'autre sans prévenir |

Si vous devez écrire hors de votre périmètre : **prévenez, ne contournez pas.**
Un fichier écrit en double sera perdu sans qu'on sache lequel des deux.

## Avant de commencer

1. `docker ps --filter name=sysdent_s0b` — le conteneur tourne ?
2. `git status` — l'arbre est-il propre ?
3. Si une migration doit être écrite : qui est le propriétaire de la tête ?

## En cas de doute

Un `git status` montre les fichiers modifiés. S'il y en a que vous ne
reconnaissez pas, **ne les écrasez pas** : ils appartiennent à l'autre agent.
