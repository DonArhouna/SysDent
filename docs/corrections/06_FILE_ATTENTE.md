# Étape 2 — File d'attente (salle d'attente) : plan d'exécution

> Ce plan est écrit **avant** toute modification de la base. Aucune migration n'est
> appliquée tant que ce document n'est pas suivi du cycle
> sauvegarde → test sur copie → application.

## 1. Le parcours qu'on veut rendre possible

C'est le cœur du rôle de secrétaire, aujourd'hui inexistant comme fonctionnalité.

1. Le patient arrive au cabinet. La secrétaire **valide son arrivée**.
2. Il entre dans la file du site.
3. Le dentiste **appelle** le patient suivant.
4. La consultation démarre : elle est créée avec **l'utilisateur connecté** comme
   `auteur_id` (jamais un dentiste choisi depuis le client).
5. Le patient part : `termine`.

## 2. État actuel — ce qui existe déjà

| Élément | État |
|---|---|
| `StatutRendezVousEnum.EN_SALLE_ATTENTE` | **existe** — le rendez-vous sait dire « en salle d'attente » |
| `rendez_vous.statut` → passage `EN_SALLE_ATTENTE` | existe |
| Table de file d'attente | **inexistante** |
| Enregistrement d'une arrivée **sans rendez-vous** (patient qui passe) | **inexistant** — c'est le cas le plus fréquent dans un cabinet |
| Ordre de passage, temps d'attente | **inexistants** |
| Écran | **inexistant** |

**Conclusion : la migration est nécessaire.** On ne peut pas faire tenir une file
d'attente dans le seul statut d'un rendez-vous : un patient sans rendez-vous n'a
aucune ligne où entrer, et l'ordre de passage ne peut pas se déduire d'un statut.

## 3. Modèle — table `file_attente`

Une entrée par passage en salle d'attente, rattachée au **site** (`cabinets.id`).

| Colonne | Type | Rôle |
|---|---|---|
| `id` | UUID PK | |
| `patient_id` | UUID → `patients.id`, `ondelete=CASCADE`, index | qui attend |
| `dossier_medical_id` | UUID → `dossiers_medicaux.id`, `ondelete=CASCADE`, index | permet de créer la consultation sans rejouer la jointure |
| `cabinet_id` | UUID → `cabinets.id`, `ondelete=CASCADE`, **index**, NOT NULL | le site : **frontière d'isolation** |
| `rendez_vous_id` | UUID → `rendez_vous.id`, `ondelete=SET NULL`, **unique**, nullable | le RDV honoré, si aucun |
| `statut` | enum `EN_ATTENTE` / `APPele` / `EN_CONSULTATION` / `TERMINE` / `ABSENT` / `ANNULE`, index | |
| `heure_arrivee` | `timestamptz` NOT NULL, index | base du temps d'attente |
| `ordre_passage` | `Integer` NOT NULL | **ordre d'arrivée**, convenu avec le propriétaire |
| `prioritaire` | `Boolean` default false | urgence déclarée par l'accueil |
| `motif_urgence` | `Text` nullable | pourquoi, en clair |
| `dentiste_id` | UUID → `utilisateurs.id`, `ondelete=SET NULL`, index, nullable | destinataire — **un utilisateur, pas un `praticiens`** |
| `consultation_id` | UUID → `consultations.id`, `ondelete=SET NULL`, nullable, unique | consultation créée au démarrage |
| `appele_par_id` / `appele_par_email` | UUID / varchar | traçabilité de l'appel |
| `appele_le` | `timestamptz` nullable | début du temps d'attente en salle |
| `termine_le` | `timestamptz` nullable | |
| `notes` | `Text` nullable | |

Contrainte d'intégrité : **au plus une entrée active par patient et par site**.
Implémentée par un index unique partiel :

```sql
CREATE UNIQUE INDEX uq_file_attente_active
  ON file_attente (patient_id, cabinet_id)
  WHERE statut IN ('EN_ATTENTE', 'APPele', 'EN_CONSULTATION');
```

Pourquoi une contrainte en base et non dans le service : deux secrétaires qui
enregistrent une arrivée au même instant ne passent pas par le même code Python —
la seule garantie fiable est la base.

### Index

- `(cabinet_id, statut, ordre_passage)` — **la requête de la salle d'attente**
- `(heure_arrivee)` — purge des entrées anciennes

### Chois d'architecture

**Ordre d'arrivée, pas de score de priorité.** Décidé avec le propriétaire : il
doit être vérifiable à l'œil. Un score composite (urgence × ancienneté × RDV)
produirait un ordre que personne ne sait expliquer à un patient qui attend depuis
une heure. L'urgence se gère par `prioritaire` + `ordre_passage` remonté
manuellement par la secrétaire (glisser-déposer), donc toujours explicite.

**Le destinataire est un `utilisateurs.id`**, jamais un `praticiens.id`. C'est la
conséquence directe de la décision « le dentiste est un utilisateur » : le jour de
la fusion (étape 5), il n'y aura rien à migrer dans cette colonne.

**Pas de score, pas deWeights, pas de minuterie serveur.** Le temps d'attente est
calculé à la lecture à partir de `heure_arrivee`.

## 4. Permissions

Nouveau module `ATTENTE` dans le catalogue, avec les actions :

| Action |Qui | Pourquoi |
|---|---|---|
| `ATTENTE:READ` | secrétaire, dentiste, admin | voir la file |
| `ATTENTE:CREATE` | secrétaire, admin | enregistrer une arrivée |
| `ATTENTE:UPDATE` | secrétaire, admin | réordonner, retirer, marquer absent |
| `ATTENTE:CALL` | dentiste, admin | appeler le patient suivant |

**Le caissier n'en a aucune.** Il a besoin de « patients terminés à régler », ce
qui n'est pas la file d'attente : c'est une liste de **factures non soldées**. Il
lira donc `/factures?statut=...`, pas `/attente`. Conséquence : **aucun contenu
clinique** dans la file, même pour les rôles qui y ont accès — seuls nom, prénom,
numéro de dossier, motif d'arrivée et heure.

Matrice à écrire :

```python
"ATTENTE": [READ, CREATE, UPDATE],        # secrétaire
"PRATICIEN": [..., READ, CALL],           # médecin : voit et appelle
"ADMIN_CABINET": (joker, rien à ajouter)  # tout le catalogue sauf exclusions
```

## 5. Endpoints

| Méthode | Route | Permission | Effet |
|---|---|---|---|
| `POST` | `/attente/arriver` | `ATTENTE:CREATE` | enregistre l'arrivée (avec ou sans `rendez_vous_id`), calcule `ordre_passage` |
| `GET` | `/attente` | `ATTENTE:READ` | file du site : `?cabinet_id=&statut=&limit=` |
| `POST` | `/attente/{id}/appeler` | `ATTENTE:CALL` | `EN_ATTENTE` → `APPele`, horodate |
| `POST` | `/attente/{id}/demarrer` | `CALL` + `CONSULTATIONS:CREATE` | crée la consultation avec `auteur_id` **issu du jeton**, `EN_CONSULTATION` |
| `POST` | `/attente/{id}/terminer` | `CALL` | → `TERMINE`, rend le patient au parcours de facturation |
| `POST` | `/attente/{id}/absent` | `ATTENTE:UPDATE` | → `ABSENT` |
| `PATCH` | `/attente/ordre` | `ATTENTE:UPDATE` | réordonnancement par liste d'ids |

### Concurrence — « deux dentistes appellent le même patient »

Le test demandé par le mission. La réponse doit être **424 / 409**, pas un
écrasement silencieux : si le patient est déjà `APPele` ou `EN_CONSULTATION`, le
second appelant reçoit une erreur explicite. Implémentation : `SELECT … FOR UPDATE`
sur la ligne + relecture du statut dans la même transaction, puis refus si le
statut a changé. Un simple « relire puis écrire » laisserait passer la fenêtre
entre les deux.

### Isolation

- Inter-sites : `cabinet_id` filtré par les sites accessibles à l'utilisateur.
- Inter-tenant : la base est par tenant, l'isolation est structurelle. Un contrôle
  reste obligatoire : un `patient_id` appartenant à un autre site doit être refusé
  (`422`), pas créer une ligne orpheline.
- `dentiste_id` doit appartenir au même tenant **et** porter un profil de dentiste ;
  sinon `422`.

## 6. Écrans

**Salle d'attente** (`/attente`), deux usages selon les permissions :

- **secrétaire** : *Enregistrer une arrivée* (recherche patient, RDV optionnel,
  case « urgence »), réordonnancement par glisser-déposer, badges de statut,
  retrait / absent
- **dentiste** : sa file, bouton **Appeler** puis **Démarrer la consultation**,
  temps d'attente affiché en direct

Design system existant (cartes, badges, deux thèmes), responsive tablette, i18n,
polling court (~10 s) sur la liste — plus simple et plus robuste qu'un WebSocket
que l'on ne peut pas tester ici.

## 7. Déroulé d'exécution — l'ordre est obligatoire

1. **Plan** — ce document.
2. **Sauvegarde** — `docker exec sysdent_s0b pg_dump` de la base de démo vers
   `%LOCALAPPDATA%\Temp\opencode\`. Consigner le nom du fichier.
3. **Test sur copie** — restaurer la sauvegarde dans une base `*_copie`, appliquer
   la migration dessus, vérifier : création de la table, index, contrainte
   partielle, et que les 344 tests passent sur la copie.
4. **Application** — seulement si l'étape 3 est verte.
5. **Non-régression** — suite complète sur la base de démo d'origine.

## 8. Tests à écrire

| Test | Preuve |
|---|---|
| arrivée avec RDV / sans RDV | les deux cas du cabinet réel |
| ordre de passage | ordre d'arrivée respecté, priorité manuelle respectée |
| appel → démarrer → terminer | le parcours complet, consultation créée avec l'`auteur_id` du jeton |
| **deux dentistes appellent le même patient** | le second reçoit une erreur, pas un écrasement |
| patient déjà dans la file | refus, contrainte unique respectée |
| isolation inter-sites | file d'un site non lisible depuis un autre |
| permissions par rôle | secrétaire / dentiste / caissier / admin |
| temps d'attente | calculé, pas stocké |

## 9. Réversible

`downgrade()` = `DROP TABLE file_attente`. La table ne touche aucune donnée
existante : elle est **purement additive**. Les seules écritures possibles sont
les arrivées, qu'on peut exporter avant.

## 10. Risques assumés

| Risque | Traitement |
|---|---|
| `ON DELETE CASCADE` sur `patient_id` : supprimer un patient efface son historique de passage en salle | acceptable — même comportement que le reste du schéma patient, et cohérent avec le RGPD (droit à l'effacement) |
| la migration n'est pas couverte par les tests automatisés du dépôt (les tests tournent sur la base de démo déjà migrée) | d'où l'étape 3 : le seul contrôle fiable est le test sur copie |