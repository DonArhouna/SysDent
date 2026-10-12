# Tarification et prise en charge (CDC 5.6 et 5.7)

Ce document est la reference du pole : qui peut faire quoi, et pourquoi les
regles sont ce qu'elles sont. Le detail des regles vit dans le code, a cote de
la regle qu'il applique.

## Deux ressources, deux raisons

Modifier un tarif engage l'argent du cabinet. Declarer une prise en charge
engage la responsabilite du cabinet vis-a-vis d'un payeur. Un profil qui peut
l'un n'a pas pour autant l'autre : d'ou `TARIFS:*` et `ASSURANCE:*`, plutot
qu'une ressource unique.

Quatre actions seulement : `READ` et `WRITE`. La tarification est un
referentiel, pas un jeu de donnees que l'on supprime. Un acte se **desactive**,
ce qui est une mise a jour : un acte cite par une facture ne peut pas
disparaitre.

## Matrice role x permission

| role | `TARIFS:READ` | `TARIFS:WRITE` | `ASSURANCE:READ` | `ASSURANCE:WRITE` |
|---|---|---|---|---|
| `ADMIN_CABINET` | oui | **oui** | oui | **oui** |
| `PRATICIEN` | oui | non | oui | non |
| `ASSISTANT` | oui | non | oui | non |
| `SECRETAIRE` | oui | non | oui | **oui** |
| `COMPTABLE` | oui | non | oui | non |
| `GESTIONNAIRE_STOCK` | oui | non | non | non |

Trois regles derriere ce tableau :

- **Le praticien lit, il ne fixe pas.** Il doit voir le prix d'un acte pour le
  facturer et l'expliquer au patient ; le tarif se decide au cabinet.
- **L'accueil declare une prise en charge, pas un taux.** Il saisit la carte de
  mutuelle du patient a la creation de sa fiche, ce qui est son travail. Il ne
  touche ni aux organismes ni aux taux : un taux errone se reproduit sur toutes
  les factures du jour, et le corriger apres coup est plus cher que de ne pas
  l'exposer.
- **Le magasinier lit le tarif** pour commander au prix du cabinet et consume en
  valeur, sans avoir a voir les droits de prise en charge.

`TARIFS:WRITE` n'est accorde qu'a `ADMIN_CABINET`. C'est le seul role
court-circuite par `require_permissions` : l'ajouter au catalogue suffit a le lui
accorder, et aucun autre role ne le recoit par la matrice.

`ASSURANCE:WRITE` est le seul `WRITE` partage. La regle est explicite dans
`src/common/permissions.py`, et le test `test_matrice_role_sur_la_tarification`
l'emboutit.

## La nomenclature a change de maison

Les routes `/api/v1/nomenclature/actes` demandaient `CONSULTATIONS:READ` et
`CONSULTATIONS:CREATE`, et repondaient en `dict`. Avoir le droit de creer une
consultation ne devrait pas donner le droit de fixer le prix des actes du
cabinet : c'etait un defaut de fond, pas une coincidence.

Les URL sont **inchangees** - des clients deployes les appellent - mais elles
deleguent desormais au module `tarification`, avec des schemas nommes et la
bonne permission :

| route | avant | maintenant |
|---|---|---|
| `GET /nomenclature/actes` | `CONSULTATIONS:READ` | `TARIFS:READ` |
| `POST /nomenclature/actes` | `CONSULTATIONS:CREATE` | `TARIFS:WRITE` |

## Routes

Toutes sous `/api/v1/tarification`, toutes paginees, toutes avec un schema nomme.

| methode et chemin | permission |
|---|---|
| `GET /tarification/actes` | `TARIFS:READ` |
| `POST /tarification/actes` | `TARIFS:WRITE` |
| `GET /tarification/actes/{id}` | `TARIFS:READ` |
| `PATCH /tarification/actes/{id}` | `TARIFS:WRITE` |
| `GET /tarification/actes/{id}/tarifs` | `TARIFS:READ` |
| `PUT /tarification/actes/{id}/tarifs` | `TARIFS:WRITE` |
| `DELETE /tarification/actes/{id}/tarifs/{tarif_id}` | `TARIFS:WRITE` |
| `GET /tarification/categories` | `TARIFS:READ` |
| `POST /tarification/categories` | `TARIFS:WRITE` |
| `PATCH /tarification/categories/{code}` | `TARIFS:WRITE` |
| `DELETE /tarification/categories/{code}` | `TARIFS:WRITE` |
| `GET /tarification/organismes` | `ASSURANCE:READ` |
| `POST /tarification/organismes` | `ASSURANCE:WRITE` |
| `GET /tarification/organismes/{id}` | `ASSURANCE:READ` |
| `PATCH /tarification/organismes/{id}` | `ASSURANCE:WRITE` |
| `DELETE /tarification/organismes/{id}` | `ASSURANCE:WRITE` |
| `GET /tarification/patients/{id}/droits` | `ASSURANCE:READ` |
| `POST /tarification/patients/{id}/droits` | `ASSURANCE:WRITE` |
| `PATCH /tarification/droits/{id}` | `ASSURANCE:WRITE` |
| `DELETE /tarification/droits/{id}` | `ASSURANCE:WRITE` |

Il n'y a **pas** de `DELETE` sur un acte. Desactiver est le seul chemin.

## Regles de fond

**Le tarif d'une facture est fige.** `actes_realises.tarif_applique` est ecrit a
l'emission et ce module n'y touche jamais. Modifier le prix d'un acte ne
modifie que `tarifs_actes` et `actes_nomenclature.tarif_base`. Le `PATCH` d'un
acte n'accepte donc **pas** `tarif_base` : un PATCH general qui l'accepterait
finirait par etre appele par une edition d'ecran ordinaire. C'est verifie par
`test_tarification.py::test_un_changement_de_tarif_ne_touche_pas_une_facture`,
et par mutation.

**`tarif_base` reste lu par la facturation en place.** La migration le recopie
dans `tarifs_actes` sous `standard` sans le deplacer ni le supprimer. La
facturation consommera `tarifs_actes` plus tard ; c'est une transition, pas un
dual permanent.

**Une categorite par code, pas par id.** Un tarif se saisit par code de
categorie, et c'est ce code qui apparaitra sur une facture.

**Les contraintes sont dans la base.** Taux hors de 0 a 100, montant negatif,
doublon d'un couple (acte, categorie), suppression d'un organisme porte par un
droit : PostgreSQL refuse. Le service renvoie un message nomme avant cela, parce
qu'un 500 n'apprend rien a personne.

**Une liste est filtree par la base.** Filtrer apres coup d'une page de 50 donne
une page de 3 et un total faux.

**Un tri a toujours une clef secondaire.** `categorie` et `nom` ne sont pas
uniques : sans second critere, PostgreSQL ne promet rien sur l'ordre des ex
aequalo, et une ligne change de page entre deux parcours.

## Ce qui n'est pas fait

**La ventilation assurance / patient d'une facture.** `droits_prise_en_charge`
enregistre qui couvre quoi, mais aucune ligne de facture ne ventile le montant
entre le payeur et le patient. C'est hors perimetre de ce lot, et c'est la
prochaine etape : elle demandera sa propre permission, parce que corriger une
facture emise apres la avoir ventilee n'est pas le meme geste que declarer un
droit.

La prise en charge n'entre donc pas encore dans le calcul d'un montant. Elle est
enregistree, pas appliquee.

## Preuves

- 22 tests dans `Backend/tests/test_tarification.py`.
- Aller-retour `upgrade` / `downgrade` / `upgrade` sur une base jetable, avec
  lecture des compteurs et des contraintes a chaque etape.
- Preuve HTTP sur l'instance de test : 14 appels, 14 resultats attendus, dont
  les 403 de `PRATICIEN` sur `POST /tarification/actes`,
  `PUT /tarification/actes/{id}/tarifs` et `POST /tarification/organismes`.