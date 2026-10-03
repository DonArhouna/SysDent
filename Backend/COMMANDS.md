# 🛠️ Guide des Commandes SysDent Pro

Ce guide récapitule toutes les commandes indispensables pour le développement, la gestion de Docker, l'accès aux bases de données PostgreSQL et le lancement de l'API.

---

## 🐘 1. Connexion & Gestion PostgreSQL

### Identifiants par défaut
| Paramètre | Valeur |
|---|---|
| **Hôte (Host)** | `localhost` |
| **Port** | `5432` |
| **Utilisateur (User)** | `postgres` |
| **Mot de passe (Password)** | `postgres_password` |
| **Base centrale (Master)** | `sysdent_master` |

### 🚀 Initialisation des tables & du Super Admin
Si la base vient d'être créée, exécutez ce script pour créer toutes les tables et le premier compte administrateur :
```powershell
python init_db.py
```

### Commandes CLI Docker (`psql`)
```powershell
# Se connecter à la base Master dans le conteneur
docker exec -it sysdent_master_db psql -U postgres -d sysdent_master

# Se connecter directement en spécifiant un utilisateur
docker exec -it sysdent_master_db psql -U postgres
```

### Commandes utiles à l'intérieur de `psql`
```sql
-- Lister toutes les tables du schéma
\dt

-- Voir la structure détaillée d'une table (colonnes, clés, index)
\d societes
\d tenants_db
\d super_admins

-- Lister toutes les bases de données
\l

-- Se connecter à une autre base de données (ex: base d'un cabinet)
\c nom_de_la_base

-- Requêtes SQL courantes
SELECT * FROM societes;
SELECT * FROM tenants_db;
SELECT * FROM super_admins;

-- Quitter psql
\q
```

---

## 🐳 2. Commandes Docker Compose

Exécutez ces commandes depuis le dossier `Backend/` :

```powershell
# Démarrer tous les conteneurs en arrière-plan (avec reconstruction de l'image)
docker compose up -d --build

# Démarrer uniquement les services de base (PostgreSQL Master + Redis)
docker compose up -d master_db redis

# Voir l'état des conteneurs
docker compose ps

# Voir les logs en temps réel de tous les services
docker compose logs -f

# Voir les logs d'un service spécifique (ex: backend)
docker compose logs -f backend

# Arrêter tous les conteneurs
docker compose down

# Arrêter et supprimer également les volumes (⚠️ supprime les données)
docker compose down -v
```

---

## 🐍 3. Lancement Local (Python / PowerShell Windows)

Exécutez ces commandes depuis le dossier `Backend/` :

```powershell
# 1. Autoriser l'exécution de scripts (si restriction PowerShell)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 2. Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# 3. Installer/mettre à jour les dépendances
pip install -r requirements.txt

# 4. Lancer le serveur de développement (Port 8000 par défaut ou 8001 si 8000 occupé)
uvicorn src.main:app --reload --port 8000
# ou
uvicorn src.main:app --reload --port 8001
```

---

## 🔄 4. Migrations de Base de Données (Alembic)

Il existe **deux environnements Alembic distincts**, car il y a deux schémas différents (`src/common/base_model.py` : `Base` pour le Master, `TenantBase` pour les cabinets) :
- `Backend/alembic/` (+ `alembic.ini`) → base **Master** (`societes`, `tenants_db`, `super_admins`, `audit_logs_global`). Une seule base, l'URL vient de `.env`.
- `Backend/alembic_tenant/` (+ `alembic_tenant.ini`) → schéma **Tenant** (`patients`, `consultations`, `facturation`, etc.). Appliqué à N bases (une par cabinet) : l'URL de la base cible doit être passée explicitement à chaque commande.

Toutes les commandes s'exécutent depuis `Backend/`.

### Schéma Master
```powershell
# Après avoir modifié src/modules/master/models.py :
python -m alembic revision --autogenerate -m "description_du_changement"

# Appliquer les migrations en attente sur la base Master (.env)
python -m alembic upgrade head

# Revenir en arrière d'une révision
python -m alembic downgrade -1
```

### Schéma Tenant
```powershell
# Après avoir modifié src/modules/tenants/models.py, générer la révision contre UNE base
# tenant existante (le diff sert de référence pour toutes les autres) :
python -m alembic -c alembic_tenant.ini -x tenant_db_url="postgresql+psycopg2://postgres:postgres_password@localhost:5432/<nom_base_tenant>" revision --autogenerate -m "description_du_changement"

# Appliquer cette migration à une base tenant précise :
python -m alembic -c alembic_tenant.ini -x tenant_db_url="postgresql+psycopg2://postgres:postgres_password@localhost:5432/<nom_base_tenant>" upgrade head   
```
Pour une **nouvelle société**, cette dernière commande est exécutée automatiquement par `MasterTenantService.create_societe_and_provision_tenant` (voir `src/core/migrations.py`) : pas besoin de la lancer à la main.

⚠️ **Règle d'équipe :** plus aucun `Base.metadata.create_all` / `TenantBase.metadata.create_all` dans le code applicatif. Toute évolution de schéma passe par une révision Alembic, relue avant d'être appliquée (l'autogenerate ne détecte pas tout : renommages de colonnes, changements de type, etc.).

⚠️ **Base de référence pour l'autogenerate :** la commande `revision --autogenerate` du schéma Tenant compare le modèle ORM à l'état réel d'une base. Il faut donc pointer vers une base tenant **à jour** (appliquée jusqu'à `head`), sinon Alembic génère un diff qui revient à un état antérieur et crée des colonnes en double. Si vous n'avez pas de base tenant sous la main, créez-en une jetable :
```powershell
docker exec sysdent_master_db psql -U postgres -d postgres -c "CREATE DATABASE sysdent_tenant_ref;"
python -m alembic -c alembic_tenant.ini -x tenant_db_url="postgresql+psycopg2://postgres:postgres_password@localhost:5432/sysdent_tenant_ref" upgrade head
```

### Appliquer une migration à TOUS les cabinets existants
Quand une révision touche le schéma Tenant, elle doit être appliquée à chaque base cabinet déjà provisionnée. Liste des bases :
```powershell
docker exec sysdent_master_db psql -U postgres -d sysdent_master -t -A -c "SELECT db_name FROM tenants_db WHERE statut = 'ACTIVE';"
```
Puis, pour chaque base :
```powershell
python -m alembic -c alembic_tenant.ini -x tenant_db_url="postgresql+psycopg2://postgres:postgres_password@localhost:5432/<db_name>" upgrade head
```
Les nouvelles sociétés, elles, l'auront déjà via le provisioning automatique.

---

## 🧪 5. Tests

Les tests utilisent une **vraie base PostgreSQL jetable** (créée et supprimée par test), pas SQLite : le module emploie du JSONB, des UUID natifs et des `INSERT ... ON CONFLICT`, que SQLite ne reproduit pas fidèlement. Un test vert sur SQLite ne prouverait rien sur la numérotation ni sur l'atomicité des compteurs.

```powershell
# Suite complète
.\.venv\Scripts\python.exe -m pytest tests/ -q

# Modules métier (hors tests d'isolation)
.\.venv\Scripts\python.exe -m pytest tests/ -q --cov=src.modules.patients --cov=src.modules.consultations --cov=src.common.numerotation --cov-report=term-missing

# Avec rapport de couverture
.\.venv\Scripts\python.exe -m pytest tests/ -q --cov=src.modules.patients --cov=src.common.numerotation --cov-report=term-missing

# Un seul fichier
.\.venv\Scripts\python.exe -m pytest tests/test_patients_numerotation.py -v

# Un seul test
.\.venv\Scripts\python.exe -m pytest tests/test_patients_dossier.py::test_alertes_grossesse_et_allergie_grave -v
```

Les fixtures lisent l'hôte et le port PostgreSQL depuis `.env` (`TENANT_DB_*`), ou depuis la variable `TEST_MASTER_DB_URL` si elle est définie (utile pour cibler une instance éphémère). **Vérifiez que le port 5432 n'est pas occupé par un second serveur PostgreSQL** — voir §7.

⚠️ `TEST_MASTER_DB_URL` ne couvre **que** les bases tenants jetables. Les tests de la console Master (`tests/test_security_master_auth.py`) lisent `settings.master_db_async_url`, donc ils ignorent cette variable et restent sur le port de `.env`. Sur une machine où le 5432 est contesté, il faut donc pointer aussi `MASTER_DB_PORT`, sinon ces tests échouent avec une erreur de connexion `asyncpg`.

Si le port 5432 est inutilisable sur votre poste, le script suivant monte une instance jetable sur un port libre et positionne les variables d'environnement pour la session PowerShell courante :

```powershell
. .\_setup_test_db.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head   # une fois, sur la base Master
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

⚠️ **La suite est lente (~6-7 minutes, 190 tests)** : chaque test crée une base, y applique les 7 révisions Alembic, puis la supprime. C'est le prix d'une isolation réelle — une base partagée ferait gagner du temps mais créerait des faux verts.

⚠️ Sous Windows, la pile réseau d'asyncpg abandonne parfois une connexion en cours (`WinError 995`) quand la suite ouvre et ferme des centaines de sockets. La fixture `tenant_db` réessaie une fois : c'est de la résilience de l'outillage de test, pas un comportement du produit.

⚠️ SQLAlchemy est épinglé à `<2.1.0` : la 2.1.x casse le cache de requêtes Cython sous coverage (`TypeError: 'InternalTraversal' object is not callable`). Les tests passent sans `--cov` mais plantent avec.

⚠️ `app.dependency_overrides` est un dictionnaire **global** : deux clients de test ne peuvent pas conserver leurs injections simultanément, la dernière écrase la première. Les fixtures d'isolation réinstallent l'injection du cabinet concerné avant chacun de ses appels (`Ctx.use()`).

⚠️ `require_permissions` lit les permissions **du JWT**, pas de la base. Pour tester le RBAC de bout en bout, il faut remplacer l'en-tête `Authorization` : surcharger `get_current_user` ne suffit pas.

⚠️ **Ne jamais réutiliser un moteur global dans un test.** `master_engine` est instancié à l'import : son pool reste attaché à la première boucle d'événements qui l'a utilisé, et le test suivant échoue sur « Event loop is closed ». Les fixtures `master_db` et `tenant_db` créent un moteur dédié par test, et la console Master est testée via une surcharge de `get_master_db`.

⚠️ Un `UPDATE` sur `Model.__table__` **n'actualise pas** l'`identity_map` SQLAlchemy : la session renvoie alors l'instance périmée. Pour modifier une entité déjà chargée, passer par l'ORM (`objet.attribut = ...`) plutôt que par un `UPDATE` Core.

⚠️ `expire_on_commit=False` (réglage applicatif) laisse les **collections** déjà chargées en cache dans l'`identity_map`. Une requête de rechargement après écriture ne les rafraîchit pas : une ligne ajoutée ou supprimée par le traitement courant reste invisible. Utiliser `.execution_options(populate_existing=True)` sur les requêtes de rechargement qui doivent voir les collections modifiées. C'est le cas de `OdontogrammeService._charger` et `OrdonnanceService._charger`.

⚠️ Un `rollback` (provoqué par toute requête en erreur) **expire** les objets du session. Relire ensuite un attribut d'un `Utilisateur` déjà chargé (`auteur.id`) depuis une coroutine lève `MissingGreenlet`. En production chaque requête charge un utilisateur neuf, le problème n'apparaît pas ; en test, la fixture `client_authenticated` renvoie volontairement une **copie détachée** pour reproduire ce comportement et supprimer cette classe d'échecs trompeurs.

⚠️ FastAPI teste les routes **dans l'ordre de déclaration** : un sous-routeur comme `/ordonnances/medicaments` est absorbé par `/ordonnances/{prescription_id}` s'il est enregistré après. L'ordre dans `src/api/v1/router.py` est significatif — voir le commentaire qui l'accompagne. La même règle s'applique **dans** un routeur : `/rendez-vous/{id}` est déclaré après `/rendez-vous/agenda`, sinon l'agenda serait interprété comme un identifiant.

⚠️ **Assigner une chaîne à une colonne `Enum` laisse l'attribut ORM en `str`** jusqu'au rechargement suivant : SQLAlchemy ne convertit la valeur qu'à la lecture. `.statut.value` échoue alors. Toujours convertir à l'écriture (`StatutConsultationEnum.EN_COURS`). C'est invisible dans les modules qui rechargent systématiquement, et explosif dans ceux qui sérialisent l'objet courant — le module Rendez-vous l'a révélé pour le module Consultations.

⚠️ **`error.details` part tel quel dans un `JSONResponse`.** Y mettre un `datetime` lève « Object of type datetime is not JSON serializable ». Les conflits de rendez-vous transportent donc des chaînes ISO.

⚠️ **Une colonne `Enum(...)` n'accepte pas `type='exclude'` dans `op.drop_constraint`** : Alembic ne connaît que check/foreignkey/primary/unique. Utiliser `ALTER TABLE … DROP CONSTRAINT` en SQL brut.

---

## 🔐 5ter. Sécurité — Sprint 0bis

Ce sprint a fermé les brèches identifiées lors de l'audit. Points à connaître avant de toucher à l'authentification :

| Élément | Où | Rôle |
|---------|-----|------|
| Catalogue de permissions | `src/common/permissions.py` | Source de vérité `MODULE:ACTION` + matrice des 6 rôles métier |
| Seed RBAC | `src/modules/rbac/services.py` | Sème permissions, rôles et matrice au provisioning |
| Console Master | `src/modules/master/dependencies.py` | `get_current_super_admin` : exige rôle SUPER_ADMIN **et** `tenant_id` absent |
| Sessions | `src/modules/auth/services.py` | Rotation + révocation via `jti` persisté |
| Limitation de débit | `src/core/rate_limit.py` | Fenêtre glissante en mémoire, avant tout accès base |
| Index de routage | `src/modules/master/models.py` (`UtilisateurIndex`) | email → société en base Master, login en O(1) |

**Deux règles qui ne doivent pas être contournées :**

1. `require_permissions` court-circuite `ADMIN_CABINET` et `SUPER_ADMIN`. C'est volontaire : `ADMIN_CABINET` est le rôle de secours qui empêche un cabinet de se verrouiller hors de sa base. Ne pas le retirer.
2. Un rôle créé via `POST /rbac/roles` naît **sans aucune permission**. Les droits s'accordent une par une. Ne pasSeeder les rôles d'un accès complet à la création : ce serait une escalade en une requête.

**Limitation connue du rate limiter :** il est en mémoire, donc par process. En cas de déploiement multi-workers ou multi-instances, la limite réelle est multipliée par le nombre de workers. Passer alors par un compteur Redis partagé. Le verrouillage persistant du compte Super Admin (`super_admins.verrouille_jusqua`) reste valable dans tous les cas.

**Mot de passe du Super Admin :** `init_db.py` lit `SUPER_ADMIN_PASSWORD`. En `APP_ENV=production`, l'absence de cette variable est une erreur fatale. En développement, une valeur de secours est tolérée pour que le script reste exécutable.

---

## 🦷 5bis. Modules métier livrés

| Module | Prefixe API | Statut |
|--------|-------------|--------|
| Patients & Dossier Médical | `/api/v1/patients` | D1A — CRUD, recherche, archivage, état général, antécédents, alertes |
| Consultations & Actes | `/api/v1/consultations` | D1B — workflow PLANIFIEE→EN_COURS→TERMINEE, actes, total facturable |
| Nomenclature des actes | `/api/v1/nomenclature/actes` | D1B — tarification du cabinet |
| Odontogramme | `/api/v1/odontogramme` | D1C — dents, faces, historique, charting parodontal |
| Ordonnances & prescriptions | `/api/v1/ordonnances` | D1D — référentiel, contre-indications, interactions, signature |
| Référentiel médicamenteux | `/api/v1/ordonnances/medicaments` | D1D — formulaire semé au provisioning, règles en base |
| Cabinets, salles & fauteuils | `/api/v1/cabinets` | D2A — sites, ressources physiques, vue planning |
| Praticiens | `/api/v1/praticiens` | D2A — rattachement au site, numéros d'ordre |
| Disponibilités | `/api/v1/praticiens/{id}/disponibilites` | D2A — plages de travail, créneaux proposables |
| Rendez-vous & Agenda | `/api/v1/rendez-vous` | D2B — conflits praticien **et** fauteuil, cycle de vie |
| Blocage de fauteuil | `/api/v1/rendez-vous/fauteuils/blocage` | D2B — panne, réparation, réservation interne |
| RBAC & rôles | `/api/v1/rbac` | Sprint 0bis — catalogue, rôles, attribution de permissions |

**Permissions RBAC utilisées** (format `MODULE:ACTION`) :
- `PATIENTS:READ`, `PATIENTS:CREATE`, `PATIENTS:UPDATE`
- `CONSULTATIONS:READ`, `CONSULTATIONS:CREATE`, `CONSULTATIONS:UPDATE`
- `ODONTOGRAMME:READ`, `ODONTOGRAMME:UPDATE`
- `ORDONNANCES:READ`, `ORDONNANCES:CREATE`, `ORDONNANCES:UPDATE`, `ORDONNANCES:SIGN`
- `CABINETS:READ`, `CABINETS:CREATE`, `CABINETS:UPDATE`, `CABINETS:DELETE`
- `PRATICIENS:READ`, `PRATICIENS:CREATE`, `PRATICIENS:UPDATE`, `PRATICIENS:DELETE`
- `DISPONIBILITES:READ`, `DISPONIBILITES:CREATE`, `DISPONIBILITES:UPDATE`, `DISPONIBILITES:DELETE`
- `AUDIT:READ`, `ADMIN:READ`, `ADMIN:UPDATE`

Dans la matrice des rôles :
- `SECRETAIRE` n'a **aucune** permission `ORDONNANCES:*` (y compris `:READ`) : la prescription est un acte médical réservé au praticien.
- `SECRETAIRE` et `ASSISTANT` ont `CABINETS:READ` / `PRATICIENS:READ` / `DISPONIBILITES:READ` : ils **placent** un rendez-vous, ils ne modifient ni le décor ni les horaires des dentistes. Seul le `PRATICIEN` gère ses disponibilités.
- `COMPTABLE` n'a rien du pôle 2 clinique : un comptable n'a pas à voir les fauteuils ni les agendas.

Le catalogue complet et la matrice des rôles sont dans `src/common/permissions.py`. ⚠️ Les cabinets provisionnés **avant** le Sprint 0bis n'ont pas de permissions seedées : leurs rôles non-administrateur sont donc sans accès. Même problème pour le formulaire médicamenteux de D1D. Relancer les deux seeds sur ces bases :

```python
# depuis Backend/, sur une base tenant existante
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import settings
from src.modules.rbac.services import RbacService
from src.modules.ordonnances.services import MedicamentService

async def main():
    engine = create_async_engine(settings.master_db_async_url.replace('sysdent_master', '<nom_base_tenant>'))
    async with async_sessionmaker(bind=engine, class_=AsyncSession)() as s:
        print(await RbacService.bootstrap_complet(s))
        print('molecules ajoutees :', await MedicamentService.semer_formulaire(s))
        await s.commit()

asyncio.run(main())
"
```

**Contrat pour le pôle Facturation (D2C)** : une facture se génère depuis `GET /api/v1/consultations/{id}/total`, qui renvoie le total **déjà recalculé** à partir des lignes d'actes (`total_actes`, `nb_actes`, `devise: XOF`). Le montant n'est jamais ressaisi. Les générateurs de `numero_facture`, `generer_numero_recu_paiement` et `generer_numero_devis` sont déjà prêts dans `src/common/numerotation.py`.

---

## 🦷 5ter. Odontogramme (D1C) — contrat pour le composant SVG

Le vocabulaire dentaire (numérotation FDI, faces, états) est centralisé dans `src/common/dentaire.py`, **référentiel partagé avec le module Consultations**. Ajouter un état odontologique se fait à un seul endroit, et les deux modules restent cohérents.

### Points d'API

| Route | Effet |
|-------|-------|
| `GET /odontogramme/patients/{id}` | Odontogramme complet. **Le génère s'il n'existe pas** (RG11) |
| `POST /odontogramme/patients/{id}` | Création explicite, choix `ADULTE` / `ENFANT` / `MIXTE`. Idempotente |
| `PATCH /odontogramme/patients/{id}/dent` | Change l'état d'une dent, écrit l'historique (RG10) |
| `PATCH /odontogramme/patients/{id}/dents` | Lot de dents en une transaction (détartrage) |
| `PUT /odontogramme/patients/{id}/dent/{fdi}/faces` | Met à jour les faces d'une dent |
| `GET /odontogramme/patients/{id}/dent/{fdi}/historique` | Historique horodaté d'une dent |
| `GET /odontogramme/patients/{id}/historique` | Historique toutes dents confondues |
| `POST /odontogramme/patients/{id}/charting` | Relevé parodontal (sondage 6 points + indices) |
| `GET /odontogramme/referentiel/etats` | **Catalogue des états + couleurs, à consommer tel quel** |

### Règles que le frontend doit connaître

1. **`/referentiel/etats` est la source de vérité pour les couleurs.** Le composant SVG ne doit pas coder la liste des états en dur : chaque entrée porte `code`, `libelle`, `couleur` (hex) et `categorie` (`SAINE` / `SOIGNEE` / `ATTENTION` / `AUTRE`).
2. **RG11** : 32 dents en `ADULTE`, 20 en `ENFANT`. Le numéro FDI va de 11 à 48 (définitives) ou 51 à 85 (lait).
3. **La lecture génère l'odontogramme.** Un patient créé avant D1C n'en a pas ; le premier `GET` le crée. Pas de 404 à gérer côté UI.
4. **`a_alerte: true`** signale une dent qui appelle une décision (carie avancée, reprise de TCR, extraction planifiée…). C'est le signal à afficher en surbrillance.
5. **Le résumé** (`nb_dents_soignees`, `nb_dents_a_traiter`, `nb_dents_absentes`, `resume`) évite au praticien de parcourir les 32 dents.
6. **Le type d'un état est une chaîne**, pas un enum fermé : ajouter un code côté backend ne casse pas le frontend.

---

## 💊 5quater. Ordonnances (D1D) — contrat pour le frontend

Le module le plus sensible du pôle médical : prescrire un médicament contre-indiqué est un risque patient direct. Sa particularité est que **les règles vivent en base, pas dans le code** — ajouter une règle médicamenteuse est une mise à jour de données.

### Points d'API

| Route | Effet |
|-------|-------|
| `GET /ordonnances/medicaments` | Référentiel avec les règles. Filtres `q`, `forme`, `classe` |
| `POST /ordonnances/medicaments` | Ajoute un produit **et ses règles**, sans redéploiement |
| `POST /ordonnances/controle` | **Contrôle à blanc** : répond sans rien écrire (UC8) |
| `POST /ordonnances` | Émet une ordonnance liée à une consultation |
| `POST /ordonnances/{id}/signer` | Verrouille l'ordonnance : plus aucune modification |
| `POST/PATCH/DELETE /ordonnances/{id}/lignes[/{ligne_id}]` | Édition tant que non signée |
| `GET /ordonnances?patient_id=&consultation_id=` | Historique |

### La distinction à comprendre avant d'intégrer l'UI

Deux gravités, et le frontend doit les traiter différemment :

| Gravité | Effet serveur | Code erreur | Ce que l'UI doit faire |
|---------|---------------|-------------|-----------------------|
| `INTERDIT` | Ligne **refusée**, rien n'est écrit | `CONTRE_INDICATION_ABSOLUE` | Afficher `error.details.alertes` en **rouge bloquant**. Ne pas proposer de contourner |
| `PRECAUTION` | Ligne **acceptée** si `justification_precaution` est fournie | `JUSTIFICATION_PRECAUTION_REQUISE` | Ouvrir un champ **obligatoire** justifiant la décision, puis renvoyer la ligne |

⚠️ Ne jamais fusionner les deux en un simple avertissement : la première est une sécurité, la seconde est une trace.

### Autres règles que le frontend doit connaître

1. **`/controle` est le bon point d'appel pendant la saisie.** Le praticien teste avant de taper la posologie, sans rien laisser derrière lui. La réponse renvoie aussi `conditions_actives` (l'état du patient ayant déclenché les règles) : c'est ce qui rend le refus compréhensible au lieu d'être arbitraire.
2. **Une ordonnance signée est immuable.** `422 / PRESCRIPTION_SIGNEE` sur toute modification, y compris l'ajout ou la suppression d'une ligne. On ne la « dé-signe » pas : on en émet une nouvelle.
3. **`medicament_id` ou `medicament_texte`, au moins l'un des deux.** Un produit hors référentiel reste prescriptible (préparation locale) mais déclenche une alerte `MEDICAMENT_HORS_REFERENTIEL` : aucune contre-indication n'a pu être évaluée. **L'UI doit rendre cette alerte visible**, sinon le praticien croira à un contrôle effectué.
4. **Les alertes sont conservées dans l'acte** (`prescriptions.alertes`). Le référentiel peut évoluer après coup ; ce qui a été signalé au moment de la prescription reste attesté.
5. **Un refus n'est écrit ni en base ni en audit métier** — la transaction est annulée. Il reste dans les **journaux serveur** (`prescription_refusee_contre_indication`, puis l'événement d'exception `CONTRE_INDICATION_ABSOLUE`). Ne pas annoncer une traçabilité en base du refus : elle n'existe pas.
6. **Le formulaire de départ (14 molécules) est semé au provisioning.** Un cabinet créé avant D1D n'en a pas : relancer `MedicamentService.semer_formulaire` sur sa base. C'est idempotent.
7. ⚠️ **Le formulaire est un point de départ technique, pas une base pharmacopée.** Il doit être revu par un pharmacien avant usage sur des patients réels. Les posologies sont celles de l'adulte uniquement.

### Vérification de bout en bout

```powershell
.\.venv\Scripts\python.exe .\_verify_d1d.py
```

---

## 🏢 5quinquies. Cabinets & Ressources (D2A) — socle du pôle 2

Premier jalon du pôle 2 : le **décor physique et organisationnel** du cabinet. Le module Agenda (D2B) le consomme sans le redéfinir. Le vocabulaire des disponibilités est centralisé dans `src/common/disponibilite.py`, **référentiel partagé** — même principe que `dentaire.py` pour D1B/D1C.

### Points d'API

| Route | Effet |
|-------|-------|
| `GET /referentiel/disponibilites` | Jours, types de plage, durée de créneau. **Contrat de formulaires** |
| `GET/PATCH /cabinets[/{id}]` | Sites, horaires d'ouverture, compteurs |
| `GET/POST /cabinets/{id}/salles` | Salles d'un site |
| `GET /cabinets/{id}/fauteuils` | **Vue planning** : tous les fauteuils du site, salle comprise |
| `POST /salles/{id}/fauteuils` · `PATCH/DELETE /fauteuils/{id}` | Fauteuils |
| `GET/POST /praticiens` | Profils praticiens (rattachés à un compte existant) |
| `GET/POST/PATCH /praticiens/{id}/disponibilites` | Plages de travail |
| `GET /praticiens/{id}/creneaux?date=` | **Créneaux proposables au patient** |
| `POST/DELETE /cabinets/{id}/praticiens/{id}/rattachement` | Rattachement au site |

### Les deux notions à ne jamais confondre

| | Horaires d'ouverture | Disponibilités |
|---|---|---|
| Portée | le **bâtiment** (`Cabinet.horaires_ouverture`) | **ce praticien** (`Disponibilite`) |
| Qui les saisit | l'administrateur | le praticien |
| Type de plage | — | `CONSULTATION` / `URGENCE` / `BLOCKING` |

Un créneau proposable au patient doit être dans les deux. Le module Agenda fera l'intersection.

### Règles que le frontend doit connaître

1. **`type` ∈ {`CONSULTATION`, `URGENCE`, `BLOCKING`}.** `BLOCKING` **retire** des créneaux (congé, formation) alors que `CONSULTATION` en crée. Confondre les deux ferait proposer un créneau à un dentiste absent. Une `BLOCKING` peut **recouvrir exactement** une plage `CONSULTATION` : c'est ainsi qu'on déclare une formation l'après-midi.
2. **L'identité d'une plage** = (praticien, jour *ou* date, heure début, heure fin, **type**, site). Un doublon exact est refusé ; deux plages distinctes du même jour sont acceptées et fusionnées au calcul.
3. **`/creneaux` renvoie toujours un `avertissement` explicite** quand la liste est vide. Une liste vide signifie trois choses très différentes : aucune disponibilité déclarée (panne de configuration), toutes les plages bloquées (absence), ou journée uniquement en indisponibilité. Ne jamais afficher « agenda complet » sur la seule foi d'une liste vide.
4. **Un fauteuil utilisé ne se supprime pas** (`422 FAUTEUIL_UTILISE`) : `consultations.fauteuil_id` est en `ON DELETE SET NULL`, la suppression effacerait le lieu du soin. Le désactiver suffit.
5. **Détacher un praticien clôture son rattachement** (`date_fin` renseignée) au lieu de le supprimer : ses consultations passées restent attribuables.
6. ⚠️ **`consultations.fauteuil_id` n'est pas encore écrit par l'API** (migration posée, D2B le branchera à l'ouverture d'une consultation depuis un rendez-vous). `/creneaux` ne retranche pas non plus les rendez-vous déjà pris : D2B s'en chargera.
7. **Un tenant est multi-site.** `ConsultationService._resoudre_cabinet` refuse de deviner si plusieurs sites sont actifs (`422 CABINET_AMBIGU`). Les listes filtrables par `cabinet_id` sont donc le cas normal, pas un cas particulier.

### Vérification de bout en-bout

```powershell
.\.venv\Scripts\python.exe .\_verify_d2a.py
```

---

## 📅 5sexies. Rendez-vous & Agenda (D2B) — le cœur du pôle 2

### La décision structurante : **la base est l'arbitre des conflits**

Deux **contraintes d'exclusion PostgreSQL** interdisent physiquement le double-booking :

```sql
-- rendez_vous : un praticien ne peut pas avoir deux RDV qui se chevauchent
EXCLUDE USING gist (praticien_id WITH =, tstzrange(debut, fin, '[)') WITH &&)
  WHERE (statut NOT IN ('ANNULE', 'ABSENT', 'TERMINEE'))

-- creneaux_fauteuil : un fauteuil ne peut pas être occupé deux fois
EXCLUDE USING gist (fauteuil_id WITH =, tstzrange(debut, fin, '[)') WITH &&)
```

Une vérification applicative **ne peut pas** empêcher deux secrétaires de valider au même instant : entre son test et son `INSERT`, l'autre passe. Le service fait malgré tout un contrôle préalable — non pour protéger la base, mais pour **nommer l'obstacle** dans le message : une violation de contrainte ne dit pas « Mme Diop, détartrage, 09:00 ».

⚠️ **`btree_gist` est requis** (opérateur `=` sur UUID pour un index GiST). La révision `f4433b308196` la crée sur chaque base tenant. En production, le rôle de création de base doit avoir le droit d'installer des extensions.

### Occupation de fauteuil : une seule table, toutes causes confondues

`creneaux_fauteuil` porte les rendez-vous **et** les indisponibilités (panne). C'est ce qui permet à la contrainte de fauteuil de couvrir les deux d'un seul trait. Répartir les deux cas entre deux tables obligerait à revérifier en croisant — et rouvrirait la fenêtre de course qu'on vient de fermer.

### Points d'API

| Route | Effet |
|-------|-------|
| `POST /rendez-vous` | Prise de RDV. **422 `CRENEAU_DEJA_OCCUPE`** avec le détail du conflit |
| `GET /rendez-vous/creneaux-libres` | **Créneaux disponibles** : heures déclarées moins ce qui est pris |
| `GET /rendez-vous/agenda?date=` | Journée : rendez-vous **et** indisponibilités de fauteuil |
| `POST /rendez-vous/{id}/statut` | Faire avancer le cycle de vie |
| `POST /rendez-vous/{id}/planifier` | Report atomique (libère l'ancien, réserve le nouveau) |
| `POST /rendez-vous/{id}/consultation` | Ouvre la consultation, reprend le fauteuil |
| `POST /rendez-vous/fauteuils/blocage` | Immobilise un fauteuil sans rendez-vous |
| `GET /rendez-vous/referentiel` | Cycle de vie + graphe des transitions |

### Règles que le frontend doit connaître

1. **Le cycle est fermé.** `Planifié → Confirmé → Salle d'attente → Consultation → Terminé`, plus `Annulé` et `Absent` à tout moment avant la consultation. Un rendez-vous annulé ne se rouvre pas. `error.details.transitions` liste ce qui reste possible : **n'afficher que ces actions**.
2. **`error.details.conflits` est le cœur de l'UX.** Chaque conflit dit la ressource (`PRATICIEN` / `FAUTEUIL`), le créneau, le patient et le motif. C'est ce qui permet de proposer 09:30 au lieu d'afficher « conflit ».
3. **Hors disponibilités déclarées : accepté mais signalé.** `hors_disponibilites: true` dans la réponse et l'avertissement dans le message. Un cabinet qui n'a pas saisi ses horaires doit pouvoir prendre un rendez-vous, et une urgence ne peut pas attendre. Les **conflits**, eux, restent bloquants : ils sont physiques.
4. **Un créneau adjacent est valide.** 09:00-09:30 puis 09:30-10:00 passe. Les bornes sont ouvertes en fin, sinon un cabinet ne pourrait pas remplir une matinée.
5. **Tout statut terminal libère le fauteuil.** La contrainte de fauteuil ne voit pas le statut du rendez-vous (autre table) : c'est le service qui libère. `consultations.fauteuil_id` conserve l'historique du lieu du soin.
6. **Un rendez-vous sans fauteuil est possible** (visite d'évaluation, urgence). `/creneaux-libres` ne propose un créneau que s'il reste au moins un fauteuil libre.
7. **Le cycle se termine par le module Consultations** : le module Rendez-vous ne termine jamais seul un rendez-vous en consultation.

### Vérification de bout en bout

```powershell
.\.venv\Scripts\python.exe .\_verify_d2b.py
```

---

## 🌐 6. Liens & Endpoints Utiles

- **Documentation Swagger UI** : [http://localhost:8000/docs](http://localhost:8000/docs) (ou port 8001)
- **Documentation ReDoc** : [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Vérification de santé** : [http://localhost:8000/health](http://localhost:8000/health)

---

## ⚠️ 7. Conflit de port PostgreSQL 5432 (piège connu sur cette machine)

Si l'API échoue au démarrage avec `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9` ou `password authentication failed`, **ce n'est pas un bug du code**. Cela signifie que deux serveurs PostgreSQL se partagent le port 5432 et que les connexions partent vers le mauvais.

Le service Windows `postgresql-x64-16` (installation native) et le conteneur Docker `sysdent_master_db` écoute tous deux sur 5432. Les connexions se répartissent aléatoirement entre les deux : le serveur natif répond avec des messages encodés en Windows-1252, d'où le `0xe9` (è) illisible en UTF-8.

Diagnostic :
```powershell
# Qui écoute sur 5432 ?
netstat -ano | Select-String ':5432'

# Le service natif tourne-t-il ?
Get-Service postgresql-x64-16
```

Deux solutions, au choix :
- **Arrêter le service Windows natif** si vous utilisez uniquement Docker (le projet est conçu pour Docker) :
  ```powershell
  Stop-Service postgresql-x64-16
  ```
- **Changer le port du conteneur** dans `docker-compose.yml` (par exemple `5434:5432`) et répercuter dans `.env` (`MASTER_DB_PORT`, `TENANT_DB_PORT`).

⚠️ Cette machine a **deux** installations PostgreSQL ; c'est la cause la plus fréquente des échecs de connexion sur ce poste.
