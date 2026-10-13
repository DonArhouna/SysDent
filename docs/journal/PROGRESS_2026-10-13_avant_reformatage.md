# SysDent Pro — état de reprise
> Ce qui est **prouvé**, et sa preuve. Détail : `docs/journal/`, et
> `git log -p -- docs/PROGRESS.md`.
## ACCÈS
Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la tête `e8b2c4a7d1e5`,
login **200**. Aucun compte réel n'a jamais été utilisé. Le 500 du login avait **deux causes** : le
conteneur arrêté, et deux défauts de code, une connexion pas encapsulée par SQLAlchemy et une erreur
de schéma **deux niveaux** sous `ProgrammingError` : 500 -> 503.
## Défauts d'interface, tous nommés
Cinq 422 et un 403, une famille : **le garde existait ailleurs dans le fichier et n'était pas
branché**. Odontogramme : cinq états écrits en dur, dont `SOIGNEE` que `ETATS_DENT` refuse, et
l'état par défaut étant accepté, il fallait *changer* une lésion pour y tomber ; `face` devient
`CodeFace`. Consultation : `cabinet_id: ''` quand aucun site n'est résolu, motif vide refusé par
`min_length=2`.
## Tests : instance dédiée
Instance `sysdent_test_pg`, port **55436**, **tmpfs**, base-témoin `sysdent_instance_test_marker`.
`settings` réorienté **avant tout import de `src`**, garde vérifiant que la redirection a pris.
**Fuite de bases** : `BASES_CREEES_PAR_LA_SESSION` était déclaré deux fois, un `set` puis une `list`
; le second écrasait le premier, d'où 16 bases par exécution, ramenées à **5 avant et après trois
exécutions, 0 erreur.** Les tests de supervision **fabricent leurs propres cas**.
## Tarification et prise en charge : chaînes livrées, rien d'appliqué
`b3d7f1a9c2e4` (4 tables de tarification et de prise en charge) et `c4e7a2b6d9f1` (catalogue :
`ASSURANCE:WRITE` devient `ASSURANCE:WRITE_PATIENT`) sont écrits, relus et vérifiés sur base
jetable. **Aucune n'est appliquée à une base réelle.**



**Chaîne tenant, relue fichier par fichier le 12/10.** Vingt fichiers, **une seule tête**
(`c4e7a2b6d9f1`), **aucune branche**. `b3d7f1a9c2e4.down_revision` vaut bien `e8b2c4a7d1e5`, **rien
ne s'intercale**, et `c4e7a2b6d9f1` **enchaine directement après** : `upgrade head` l'appliquerait,
il faut nommer la cible.
## Sauvegarde, mesures et dossier de décision, le 12/10
**Sauvegarde, mesures et dossier de décision, le 12/10.** Sauvegarde fraîche **hors dépôt et hors
synchronisation**, volume local `C:` : `C:\sauvegardes_sysdent\cabinet_5bd215_2026-10-12_1844\`.
Archive `cabinet_5bd215.dump`, 262.6 Ko, code de sortie 0, **`pg_restore -l` lisible, 399 entrées**,
SHA-256 `1818375ceabe64141bbfeb2a78aaf095848af02385d1b49dd6903a77ab97f6b3`. Dumps antérieurs
intouchés.

**Référence avant écriture** : `e8b2c4a7d1e5`, 49 tables, **patients 33, utilisateurs 11,
consultations 31, factures 43**, 53 lignes de facture, 6 rôles, 45 permissions, 99 liens, 14 actes.
**`tarif_base` et `actes_realises.tarif_applique` présentes**, 4 tables de tarification absentes.
**0 permission du module `ASSURANCE`** : aucun lien `ASSURANCE:WRITE` à reporter. Mesures complètes,
sans donnée personnelle : `MESURES_ETAT_ACTUEL.txt`.

**Dossier de décision hors dépôt** : `DEMANDE_AUTORISATION_ALEMBIC.md`, même dossier. Motif, chemin
de l'exécutable bloqué, commande nommant la cible, garanties, exclusions. Aucun mot de passe ni
identifiant.

**Tentative refusée.** Autorisation écrite reçue le 12/10, puis `alembic.exe` bloqué par la
stratégie de contrôle d'application, sans contournement. **Base intacte** : `e8b2c4a7d1e5`, 49
tables, 11 utilisateurs, 33 patients, 31 consultations, 43 factures. `b3d7f1a9c2e4` toujours non
appliquée.

**Écart de schéma, réponse contrôlée.** Les 500 de `/tarification/*` venaient des tables
absentes, reproduit sur l'instance de test. Le triage, jusqu'ici limité au login, est devenu global
: `src/core/schema_perime.py`. Un écart de schéma répond **503 `SCHEMA_EN_RETARD`**, jamais 500. Le
journal porte le cabinet et la table manquante, la réponse n'en dit rien. Le client affiche un
message nommant la mise à jour du schéma, avec « Réessayer » et sans bouton d'écriture. 8 tests
backend et 6 client, chacun avec mutation rouge, plus preuve HTTP 503 sur base jetable.
Antérieurement : 32 tests backend, 62 client, HTTP réel 14/14. Voir `docs/TARIFICATION.md`. **Route
Stock hors de la coquille, corrigée.** `/stock/fournisseurs` était sans `AppShell` : la page prenait
tout l'écran. Une route sur trois, les deux autres correctes. Test structurel sur `App.tsx`, rouge
avant et dès qu'on retire une enveloppe. **Rendu non vérifié.** **Scrollbar fine, en tokens.** Règle
écrite pour les deux moteurs : Firefox lit `scrollbar-width` et `scrollbar-color`, Chromium et
Safari le pseudo-élément. Poignée de 8 px, survol par token, déclarée dans `:root` **et** `.dark`
avec des valeurs différentes. 7 tests. **Rendu non vérifié.**
## Sécurité : valeurs retirées du dépôt
Le dépôt est public. Un inventaire a compté les valeurs sans jamais les afficher : 3 valeurs
concrètes dans `.env.example` et `_create_cabinet.py`, 13 occurrences du défaut de développement
connu dans 5 fichiers. Toutes sont remplaces par un gabarit explicite, ou le fichier est retire du
suivi. **Zéro occurrence dans l'arbre suivi.** Rotation des mots de passe : faite par le
propriétaire, hors agent. Réécriture d'historique : **non décidée, non faite**, et elle ne protège
pas les clones existants. Les valeurs par défaut de `config.py` restent à retirer, avec tests de
démarrage. Retirés du suivi, **présents sur disque** : `Backend/COMMANDS.md`,
`RAPPORT_AVANCEMENT_SysDent.md`, `Backend/_create_cabinet.py`. Les deux documents portaient une
typographie que le crochet refuse ; le script porte un mot de passe d'administrateur en clair.
## Cabinet 5bd215, état réel
Révisions appliquées le 13/10 par le propriétaire : `b3d7f1a9c2e4`, puis `c4e7a2b6d9f1`, puis
`f1a7c3d90b28`, puis `d6a1f4c92b57`. Contrôlé : 33 patients, 12 utilisateurs, 31 consultations, 43
factures, compte réel présent, `TARIFS:WRITE` au seul `ADMIN_CABINET`, `ASSURANCE:WRITE_PATIENT` au
seul `SECRETAIRE`, 0 doublon. Sauvegarde de référence `cabinet_5bd215_2026-10-13_1430`, SHA-256
`0bc72666...c08`. Chaîne tenant, tête en dernier : `e8b2c4a7d1e5`, `b3d7f1a9c2e4`, `c4e7a2b6d9f1`,
`f1a7c3d90b28`, `d6a1f4c92b57`, `c8b2e5f1a73d` (notifications, **non appliquée**). Politique
`alembic.exe` : exécution **autorisée constatée le 13/10**, à signaler à l'administrateur. Contrôle
HTTP et rendu navigateur : non faits.
## Reste à faire
1. **Catalogue des permissions, correctif écrit, non appliqué.** L'écran Rôles et Permissions rend
   `GET /rbac/permissions`, qui lit la table `permissions` : sur le cabinet, **45 permissions, zéro
   `TARIFS:*` ni `ASSURANCE:*`**, aucune migration ne les inscrivait. La révision **`f1a7c3d90b28`**
   les sème, idempotente, `downgrade` inclus, après `c4e7a2b6d9f1` : posée sur `b3d7f1a9c2e4`, elle
   aurait créé une branche et deux têtes. Chaîne relue : 21 révisions, une seule tête. **Ordre
   d'application : `b3d7f1a9c2e4`, puis `c4e7a2b6d9f1`, puis `f1a7c3d90b28`.** Fixture semée par le
   service du provisionnement, test de parité vert. **Aller-retour non fait** : `alembic.exe` bloqué
   par la politique, aucune jetable créée.
2. **Propriétaire : trancher l'exécution** de `b3d7f1a9c2e4`, bloquée par la politique du poste.
   **Cible explicite obligatoire** : `upgrade head` emporterait aussi `c4e7a2b6d9f1`.
3. **Périmètre réel avant toute migration** : 5 cabinets ont une base sur 122 déclarés, les 117
   autres seront arrêtés, pas migrés. Accès aux bases à rétablir avant tout comptage.
4. **Ventilation assurance / patient d'une facture** : hors périmètre, non codée. La prise en charge
   est **enregistrée, pas appliquée** au calcul d'un montant. Demande une permission propre :
   corriger une facture émise après l'avoir ventilée n'est pas le même geste qu'un droit.
5. Faire consommer `tarifs_actes` par la facturation, `tarif_base` restant lu en attendant :
   transition, pas dual permanent. Puis rechargement client, modification d'une face, parité.
