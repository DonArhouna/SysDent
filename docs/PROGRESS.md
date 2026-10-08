# SysDent Pro — journal de reprise

> **Usage** : ce fichier est le point de départ de toute session. Il dit où on en
> est, ce qui est **prouvé**, ce qui ne l'est pas, et par où reprendre.
> Mis à jour à la fin de chaque étape. Un commit atomique par étape.


---

## ACCES DU PROPRIETAIRE : **PRESQUE** — 2026-10-08

`rhonekane@gmail.com` existe, est **Super Admin**, et le mot de passe a ete
reinitialise avec la commande operateur. Le blocage 500 est **corrige et prouve
sur le serveur en service** :

```
1. login                      : 200, jeton d'enrolement recu
2. GET /2fa/preparation      : 200   (echouait en 500)
   secret TOTP present       : oui (32 caracteres)
   URI otpauth presente      : oui
```

### Ce qui reste a faire, par vous

1. **Tourner le mot de passe.** Celui utilise pour la preuve ci-dessus a ete
   produit par la commande et n'est connu que d'elle : il doit etre ecrase.

   ```powershell
   cd Backend
   .\.venv\Scripts\python.exe -m src.modules.platform.admin reinitialiser-mot-de-passe `
       --email rhonekane@gmail.com --motif "Ouverture du backoffice" --generer
   ```

   Le mot de passe s'affiche **une seule fois**. Copiez-le.

2. **Enroler le second facteur.** L'ecran d'enrolement du backoffice **n'existe
   pas encore** : il fait partie du travail restant (assistant QR, saisie du
   code, codes de secours). En attendant, l'API le permet - mais le secret ne
   doit jamais transiter par un terminal partage.

L'ancien compte `aminadiop@sysdent.pro` reste **actif** : le desactiver avant que
votre acces soit prouve laisserait la plateforme sans Super Admin utilisable.

### Quatre defauts empiles, tous en 2FA

Aucun n'etait visible sans executer le parcours.

1. **`preparer_2fa` resolvait `user_enrolement` sans l'utiliser** : elle passait
   `user` au service, qui vaut `None` sur un jeton d'enrolement. D'ou
   `AttributeError` sur `secret_2fa_chiffre` - le 500. La route refuse
   maintenant explicitement quand aucun porteur n'est resolu.
2. **`generer_codes_secours` reinterpretait du base64url comme de l'hexadecimal** :
   `int(c, 16)` levait ValueError hors de `[0-9a-f]`. Tirage uniforme dans
   l'alphabet, unicite garantie dans le lot.
3. **`JournalService` utilise sans etre importe** dans `routers/auth.py` :
   NameError a l'activation.
4. **Le code de secours n'etait cable qu'a l'ACTIVATION**, jamais sur le defi de
   connexion. Un compte dont le telephone n'est absent ne pouvait plus se
   reconnecter du tout.

Le point 4 est le plus grave : le mecanisme etait produit, stocke, et **mort**.

### Ecart de couverture trouve par injection de defaut

Retirer la clause `usage == ENROLEMENT_2FA` de `get_current_platform_user_enrolement`
laissait les 10 tests **verts**. Aucun test ne couvrait la restriction de portee -
le controle de securite le plus discret du module. Le test qui l'attrape est
ecrit : l'injection donne desormais **1 echec sur 12**, puis 12 verts apres
remise. Assertions inchangees dans les 10 tests d'origine.

### Etat verifie sans ambiguite

| Point | Etat |
|---|---|
| Migration `a3e7d1b95c24` | appliquee, allers-retouts verifies 2 fois sur copie |
| Login sans 2FA -> jeton d'enrolement, aucune session | **prouve** |
| Jeton rejete sur `/platform/auth/me`, une route client, `/auth/refresh` | **prouve** |
| `/2fa/preparation` sur le serveur en service | **prouve** : 200 + secret + URI |
| 12 tests d'enrolement | **12 verts**, assertions inchangees |
| Sensibilite a la restriction de portee | **prouvee** par injection de defaut |
| CLI d'operateur (`lister`, `creer-super-admin`, `reinitialiser-mot-de-passe`, `reinitialiser-2fa`) | **prouvee par execution** |
| `rhonekane@gmail.com` | cree, Super Admin, mot de passe a tourner par vous |
| Non-regression complete | **en cours** - voir le verdict en fin de journal |
| Ecran d'enrolement dans le backoffice | **a faire** |

### Reprise, dans cet ordre

1. Vous : tourner le mot de passe avec `--generer`, puis prouver la connexion.
2. **Assistant d'enrolement dans `Backoffice/`** : QR, saisie du code, codes de
   secours avec confirmation, jeton en memoire uniquement.
3. Regenerer le client OpenAPI, `npm run verifier`.
4. Desactiver `aminadiop@sysdent.pro` **apres** avoir prouve votre acces.
5. Puis : les 5 endpoints manquants, Lots 1 et 2, puis Lots 3-6.

### Regle a retenir

Une dependance « soft » n'existe que pour une route a **deux** types de jeton, doit
etre documentee, et son comportement par defaut doit etre le **refus**. Son captage
est **type**, jamais elargi : un `except Exception` transformerait un defaut de notre
code en « aucun jeton », donc en 401 - et une panne deviendrait impossible a
diagnostiquer. Contrat complet dans `dependencies.py`.

## État à date : 2026-10-08 (session 3)

**Étape en cours : 1 — non-régression backend et accélération de la suite.**
La suite n'a jamais été verte : elle dépassait 40 min et fut abandonnée deux fois.
Verdict en cours. L'écran Fournisseurs et la pagination stock sont livrés ; l'étape
file d'attente reste donc bloquée.

---

## ENROLEMENT 2FA — À 50 %, À REPRENDRE (2026-08-07)

### Ce qui est fait et vérifié

| Élément | Preuve |
|---|---|
| Migration `a3e7d1b95c24` (enum `ENROLEMENT_2FA`, colonnes `changement_mot_de_passe_obligatoire` et `codes_secours_haches`) | **allers-retours 2 fois sur copie**, puis appliquée sur la base réelle, compte conservé |
| Tests écrits **avant** le correctif | **9 échecs sur 10** — le défaut est donc bien Reproduit |
| Login sans 2FA active → jeton d'enrôlement, **aucune session** | 4 tests verts |
| Le jeton est **rejeté** sur `/platform/auth/me`, sur une route client et sur `/auth/refresh` | 3 tests verts |
| Codes de secours : génération sans alphabet ambigu, **hachés** en Argon2, usage unique à la consommation | codé, pas encore testé de bout en bout |

### Ce qui BLOQUE — 5 tests en échec

`GET /platform/auth/2fa/preparation` renvoie **500** avec un `NoneType` : le jeton
d'enrôlement est bien émis et accepté par la dépendance, mais la route ne résout
plus d'utilisateur. Deux causes possibles, non tranchées :

1. la dépendance « soft » rend `None` sur une exception que je n'ai pas identifiée
   (le contrôle d'adresse IP lève `PermissionDeniedException`, un nom différent de
   celui que j'avais importé) ;
2. le corps de `preparer_2fa` utilise encore une variable qui n'est plus alimentée
   après le changement de signature.

**L'accès du propriétaire n'est donc PAS opérationnel.** Le compte
`rhonekane@gmail.com` n'a pas été créé et l'ancien compte reste tel quel.

### Ordre de reprise, test par test

1. `GET /platform/auth/2fa/preparation` renvoie 200 avec `secret` et `uri`
2. `POST /platform/auth/2fa/activation` renvoie la session **et** les codes de secours
3. un code de secours ouvre une session, puis le même code est refusé
4. le jeton d'enrolement ne vaut plus rien après activation
5. **injection de défaut** : retirer la clause `usage == ENROLEMENT_2FA` de la
   dépendance et vérifier qu'un test échoue
6. commandes d'opérateur CLI + `docs/backoffice/OPERATIONS.md`
7. compte `rhonekane@gmail.com`, preuve par exécution, puis désactivation de l'ancien

### Rappel de la migration

Rétro-compatible : la colonne `changement_mot_de_passe_obligatoire` n'est pas utilisée
par le code livré, et `codes_secours_haches` ne l'est que par l'activation. La
migration peut donc être annulée sans effet de bord.

---

## VERDICT DE NON-RÉGRESSION — 2026-10-08

| Exécution | Passés | Échoués | Ignorés | Durée |
|---|---|---|---|---|
| Départ de session | **380** | **0** | **0** | **13,1 min** |

+4 tests CORS. Sous le seuil de 15 min.

---

## BLOCAGE TROUVÉ — la 2FA obligatoire rend la plateforme inutilisable

`POST /platform/auth/login` refuse la connexion quand `deux_facteurs_actif` est
faux : `401 DEUX_FACTEURS_NON_ACTIVE`, « contactez un Super Admin pour la
réinitialiser ».

Or **la seule façon de réinitialiser la 2FA est `GET
/platform/auth/2fa/preparation`, qui exige une session déjà ouverte**. La
2FA est donc obligatoire, et son enrolment exige d'être déjà connecté : sur une
plateforme à un seul Super Admin, il n'existe **aucune sortie**.

C'est un défaut réel du backend, pas une lacune de configuration. Il n'a pas été
détecté parce qu'aucun test ne couvrait « le seul Super Admin perd sa 2FA ».

**Correctif attendu** : une commande d'opérateur (CLI), au niveau serveur, qui
ré-enrolle la 2FA d'un compte sans exiger de session — l'équivalent d'un
`reset_mfa` chez un fournisseur d'identité. C'est une nécessité d'exploitation
reconnue pour toute plateforme à 2FA obligatoire, et elle doit être journalisée.

**Non fait** : contexte épuisé avant d'atteindre l'implémentation. C'est la
première chose à reprendre.

---

## VERDICT DE NON-RÉGRESSION

**376 passés, 0 échec, 0 ignoré, 12,7 min.**

Contient le test de contrat de pagination (32 tests) et l'ensemble des 344 tests
d'origine. Aucun test supprimé, ignoré ni assoupli. Sous le seuil de 15 min.

Trois passages ont été nécessaires, et les échecs venaient de mes propres
modifications, pas du produit : deux fois j'avais renommé un paramètre d'un côté
seulement (`limite` → `limit` sur l'odontogramme), une fois le middleware refusait
des requêtes **valides** parce qu'il ignorait les alias de paramètre. La suite a
sorti les trois ; c'est sa fonction.

---

## CHANGEMENT DE PRIORITÉ — backoffice

Le propriétaire a décidé de démarrer le **frontend du backoffice**. Les étapes
suivantes sont **reportées, pas abandonnées**.

### Reportés — ordre conservé

| # | Étape reportée | Note |
|---|---|---|
| 1 | **Recherche serveur des ordonnances** | JOIN entre modules, trois conditions : isolation inter-tenant testée, fonction de service dédiée (pas d'accès direct aux tables d'un autre module depuis le routeur), colonnes indexées, **mesure sur ≥ 10 000 ordonnances** |
| 2 | **Historique clinique** et traçabilité du dentiste | |
| 3 | **Autocomplétion des médicaments** | message explicite « N résultats affichés sur M : affinez votre recherche » quand la limite est atteinte ; aucune troncature silencieuse |
| 4 | **File d'attente (salle d'attente)** | migration `e8b2c4a7d1e5` écrite et testée sur copie, **non appliquée** |
| 5 | Référentiels configurables, fusion Praticien → Utilisateur, rôle Médecin chef | |
| 6 | **CI** : branchement de `inventaire_listes.py` et du test de contrat | le backend n'a pas de CI ; à créer |
| 7 | `MATRICE_ROLES.md` et `RAPPORT_FINAL.md` régénérés depuis le code | |

### Décisions prises

- **Décision 7 — client TypeScript généré depuis l'OpenAPI : OUI.** `openapi-typescript`
  + `openapi-fetch`, appliqués **d'abord au backoffice** (projet neuf, coût de migration
  nul). Pour l'application client : types générés, utilisés pour les **nouveaux** écrans,
  plus un script CI `contrat:verifier` qui échoue si les types ne correspondent plus à
  l'OpenAPI. Migration progressive consignée ci-dessus.
- **Décision 8 — les 12 routes de liste non semables : reportée.** Elles restent au
  registre dans `docs/TESTS.md`. **D'ici là, toute nouvelle route de liste — y
  compris au backoffice — doit être semable et couverte par le contrat
  comportemental dès sa création. Le stock ne doit pas augmenter.**

---

## Étape 1 — Non-régression et performance de la suite

### Mesures, pas suppositions

| Cause | Mesure | Coût total |
|---|---|---|
| Les **17 migrations Alembic s'exécutent pour chaque test** (création de base, migration, suppression) | démarrage d'Alembic + import de toute l'application + 17 lots de DDL, répété ~320 fois | la quasi-totalité de la suite |
| Hachage de mot de passe à **coût de production** | `get_password_hash` **440 ms**, `verify_password` **574 ms** | ~8 min 30 sur 320 tests |

Écartées après vérification : aucune attente réelle (`sleep`) dans les tests, et les
N+1 ont été traités par `selectinload` lors du chantier Finance.

### Corrections — sans affaiblir aucune assertion

**1. Modèle de base migré une fois, cloné par test.** `CREATE DATABASE … TEMPLATE`
copie au niveau des fichiers : quelques dizaines de millisecondes au lieu de rejouer
17 migrations.

> Ce qui ne change pas, et c'est l'essentiel : chaque test garde **sa propre base
> physique**, créée depuis un modèle vide et sans connexion ouverte. L'isolation
> reste structurelle ; elle est seulement obtenue plus vite.

**2. Hachage rapide en session de test.** PBKDF2-SHA256 à 1 000 itérations
(2,2 ms au lieu de 440 ms), salé et réellement irréversible : les tests qui
vérifient qu'un mauvais mot de passe échoue restent honnêtes.

> `src/core/security.py` garde ses paramètres de production. Seul le nom lié dans
> chaque module est remplacé, pendant la seule session de test. Aucun code livré
> n'est modifié, et aucun test ne vérifie Argon2 ou bcrypt lui-même (grep : 0).

**Un bug d'implémentation rencontré au passage.** La boucle de remplacement
comparait chaque module à `src.core.security` **pendant** la substitution : dès la
première substitution la référence n'était plus l'original, donc plus aucun module ne
« correspondait ». Le remplacement échouait **silencieusement**, sans lever la moindre
erreur ; seule la mesure du coût (440 ms toujours présents) l'a révélé. Les
originaux sont désormais capturés avant toute substitution.

### Verdict

| Exécution | Passés | Échoués | Ignorés | Durée |
|---|---|---|---|---|
| Avant corrections | — | — | — | **> 40 min, jamais achevée** |
| Après modèle cloné + hachage rapide | 344 | 0 | 0 | 18,8 min |
| **Après clonage des tests d'isolation** | **344** | **0** | **0** | **12,1 min** |

**Objectif < 15 min atteint**, et cette fois sur le code qui contient la pagination
de `/rendez-vous` et `/ordonnances` — le verdict intermediate ne la couvrait pas.

Ce sont les **mêmes 344 tests** qu'avant : aucun supprimé, aucun ignoré, aucun
assoupli.

### Goulot résiduel

Les tests **plateforme** (`tests/platform/test_auth_et_roles.py`) ont encore un
setup de 3 à 5 s : `platform_engine_test` applique les migrations plateforme à
chaque test, exactement le défaut corrigé côté tenant. Gain estimé ≈ 1 min. Non
fait — sous 15 min, l'effort ne se justifie pas encore ; à reprendre si la suite
repasse le seuil.

Commandes et pièges : `docs/TESTS.md`.

---

## Étape 2 — Contrat de pagination

### Inventaire extrait des routes enregistrées

`Backend/tests/inventaire_listes.py` lit le spectre OpenAPI de l'application — ni
mémoire, ni documentation — et **échoue (code 1)** si une liste volumineuse n'est
pas paginée. C'est l'instrument qui empêche la régression.

> Deux pièges rencontrés en l'écrivant, tous deux silencieux :
> - les routers inclus ne sont **pas aplatis** dans `app.routes` sur cette version
>   de FastAPI (`_IncludedRouter`) ; ne pas les traverser donnait **0 route** ;
> - `tests/platform/` **masque le module standard `platform`** dont SQLAlchemy a
>   besoin, car Python ajoute le dossier du script en tête de `sys.path`. L'erreur
>   affichée n'avait aucun rapport avec l'objet du script.

### Résultat : 47 conformes, **2 listes volumineuses non paginées**

| Chemin | Constat |
|---|---|
| `GET /rendez-vous` | liste non bornée, croît avec l'activité du cabinet |
| `GET /ordonnances` | idem |

### Vues bornées — décision, pas oubli

Un module peut contenir une liste volumineuse **et** des vues bornées. Les confondre
ferait paginer l'agenda — qui tient dans un écran — tout en laissant passer la vraie
liste : l'inverse de l'effet voulu.

| Chemin | Nature |
|---|---|
| `/rendez-vous/agenda` | vue d'une journée |
| `/rendez-vous/creneaux-libres` | créneaux d'un créneau de place |
| `/rendez-vous/referentiel` | statuts de rendez-vous |
| `/ordonnances/medicaments` | catalogue de médicaments |
| `/stock/alertes` | produits sous le seuil |

### Défauts réels trouvés par le test de contrat

Le test a échoué **sur du code déjà livré**, pas sur un défaut injecté :

| Défaut | Effet |
|---|---|
| **Tri non déterministe** sur `Fournisseur.nom` (sans clé secondaire) | 60 fournisseurs dont 4 noms distincts, paginés en 3 pages → **57 identifiants uniques, 3 doublons et 3 manquants**. Une ligne apparaissait deux fois et une autre disparaissait. L'écran, lui, affichait une liste plausible. |
| `/caisse/paiements-hors-session` : `limit` sans `page`, et `total_records = len(items)` | plafonné à 100, annonçait 100 alors qu'il pouvait en exister 150 — troncature silencieuse sur une liste comptable |
| `/caisse/sessions` : `limit=50` sans page, enveloppe non paginée | l'historique de caisse perdait ses journées anciennes sans message |
| `limite` coexistant avec `limit` | l'ancien nom restait sur une route ; un appel l'utilisant aurait été ignoré |

Tous corrigés : clé secondaire `id` sur les tris paginés (fournisseurs, articles,
commandes, mouvements, factures, devis, consultations), `/caisse/sessions` et
`/caisse/paiements-hors-session` paginées avec total réel.

### Refus des paramètres inconnus

Un middleware rejette (422) tout paramètre de requête qu'aucune route ne déclare.
Le bug de référence — le tableau de bord envoyait `limit` à une route attendant
`limite` — devient désormais **impossible** : il est détecté au premier appel, et
le test de contrat le vérifie sur chaque route semable.

> Trois pièges rencontrés en écrivant ce middleware, tous **silencieux** :
> - les routers inclus ne sont pas aplatis dans `app.routes` — il faut suivre
>   `original_router`, et ce nœud **n'a pas** d'attribut `routes` ;
> - `route.path` est le chemin **relatif au router**, alors que la requête porte le
>   chemin monté : comparer les deux ne matchait jamais, et le contrôle était
>   simplement inerte ;
> - la table doit être bâtie à la **première requête**, pas à l'enregistrement du
>   middleware, qui est posé avant l'inclusion des routes.

### Fait dans cette étape

- `/rendez-vous` et `/ordonnances` paginés : enveloppe `PaginatedResponse`,
  `page`/`limit` avec `LIMITE_PAGE_MAX` (100) et **422** sur valeur invalide,
  `total` calculé sur les mêmes filtres que les lignes
- **Clé secondaire de tri** (`id`) sur les deux : sans elle, deux lignes de même
  date sortent dans un ordre que PostgreSQL ne garantit pas être stable, et
  sautent d'une page à l'autre. C'est le défaut que le test de contrat doit traquer
- Filtre **signature** des ordonnances déplacé côté serveur, pagination branchée sur
  la liste, retour page 1 sur changement de filtre
- Frontend mis à jour sur les trois appels (`rendezvous-api`, `ordonnances-api`,
  `ordonnances-list-page`) : `dashboard.tsx` envoyait déjà `?page=1&limit=5`, que le
  backend **ignorait** puisqu'il attendait `limite`

### Reste à faire

1. **Test de contrat exécutable** : insérer 60 lignes, vérifier que `page`/`limit`
   sont réellement pris en compte, `total` exact, aucune ligne perdue ni dupliquée
   sur l'ensemble des pages. `inventaire_listes.py` ne vérifie que la *forme* de
   l'enveloppe, pas le comportement.
2. Test de contrat exécutable : 60 lignes insérées, `page`/`limit` réellement pris
   en compte, `total` exact, **aucune ligne perdue ni dupliquée** sur l'ensemble des
   pages, tri déterministe avec clé secondaire
3. Recherche, filtres et tri **côté serveur**, combinés avec la pagination
4. Frontend : `Pagination` sur chaque liste, page et filtres **dans l'URL**, retour
   page 1 sur changement de filtre, debounce, sélecteur de taille de page

---

## Livré — session 2 : écran Fournisseurs, pagination stock, purge de session


### Détail — écran Fournisseurs et pagination des listes

Signalé par le propriétaire : pas d'écran Fournisseurs dans le menu Stock, et
pagination absente des listes. L'audit a donné plus large que la demande.

### Trois défauts trouvés en_route

| # | Défaut | Effet |
|---|---|---|
| 1 | **`/stock/commandes` plafonné à 50 lignes sans `page` ni `offset`** | au-delà de 50 commandes, la liste était **tronquée en silence**. Exactement la famille « donnée absente présentée comme un zéro » : l'utilisateur croyait qu'il n'y avait rien d'autre. |
| 2 | **`/stock/fournisseurs` renvoyait la liste entière** | pas bornée |
| 3 | **Une seule liste sur six était paginée**, écrite à la main sur `patients-list-page` | cinq listes renvoyaient tout, ou se bornaient à un plafond invisible |

Listes **non** paginées, et c'est correct : `/cabinets`, `/roles`, `/permissions`,
`/praticiens` — des listes de référence de quelques éléments, la pagination n'y
apporterait rien.

### Ce qui est fait

**Backend** — `/stock/fournisseurs` et `/stock/commandes` passent en
`PaginatedResponse`, services modifiés pour renvoyer `(lignes, total)`. Le total
partage les mêmes filtres que les lignes : les calculer séparément inviterait à
les faire diverger.

> **Piège rencontré** : `params: PaginationParams = Depends()` sur un modèle
> Pydantic **ne lie pas les query params** — `page` et `limit` seraient restés à
> 1/20 et la pagination inopérante depuis le client, sans erreur visible. Suivi du
> motif explicite déjà employé lignes 153-154 du même fichier.

**Frontend**
- `components/ui/pagination.tsx` — composant **partagé** (compte toujours visible,
  boutons seulement si plusieurs pages, récupération si la page demandée a
  disparu). Remplace le bloc dupliqué de `patients-list-page`.
- `fournisseurs-panel.tsx` — **écran Fournisseurs** : recherche, tableau
  (raison sociale, contact, téléphone, email), modification, retrait. Onglet,
  route `/stock/fournisseurs`, entrée de menu.
- Panneau Commandes : pagination commandes **et** recherche fournisseurs avec
  différé de 300 ms ; suppression de la carte « Fournisseurs » doublon.
- La création en ligne depuis la saisie de commande **est conservée** — c'est là
  qu'on découvre qu'un fournisseur manque.

### Preuve

Exécution réelle sur la base de démo :

| Contrôle | Résultat |
|---|---|
| Fournisseurs page 1, limit 3 | 3 lignes sur 8, 3 pages |
| Recherche par nom | 1 résultat |
| Enveloppe `{ items, meta }` sans `data` | conforme au contrat du panneau |
| Retrait d'un fournisseur | 200, `actif=false` |
| Commandes page 2 distincte de la page 1 | oui, total 8 |
| `npm test` | **12/12** (4 nouveaux tests sur `Pagination`) |
| `tsc -b` / `oxlint` / `build` | propres, 0 erreur |

### Reste sur ce sujet

Les listes **consultations, devis, ordonnances et factures** n'ont toujours pas de
pagination côté interface. À traiter avec le composant partagé — le backend
`/factures` est déjà paginé, `/consultations` et `/ordonnances` sont à vérifier.

---

## Étape 3 — File d'attente : migration prête, application en attente

### Ce qui est fait

| Livrable | État |
|---|---|
| `docs/corrections/06_FILE_ATTENTE.md` — plan d'exécution | écrit avant toute modification |
| Sauvegarde de la base de démo | `%LOCALAPPDATA%\Temp\opencode\sysdent_demo_avant_file_attente_20261007_2104.dump` (0,25 Mo) |
| Copie de test `sysdent_copie_file_attente` | créée, 8 rdv / 32 patients / 30 consultations restaurés |
| `e8b2c4a7d1e5_file_attente.py` | écrite, appliquée sur la copie, **aller-retour vérifié 2 fois** |

### Preuve sur copie

| Contrôle | Résultat |
|---|---|
| Table `file_attente` créée | oui |
| 11 index, dont les 3 uniques partiels | oui |
| **Deuxième arrivée du même patient** | **REFUSÉE** — `duplicate key value violates unique constraint "uq_file_attente_actif"` |
| Nouvelle arrivée après clôture du passage | acceptée |
| `downgrade` | table supprimée |
| Ré-application après `downgrade` | **échouait** — voir ci-dessous |
| Données préexistantes après aller-retour | 8 rdv / 32 patients / 30 consultations, intactes |

### Un défaut de réversibilité trouvé et corrigé

Le premier aller-retour a **échoué** : `op.drop_table` ne supprime pas le type énuméré
créé par `create_table`. La ré-application levait
`DuplicateObject: type "statutfileattenteenum" already exists`.

Une migration « réversible » sur le papier ne l'est pas si son aller-retour échoue :
c'est précisément ce que le test sur copie sert à attraper, et un `downgrade` qui
fonctionne une seule fois ne prouve rien. Corrigé par un `DROP TYPE IF EXISTS` dans
`downgrade()`, puis vérifié sur deux cycles complets.

> **À surveiller** : aucune autre migration de ce dépôt ne comporte de `DROP TYPE`
> (`grep` sur `alembic_tenant/versions/` : zéro occurrence). La même latence
> existe probablement ailleurs. À auditer à l'étape 7.

### Pourquoi la migration n'est pas encore appliquée

La suite complète backend tournait encore (20 % au moment de l'arrêt) : la règle
« non-régression verte avant de passer à l'étape suivante » n'est pas satisfaite.
La migration étant **purement additive** — elle crée une table et ne touche aucune
table ni aucune ligne existante — le risque de régression est faible, mais « faible »
n'est pas « prouvé », et la règle l'interdit.

### Reprise — ordre exact

1. `docker ps` → `sysdent_s0b` doit être `Up`
2. Reprendre la suite : `cd Backend`, poser `MASTER_DB_PORT=55435` et
   `TENANT_DB_PORT=55435`, puis `.\.venv\Scripts\python.exe -m pytest -q --tb=short`
   → doit être **verte**
3. Appliquer : poser
   `ALEMBIC_TENANT_DB_URL='postgresql+psycopg2://postgres:<pw>@127.0.0.1:55435/sysdent_tenant_clinique_cabinet_sn_5bd215'`
   puis `.\.venv\Scripts\python.exe -m alembic -c alembic_tenant.ini upgrade head`
4. Modèle ORM `FileAttente` + `StatutFileAttenteEnum` dans `src/modules/tenants/models.py`
5. Permissions `ATTENTE:READ/CREATE/UPDATE/CALL` dans `src/common/permissions.py`
   (matrice dans `06_FILE_ATTENTE.md` §4)
6. Module `src/modules/attente/` : services, router, schemas — 7 endpoints (§5 du plan)
7. Tests `tests/test_file_attente.py` — dont **concurrence** (§8 du plan)
8. Écrans `/attente` secrétaire + dentiste
9. Rejouer la suite complète

Le mot de passe de la base se lit dans `Backend/.env`, clé `TENANT_DB_PASSWORD`
(il n'est pas dans `.env.example` en clair). La copie `sysdent_copie_file_attente`
peut être supprimée : `docker exec sysdent_s0b psql -U postgres -c 'DROP DATABASE sysdent_copie_file_attente'`.

---

## Historique — session 2, étape 0 : reprise

### Dépôt

| | |
|---|---|
| Branche | `main`, **arbre propre** (0 fichier modifié) |
| Dernier commit | `6d669e1` — *feat: add platform module, stock, caisse, utilisateurs, alembic platform migrations and full documentation* (2026-10-07 18:27, 147 fichiers) |
| Contrainte levée | La session précédente laissait ~73 fichiers non commités. C'est fini : tout est dans `6d669e1`. |
| Tête Alembic tenant | `d7f2a9c4b6e1` (17 migrations) |

### Infrastructure au contrôle

Les quatre conteneurs tournaient déjà : `sysdent_s0b` (55435), `sysdent_master_db` (5432), `sysdent_redis`, `emp_postgres`.

### Outillage frontend — gaps comblés

Le dépôt client **n'avait aucun outillage de test** : ni Vitest, ni jsdom, ni
Testing Library. Toute la vérification frontend reposait sur `tsc -b` et
`oxlint`, qui ne disent rien du comportement. Ajouté :

- `vitest@3.2.7` + `@vitest/coverage-v8@3.2.7` (épinglés : `@vitest/ui@3.2.7` était
  déjà présent et exige `vitest@3.2.7` — une installation non épinglée échoue en
  `ERESOLVE`)
- `jsdom`, `@testing-library/react`, `@testing-library/dom`, `@testing-library/jest-dom`
- `npm run test` / `npm run test:watch`
- **Pas de MSW** : les assertions portent sur le *nombre d'appels* et le *nombre de
  purges*, pas sur l'encodage HTTP. Un `fetch` piloté à la main prouve le
  mécanisme réel sans dépendance supplémentaire.
  → **décision à valider** : accepter un test sans intercepteur réseau ?

`npm install` exige `npm install-scripts approve esbuild` (npm 11+) sinon Vitest ne
trouve pas son binaire. Déjà fait sur ce poste ; à refaire sur un poste neuf.

---

## Historique — session 2 : correctif de session expirée, **PROUVÉ**

### Le défaut

Session expirée → 401 → échec du renouvellement → l'application **continuait
d'appeler l'API avec un jeton mort**. Cascade de 401 puis de 403 qui ne
parlaient d'aucune permission réelle : l'utilisateur cherchait une panne de droits
inexistante.

### Ce que les tests ont trouvé en plus du défaut connu

Trois défauts réels, découverts **par les tests** et non à la lecture :

| # | Défaut | Effet |
|---|---|---|
| 1 | **Cache React Query non vidé** à la déconnexion (S0-7) | Sur un poste partagé, la personne suivante voit les données de la précédente avant même que la première requête ne revienne. Fuite inter-utilisateurs. |
| 2 | **Site mémorisé jamais purgé** (`cabinet-store`, `localStorage: sysdent-cabinet-storage`) | Un identifiant de site = un identifiant de tenant. Le second utilisateur porte ses requêtes vers le site du premier. Le backend refuse (l'isolation tient), mais l'application demande une donnée qui n'est pas la sienne et affiche une erreur incompréhensible. **Trouvé par le test, pas par la relecture.** |
| 3 | **Aucun multi-onglets** | Le `localStorage` partagé ne met pas à jour un store déjà chargé : un onglet resté ouvert continue d'appeler l'API avec un jeton révoqué. |

Et un défaut dans le **correctif précédent lui-même** :

| # | Défaut | Cause |
|---|---|---|
| 4 | **Six purges au lieu d'une** | Le verrou « purge en cours » ne verrouillait rien : les six 401 arrivent **échelonnés**, chacun après la résolution de la promesse de renouvellement partagée. La première purge se termine avant que la suivante n'arrive. L'état correct est « cette session est **déjà morte** », pas « une purge est en cours ». |

### Couverture de la chasse à la fuite

| Emplacement | Verdict |
|---|---|
| `localStorage: sysdent-auth` | purgé (jetons + profil) |
| `localStorage: sysdent-cabinet-storage` | **purgé (correction)** |
| `localStorage: thème` | laissé — préférence non sensible, expressly autorisé |
| `sessionStorage` | aucune écriture dans le dépôt |
| IndexedDB | aucun usage |
| Service Worker / Cache API | absent (`public/` ne contient que deux SVG) |
| Brouillons de formulaires | aucun : les « brouillons » du code sont des **statuts** de documents (`BROUILLON`), pas de l'état local |
| Toasts | messages d'erreur backend, pas de donnée de santé structurée ; non purgés (arbitrage documenté) |

### Preuve

`Frontend/src/test/session-expiree.test.ts` — 6 tests.

**Avant correction : 3 échecs** (purge du site, multi-onglets, six purges).
**Après : 6/6 verts.** `tsc -b` propre, `oxlint` 0 erreur.

| Test | Prouve |
|---|---|
| purge unique, pas de rejeu, pas de cascade | 2 appels seulement (métier puis refresh) — c'est le défaut observé |
| six requêtes simultanées | 1 seul `POST /auth/refresh`, 7 appels au total, 1 purge |
| session valide survit | rejeu avec le **nouveau** jeton, 0 purge |
| second utilisateur ne voit rien | `client.clear()` **avant** toute navigation |
| site mémorisé purgé | store cabinet + `localStorage` |
| multi-onglets | l'onglet B est purgé **sans** que B ait déconnecté |

### Non vérifié

**Le rendu navigateur.** Aucun test de ce fichier n'observe ce qui s'affiche. Le
comportement visible reste à confirmer par l'utilisateur : laisser expirer la
session → redirection vers `/login`, **aucune** cascade 401/403.

### Leçon — les défauts d'exécution ne se voient pas au build

La purge de session **cassait le démarrage de l'application** : `QueryProvider` est
monté au-dessus de `BrowserRouter` (`main.tsx`), et le `useNavigate()` que j'y avais
ajouté levait
`useNavigate() may be used only in the context of a <Router> component`.

`tsc -b` était propre, `oxlint` à 0 erreur, la suite backend verte. **Aucun de ces
contrôles ne pouvait le voir** : le défaut n'existe qu'à l'exécution dans un
navigateur.

Désormais `src/test/arbre-application.test.tsx` monte l'arbre de fournisseurs dans
l'ordre réel de `main.tsx` et échoue si un hook de routeur est appelé au mauvais
niveau. Sensibilité prouvée : bug réintroduit → le test reproduit exactement
l'erreur de l'utilisateur ; corrigé → 8/8 verts, build passé.

C'est le seul filet pour cette famille de défauts. **À étendre** : tout composant
consommant `useNavigate` / `useLocation` hors d'un routeur a le même risque, et
personne n'a de navigateur pour le découvrir.

---

## Reste à faire

| # | Étape | État |
|---|---|---|
| 2 | File d'attente (salle d'attente) | à faire — **démarre ici** |
| 3 | Historique clinique | à faire |
| 4 | Référentiels configurables | à faire |
| 5 | Fusion Praticien → Utilisateur | à faire — risque élevé, ne pas apply sans test sur copie |
| 6 | Rôle Médecin chef | à faire |
| 7 | Contrôle de dérive | à faire |
| 8 | État d'écart du cahier des charges | à faire, sans implémentation |

### Documents périmés

- `docs/corrections/RAPPORT_FINAL.md` — écrit avant les six derniers chantiers
- `docs/corrections/MATRICE_ROLES.md` — idem, à **régénérer depuis le code**
- `docs/audit/05_FEUILLE_DE_ROUTE.md` — **S0-7 à clore** (prouvé par le test
  « vide le cache React Query »)

---

## Décisions à valider

4. **Recherche serveur sur les ordonnances** — la page filtre encore le texte en
   client sur la page courante. Corrigé il faudrait une recherche serveur portant sur
   nom et numéro de dossier du patient, donc un JOIN qui traverse deux modules.
   À valider : est-ce attendu avant l'étape file d'attente ?
5. **`/caisse/sessions` non paginée** — croît d'une session par jour et par caissier.
   Volumineuse à l'échelle d'un an, mais la page n'affiche que les sessions récentes.
   Volontairement laissée en dehors de l'inventaire : à confirmer.
6. **Vues bornées classées comme telles** (`agenda`, `creneaux-libres`, `referentiel`,
   `medicaments`, `alertes`) — décision assumée et documentée dans
   `inventaire_listes.py`, pour qu'elle se relise au lieu de se découvrir par
   absence. À valider : `/ordonnances/medicaments` croît avec le catalogue et
   pourrait mercer la pagination un jour.

1. **Tests frontend sans MSW** (fetch piloté) — choix fait pour l'économie et la
   précision ; à confirmer.
2. **Toasts non purgés à la déconnexion** — un message d'erreur backend peut
   contenir un nom de patient ; il resterait à l'écran pour l'utilisateur suivant.
   Arbitrage : purge nécessaire ou surcoût injustifié ?
3. **`BroadcastChannel` sans repli `storage`** — disponible partout depuis 2022 ;
   pas de repli pour les navigateurs antérieurs.