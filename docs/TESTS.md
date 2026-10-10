# Tests

Les tests du backend parlent à PostgreSQL. Cette page explique **quelle
instance** ils doivent viser, comment la lancer, et ce qui les empêche d'écrire
dans l'instance de développement.

---

## La règle, en une phrase

**Les tests n'ont le droit de viser qu'une instance qui porte la base-témoin
`sysdent_instance_test_marker`.** Cette base n'existe que sur l'instance de
tests ; aucune instance réelle ne la porte. Au démarrage de chaque session,
`tests/conftest.py` la vérifie et **refuse de s'exécuter** si elle est absente.

Conséquence : une session de tests qui viserait par mégarde l'instance de
développement s'arrête sur un message, avant le moindre `CREATE DATABASE`.

## Lancer l'instance de tests

L'instance est **distincte** de celle de développement : port `55436` (le
développement est sur `55435`), volume `tmpfs` (rien n'est écrit sur le disque),
identifiants imposés par variable d'environnement.

PowerShell :

```powershell
$env:TEST_PG_PASSWORD = "<mot de passe de votre choix, uniquement pour les tests>"
cd Backend
docker compose -f docker-compose.test.yml up -d
```

Le mot de passe n'a pas de valeur par défaut dans le fichier de composition :
`docker compose` refuse de démarrer sans lui. Il n'est donc jamais écrit dans le
dépôt, et il ne peut pas être confondu avec celui du développement.

Arrêter l'instance :

```powershell
docker compose -f docker-compose.test.yml down
```

Le volume étant `tmpfs`, `down` suffit : il n'y a pas de volume nommé à
supprimer.

## Pointer les tests sur cette instance

Les tests lisent **exclusivement** `TEST_DATABASE_URL`. Elle est **obligatoire et
sans valeur par défaut** : sans elle, la session s'arrête.

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://<utilisateur>:<mot de passe>@localhost:55436/postgres"
```

Le nom de base dans l'URL est `postgres` : c'est le point d'entrée
d'administration, depuis lequel la garde de démarrage vérifie le marqueur et
puis crée `sysdent_master_test`, `sysdent_platform_test` et le modèle de tenant.

## Ce que les tests utilisent sur cette instance

| Base | Rôle | Créée par |
|---|---|---|
| `sysdent_instance_test_marker` | Preuve que l'instance est dédiée aux tests | `docker/init-test/10_marqueur.sql`, au démarrage du conteneur |
| `sysdent_master_test` | Registre, index des emails, super-admins | `conftest.py` |
| `sysdent_platform_test` | Console, quotas, annonces | `conftest.py` |
| `sysdent_modele_tenant_test` | Modèle migré, **cloné** par base de test | `base_de_test.py` |

Aucune de ces bases ne porte de donnée réelle : elles sont sur une instance
`tmpfs`, sans volume sur disque.

## Les bases que les tests ne doivent jamais viser

La garde de démarrage échoue également si `TEST_DATABASE_URL` :

- désigne le même `hôte:port` que l'instance de développement ;
- nomme une base réelle : `sysdent_master`, `sysdent_platform`, ou une base de
  cabinet du registre.

Ces trois refus sont **cumulatifs** : il faut que les trois soient satisfaits
pour qu'une session démarre.

## Lancer les tests

Depuis `Backend/` :

```powershell
$env:TEST_DATABASE_URL = "..."
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

## Ce que le hook de commit vérifie, et ce qu'il ne vérifie pas

Le hook `pre-commit` (`Backend/scripts/controle_integrite.py`) vérifie la
compilation, l'unicité de tête de chaque chaîne Alembic, et l'absence de
caractères d'écritures non latines dans les fichiers modifiés. Il **ne vérifie
pas** la base visée : c'est la garde de démarrage des tests qui le fait, parce
qu'elle peut, elle, se connecter et constater.

## Ne pas contourner la garde

Si une session échoue en annonçant que l'instance n'est pas marquée, la réponse
n'est pas de désactiver le contrôle. C'est de lancer
`docker compose -f docker-compose.test.yml up -d`. Une garde qu'on écarte
quand elle gêne est une garde qui ne protège plus au moment où l'on en aurait
besoin.