# 🦷 SysDent Pro - Backend API (FastAPI)

API Backend robuste, sécurisée et haute performance pour la gestion de cabinets et cliniques dentaires, conçue selon les meilleures pratiques d'ingénierie logicielle et les exigences médicales.

---

## 🏗️ Architecture & Technologies Clés

- **Framework** : [FastAPI](https://fastapi.tiangolo.com/) (Asynchrone Python 3.11+)
- **ORM & Migrations** : [SQLAlchemy 2.0 (Async)](https://docs.sqlalchemy.org/) + `asyncpg` + [Alembic](https://alembic.sqlalchemy.org/)
- **Multi-Tenancy** : Isolation physique par base de données (**Master DB** + **Bases Cabinets dédiées**) avec routage dynamique asynchrone et cache LRU d'engines.
- **Sécurité & Auth** : Tokens JWT (Access court + Refresh long en rotation), support des Cookies HttpOnly `SameSite=Strict` (Protection XSS/CSRF), hashage **Argon2 / Bcrypt**.
- **Traçabilité & Audit Trail** : Table d'audit immuable pour toutes les consultations, modifications d'odontogramme et factures.
- **Logging** : Logging structuré JSON en production via [structlog](https://www.structlog.org/) avec Corrélation ID (`X-Request-ID`).
- **Validation** : Pydantic v2 ultra-rapide compilé en Rust.

---

## 📁 Arborescence du Projet

```
Backend/
├── .env.example              # Modèle des variables d'environnement
├── .env                      # Variables d'environnement locales
├── pyproject.toml            # Définition du projet Python
├── requirements.txt          # Dépendances pip de production
├── Dockerfile                # Image de conteneurisation
├── docker-compose.yml        # Orchestration PostgreSQL Master, Redis et Backend
├── alembic.ini               # Configuration des migrations
└── src/
    ├── core/                 # Config, DB Managers, Securité, Exceptions, Logging, Middlewares
    ├── common/               # Modèles de base, schémas de réponse, pagination
    ├── modules/
    │   ├── master/           # Gestion des structures / sociétés (DB Master)
    │   ├── auth/             # Authentification, sessions et dépendances RBAC
    │   ├── tenants/          # Modèles complets du schéma cabinet (Patients, Soins, Odontogramme, Facturation)
    │   └── audit/            # Service et consultation de l'audit trail
    ├── api/v1/               # Agrégation des routeurs d'API
    └── main.py               # Point d'entrée FastAPI
```

---

## 🚀 Démarrage Rapide

### 1. Avec Docker Compose (Recommandé)
```bash
docker compose up -d --build
```
L'API sera disponible sur `http://localhost:8000`.  
La documentation interactive Swagger sera accessible sur `http://localhost:8000/docs`.

### 2. En Local (Python 3.11+)
```bash
# Créer et activer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur de développement
uvicorn src.main:app --reload --port 8000
```

---

## 🛡️ Endpoints Principaux

| Méthode | Endpoint | Rôle |
|---|---|---|
| `GET` | `/health` | Vérification de l'état de santé du service |
| `POST` | `/api/v1/auth/login` | Connexion et délivrance des tokens JWT / Cookies |
| `POST` | `/api/v1/auth/refresh` | Renouvellement et rotation de token |
| `POST` | `/api/v1/auth/logout` | Déconnexion et révocation de session |
| `GET` | `/api/v1/auth/me` | Informations de profil et permissions du compte connecté |
| `GET` | `/api/v1/master/societes` | Liste des sociétés et cabinets provisionnés (Super Admin) |
| `POST` | `/api/v1/master/societes` | Création d'une nouvelle structure et provisionnement de sa DB |
| `GET` | `/api/v1/audit` | Consultation du journal d'audit légal |
