# Chantier 5 — Simplifier le menu Praticiens

> **Statut** : analyse établie par lecture du code et exécution. La
> simplification elle-même est à implémenter ; ce document fixe la cible et la
> façon de la vérifier.
> **Périmètre** : `Frontend/src/features/praticiens/` (1 520 lignes, 52
> occurrences du mot *praticien* sur la seule page).

## 1. Ce que le menu propose aujourd'hui

Une seule entrée :

```
navigation.ts:58  { label: 'Praticiens', href: '/praticiens', permission: 'PRATICIENS:READ' }
```

Un menu à une entrée ne se « simplifie » pas — il faut donc comprendre **ce que
cette entrée ought contenir**. La page répond mal à la question : elle porte le
titre `Praticiens & Disponibilités` et fait deux choses sans rapport.

## 2. Le constat, établi sur la page réelle

| Constat | Mesure |
|---|---|
| Un écran fait deux métiers | `praticiens-page.tsx`, 23,5 Ko : l'annuaire des personnes **et** le planning hebdomadaire |
| Les jours de la semaine sont écrits en dur dans le composant | `JOURS_SEMAINE` (ligne 30), lundi → samedi, en dur |
| On ne peut pas ajouter un praticien | `POST /praticiens` n'existe pas (S0-6 de la feuille de route) |
| Le volume réel est faible | tenant de démonstration : **2 praticiens, 1 cabinet, 5 disponibilités** |

Les routes de disponibilités existent bien et fonctionnent
(`GET,POST /praticiens/{id}/disponibilites`, `DELETE /disponibilites/{id}`) — il
n'y a donc pas de fonctionnalité morte à supprimer, seulement une fonctionnalité
**mal placée**.

## 3. Pourquoi le découplage du Chantier 3 change la réponse

C'est le point clé, et c'est pourquoi ce chantier ne pouvait pas être traité
avant le précédent.

Un praticien **n'est plus une entité métier à part** : c'est un compte
d'utilisateur auquel peut s'attacher — ou non — un profil réglementaire (numéro
d'Ordre, spécialité, signature). Le serveur fonctionne désormais ainsi, et c'est
vérifié par exécution : un compte sans profil ouvre une consultation.

La question « qui est le praticien ? » a donc trois réponses distinctes, et
aujourd'hui une seule entrée de menu les mélange :

| Question | Ce qui la répond | Où ça devrait vivre |
|---|---|---|
| *Qui se connecte au cabinet ?* | les **comptes** et leurs rôles | **Utilisateurs** — déjà présent |
| *Qui est inscrit à l'Ordre ?* | le profil réglementaire | **Praticiens** |
| *Quand un praticien travaille-t-il ?* | les disponibilités | **Agenda & RDV** |

L'entrée « Praticiens » recouvre aujourd'hui les trois. Après le Chantier 3, elle
ne peut plus prétendre être l'annuaire des praticiens : **ce sont les comptes**.
Et le planning n'a rien à y faire.

## 4. La cible

### 4.1 Trois écrans, trois questions

| Écran | Contenu | Retiré de Praticiens |
|---|---|---|
| **Praticiens** | l'annuaire réglementaire : nom, spécialité, **numéro d'Ordre**, statut actif, signature | les disponibilités |
| **Utilisateurs** (existant) | les comptes, les rôles, l'accès au cabinet | — |
| **Agenda & RDV** | les rendez-vous, et la grille des disponibilités | la grille hebdomadaire |

### 4.2 Ce que devient la page `Praticiens`

- **Elle perd** la grille hebdomadaire et le sélecteur de jour. C'est un
  calendrier, pas un annuaire — et le mot *disponibilités* dans le titre
  annonçait déjà le problème.
- **Elle gagne** ce qui manque et qui la rend utile : le **numéro d'Ordre** en
  colonne lisible, et surtout le bouton **« Ajouter un praticien »** — dont
  l'absence est la vraie raison pour laquelle cette page est unsatisfactory.
  Un annuaire où l'on ne peut rien ajouter n'est pas un annuaire.
- `JOURS_SEMAINE` sort du composant vers une constante du domaine traduite.

### 4.3 Le bouton « Ajouter un praticien »

C'est le **verrou** du chantier, et il est backend
(`POST /praticiens` : service + route). Sans lui, la simplification ne produit
qu'un écran plus maigre.

À noter : depuis le Chantier 3, le formulaire de création d'un praticien n'a
**plus à exiger** un numéro d'Ordre — il est optionnel. Ce qui est obligatoire,
c'est le compte lié. Le formulaire doit donc créer le compte **et** le profil
réglementaire en un seul geste, sans que le praticien ait à ressaisir ses
coordonnées.

> Point d'attention : créer un utilisateur est aujourd'hui impossible depuis
> l'interface (`POST /rbac/users` → 404, cf. `MATRICE_ROLES.md` §3). Le bouton
> « Ajouter un praticien » dépend donc de ce manque : il faudra soit créer les
> deux, soit rendre la création de praticien possible sans elle — ce qui serait
> une erreur de sécurité.

## 5. Ce que le chantier ne corrige pas

- **La file d'attente de la secrétaire** reste inexistante.
- **Le module Utilisateurs** reste le manque bloquant n° 1, et il bloque le
  bouton du §4.3.
- La **création d'un rôle « Médecin chef »** reste une question ouverte
  (`MATRICE_ROLES.md` §4).

## 6. Vérification attendue

| Critère | Comment on le prouve |
|---|---|
| Aucun mot *disponibilité* dans `features/praticiens/` | recherche sur le répertoire |
| Aucune constante de jour en dur | `JOURS_SEMAINE` absent des composants |
| Le numéro d'Ordre est lisible dans l'annuaire | colonne présente |
| On peut ajouter un praticien | `POST /praticiens` répond 201 **et** le flux complet est rejoué |
| L'annuaire reste lisible à 2 praticiens comme à 40 | contrôle visuel sur les deux tailles |
| `npx tsc -b` et `oxlint` | aucun nouvel avertissement |
| Non-régression | suite complète verte |

Les cinq derniers points n'ont **pas** été vérifiés à ce jour : ce document
décrit une cible, pas un acquis.
