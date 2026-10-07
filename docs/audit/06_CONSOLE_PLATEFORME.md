# 06 — Console PLATEFORME (éditeur)

> **Date** : 5 octobre 2026 · Document de référence de la console de l'éditeur.
>
> Complète [05 — Feuille de route](05_FEUILLE_DE_ROUTE.md), qui annonçait la
> console comme **Sprint 3**. Ce document décrit ce qui est construit et
> vérifié, et ce qui reste à faire.
>
> Toutes les routes listées ci-dessous sont extraites de `GET /api/v1/openapi.json`
> sur une instance en fonctionnement : la liste est vérifiable, pas déclarative.

---

## 1. Ce qu'est la console plateforme

C'est l'**outil de l'éditeur** — le côté de SysDent qui vend et soutient les
cabinets, distinct de l'API client que chaque cabinet utilise.

La séparation n'est pas cosmétique. Le client vit dans **une base par cabinet**
(isolation clinique) ; la console vit dans **sa propre base**, à côté. Aucun
code de la console ne touche une base cabinet, et aucun code client ne sait que
la console existe. C'est ce qui permet de mettre la console en maintenance sans
interrompre les cabinets, et de facturer l'éditeur sans qu'un cabinet puisse
voir ses voisins.

```
┌──────────────────────┐        ┌──────────────────────────┐
│  API CLIENT          │        │  CONSOLE PLATEFORME      │
│  /api/v1/*           │        │  /api/v1/platform/*      │
│                      │        │  /api/v1/onboarding/*    │
│  base master         │───────▶│                          │
│  + 1 base / cabinet  │ auth   │  base plateforme         │
│  contenu clinique    │        │  aucun contenu clinique   │
└──────────────────────┘        └──────────────────────────┘
```

---

## 2. Surface d'attaque — l'état réel

| Domaine | Chemins | Opérations |
|---|---|---|
| Platform · Authentification | 8 | 8 |
| Platform · Tenants (cycle de vie) | 10 | 10 |
| Platform · Utilisateurs & Rôles | 10 | 10 |
| Platform · Plans, abonnements & facturation | 13 | 13 |
| Platform · Supervision & journal | 8 | 8 |
| Platform · Accès support | 3 | 3 |
| Onboarding public | 3 | 3 |
| **Total** | **44 chemins** | **55 opérations** |

Sur 133 routes applicatives au total, **44 sont de la console**.

---

## 3. Authentification et rôles

`POST /api/v1/platform/auth/login` — jeton JWT distinct du client, audience
`platform`, expiration courte.

Cinq rôles, une matrice unique déclarée dans
`src/modules/platform/permissions.py:MATRICE_ROLES` :

| Rôle | Niveau | Périmètre |
|---|---|---|
| `SUPER_ADMIN_PLATEFORME` | 1 | Tout, y compris la gestion des comptes |
| `SUPPORT` | 2 | Lecture cabinets + accès support encadré. **Pas** de facturation |
| `FACTURATION` | 3 | Plans, abonnements, factures |
| `COMMERCIAL` | 4 | Création et suivi des cabinets en essai |
| `AUDITEUR` | 5 | Lecture seule + export d'audit |

`MATRICE_ROLES` est une **source de vérité, pas un script de seed** :
`appliquer_matrice` réaligne la base dessus, donc un rôle créé à la main ne
peut jamais recevoir un droit non déclaré. Ajouter une permission dans le code
ne l'accorde pas implicitement.

La 2FA est **obligatoire pour tout compte plateforme**, sans exception : le flux
de connexion renvoie toujours `deux_facteurs_requis: True` et n'ouvre de
session qu'après validation d'un code TOTP. Un compte dont le secret n'est pas
encore confirmé active son second facteur **au premier login** plutôt que de
rester bloqué — sinon le tout premier compte créé serait inatteignable par son
propre titulaire.

C'est un choix assumé : une console administrable sans second facteur est un
back-office, pas une console d'éditeur.

---

## 4. Le contrat commercial, exposé au client

C'est le point le moins évident de la conception. Le client **ne possède pas**
la notion de plan : il possède une liste de droits et de compteurs.

`GET /api/v1/auth/me` renvoie **à plat** (pas d'objet `contrat` imbriqué), en
plus du profil habituel :

```json
{
  "id": "…", "email": "…", "prenom": "…", "nom": "…",
  "role": "ADMIN_CABINET",
  "permissions": ["PATIENTS:READ", "…"],
  "tenant_id": "…",
  "plan_code": "ESSENTIEL",
  "quotas":    { "praticiens": 5, "salles": 2, "utilisateurs": 10 },
  "features":  { "RDV": true, "FACTURATION": true, "IMAGERIE": false }
}
```

Les trois champs ont un **défaut** (`None`, `{}`) : un client plus ancien qui
les ignore continue de fonctionner. C'est ce qui permet de livrer le contrat
commercial sans casser une seule des bases déjà déployées.

Pourquoi le client lit `quotas` : parce que c'est **la seule façon fiable**
d'afficher « 3 praticiens sur 5 » sans que le client invente ses propres règles
commerciales. Les règles changent quand l'éditeur change de plan ; elles ne
doivent pas être réimplémentées dans 500 cabinets.

`GET /api/v1/platform/tenants/{id}/quotas/simulation` permet de prévisualiser
l'effet d'un changement de plan **avant** de l'appliquer.

---

## 5. Accès support — le point le plus sensible

Quand un cabinet signale un bug, l'éditeur doit voir son problème. Il ne doit
**jamais** pouvoir lire son dossier patient. Ces deux besoins sont incompatibles,
donc ils sont séparés.

### 5.1 Ce qui est autorisé

Un accès support est un **objet explicite**, pas un super-pouvoir :

1. un administrateur plateforme l'ouvre pour un cabinet, avec un **motif** ;
2. il produit un jeton **court** (30 min par défaut) et **à portée limitée** ;
3. chaque usage est **journalisé** côté plateforme ;
4. il est **révoquable**, et la révocation prend effet **immédiatement**.

### 5.2 Listes blanches, pas listes noires

C'est la décision structurante. Une liste noire (« sauf `/patients` ») est fausse
dès qu'on ajoute une route : **l'oubli est silencieux**. Une liste blanche
(« seulement `/rbac` et `/audit` ») est sûre par défaut : une route nouvelle
est exclue tant qu'on n'a pas décidé de l'inclure.

Le contrôle est appliqué au point central unique par lequel passe toute route
tenant (`get_token_payload` dans `src/modules/auth/dependencies.py`), pas
route par route. Une route oubliée ailleurs dans le code ne peut pas contourner.

### 5.3 Ce que cela a empêché

Le test d'isolation clinique de la Phase D a détecté une **vraie fuite** pendant
le développement : le jeton support lisait `/factures/journal-caisse`. Elle
n'aurait pas été visible en testant route par route. C'est l'argument le plus
fort en faveur de la liste blanche appliquée au point central.

### 5.4 Revalidation à chaud

Le jeton support est **revérifié à chaque requête** (statut, expiration,
révocation), pas seulement à l'émission. Une révocation prend donc effet
immédiatement, même sur un jeton encore valide cryptographiquement. Un jeton
révoqué mais non expiré est le scénario d'incident réaliste — on ne peut pas
attendre qu'il expire pour agir.

---

## 6. Le journal immuable

Le journal d'audit plateforme est protégé **par la base**, pas par le code
applicatif : un déclencheur refuse `UPDATE`, `DELETE` et `TRUNCATE`.

Un journal qu'on peut modifier depuis le code applicatif n'est pas un journal.
Protéger par convention (« ne modifie pas le journal ») protège des
développements, pas des DBA ni d'une requête écrite en urgence.

`GET /api/v1/platform/audit/export` produit un export CSV de ce journal.

---

## 7. Onboarding public

Trois routes, **sans authentification** — c'est le seul cas dans tout le système
où c'est normal, puisque c'est la porte d'entrée d'un client inconnu :

| Route | Rôle |
|---|---|
| `POST /onboarding/inscription` | Crée la demande + provisionne le cabinet |
| `POST /onboarding/verification-email` | Vérifie l'e-mail, déverrouille la connexion |
| `GET /onboarding/etat` | Suivi de l'avancement de la demande |

**Sécurité :** le cabinet créé est `PENDING_VERIFICATION`. La connexion client
est **bloquée** tant que l'e-mail n'est pas vérifié, ce qui empêche de
réserver un nom de cabinet et de s'attribuer une identité avant de prouver
posséder l'adresse.

Deux étapes séparées pour le premier geste : *créer le cabinet* puis *y créer
une salle*. Un cabinet sans salle n'a aucune raison d'exister immédiatement, et
la demande en deux temps est plus juste pour l'utilisateur.

---

## 8. Lancer le backend

### 8.1 Le blocage `uvicorn.exe`

```
ResourceUnavailable: Le programme "uvicorn.exe" n'a pas pu être exécuté :
Une stratégie de contrôle d'application a bloqué ce fichier.
```

Ce n'est **ni un problème de port, ni de dépendance**. C'est l'**exécutable**
`.venv\Scripts\uvicorn.exe` qui est refusé, parce qu'il s'agit d'un binaire
distinct. L'interpréteur `.venv\Scripts\python.exe` passe.

Le contournement est de lancer uvicorn comme **module** :

```powershell
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

`run_dev.py` fait exactement cela et rien d'autre :

```powershell
python run_dev.py                 # 127.0.0.1:8000, avec --reload
python run_dev.py --port 8001
python run_dev.py --no-reload     # plus rapide, utile en CI
python run_dev.py --log-level debug
```

L'API est sur `API_V1_PREFIX` : `/docs` et `/api/v1/openapi.json`.
Le `/openapi.json` à la racine renvoie un 404 enveloppé — c'est normal,
le préfixe est configuré dans `src/main.py`.

### 8.2 Amorçage

```powershell
$env:PLATFORM_ADMIN_EMAIL = "admin@votredomaine.fr"
python init_platform.py
```

---

## 9. Vérification — ce qui a été réellement exécuté

Chaque phase a un script de vérification qui **exécute** le comportement et
sort en code non nul au moindre échec. Un test qui passe est un test qui a
tourné ; rien n'est déclaré sur la seule intention.

| Phase | Objet | Résultat |
|---|---|---|
| C | Plans, changement de plan, quotas, factures | **46/46**, exit 0 |
| D | Accès support encadré, isolation clinique | **39/39**, exit 0 |
| E | Supervision, stats, `/platform/sante`, annonces | **35/35**, exit 0 |
| F | Onboarding public | **27/27**, exit 0 |
| — | `pytest tests/platform` | **13/13**, exit 0 |
| — | Non-régression suite client | 313 passés, **3 échecs préexistants** (§ 9.2) |

Smoke test sur une instance réellement démarrée :

| Contrôle | Attendu | Obtenu |
|---|---|---|
| `GET /health` | 200 | 200 |
| `GET /docs` | 200 | 200 |
| `POST /onboarding/inscription` (payload invalide) | 422 + champs détaillés | 422 |
| `GET /platform/sante` sans jeton | 401 | 401 |
| `GET /auth/me` sans jeton | 401 | 401 |

### 9.1 Les tests de la plateforme tournent sur PostgreSQL, pas SQLite

Délibérément. La console repose sur des **déclencheurs** (le journal immuable),
des **énumérations natives** et du **JSONB**. SQLite ne peut ni reproduire ces
déclencheurs ni valider l'immuabilité : le test y passerait sur une garantie
que la production n'a pas. Un test qui ne peut pas échouer ne vaut rien.

### 9.2 Trois échecs préexistants, non corrigés

Non-régression de la suite client, exécutée en entier :

| Fichier | Résultat |
|---|---|
| `tests/test_cabinets.py` | 45 passés, **2 échecs** |
| Reste de `tests/` | 268 passés, **1 erreur** |

```
test_utilisateur_inexistant_refuse      - RuntimeError: Event loop is closed
test_numero_ordre_duplique_refuse        - RuntimeError: Event loop is closed
test_rendez_vous_refuse_sur_fauteuil_bloque (erreur de setup)
```

Ce sont des **fuites de connexion `asyncpg`** : le gestionnaire de moteurs
tenant met en cache un moteur globalement, et son pool de connexions survit au
test qui l'a créé. Le test suivant ouvre une nouvelle boucle d'événements et
hérite d'un pool attaché à une boucle **fermée**.

Les trois sont **dépendants de l'ordre** : chaque test passe isolément
(`test_rendez_vous_refuse_sur_fauteuil_bloque` passe seul en 5 s) et échoue
quand un test précédent a laissé un pool vivant.

**Vérifié préexistant**, et non supposé : les mêmes échecs surviennent avec
`src/core/database.py` revenu à sa version d'origine via `git stash`. Le
correctif a été réappliqué puis vérifié identique octet pour octet. Mes
modifications ne sont donc pas en cause.

La cause est architecturale — un cache global de moteurs d'un côté, une boucle
d'événements par test de l'autre — et dépasse le périmètre de la console. Je ne
l'ai pas contournée : un contournement aurait fait **disparaître** le symptôme
sans traiter la fuite, et aurait rendu la suite verte de façon trompeuse. C'est
le premier chantier de la suite (doc 06, § 11).

---

## 10. Limites assumées

- **Pas d'interface.** Le backend est complet et vérifié ; l'écran de console
  côté frontend n'existe pas encore. C'est le prochain chantier.
- **Un seul administrateur initial.** `init_platform.py` en crée un ; il n'y a
  ni rotation de clé ni workflow de demande d'accès à la console.
- **Facturation sans paiement.** Les factures sont créées et suivies
  (brouillon → émise → payée), mais aucun prestataire de paiement n'est branché.
- **Une seule région.** Devise et fiscalité sont supposées Hors Taxes UE.
- **Support : deux surfaces seulement.** La liste blanche ouvre `rbac` et
  `audit`. Ouvrir une troisième surface est un choix explicite à faire, pas un
  effet de bord.

---

## 11. Suite

1. **Frontend console** — la console est inexploitable sans écran.
2. **Fixer la fuite de pool `asyncpg`** — préexistant, mais il rend la suite
   client non fiable et masquera les vraies régressions.
3. **Paiement réel** — brancher un prestataire sur le cycle de vie des factures.
4. **Clé de rotation** — pour que le bootstrapping reste tenable à plusieurs mains.

---

## Voir aussi

- [01 — Couverture API](01_COUVERTURE_API.md)
- [03 — Analyse multi-tenant](03_ANALYSE_MULTI_TENANT.md)
- [04 — Fonctionnalités manquantes](04_FONCTIONNALITES_MANQUANTES.md)
- [05 — Feuille de route](05_FEUILLE_DE_ROUTE.md)
