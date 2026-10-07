# Matrice des rôles — implémentée et vérifiée

> **Date** : 6 octobre 2026 · **Source** : `Backend/src/common/permissions.py`
> (`MATRICE_ROLES`) et les gardes `require_permissions(...)` des routeurs.
>
> **Règle** : une permission de cette table est appliquée **côté serveur**. Le
> frontend lit `/auth/me` et masque menus et boutons, mais un accès direct par
> URL sur une route non autorisée donne une **403 propre**, jamais une page.

## Comment lire le tableau

`C/R/U/D` = Créer / Lire / Modifier / Supprimer. Les autres actions possibles
sont `EXPORT` et `SIGN`, indiquées explicitement. `TOUT` = au moins les quatre
actions de base.

---

## 1. Matrice implémentée

| Rôle | Patients | Consultations | Odontogramme | Ordonnances | Cabinets | Praticiens | Disponibilités | Agenda | Facturation | Stock | Audit | Admin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Admin cabinet** (44) | TOUT | TOUT | R,U | TOUT | TOUT | TOUT | TOUT | TOUT | TOUT | TOUT | E,R | R |
| **Praticien** (20) | TOUT | TOUT, SIGN | R,U | TOUT, SIGN | R | R | TOUT | — | — | — | — | — |
| **Assistant** (11) | C,R | C,R | R | R | R | R | R | R | — | R | — | — |
| **Secrétaire** (12) | C,R | R | — | — | R | R | R | C,R,U | C,R | R | — | — |
| **Comptable** (8) | — | — | — | — | — | — | — | — | TOUT, EXPORT | R,U | R | — |
| **Gestionnaire de stock** (5) | — | — | — | — | — | — | — | — | R | TOUT | — | — |

Points de conception qui méritent d'être explicites :

- **Le caissier n'a aucun accès clinique.** Ni dossier patient, ni consultation,
  ni odontogramme, ni ordonnance. Il lit le stock et la facturation, rien de
  plus. Le contrôle est réel, pas seulement masqué dans l'interface.
- **Le dentiste n'a aucun accès à l'encaissement.** Il ne voit ni la facturation
  ni le stock : le soin et l'argent sont deux pouvoirs séparés.
- **L'administrateur de cabinet n'a pas `ADMIN:UPDATE`** — c'est la seule
  permission que le produit lui retire : on ne veut pas qu'il puisse réécrire la
  matrice des rôles lui-même (`retirer_permission` refuse sur ce rôle).
- **`ADMIN_CABINET` court-circuite le contrôle** (`ROLES_SANS_CONTROLE_PERMISSIONS`).
  C'est un choix à valider : il rend le rôle non restreignable, y compris par
  lui-même.
- **Le gestionnaire de stock lit la facturation** : il doit pouvoir valoriser ce
  qu'il recharge, même s'il n'encaisse pas.

---

## 2. Vérification par exécution réelle

Comptes de test créés sur le tenant de démonstration, un par rôle, puis
interrogation des routes sensibles. Résultat mesuré le 6 octobre 2026 :

| Rôle | Route | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| **Secrétaire** | `GET /stock/articles` | 200 | **200** | 🟢 lit le stock |
| **Secrétaire** | `POST /stock/articles` | 403 | **403** | 🟢 ne crée pas d'article |
| **Comptable** | `GET /stock/articles` | 200 | **200** | 🟢 valorise le stock |
| **Comptable** | `GET /patients` | 403 | **403** | 🟢 n'entre pas dans le dossier patient |
| **Praticien** | `GET /stock/articles` | 403 | **403** | 🟢 pas d'accès au stock |
| **Praticien** | `GET /consultations` | 200 | **200** | 🟢 voit les consultations |
| **Praticien** | `GET /patients` | 200 | **200** | 🟢 accès clinique |

**6 contrôles sur 6, conformes.** Le refus porte le code
`PERMISSION_DENIED` et un message nommant la permission manquante : l'utilisateur
sait quoi lui manque, et l'interface ne révèle pas ce qu'il n'a pas le droit de voir.

Permissions STOCK lues sur l'API pour chaque rôle :

| Rôle | Permissions STOCK |
|---|---|
| `ADMIN_CABINET` | CREATE, DELETE, READ, UPDATE |
| `GESTIONNAIRE_STOCK` | CREATE, DELETE, READ, UPDATE |
| `COMPTABLE` | READ, UPDATE |
| `SECRETAIRE` | READ |
| `ASSISTANT` | READ |
| `PRATICIEN` | *(aucune)* |

---

## 3. Ce que la matrice ne couvre pas encore

Ces points sont **non vérifiés** ou **non existants**, et je ne les présente pas
comme acquis.

| Sujet | État | Constat |
|---|---|---|
| **Comptes de test créés par l'API** | 🔴 impossible | `POST /rbac/users` → **404**. Les comptes ci-dessus ont été posés **directement en base** (y compris la ligne `utilisateur_index` du master, sans laquelle l'authentification ne trouve pas le tenant). C'est un outillage de test, pas une fonctionnalité. **Un cabinet ne peut toujours pas créer ses utilisateurs** — c'est le manque P0 le plus coûteux du produit. |
| **Rôles `SECRETAIRE` → création/mise à jour de RDV** | 🟡 non testé | La matrice accorde `AGENDA:CREATE, READ, UPDATE` mais je n'ai pas exercé la route de création de rendez-vous. |
| **Assistant** et **Gestionnaire de stock** en rôle connecté | 🟡 non testé | Permissions lues sur l'API, mais aucun appel effectué avec ces comptes. |
| **File d'attente** | 🔴 inexistante | La mission en fait le cœur du rôle de la secrétaire. **Aucun modèle, aucune route, aucun écran.** La permissions `AGENDA:*` ne lui donnent aucune existence. |
| **Clôture de caisse** | 🔴 inexistante | Le caissier a `FACTURATION:*` mais il n'y a **aucun écran ni endpoint de clôture** (totaux par mode, écarts de species). |
| **Rôles personnalisés** | 🟡 partiel | `POST /rbac/roles` existe et la matrice s'applique aux rôles créés ; **aucune suppression de rôle**, et le catalogue de permissions est figé dans le code. |
| **`ADMIN_CABINET` restreignable** | 🔴 non | Court-circuit total des permissions. Un administrateur délégué qui ne gère que les utilisateurs est **impossible** à créer aujourd'hui. |
| **Journal d'audit visible du client** | 🔴 à retirer | `GET /audit` est exposé au client et renvoie des données ; l'export reste réservé au backoffice. Cf. Chantier 4. |
| **Permissions du backoffice** | 🟡 non documentée ici | Les rôles plateforme (`SUPER_ADMIN`) ne passent pas par cette matrice : ils ont leur propre frontière. Cf. `docs/audit/03_ANALYSE_MULTI_TENANT.md` § B3. |

---

## 4. Décision à valider 🟡 — le rôle « Médecin chef »

La mission décrit un **médecin chef** qui voit toutes les consultations du
cabinet et valide les plans de traitement importants. **Ce rôle n'existe pas**
dans la matrice : les six rôles réels sont Admin, Praticien, Assistant,
Secrétaire, Comptable, Gestionnaire de stock.

Deux options :

| Option | Description | Conséquence |
|---|---|---|
| **A — rôle distinct** | Ajouter `MEDECIN_CHEF` : clinicians comme le praticien, plus lecture de **toutes** les consultations du cabinet | Exige de distinguer « mes consultations » de « celles du cabinet » dans les gardes. Chantier 3 le touchera de toute façon. |
| **B — permissions du praticien** | Le praticien voit déjà ses patients ; on lui ajoute la lecture transversale | Moins de rôles, mais on perd la distinction de responsabilité |

**Recommandation : A.** La supervision clinique est une responsabilité réelle et
distincte ; la diluer dans le rôle Praticien rendrait la validation de plans
impossible à attribuer à quelqu'un en particulier.

---

## 5. Reproduire la vérification

```
Backend/_verif_matrice_roles.py
```

Prérequis : le conteneur PostgreSQL démarré, et les comptes de test présents en
base. Le script échoue (code 1) au moindre écart entre le code HTTP observé et
le code attendu.
