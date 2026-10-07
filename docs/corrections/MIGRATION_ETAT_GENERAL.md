# Plan de migration — 4 champs cliniques de l'état général

> **Date** : 5 octobre 2026 · **Base** : tenant (`etats_generaux`)
> **Révision courante (head)** : `c4f8a2d91e05`
> **Objectif** : ajouter les quatre champs cliniques exigés par le cahier des
> charges et aujourd'hui **absents du schéma et de la base**.

## 1. Pourquoi ces quatre colonnes

Le cahier des charges exige : « diabète + type + **traitement**, HTA +
**traitement**, allergies détaillées, antécédents médicaux, **groupe
sanguin** ». Vérification faite sur le code :

| Champ | Schéma de saisie | Colonne | Conséquence |
|---|---|---|---|
| `diabete_traitement` | ❌ | ❌ | `PATCH` répond 200, la saisie est perdue |
| `hta_traitement` | ❌ | ❌ | idem |
| `groupe_sanguin` | ❌ | ❌ | idem |
| `antecedents_familiaux` | ❌ | ❌ | idem |

Avant ce chantier, `BaseSchema` n'interdisait pas les champs inconnus : ces
quatre noms étaient acceptés puis jetés en silence. `extra="forbid"` a déjà été
posé sur `EtatGeneralBase` et `EtatGeneralUpdate` : ils répondent désormais
**422**, ce qui rend la perte visible. Cette migration referme la boucle.

## 2. Contenu de la migration

Quatre colonnes **nullables**, sur `etats_generaux` :

| Colonne | Type | Justification de la longueur |
|---|---|---|
| `diabete_traitement` | `VARCHAR(200)` | « Metformine 850 mg, 2×/j » |
| `hta_traitement` | `VARCHAR(200)` | « Amlodipine 5 mg » |
| `groupe_sanguin` | `VARCHAR(10)` | « O+ », « AB- » |
| `antecedents_familiaux` | `TEXT` | récit libre, longueur non bornée |

**Toutes `nullable=True`, sans valeur par défaut.** Un patient dont l'état
general n'a jamais été saisi ne doit pas se retrouver avec un groupe sanguin
vide qui se lirait comme « renseigné et inconnu ».

## 3. Réversibilité

`downgrade()` supprime les quatre colonnes dans l'ordre inverse. La perte de
données en rétrogradation est **inévitable et assumée** : des valeurs
saisies entre l'`upgrade` et le `downgrade` seraient perdues. C'est le prix
standard d'une colonne ajoutée ; aucune donnée n'est transformée, seulement
des ajouts.

## 4. Sûreté sur les données de santé

| Risque | Traitement |
|---|---|
| Perte de données existante | **Aucune** : uniquement des `ADD COLUMN` nullable. Aucune ligne n'est lue, réécrite ou verrouillée. |
| Verrouillage de la table | `ADD COLUMN` sans `NOT NULL` ni défaut prend un `ACCESS EXCLUSIVE` très bref, sans réécriture de table sur PostgreSQL. Les tables de démo font quelques milliers de lignes au plus. |
| Réversibilité | `downgrade()` écrit, testé. |
| Copie de test | La migration est jouée sur une **copie** de base de démo avant la base réelle. |

## 5. Déroulé d'exécution (à faire dans cet ordre)

1. **Sauvegarde** de la base de démo (`pg_dump`) — fichier daté.
2. **Copie** de la base de démo vers une base jetable.
3. Jouer `upgrade` sur la copie, vérifier les quatre colonnes, insérer une ligne
   de contrôle, rejouer `downgrade`, vérifier la disparition.
4. Rejouer `upgrade` sur la copie (la base doit être revenue à l'état attendu).
5. **Jouer `upgrade` sur la base de démo réelle.**
6. Vérifier par appel API que les quatre champs se conservent et se relisent.

## 6. Hors périmètre de cette migration

- Rendre les booléens `grossesse`/`diabete`/`hta`/`tabac`/`alcool`/`allaitement`
  nullables pour introduire un état « inconnu » : cela changerait le
  comportement des alertes de contre-indication et relève d'une décision de
  domaine, pas d'un correctif de saisie. Voir « décision à valider » du
  diagnostic.
- Index sur `groupe_sanguin` : sans requête de tri par groupe sanguin, un index
  serait inutile. À réexaminer si une recherche par groupe apparaît.
