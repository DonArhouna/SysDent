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

```powershell
# Générer une nouvelle révision de migration automatique
alembic revision --autogenerate -m "description_du_changement"

# Appliquer toutes les migrations en attente
alembic upgrade head

# Revenir en arrière d'une révision
alembic downgrade -1
```

---

## 🌐 5. Liens & Endpoints Utiles

- **Documentation Swagger UI** : [http://localhost:8000/docs](http://localhost:8000/docs) (ou port 8001)
- **Documentation ReDoc** : [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Vérification de santé** : [http://localhost:8000/health](http://localhost:8000/health)
