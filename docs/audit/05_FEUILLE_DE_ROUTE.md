# 05 — Feuille de route

> **Date** : 4 octobre 2026 · **Synthèse actionnable** des documents 01 à 04.
>
> **Principe d'ordonnancement :** on ne construit rien au-dessus d'une fondation
> qui tombe. Chaque sprint a un **préalable bloquant** ; si le préalable n'est
> pas fait, le sprint est reports.

> **Mise à jour 5 octobre 2026 :** la **console PLATEFORME** annoncée plus bas
> comme Sprint 2 — Onboarding est **construite et vérifiée** (44 chemins,
> 55 opérations).
> Voir [06 — Console PLATEFORME](06_CONSOLE_PLATEFORME.md) pour l'état réel,
> les décisions structurantes (liste blanche de l'accès support, journal
> immuable) et les résultats de vérification. Restent ouverts : l'interface
> frontend, et deux échecs de tests clients **préexistants** (fuite de pool
> `asyncpg`) documentés au § 9.2 du document 06.

---

## 1. L'énoncé en une phrase

Le système est **architecturalement bon et fonctionnellement incomplet**.

La partie difficile — l'isolation multi-tenant, le RBAC, le moteur de
rendez-vous avec sa contrainte d'exclusion PostgreSQL, le module de facturation
avec son recalcul du reste à payer — est **écrite, testée et cohérente**. Ce qui
manque, ce sont **trois trous**, pas trois couches d'architecture :

1. **Deux écrans morts** (factures, rôles) — des bugs d'une ligne.
2. **Aucun module Utilisateurs** — 45 permissions et 6 rôles sans personne à
   qui les attribuer.
3. **Aucune interface de provisioning ni d'onboarding** — le produit ne peut pas
   être vendu en l'état.

Tout le reste (imagerie, stérilisation, abonnements, multi-sites) est de la
**valeur ajoutée** à construire après.

---

## 1 bis. Suivi d'avancement au 6 octobre 2026

Ce qui suit décrit ce qui a été **réellement exécuté et vérifié**, pas ce qui est
prévu. Les chantiers non livrés sont explicitement signalés comme tels.

| Chantier | Attendu par la mission | État | Preuve |
|---|---|---|---|
| État Général patient | modification qui échoue | 🟢 **livré** | 4 causes racines, migration réversible, 26 lignes préservées |
| Factures | écran qui renvoie 500 | 🟢 **livré** | `GET /factures` → 200, 10 factures |
| Produits / Stock | module absent | 🟢 **livré** | 9 tables, 9 routes, parcours complet testé, alertes de seuil |
| Commandes & réceptions | absents | 🟢 **livré** | 26 contrôles, dont stock non crédité à l'émission et réception sans double validation |
| Caisse / clôture | absent | 🟢 **livré** | 26 contrôles + 11 tests ; écart d'espèces, totaux figés par mode |
| Matrice des rôles | 6 profils à vérifier | 🟢 **vérifiée** | 6 contrôles par exécution réelle — voir `docs/corrections/MATRICE_ROLES.md` |
| Consultation / Praticien | découplage demandé | 🟢 **livré** | 12 contrôles — un compte sans profil d'Ordre consulte et consigne |
| Utilisateurs | endpoints absents | 🔴 **non livré** | `POST /rbac/users` → 404. Reste le manque bloquant n° 1 |
| File d'attente | cœur du rôle secrétaire | 🔴 **non livré** | aucun modèle, aucune route, aucun écran |
| Notions plateforme dans l'UI | à retirer du client | 🔴 **non livré** | Chantier 4 |
| Menu Praticiens | 52 occurrences dans une page | 🔴 **non livré** | Chantier 5 |
| Création d'un praticien | impossible | 🟡 **partiel** | `GET` existe ; `POST` toujours manquant |
| Rendez-vous | agenda | 🟡 **partiel** | API présente, file d'attente absente |

### Ce que le Chantier 3 a réellement changé

`consultations.praticien_id` était `NOT NULL` vers `praticiens.id`, et trois
modules refusaient de travailler sans profil d'Ordre : consultations,
odontogramme, ordonnances.

Le point décisif : **`Praticien.numero_ordre` est déjà nullable**. La garde était
donc **plus stricte que le modèle de données qu'elle prétendait protéger**.

Désormais l'auteur d'un acte est le **compte authentifié** — il vient du JWT, il
est horodaté, il ne peut pas être inventé — et le profil `Praticien` devient une
attribution réglementaire facultative.

Une exception est **volontairement conservée** : l'ordonnance exige encore un
profil, parce qu'un support papier qui sort du cabinet engage la responsabilité
de son auteur. L'asymétrie est assumée et documentée dans
`docs/corrections/03_CONSULTATION_PRATICIEN.md` §5, avec la cible proposée —
exiger aussi un numéro d'Ordre renseigné.

### Deux constats qui changent l'ordre de priorité

1. **Les 45 permissions et les 6 rôles ne servent à personne.** On peut vérifier
   la matrice rôle par rôle par exécution réelle, mais **aucun utilisateur ne peut
   être créé depuis l'interface**. Tant que le module Utilisateurs n'existe pas,
   le RBAC est une théorie que personne ne peut appliquer.
2. **Un défaut de rapport comptable a été trouvé et corrigé.** L'assurance était
   dans le catalogue des modes de paiement mais pas dans les totaux de clôture :
   le rapport de journée annonçait un chiffre inférieur au réel, sans aucun
   signal. C'est le genre de défaut qu'un cabinet découvre en comptant.

### Ce qui bloque encore la recette

- **`_psycopg` bloqué par la politique Windows** : aucun nouveau tenant ne peut
  être provisionné. Un cabinet neuf n'a donc jamais été observé de bout en bout.
- **Conteneur PostgreSQL arrêté silencieusement pendant la nuit du 5 au 6 octobre**,
  ce qui a valu 295 erreurs sur une suite de tests. Les données n'étaient pas
  perdues, mais il faut vérifier la connectivité avant de lancer une suite de
  25 minutes.

---

## 2. Sprint 0 — Débloquer (1 jour)

> **Ce sprint n'ajoute aucune fonctionnalité.** Il répare ce qui est cassé et
> réconcilie le plan de travail. Sans lui, tout ce qui suit est construit sur
> du sable.

| # | Action | Emplacement | Pourquoi maintenant |
|---|---|---|---|
| **S0-1** | `selectinload(Facture.paiements).selectinload(Paiement.echeance)` | `facturation/services.py:457` | **La page Factures renvoie 500 dès qu'une facture est réglée** (8 sur 10 en démo). Une ligne. |
| **S0-2** | `.selectinload(Role.utilisateurs)` | `rbac/services.py:182` | **La page Roles renvoie 500.** Une ligne. |
| **S0-3** | Extraire `ouvrir_session_tenant()` ; lire `tenant_id` dans le refresh token | `auth/dependencies.py`, `auth/router.py:101-135` | **La session meurt au bout de 15 min.** Bloquant pour toute recette longue. |
| **S0-4** | Semer `ActeNomenclature` au provisionnement | `master/services.py:106` (à côté de `semer_formulaire`) | **Un cabinet neuf ne peut rien facturer.** Une lecture, une ligne. |
| **S0-5** | `limit` borné (`Query(le=100)`) sur `/rendez-vous`, `/ordonnances`, `/nomenclature/actes` | 3 routeurs | Évite qu'un `limit=99999` tue le serveur. `/nomenclature/actes?limit=201` renvoie 500 au lieu de 422. |
| **S0-6** | `POST /praticiens` : service + UI | `praticiens-api.ts` + page | **Impossible d'ajouter un dentiste.** C'est la première action d'un cabinet. |
| **S0-7** | `queryClient.clear()` à la déconnexion et au changement d'utilisateur | App React Query | **Seule fuite inter-tenant plausible du système.** 3 lignes. |
| **S0-8** | Déverrouiller `_psycopg` (politique Windows) | Environnement | **Aucun nouveau cabinet ne peut être provisionné** sans `_psycopg`. Bloque la recette. |

**Critère de sortie** : `GET /factures` et `GET /rbac/roles` renvoient 200 sur une
base de démonstration avec paiements ; une session survit 30 minutes ; un
`POST /master/societes` aboutit et produit un cabinet **capable de facturer**.

**Prérequis :** validation explicite du propriétaire pour toucher au backend
auth (S0-3) et au provisionnement (S0-4). Ce sont des modifications backend —
elles n'ont **pas** été faites.

---

## 3. Sprint 1 — La décision n°1 devient réelle (2 semaines)

> **Objectif :** un cabinet peut recruter, attribuer des droits, et cloisonner ses
> sites. C'est la décision métier validée n°4 et le pilier de l'architecture.

**Dépendances :** S0. **Bloque :** Sprint 3 (backoffice), Sprint 4 (multi-sites).

### 3.1 Backend — module Utilisateurs (le plus gros manque)

| Endpoint | Rôle |
|---|---|
| `GET /utilisateurs` | lister (filtres : rôle, actif, site) — `PATIENTS:READ` non, `ADMIN:READ` oui |
| `POST /utilisateurs` | créer + activer |
| `PATCH /utilisateurs/{id}` | profil, rôle, actif |
| `POST /utilisateurs/{id}/mot-de-passe` | réinitialisation (admin) |
| `DELETE /utilisateurs/{id}` | désactiver (suppression logique, jamais physique) |
| `GET /utilisateurs/{id}/sessions` · `DELETE /sessions/{id}` | sessions actives (la table **existe déjà**) |

Le contrat frontend **existe déjà** (`utilisateurs-api.ts`, `types.ts`,
`utilisateurs-page.tsx`) : il est écrit contre un contrat *proposé*, à valider
avant de coder. En particulier : `DELETE` devrait **désactiver**, pas effacer —
une facture doit garder son auteur.

**Garde-fous obligatoires** (doc 03, § 4.5) :

- ❌ Impossible de supprimer ou désactiver le **dernier** `ADMIN_CABINET` actif
- ❌ Impossible de s'attribuer un rôle supérieur au sien
- ❌ Un rôle système ne peut pas être supprimé
- ✅ Toute création / modification / désactivation est **journalisée** dans
  `audit_logs` avec l'auteur, la cible et le détail

### 3.2 Backend — RBAC à deux dimensions

- `utilisateur_cabinet` (n-u1-tiers) : un compte, plusieurs cabinets, avec rôle
  par rattachement → **multi-cabinet possible**
- Porter `tentatives_echouees` / `verrouille_jusqua` sur `utilisateurs` — **le
  modèle existe déjà pour `super_admins`, c'est du travail déjà à moitié fait**
- `POST /rbac/roles` : ajouter **`DELETE`** avec refus sur les rôles système
- Rendre `ADMIN_CABINET` pilotable : matérialiser ses 45 permissions en base au
  lieu du court-circuit `ROLES_SANS_CONTROLE_PERMISSIONS`, en gardant **une**
  exception : ne peut pas retirer `ADMIN:UPDATE` à lui-même
- Vérifier que `audit_logs` capte les changements de droits (à confirmer)

### 3.3 Frontend

- Brancher `utilisateurs-page.tsx` (déjà écrite) sur les vrais endpoints
- Page « Inviter un utilisateur » : email, rôle, périmètre site, envoi du lien
- Page « Rôles » : brancher la suppression ; refléter l'état réel
- Bandeau « dernier administrateur » qui empêche l'action avec une explication
- Sélecteur de site dans la topbar (si multi-site)

### 3.4 Données

- Migration Alembic additive (`utilisateur_cabinet`, colonnes sur `utilisateurs`)
- Backfill : chaque `utilisateur` actuel crée son rattachement sur son cabinet

**Critère de sortie** : un admin de cabinet crée une secrétaire, lui donne le rôle
`SECRETAIRE`, vérifie qu'elle ne voit pas le dossier médical, la désactive, se
déconnecte, se reconnecte. **Et ne peut pas se supprimer lui-même.**

---

## 4. Sprint 2 — Onboarding (2 semaines)

> **Objectif :** un nouveau cabinet passe de « créé » à « facturant », sans
> intervention d'un script Python.

**Dépendances :** Sprint 1 (l'admin doit pouvoir inviter d'autres utilisateurs),
S0-4 (nomenclature).

### 4.1 Provisionnement

| Action | Détail |
|---|---|
| `POST /platform/tenants/{id}/provisioning` | **relancer un `PROVISIONING` bloqué** — aujourd'hui il faut le script |
| Vérification d'email | lien signé, 24 h, → statut `PENDING_VERIFICATION` → `ACTIVE` |
| Idempotence | relancer le provisionnement ne doit pas dupliquer rôles ni admin |
| Compensation | si l'étape 6 échoue, rollback propre du `Cabinet` et de l'admin |
| Compteurs | durée, étapes, message d'erreur **utilisable par un humain** |

### 4.2 Assistant de configuration (7 étapes, non bloquantes)

Identité → Sites → Salles & fauteuils → Équipe → Horaires → **Tarifs** →
Paiements & documents

Les étapes 5 (horaires) et 6 (tarifs) sont **la cause racine** de S0-4 : sans
elles, le cabinet démarre « configuré » mais incapable de fonctionner.

### 4.3 Interface plateforme (minimum viable)

`/platform/tenants` (liste, recherche, filtres, création) + détail (état, plan,
usage, actions suspendre / réactiver). Suffisant pour **opérer** un premier
client sans script.

**Critère de sortie** : un commercial crée un cabinet depuis l'interface, reçoit
le lien d'invitation, l'admin active son compte, suit l'assistant, saisit 3 actes
de nomenclature, ouvre son premier créneau et émet sa première facture.

---

## 5. Sprint 3 — Sécurité & conformité (1 semaine, parallèle)

> Aucun nouveau module. Ce qui manque ici est **légal**, pas confortable.

| # | Action | Pourquoi | Réf. |
|---|---|---|---|
| 1 | **Traçabilité de la stérilisation** | **Obligation légale.** Sans elle, on ne peut pas ouvrir un cabinet | F1 |
| 2 | **Sauvegarde automatique par tenant** | Continuité d'activité. `_psycopg` bloqué = aucune sauvegarde fiable aujourd'hui | I5 |
| 3 | **Journal d'audit immuable** | Sans preuve d'intégrité, il ne prouve rien | I1 |
| 4 | **Accès bris de glace** | Tout accès non motivé est une violation | I2 |
| 5 | **2FA sur les utilisateurs du cabinet** | Le mécanisme existe pour `super_admins` — à porter | I6 |
| 6 | **Refresh token en cookie `httpOnly`** | Retirer la dette XSS documentée dans `api.ts` | doc 03 § 4.6 |
| 7 | **Politique de rétention + purge automatique** | Obligation légale ; protège le client du stockage infini | I4 |
| 8 | **Consentement éclairé signé** | **Obligation légale**, absent | A1 |
| 9 | **Clôture de caisse + rapport Z** | Obligation comptable | G1 |
| 10 | **Clôture : retrait du secret `localStorage`** | Décision de design à valider | — |

**Critère de sortie** : un juriste peut demander «Montrez-moi la preuve que
l'instrument utilisé pour ce patient a été stérilisé, et qui a accédé à son
dossier depuis 30 jours » — et la réponse existe.

---

## 6. Sprint 4 — Modules cliniques à forte valeur (3 semaines)

> Par ordre de valeur, pas de commodité. Les deux premiers **conditionnent
> l'exploitation réelle** d'un cabinet.

| # | Module | Valeur | Eff. | Note |
|---|---|---|---|---|
| 1 | **Recherche globale de données** | La palette Ctrl+K **existe déjà sans la recherche**. Un champ qui trouve patient, RDV, facture, dossier. Coût faible, gain d'usage quotidien immédiat | M | Le frontend est déjà là |
| 2 | **Praticiens : création, disponibilités, remplacements** | Un cabinet ne peut pas tourner sans une deuxième personne. Complète S0-6 | M | |
| 3 | **Stock** | Module **entièrement absent** (5 appels 404). Un cabinet achète, consomme, stocke, périme | **L** | Prévoir les référentiels catégories/unités (doc 02 § 3.2) |
| 4 | **Plan de traitement multi-séances** | Évite la facturation à la volée ; rend le devis lisible | **L** | S'appuie sur `devis` existant |
| 5 | **Imagerie & photos** | **Le dentiste ne peut pas prescrire sans voir.** Bloque implantologie, ortho, endodontie | **L** | **Nécessite une couche de stockage objet — elle n'existe pas** |
| 6 | **Pédodontie (dents temporaires)** | La moitié d'une clientèle familiale. **Les dents temporaires n'existent pas dans le modèle** | **L** | À vérifier avant de chiffrer |
| 7 | **Suivi post-opératoire** | Obligation de bonne practice ; moment clé de la réputation | M | |
| 8 | **Rappels / recall** | Remplit l'agenda existant — souvent plus rentable que d'en chercher | M | |

**Prérequis de S4-5** : une couche de stockage de fichiers avec **cloisonnement
tenant obligatoire** dès le premier octet. C'est le point où une erreur
d'architecture coûte le plus cher à rattraper — le corriger après 10 000 radios
fugaîtisés, c'est Notify.

---

## 7. Sprint 5 — Communication & finance (2 semaines)

| # | Module | Valeur | Eff. |
|---|---|---|---|
| 1 | Confirmation de RDV (SMS/email) | **Réduit les absents de 15-25 %** | S |
| 2 | Relances d'impayés | Élimine les créances invisibles. `Date_echeance` existe déjà | S |
| 3 | Modèles de SMS/email | Base de toute la communication | M |
| 4 | Campagnes ciblées | « patients à jour depuis 2 ans », « RDV jamais honorés » | M |
| 5 | Rapprochement des paiements mobiles | **Wave / Orange Money : une part majeure des encaissements en Afrique de l'Ouest.** Sans ça, le CA du jour est un flux aveugle | M |
| 6 | Bulletin de salaire / rétrocessions | Modèle économique de groupe | **L** |
| 7 | Tiers payant & assurances | Double le panier moyen | **L** |
| 8 | Signature du devis | **Sans signature, pas d'engagement opposable** | S |

**Note** : aucun SMS/email n'est envoyé aujourd'hui — il n'existe **aucune** tâche
de fond dans le backend. C'est une brique d'infrastructure à poser d'abord
(worker, file, templates), pas une fonctionnalité à greffer.

---

## 8. Sprint 6 — Backoffice & plateforme (après validation)

Le **deuxième frontend**, non urgent. Le backend est déjà prêt pour (Sprint 2 a
posé `/platform/tenants`).

À prévoir, **sans implémenter** :

- Gestion des tenants : recherche, filtres, suspension / réactivation
- Plans & quotas : catalogue, limites, dépassements
- Statistiques d'usage → base de la facturation éditeur
- Support : tickets, historique
- **Impersonation encadrée** — jeton **distinct**, 15 min, journalisé **avant**
  accès, bannière visible, révoqué à la déconnexion. Jamais le token du Super
  Admin sur une session de tenant : sinon la séparation des pouvoirs disparaît
  en un clic
- Journal global (`audit_logs_global`, déjà alimenté)

---

## 9. Ce qui est explicitement **hors** de cette feuille de route

| Écarté | Pourquoi |
|---|---|
| Remplacer l'isolation par base par du `tenant_id` + RLS | **Choix déjà fait et bon.** Une seule requête sans filtre expose tout le pays. Doc 03 § B1.2 |
| Versionner l'API (`/api/v2`) | Client unique qui se met à jour en même temps que le serveur. Décision à reconsidérer **le jour où** le backoffice ou une API publique devient client externe. Doc 03 § B3.3 |
| Multi-langue (wolof) | Valeur réelle, mais **S-1** : tous les libellés sont en dur (doc 02 § 3.3). À faire **avec** l'extraction i18n, pas avant |
| Suppression physique d'un tenant | Sujet de **droit**, pas de produit. Anonymiser, conserver les factures, purger à l'échéance légale. Doc 03 § B2.4 |
| Remplacer PostgreSQL | NonJustifié. La contrainte d'exclusion `creneaux_fauteuil` est exactement le bon outil |

---

## 10. Matrice des dépendances

```
Sprint 0  Débloquer (2 bugs d'une ligne + 3 manques structurants)
    │
    ├──► Sprint 1  Utilisateurs & RBAC 2D ──► Sprint 3  Sécurité & conformité
    │        │                              │
    │        └──► Sprint 4  Multi-sites ◄───┘
    │
    ├──► Sprint 2  Onboarding (assistant + plateforme)
    │        │        (dépend de S1 pour inviter l'admin)
    │        └──► Sprint 6  Backoffice
    │
    └──► Sprint 4  Modules cliniques (dont Stock, Imagerie)
             │
             └──► Sprint 5  Communication & finance
```

**Deux dépendances non techniques à ne pas négliger :**

1. **Le verrou `_psycopg`** (politique de contrôle d'application Windows) n'est pas
   un bug de code — **aucun nouveau tenant ne peut être provisionné** tant qu'il
   n'est pas levé. Le Sprint 0 est bloqué par l'environnement.
2. **La décision multi-sites** (doc 03 § B1.5) doit être tranchée **avant** le
   Sprint 1 : propager `cabinet_id` sur les 24 tables qui ne l'ont pas coûte
   nettement moins cher **avant** d'avoir 100 000 lignes de patients.

---

## 11. Les 5 questions à trancher avant de coder

| # | Question | Enjeu | Recommandation |
|---|---|---|---|
| 1 | **Une société peut-elle avoir plusieurs sites dès le premier jour ?** | Détermine si le RBAC est à 1 ou 2 dimensions dès le Sprint 1. Le reporter coûte plus cher | **Oui → Option A** (doc 03 § B1.5) |
| 2 | **L'admin de cabinet reste-t-il admin partout ?** | Ajoute un `AND` à **toutes** les requêtes RBAC, ou pas | 1 seul admin multi-sites → 1 dimension suffit |
| 3 | **Quel hébergeur, et quel stockage pour l'imagerie ?** | Le module imagerie est le premier besoin de stockage objet du produit. Retarder le choix retarde l'imagerie | S3 compatible · MinIO en local |
| 4 | **Le refresh token reste-t-il en `localStorage` ?** | Dette XSS assumée. Un cookie `httpOnly` est la bonne réponse mais change l'API auth | **Cookie `httpOnly` + `SameSite=Strict`** (Sprint 3) |
| 5 | **Qui peut corriger le backend, et quand ?** | Le Sprint 0 est **entièrement** backend. Il est appliqué en attente de validation depuis le début de cet audit | **Décision requise maintenant** |

---

## 12. Ce que cet audit **ne** dit pas

- **Je n'ai pas exécuté l'application dans un navigateur** pendant cet audit. Les
  constats viennent de l'exécution réelle des endpoints contre une base peuplée
  (via `ASGITransport`) et de la lecture du code. Le rendu visuel n'est pas
  réévalué ici.
- **Je n'ai pas audité le backend pour le code mort, la duplication ou la
  complexité.** L'inventaire des 119 routes dit quels endpoints sont utilisés par
  le frontend, pas lesquels sont morts côté serveur.
- **Je n'ai pas mesuré les performances** (temps de réponse par endpoint, tenue en
  charge à 50 utilisateurs simultanés). La mission ne le demandait pas, et cela
  demanderait un jeu de données réaliste.
- **Les estimations d'effort sont indicatives.** Elles supposent une personne
  connaissant le code, pas une équipe qui le découvre.
- **Le formulaire médicaments (14 molécules) n'est pas une pharmacopée.** Il
  nécessite une relecture d'un pharmacien avant toute prescription réelle.
- **Les durées de conservation, obligations DASRI et règles de consentement**
  citées sont celles du cadre français. **Elles doivent être validées par un
  juriste du pays de déploiement** — le contexte visé est l'Afrique de
  l'Ouest, pas la France.
