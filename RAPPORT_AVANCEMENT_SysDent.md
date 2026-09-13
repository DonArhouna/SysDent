# 🦷 SysDent Pro — Rapport d'Avancement, Reste à Faire & Plan d'Action Équipe (3 Développeurs)

**Date :** 13 Septembre 2026  
**Branche de référence :** `main` (commit `f725bad`)  
**Contexte :** Projet de gestion multi-cabinet médico-dentaire (Architecture Monolithe Modulaire Multi-Tenant)  
**Cible :** Équipe de développement (3 développeurs full-stack / backend)

---

## 📑 Sommaire

1. [Synthèse Exécutive du Projet](#1-synthèse-exécutive-du-projet)
2. [Audit Approfondi : Ce qui a été Réalisé](#2-audit-approfondi--ce-qui-a-été-réalisé)
3. [Dette Technique & Bloquants Immédiats (Phase 0)](#3-dette-technique--bloquants-immédiats-phase-0)
4. [Ce qui Reste à Développer](#4-ce-qui-reste-à-développer)
5. [Répartition Stratégique des Tâches pour les 3 Développeurs](#5-répartition-stratégique-des-tâches-pour-les-3-développeurs)
6. [Matrice des Dépendances & Règles de Collaboration](#6-matrice-des-dépendances--règles-de-collaboration)
7. [Feuille de Route & Recommandations Git](#7-feuille-de-route--recommandations-git)

---

## 1. Synthèse Exécutive du Projet

Le projet **SysDent Pro** présente à ce jour un contraste important :

* **Côté Conception & Architecture (Dossier `Analyse/`) : Avancement ~95%**  
  La conception est particulièrement mature, complète et de niveau professionnel. Le cahier des charges fonctionnel, le Modèle Conceptuel de Données (MCD), le Modèle Logique de Données (MLD), le dictionnaire des données, les diagrammes de cas d'utilisation, les diagrammes de séquence ainsi que les 18 règles de gestion clinique sont intégralement documentés dans la documentation MkDocs.

* **Côté Backend (Dossier `Backend/`) : Avancement ~30%**  
  Le socle d'infrastructure asynchrone (FastAPI 0.110+, SQLAlchemy 2.0 Async, Pydantic v2, gestion dynamique des pools multi-tenant PostgreSQL, sécurité JWT, logging structuré) est en place avec une vingtaine de modèles ORM. En revanche, **la quasi-totalité des routes métier (Patients, Consultations, Facturation, Agenda) reste à implémenter**, et l'authentification actuelle repose sur des identifiants simulés (mock).

* **Côté Frontend (Dossier `Frontend/`) : Avancement 0%**  
  Le répertoire est actuellement vide (seul `.gitkeep` est présent). Aucune application web (Next.js / React) n'est encore initialisée.

> **Bonne nouvelle :** La clarté des spécifications et du MLD permet un découpage fonctionnel immédiat et une parallélisation optimale entre 3 développeurs, à condition de traiter préalablement un court sprint de consolidation technique (**Phase 0 : 2 à 3 jours**).

---

## 2. Audit Approfondi : Ce qui a été Réalisé

### 2.1. Conception Métier & Spécifications (`Analyse/`)
- [x] **Cahier des charges complet** (`Analyse/cahier_extracted.txt`) : Parcours patient, règles d'exercice multi-sites et multi-praticiens au Sénégal, odontogramme FDI/Universal, facturation multi-moyens (espèces, Wave, Orange Money, chèque, assurance).
- [x] **Documentation d'architecture** (`Analyse/docs/architecture_proposition.md`) : Choix validé d'un **Monolithe Modulaire** avec isolation physique stricte des données par base de données (**Master DB** + **Bases Cabinets dédiées**).
- [x] **Modélisation relationnelle complète** (`Analyse/docs/modelisation_mcd.md` et `modelisation_mld.md`) : 10 domaines modélisés (Master, Utilisateurs/RBAC, Cabinets, Patients, Médical/Consultations, Odontogramme, Rendez-vous, Facturation, Stock, Audit).
- [x] **Règles de gestion & Sécurité** (`Analyse/docs/regles.md`) : 18 règles métier définies (intégrité odontogramme, verrouillage des actes facturés, traçabilité médico-légale).

### 2.2. Backend — Socle Technique & Core (`Backend/src/core/` & `common/`)
- [x] **Point d'entrée & Lifecycle** (`Backend/src/main.py`) : FastAPI avec gestionnaire de cycle de vie `lifespan` fermant proprement les pools PostgreSQL au shutdown.
- [x] **Configuration centralisée** (`Backend/src/core/config.py`) : Gestion des variables d'environnement via `pydantic-settings` (.env).
- [x] **Gestionnaire Multi-Tenant PostgreSQL** (`Backend/src/core/database.py`) :
  - `master_engine` connecté à la base centrale `sysdent_master`.
  - `TenantDatabaseManager` assurant la création dynamique des `AsyncEngine` par cabinet avec pool de connexions et politique d'éviction LRU (jusqu'à 50 cabinets en cache).
- [x] **Sécurité & Cryptographie** (`Backend/src/core/security.py`) :
  - Hachage de mots de passe (Argon2 / Bcrypt via `passlib`).
  - Génération et validation de jetons JWT asynchrones (Access Token 15 min + Refresh Token 7 jours).
- [x] **Gestion unifiée des erreurs** (`Backend/src/core/exceptions.py` & `exception_handlers.py`) : Conformité au standard RFC 7807 (Problem Details for HTTP APIs).
- [x] **Observabilité & Middlewares** (`Backend/src/core/logging.py` & `middleware.py`) :
  - Logging structuré JSON via `structlog`.
  - Middleware de corrélation de requête (`X-Request-ID`).
- [x] **Base ORM & Schémas communs** (`Backend/src/common/`) :
  - `BaseModel`, `UUIDMixin` (UUID v4), `TimestampMixin` (`created_at`, `updated_at`).
  - Formats standardisés d'API : `APIResponse[T]`, `PaginatedResponse[T]`, `PaginationParams`.

### 2.3. Backend — Modèles de Données SQLAlchemy (`Backend/src/modules/`)
- [x] **Base Master (`Backend/src/modules/master/models.py`)** :
  - `Societe` (structures juridiques clientes, NINEA, coordonnées).
  - `TenantDB` (métadonnées de connexion et routage de la base de données dédiée).
  - `SuperAdmin` (comptes d'administration de la plateforme SysDent).
  - `AuditLogGlobal` (journalisation des opérations sur le Master).
- [x] **Base Tenant (`Backend/src/modules/tenants/models.py`)** : 21 tables déjà modélisées :
  - *RBAC & Accès* : `Role`, `Permission`, `PermissionRole`, `Utilisateur`, `SessionUser`.
  - *Organisation* : `Cabinet`, `Salle`, `Fauteuil`, `Praticien`.
  - *Dossier Patient* : `Patient`, `DossierMedical`, `EtatGeneral`, `AntecedentMedical`.
  - *Odontogramme* : `Odontogramme`, `Dent`.
  - *Consultations & Soins* : `Consultation`, `ActeNomenclature`, `ActeRealise`.
  - *Facturation* : `Facture`, `LigneFacture`, `Paiement`.
  - *Traçabilité locale* : `AuditLogTenant`.

### 2.4. Backend — Routes & Endpoints Existants
- [x] `GET /health` : Monitoring de santé du serveur.
- [x] `POST /api/v1/master/societes` : Déclaration de société et enregistrement des paramètres DB.
- [x] `GET /api/v1/master/societes` : Liste des sociétés enregistrées.
- [x] `GET /api/v1/master/societes/{id}` : Détails d'une société.
- [x] `GET /api/v1/audit` : Consultation filtrée et paginée de l'audit trail tenant (`AUDIT_READ`).
- [x] `POST /api/v1/auth/login`, `/refresh`, `/logout`, `GET /me` : Endpoints d'authentification (définis mais actuellement mockés).

### 2.5. Infrastructure & DevOps
- [x] `docker-compose.yml` opérationnel (PostgreSQL 16 Master, Redis 7, Backend FastAPI avec reload automatique).
- [x] Script d'initialisation `init_db.py` pour appliquer les migrations Alembic Master et créer le Super-Admin par défaut (`admin@sysdent.pro` / `Admin123!`).

### 2.6. Sprint 0 — Socle sécurisé (ajouté le 13/09/2026, voir §3)
- [x] **Authentification réelle** (`Backend/src/modules/auth/services.py`, nouveau) : `AuthService.authenticate()` résout le cabinet par email et vérifie le mot de passe hashé.
- [x] **Chiffrement des secrets** (`Backend/src/core/security.py`) : `encrypt_secret()` / `decrypt_secret()` (Fernet), clé `TENANT_DB_ENCRYPTION_KEY`.
- [x] **Migrations Alembic** : `Backend/alembic/` (Master) et `Backend/alembic_tenant/` (Tenant), chacun avec une révision baseline testée. Pilotage programmatique via `Backend/src/core/migrations.py`.
- [x] **Provisioning réel** (`Backend/src/modules/master/services.py`) : `CREATE DATABASE` physique + migrations Alembic tenant + création du compte admin cabinet.
- [x] **Séparation des registres SQLAlchemy** (`Backend/src/common/base_model.py`) : `Base` (Master) et `TenantBase` (Tenant) désormais distincts.

---

## 3. Dette Technique & Bloquants Immédiats (Phase 0)

> **✅ Statut : RÉSOLUE le 13/09/2026.** Les 5 points critiques ci-dessous ont tous été corrigés et **validés de bout en bout contre une vraie instance PostgreSQL** (provisioning réel + login réel + rollback testés puis nettoyés). Le détail reste ici à titre de traçabilité ; ce n'est plus une liste de travail.

| Bloquant | Fichier concerné | Description & Risque | Statut & Solution appliquée |
|---|---|---|---|
| ✅ **Bug d'import RBAC** | `src/modules/auth/dependencies.py` | `get_current_user` appelait `src.modules.tenants.models.Role` sans avoir importé le module racine `src` → `NameError` garanti dès qu'un utilisateur authentifié faisait une requête avec permissions. | **Résolu.** `Role` et `PermissionRole` sont désormais importés directement depuis `src.modules.tenants.models` et utilisés dans le `selectinload`. |
| ✅ **Login Mocké (Sécurité)** | `src/modules/auth/router.py`, nouveau `src/modules/auth/services.py` | `POST /auth/login` retournait un token avec un UUID fixe, sans vérifier email ni mot de passe. | **Résolu.** Nouveau `AuthService.authenticate()` : résout le cabinet rattaché à l'email en interrogeant les bases tenant actives, vérifie le mot de passe (Argon2 via `verify_password`), renvoie un JWT avec le vrai `user_id`/`tenant_id`/`role`/permissions. Testé avec bon et mauvais mot de passe. |
| ✅ **Provisioning DB Incomplet** | `src/modules/master/services.py` | `create_societe_and_provision_tenant` n'exécutait aucun `CREATE DATABASE` réel ni schéma. | **Résolu.** La création d'une société exécute désormais un vrai `CREATE DATABASE`, applique les migrations Alembic du schéma tenant (voir ligne suivante), puis crée le rôle `ADMIN_CABINET` et le premier compte admin cabinet à partir de `admin_email`/`admin_password`. En cas d'échec, le statut reste `PROVISIONING` (reprise manuelle possible) au lieu de laisser une société fantôme marquée `ACTIVE`. |
| ✅ **Migrations Alembic non initialisées** | `Backend/alembic/`, `Backend/alembic_tenant/` | Aucun `env.py` ni révision baseline. | **Résolu.** Deux environnements Alembic distincts et volontairement séparés : `Backend/alembic/` (schéma Master, `Base.metadata`) et `Backend/alembic_tenant/` (schéma Cabinet, `TenantBase.metadata`, appliqué à chaque base tenant via `-x tenant_db_url=...` ou `config.attributes` en usage programmatique). Révisions baseline générées par autogenerate et validées par application sur bases vierges. La base Master réelle a été `stamp`-ée à `head` (déjà à jour via l'ancien `create_all`, pas besoin de rejouer). `init_db.py` appelle maintenant `alembic upgrade head` au lieu de `create_all`. |
| ✅ **Chiffrement du mot de passe DB** | `src/core/security.py`, nouvelle clé `TENANT_DB_ENCRYPTION_KEY` | `TenantDB.db_password` stocké en clair. | **Résolu.** `encrypt_secret()`/`decrypt_secret()` (Fernet) ajoutés dans `core/security.py`. Le mot de passe est chiffré à l'écriture (provisioning) et déchiffré à la volée à la connexion (`auth/dependencies.py`, `auth/services.py`). |

**Bug additionnel découvert et corrigé en cours de route (hors liste initiale) :** `master/models.py` et `tenants/models.py` partageaient le même registre SQLAlchemy (`Base`). Dès que les deux étaient importés dans le même process — ce qui arrive dans l'app réelle —, un `metadata.create_all` créait *toutes* les tables (Master + Tenant) dans n'importe quelle base ciblée. Séparé en `Base` (Master, dans `common/base_model.py`) et `TenantBase` (Tenant) ; chaque environnement Alembic pointe sur le bon registre.

**Comment évoluer le schéma désormais (convention obligatoire pour les 3 pôles ci-dessous) :**
- Schéma Master (`src/modules/master/models.py`) : modifier le modèle puis `python -m alembic revision --autogenerate -m "..."` (depuis `Backend/`) puis `alembic upgrade head`.
- Schéma Tenant (`src/modules/tenants/models.py`, tous les modules métier RDV/Ordonnances/Stock/etc.) : modifier le modèle puis `python -m alembic -c alembic_tenant.ini -x tenant_db_url=postgresql+psycopg2://postgres:postgres_password@localhost:5432/<une_base_tenant_existante> revision --autogenerate -m "..."`, relire la migration générée, puis l'appliquer à chaque base tenant concernée avec `alembic -c alembic_tenant.ini -x tenant_db_url=... upgrade head`. Pour une nouvelle société, cette étape est automatique (`MasterTenantService` l'exécute au provisioning).
- **Plus aucun `Base.metadata.create_all` / `TenantBase.metadata.create_all` en dehors de la génération de baseline.**

---

## 4. Ce qui Reste à Développer

### 4.1. Modèles de Données Restants à ajouter dans `tenants/models.py`
Les tables suivantes sont spécifiées dans le MLD mais pas encore transcrites en code :
1. **Module Rendez-vous :** `RendezVous`, `DisponibilitePraticien`, `CreneauFauteuil`, `ListeAttente`.
2. **Module Ordonnances & Médicaments :** `Prescription`, `LignePrescription`, `MedicamentReferentiel`.
3. **Module Assurances & Tiers-Payant :** `TypePriseEnCharge`, `PriseEnChargePatient`.
4. **Module Devis & Échéances :** `Devis`, `LigneDevis`, `PlanEchelonnement`, `EcheanceFacture`.
5. **Module Stock & Fournisseurs :** `Fournisseur`, `ArticleStock`, `MouvementStock`, `CommandeFournisseur`, `LigneCommandeFournisseur`, `CycleSterilisation`.
6. **Module Documents & Imagerie :** `DocumentPatient`, `ClichéRadio` (intégration S3/MinIO).
7. **Odontogramme (Extensions indispensables du CDC) :**
   - `FaceDent` (pour le suivi des 5 faces : Mésial, Distal, Occlusal, Vestibulaire, Lingual).
   - `EtatDentHistorique` (traçabilité horodatée de l'évolution de chaque dent).
   - `ChartingParodontal` (sondage en 6 points, indice de plaque, saignement).

### 4.2. Logique Métier & Routers API Backend à Réaliser
Pour chaque domaine, il faut créer les fichiers `schemas.py`, `services.py` et `router.py` :
- **API Patients (`/api/v1/patients`) :** CRUD patient, recherche multicritères, antécédents, alertes médicales automatiques (allergies, contre-indications).
- **API Consultations & Soins (`/api/v1/consultations`) :** Workflow consultation, diagnostic, sélection des actes de nomenclature, saisie des actes réalisés.
- **API Odontogramme (`/api/v1/odontogramme`) :** Récupération de l'état de la denture (32 dents), mise à jour par face, historique d'interventions.
- **API Agenda / Rendez-vous (`/api/v1/rendez-vous`) :** Planning multi-praticiens/fauteuils, vérification anti-conflit de créneaux, gestion des absences.
- **API Facturation & Caisse (`/api/v1/factures`, `/paiements`, `/devis`) :** Émission de factures depuis la consultation, ventilation des paiements (espèces, mobile money, assurance), reçus de caisse numérotés, devis.
- **API Stock (`/api/v1/stock`) :** Gestion des stocks par cabinet, alertes seuil minimum, entrées/sorties de matériel, suivi de stérilisation.
- **Workers Asynchrones (`arq`) :** Envoi des SMS de rappel 24h avant RDV, notifications d'impayés, génération PDF asynchrone (factures, ordonnances).

### 4.3. Frontend (Chantier Intégral à Démarrer)
- **Socle UI :** Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui + Lucide Icons.
- **State Management & Data Fetching :** Zustand (session JWT et tenant courant) + TanStack Query (cache et synchronisation API).
- **Écrans & Modules Web :**
  1. *Portail Authentification* (Login multi-tenant, récupération de session).
  2. *Console Super-Admin* (Gestion des sociétés clientes, provisionnement de cabinets).
  3. *Gestion des Dossiers Patients* (Recherche instantanée, fiche patient, dossier médical).
  4. *Composant Odontogramme SVG* (Vue anatomique 32 dents interactive, clic par face, codes couleur dynamiques).
  5. *Agenda & Planning Médical* (Vue journalière/hebdomadaire par praticien et fauteuil via FullCalendar).
  6. *Module Facturation & Caisse* (Interface de caisse rapide, devis, reçu imprimable).
  7. *Module Stock* (Tableau de bord des produits, saisie des mouvements).

---

## 5. Répartition Stratégique des Tâches pour les 3 Développeurs

Pour garantir une productivité maximale, l'organisation s'effectue en **deux étapes** :
1. **Étape A (Sprint Commun - 2 jours) :** Sécurisation du socle technique (chacun prend 1 chantier bloquant).
2. **Étape B (Sprints Spécialisés) :** Répartition en 3 pôles étanches (un développeur par pôle) avec des interfaces clairement contractées.

---

### 🟢 ÉTAPE A : Sprint Socle & Déblocage (J1 - J2) — ✅ TERMINÉE (13/09/2026)

Les 3 chantiers ont été traités et validés (voir §3 pour le détail technique complet) :

* **Auth & RBAC réel** — Bug d'import corrigé, `POST /auth/login` vérifie réellement email + mot de passe via le nouveau `AuthService` (`src/modules/auth/services.py`). *(Reste hors-scope pour Étape B, à faire par le pôle qui touchera l'auth en profondeur : persistance du refresh token dans `SessionUser` avec révocation, et extension de `require_permissions` au-delà de `/audit`.)*
* **Migrations Alembic** — Deux environnements créés : `Backend/alembic/` (Master) et `Backend/alembic_tenant/` (Tenant), avec révisions baseline testées sur bases vierges. Commandes dans `Backend/COMMANDS.md` à compléter par la 1ère personne qui ajoute une table.
* **Provisioning réel** — `MasterTenantService` crée la base physique, applique les migrations Alembic tenant, crée le compte admin cabinet, et chiffre `TenantDB.db_password` (Fernet).

**➡️ L'équipe peut démarrer directement l'Étape B ci-dessous — plus aucun bloquant technique commun.**

---

### 🔵 ÉTAPE B : Répartition Fonctionnelle des 3 Pôles

```mermaid
graph TD
    subgraph "DEV 1 — PÔLE MÉDICAL & CLINIQUE"
        D1A["API Patients & Dossier Médical"]
        D1B["API Consultations & Actes"]
        D1C["API & Modèle Odontogramme Complet"]
        D1D["Frontend : Fiche Patient & Odontogramme SVG"]
    end

    subgraph "DEV 2 — PÔLE ORGANISATION, AGENDA & FINANCE"
        D2A["API Cabinets, Salles & Fauteuils"]
        D2B["API & Modèle Rendez-vous / Planning"]
        D2C["API Facturation, Caisse & Devis"]
        D2D["Frontend : Agenda FullCalendar & Module Caisse"]
    end

    subgraph "DEV 3 — PÔLE LOGISTIQUE, WORKERS & PLATEFORME"
        D3A["Initialisation Socle Frontend Next.js + UI"]
        D3B["API & Modèle Stocks & Matériel"]
        D3C["Console Super-Admin Master"]
        D3D["Workers Asynchrones (Rappels RDV, PDF, Email/SMS)"]
    end

    D3A -.->|"Fournit le template UI à"| D1D
    D3A -.->|"Fournit le template UI à"| D2D
    D1A -.->|"Fournit patient_id à"| D2B
    D1B -.->|"Fournit consultation_id & actes à"| D2C
    D2B -.->|"Fournit les RDV à notifier à"| D3D
```

---

### 👨‍💻 Développeur 1 : Pôle Médical, Soins & Odontogramme (Cœur Métier Clinique)

> **Rôle :** Responsable du dossier médical, de la consultation et du composant le plus stratégique de l'application : l'Odontogramme.

#### Missions Backend :
1. **Module Patients (`/api/v1/patients`) :**
   - Schémas Pydantic (`PatientCreate`, `PatientUpdate`, `PatientResponse`, `FiltrePatients`).
   - Service métier : Génération automatique du numéro de dossier unique, recherche multicritères, gestion des doublons, archivage.
   - Gestion de l'état général et des antécédents médicaux (détection automatique des alertes : allergies, diabète, grossesse).
2. **Module Consultations (`/api/v1/consultations`) :**
   - Workflow d'une consultation (motif, anamnèse, examen clinique, diagnostic).
   - Nomenclature des actes dentaires et saisie des `actes_realises` liés à la consultation.
3. **Module Odontogramme Avancé (`/api/v1/odontogramme`) :**
   - Compléter `models.py` avec `FaceDent`, `EtatDentHistorique`, `ChartingParodontal`.
   - Service d'historisation de chaque intervention par dent (avant/après traitement).
   - API de mise à jour rapide de l'état d'une ou plusieurs dents.

#### Missions Frontend :
1. **Gestion des Patients :** Écran de recherche/liste avec pagination, formulaire de création de dossier, fiche patient complète avec alertes médicales bien visibles (badges rouges/oranges).
2. **Composant Odontogramme SVG Interactif :**
   - Dessin vectoriel des 32 dents permanentes (système FDI).
   - Gestion du clic sur une dent ou sur l'une de ses 5 faces.
   - Application dynamique des codes couleur (vert = sain, rouge = carie, bleu = soigné, gris = absent, or = couronne).
   - Panneau latéral affichant l'historique des soins de la dent sélectionnée.

---

### 👨‍💻 Développeur 2 : Pôle Organisation, Agenda & Finance (Planning & Caisse)

> **Rôle :** Responsable du parcours administratif du patient : gestion des rendez-vous, planification des praticiens et fauteuils, facturation et encaissements.

#### Missions Backend :
1. **Module Cabinets & Ressources (`/api/v1/cabinets`) :**
   - Gestion des sites/cabinets, des salles et des fauteuils associés.
   - Profils praticiens, spécialités, numéros d'ordre et plages de disponibilité.
2. **Module Rendez-vous (`/api/v1/rendez-vous`) :**
   - Modélisation de `RendezVous` et `CreneauFauteuil`.
   - Moteur de détection des conflits (double réservation d'un praticien ou d'un fauteuil).
   - Statuts de RDV : Planifié, Confirmé, En salle d'attente, En consultation, Terminé, Annulé, Absent.
3. **Module Facturation & Caisse (`/api/v1/factures`, `/paiements`) :**
   - Génération automatique de facture à partir des `actes_realises` d'une consultation.
   - Prise en charge des paiements multiples/partiels (Espèces, Wave, Orange Money, Carte, Virement, Chèque).
   - Gestion des acomptes, des soldes restants dus et émission de reçus numérotés uniques.
   - Modélisation et gestion des **Devis** et plans d'échelonnement.

#### Missions Frontend :
1. **Module Agenda / Rendez-vous :**
   - Calendrier dynamique multi-vues (jour/semaine/mois) avec filtres par praticien et par fauteuil (via `FullCalendar`).
   - Modale intuitive de prise de rendez-vous avec recherche rapide du patient.
2. **Module Facturation & Caisse :**
   - Écran de facturation lié à la consultation terminée.
   - Interface d'encaissement avec calcul automatique du rendu de monnaie et ventilation par moyen de paiement.
   - Vue de gestion des impayés avec statut visuel.
   - Aperçu et impression directe du reçu de paiement / facture.

---

### 👨‍💻 Développeur 3 : Pôle Logistique, Socle Frontend & Plateforme (Stock, Asynchrone, Infra & Admin)

> **Rôle :** Responsable de l'outillage transversal, du socle technique Frontend, de la console Super-Admin, du stock et des traitements en arrière-plan.

#### Missions Backend :
1. **Module Stock & Fournisseurs (`/api/v1/stock`) :**
   - Modèles `ArticleStock`, `MouvementStock`, `Fournisseur`, `CommandeFournisseur`.
   - Suivi des quantités par cabinet, gestion des alertes automatiques de stock minimum.
   - Traçabilité des mouvements (entrées, consommations lors des actes, pertes/péremptions).
2. **Console Super-Admin (`/api/v1/master/tenants`) :**
   - Tableau de bord des cabinets hébergés, activation/suspension d'un tenant.
   - Monitoring de l'utilisation des bases de données et statistiques globales.
3. **Moteur de Tâches Asynchrones & Notifications (`Backend/src/workers/`) :**
   - Configuration du worker `arq` avec Redis.
   - Tâche planifiée (cron quotidien) : détection des RDV du lendemain et envoi des SMS/Emails de rappel.
   - Tâche asynchrone de génération de PDF (factures, reçus, ordonnances) avec WeasyPrint ou ReportLab.

#### Missions Frontend :
1. **Mise en place du Socle Frontend (`Frontend/`) :**
   - Initialisation du projet Next.js 14 avec TypeScript, Tailwind CSS, shadcn/ui et configuration Axios/TanStack Query.
   - Layout global réutilisable (Sidebar, Header, sélecteur de cabinet actif, déconnexion).
   - Système de routing protégé par tokens JWT stockés en HttpOnly cookie et state Zustand.
   - *Livrable clé :* Fournir un squelette UI propre et fonctionnel aux Développeurs 1 et 2 dès la fin de semaine 1.
2. **Interfaces du Pôle 3 :**
   - Console Super-Admin (gestion des sociétés et provisioning).
   - Écran de gestion du stock et inventaire avec badges d'alerte pour les ruptures.
   - Dashboard d'accueil avec KPIs généraux (CA du jour, consultations en cours, alertes stocks).

---

## 6. Matrice des Dépendances & Règles de Collaboration

### 6.1. Tableau des Dépendances entre Tâches

| Tâche | Assignée à | Dépendance directe (Bloquée par) | Débloque ensuite |
|---|---|---|---|
| ~~Socle Auth & RBAC réel~~ | Sprint 0 | — | ✅ Fait — toutes les routes sécurisées peuvent maintenant s'appuyer dessus |
| ~~Migrations Alembic~~ | Sprint 0 | — | ✅ Fait — toute nouvelle table passe par une révision Alembic (voir §3) |
| ~~Provisioning Tenant réel~~ | Sprint 0 | ~~Migrations Alembic~~ | ✅ Fait — création autonome de nouveaux cabinets de test possible dès maintenant |
| **Setup Template Frontend** | Dev 3 | Aucune | Intégration des écrans par Dev 1 et Dev 2 |
| **API Patients** | Dev 1 | Aucune (Socle Auth résolu) | Prise de RDV (Dev 2), Facturation (Dev 2) |
| **API Consultations** | Dev 1 | API Patients (Dev 1) | Facturation automatique (Dev 2) |
| **Odontogramme SVG** | Dev 1 | Setup Frontend (Dev 3), API Odontogramme (Dev 1) | Expérience clinique praticien |
| **API Agenda / RDV** | Dev 2 | ID Patient (Dev 1) | Rappels de RDV automatiques (Dev 3) |
| **API Facturation** | Dev 2 | Consultation / Actes réalisés (Dev 1) | Rapports financiers & encaissements |
| **Worker Rappels RDV** | Dev 3 | API Rendez-vous (Dev 2) | Envoi effectif des notifications SMS/Email |

### 6.2. Règles d'Or pour Travailler à 3 sans Blocage (Découplage)

1. **Priorité aux Contrats d'Interface (API First) :**  
   Avant d'écrire la logique interne, le développeur valide les schémas Pydantic (`schemas.py`) et crée la signature de la route. Dès que Swagger affiche la structure JSON attendue, les autres développeurs peuvent coder contre ce contrat.
2. **Utilisation de Fixtures / Seeds de Test :**  
   Le Développeur 2 n'attend pas que le Développeur 1 ait fini son écran de création de patient : il utilise un script de seed (`seed_data.py`) qui insère 5 patients et 3 consultations fictifs pour tester sa facturation et son agenda immédiatement.
3. **Isolation par Domaine de Fichiers :**  
   Chaque développeur travaille dans son propre sous-dossier dans `src/modules/` (ex: `src/modules/patients/`, `src/modules/billing/`, `src/modules/stock/`). Cela élimine 95% des risques de conflits Git lors des merges.
4. **Schémas de Réponse Partagés :**  
   Obligation stricte d'utiliser les classes génériques de `src/common/schemas.py` :
   - Requête simple : `APIResponse[MonSchema]`
   - Liste paginée : `PaginatedResponse[MonSchema]` générée via la fonction `paginate(...)`.
5. **Traçabilité Médicale Obligatoire :**  
   Toute action de création, mise à jour ou suppression sensible (dossier patient, dent, facture) doit appeler `await AuditService.log_action(db=db, ...)` conformément aux règles médico-légales de SysDent.

---

## 7. Feuille de Route & Recommandations Git

### 7.1. Planning par Sprints (Estimations)

```
Semaine 1 :
├── J1-J2 : SPRINT 0 (Auth réelle, Alembic, Provisioning DB) — ✅ TERMINÉ le 13/09/2026, cf. §3
└── J3-J5 : SPRINT 1 (CRUD Patients, Modèle Agenda, Modèle Stock, Wireframes UI, Init Next.js)

Semaine 2 :
├── J6-J8 : SPRINT 2 (Consultations, Planning FullCalendar, Mouvements Stock, Auth UI)
└── J9-J10: SPRINT 3 (Odontogramme SVG v1, Facturation de base, Console Super-Admin)

Semaine 3 :
├── J11-J13: SPRINT 4 (Charting parodontal, Devis/Acomptes, Workers SMS/Email)
└── J14-J15: SPRINT 5 (Intégration croisée, Recette clinique, Tests de charge & Docker final)
```

### 7.2. Stratégie de Branches Git

* Branche `main` : Code de production uniquement, protégé (merge uniquement via Pull Request validée).
* Branche `develop` : Branche d'intégration commune.
* Branches de fonctionnalités (nommage standardisé) :
  - Dev 1 : `feature/clinical-patients`, `feature/clinical-odontogramme`, `feature/clinical-consultations`
  - Dev 2 : `feature/agenda-planning`, `feature/billing-invoices`, `feature/billing-payments`
  - Dev 3 : `feature/core-frontend-init`, `feature/stock-management`, `feature/workers-notifications`
* **Règle de PR :** Chaque Pull Request doit inclure au moins un test d'intégration dans `Backend/tests/` et être relue par au moins un des deux autres développeurs avant fusion.

---

*Rapport établi le 13/09/2026 pour l'équipe technique SysDent Pro.*
