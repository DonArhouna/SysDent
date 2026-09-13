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

---

## 🌐 5. Liens & Endpoints Utiles

- **Documentation Swagger UI** : [http://localhost:8000/docs](http://localhost:8000/docs) (ou port 8001)
- **Documentation ReDoc** : [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Vérification de santé** : [http://localhost:8000/health](http://localhost:8000/health)
