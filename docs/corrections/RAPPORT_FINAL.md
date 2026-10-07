# Rapport final — corrections SysDent Pro

> **Périmètre** : ce qui a été **exécuté et vérifié** au 6 octobre 2026, et ce
> qui ne l'a pas été. Aucun point de ce rapport n'est affirmé sans une exécution
> derrière lui ; ce qui n'a pas pu être vérifié est écrit comme tel.

## 1. En une phrase

Sur les quatre chantiers fonctionnels confiés, **trois sont livrés et prouvés
par exécution**, le quatrième est analysé et documenté ; et au passage, **trois
défauts ont été trouvés qui produisaient des données fausses sans aucun signal**.

## 2. Ce qui est livré

| Chantier | Preuve | Volume |
|---|---|---|
| **État Général** — la modification échouait | 4 causes racines corrigées, migration `d7e4a1b2c9f3` | 26 lignes préservées |
| **Factures** — l'écran renvoyait 500 | `selectinload` sur `Paiement.echeance` | `GET /factures` → 200 |
| **Stock** — module absent de la base | migration `e2f7b3c8a104`, 9 tables, 9 routes | 26 contrôles |
| **Commandes & réceptions** — absents | émission sans effet sur le stock, réception créditée | 26 contrôles |
| **Caisse & clôture** — absent | migrations `f3a8d5b2c701`, `a4b9e6c3d812`, `b5c0d7e4f923` | 26 contrôles + 11 tests |
| **Matrice des rôles** — jamais vérifiée | 6 contrôles par rôle, par connexion réelle | voir `MATRICE_ROLES.md` |
| **Découplage Consultation / Praticien** | migration `c6d1e8f5a4b7` | 12 contrôles |
| **Parcours patient de bout en bout** | 7 étapes, 6 profils | 28 contrôles |

### Non-régression

| Moment | Tests |
|---|---|
| Avant travaux | 333 |
| Après module Stock | 333 |
| Après clôture de caisse | 344 |
| **Après découplage** | **344 — 0 échec** (25 min 35) |

11 tests nouveaux ont été ajoutés avec la clôture. Aucun test existant n'a été
affaibli : les 6 tests qui encaissaient sans session de caisse ont reçu une
fixture qui ouvre la caisse, parce que la nouvelle règle est la bonne règle.

## 3. Le parcours patient

Une journée de cabinet, avec les six profils, de l'accueil à la clôture —
et non une suite d'appels isolés. Sortie complète dans
`PARCOURS_PATIENT.md`.

**Cinq des 28 étapes sont des échecs volontaires.** Ce sont les garde-fous du
produit, et le parcours échoue si l'un d'eux disparaît :

| Code | Règle métier |
|---|---|
| `PRATICIEN_NON_IDENTIFIE` | un acte exige un auteur clinique rattaché |
| `PERMISSION_DENIED` | le dentiste n'a pas `FACTURATION:CREATE` |
| `DENT_NUMERO_OBLIGATOIRE` | un soin unitaire exige un numéro de dent FDI |
| `CONSULTATION_NON_TERMINEE` | on ne facture pas une séance en cours |
| `DIAGNOSTIC_OBLIGATOIRE` | on ne clôt pas une consultation sans diagnostic |

## 4. Trois défauts trouvés en construisant, que rien ne signalait

C'est le résultat le plus utile de ces journées : pas les fonctionnalités
livrées, mais les bugs qui auraient survécu.

### 4.1 Un rapport de caisse faux, en silence 🔴

`ASSURANCE` faisait partie du catalogue des modes de paiement, mais la clôture
ne portait que cinq colonnes de total. Un encaissement assurance était **ignoré
au moment de la clôture** : le rapport de journée annonçait un chiffre inférieur
au réel, sans aucun signal.

Le pire genre de défaut comptable — un faux qui a l'air vrai, découvert au
moment de compter, par le caissier, sans piste.

Corrigé (`b5c0d7e4f923`) et verrouillé par
`test_tout_mode_de_paiement_a_un_total_de_cloture`, qui échouera dès qu'un mode
sera ajouté sans colonne. Le service **refuse désormais une clôture** plutôt que
de déclarer un total qui ment.

### 4.2 La preuve d'un encaissement disparaissait avec le compte

`paiements` ne portait que `enregistre_par_id`. Supprimer un compte supprimait la
preuve de qui avait pris l'argent — sur une pièce comptable. Corrigé par
`a4b9e6c3d812`, qui fige l'email, comme sur les sessions de caisse.

### 4.3 Une garde plus stricte que le modèle de données

`consultations.praticien_id` était `NOT NULL` vers `praticiens.id`, et trois
modules refusaient de travailler sans profil d'Ordre. Or
**`Praticien.numero_ordre` est déjà nullable** : la garde exigeait donc plus que
le modèle lui-même.

Résultat : impossible d'ouvrir une consultation pour un assistant sous
supervision, un interne, un intérimaire — ou un praticien dont le numéro d'Ordre
n'est pas encore saisi, ce qui est fréquent et ralentit le cabinet au lieu de
le bloquer.

Corrigé (`c6d1e8f5a4b7`). L'auteur est désormais le compte authentifié.

## 5. Les migrations

Sept migrations créées. Toutes réversibles, toutes **testées sur une copie de la
base de démonstration avant application**, avec sauvegarde préalable à chaque
fois.

| Contrainte | Vérification |
|---|---|
| Aucun perte de données | patients, factures, paiements et sessions comptés avant/après |
| Pas de réécriture d'historique | une journée close garde ses totaux ; les sessions antérieures à l'assurance ne sont pas recalculées |
| Remplissage par des faits, pas par invention | 0 auteur incohérent avec le profil d'origine |
| La règle tient en base | refus d'une seconde session ouverte ; refus d'une consultation sans auteur |
| Le `downgrade` ne supprime rien | il **refuse** quand des consultations n'ont plus de profil, plutôt que d'en effacer |

## 6. Ce qui n'est pas fait

| Manque | Conséquence | Statut |
|---|---|---|
| **Module Utilisateurs** | `POST /rbac/users` → **404**. Un cabinet ne peut pas créer ses comptes | 🔴 bloquant n° 1 |
| **File d'attente** | cœur du rôle secrétaire : aucun modèle, route ni écran | 🔴 non livré |
| **Chantier 4** — notions plateforme dans l'UI client | non traité | 🔴 non livré |
| **Chantier 5** — menu Praticiens | analysé et documenté, non implémenté | 🟡 analysé |
| **Chantier 6** | périmètre non défini dans les éléments reçus | 🟡 à cadrer |
| **`POST /praticiens`** | impossible d'ajouter un dentiste | 🟡 partiel |
| **Rendu navigateur** | aucun navigateur connecté : contrat et types prouvés, **affichage non vérifié** | ⚠️ non vérifié |

Les comptes de test de ce rapport ont dû être posés **directement en base**,
y compris la ligne `utilisateur_index` du master — sans laquelle
l'authentification ne retrouve pas le cabinet. C'est un outillage de test, pas une
fonctionnalité, mais c'est la mesure exacte du manque Utilisateurs.

## 7. Ce qui bloque la recette

- **`_psycopg` bloqué par une politique de contrôle Windows.** Aucun nouveau
  tenant ne peut être provisionné. Un cabinet neuf **n'a jamais été observé de
  bout en bout** — nomenclature, absence de Stock, contrat de `/auth/me` sur un
  tenant neuf restent non vérifiés.
- **Le conteneur PostgreSQL s'est arrêté deux fois** (code 255), la seconde fois
  pendant le Chantier 3. Les données n'étaient pas perdues. Le réflexe acquis :
  vérifier `docker ps` **avant** de lancer une suite de 25 minutes.

## 8. Ce que la méthode m'a appris — et m'a coûté

Je note ces erreurs parce qu'elles se reproduiront autrement.

| Erreur | Conséquence | Règle tirée |
|---|---|---|
| `npx tsc --noEmit -p tsconfig.json` | j'ai annoncé « `tsc` propre » alors que **`tsconfig.json` n'est qu'un redirectionneur** : rien n'était vérifié. Le contrôle réel est `tsc -b`, qui a sorti 5 erreurs | toujours `tsc -b --force` |
| `/api/v1` oublie dans un script de verification | 6 réponses 404 au lieu de 403 — on lisait un « échec de permission » qui était une erreur de route | préfixer systématiquement |
| ma fixture ouvrait la caisse avec un dépôt de 0 | mon test attendait 20 000 et recevait 15 000 : **le test avait tort, pas le serveur** | « le test est rouge » ne veut pas dire « le code a tort » |
| `SELECT col FROM` sur une table unique au lieu de la table | `POST /stock/commandes` totalement cassé, invisible à la lecture | relire les messages SQL intégraux |
| `pg_terminate_backend` sur la base partagée | aurait détruit le travail d'un autre agent | écrit dans `COEXISTENCE_AGENTS.md` |
| une migration sans `create_type=False` | `DuplicateObject` : SQLAlchemy recrée l'ENUM dans le `CREATE TABLE` | vérifié sur copie, systématiquement |

## 9. Reproduire les vérifications

| Script | Ce qu'il prouve |
|---|---|
| `Backend/_verif_parcours_patient.py` | 28 contrôles, journée complète, 6 profils |
| `Backend/_verif_caisse.py` | 26 contrôles, ouverture → clôture → totaux figés |
| `Backend/_verif_commandes.py` | 26 contrôles, commande et réceptions |
| `Backend/_verif_matrice_roles.py` | 6 contrôles, permissions par rôle |
| `Backend/_verif_decouplage.py` | 12 contrôles, consultation sans profil d'Ordre |

Prérequis : conteneur `sysdent_s0b` démarré, variables `MASTER_DB_*` et
`TENANT_DB_*` pointant sur `127.0.0.1` (**jamais `localhost`**, qui résout en
`::1` sur cette machine). Chaque script sort en code 1 au moindre écart.

## 10. Ce que je recommande ensuite, dans cet ordre

1. **Le module Utilisateurs.** C'est le seul manque qui bloque tout le reste : les
   45 permissions et les 6 rôles ne servent à personne tant qu'on ne peut pas
   créer un compte.
2. **La file d'attente.** Sans elle, le rôle secrétaire — le plus nombreux dans
   un cabinet réel — n'a pas d'outil.
3. **La recette navigateur.** Aucun rendu n'a été vérifié. Tout ce rapport porte
   sur le contrat et les types.
4. **Trancher l'ordonnance** (`03_CONSULTATION_PRATICIEN.md` §5) : exiger aussi
   un numéro d'Ordre renseigné, ou conserver la garde actuelle.
