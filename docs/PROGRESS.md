# SysDent Pro — état de reprise
> Ce qui est **prouvé**, et sa preuve. Détail : `docs/journal/`, et
> `git log -p -- docs/PROGRESS.md`.
## ACCÈS
Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la
tête `e8b2c4a7d1e5`, login **200**. Aucun compte réel n'a jamais été utilisé. Le
500 du login avait **deux causes** : le conteneur arrêté, action du propriétaire,
et deux défauts de code, une connexion pas encapsulée par SQLAlchemy et une
erreur de schéma **deux niveaux** sous `ProgrammingError`. 500 -> 503.
## Défauts d'interface, tous nommés
Cinq 422 et un 403, une famille : **le garde existait ailleurs dans le fichier
et n'était pas branché**. Prouvé par lecture, vérifié par test.
- Odontogramme : cinq états écrits en dur, dont `SOIGNEE` que `ETATS_DENT`
  refuse. **L'état par défaut étant accepté, il fallait *changer* une lésion**
  pour y tomber ; les états viennent de `referentielEtats`. Quatre faces hors
  nomenclature, `face` devient `CodeFace` : une faute devient une erreur.
- Consultation : `cabinet_id: ''` quand aucun site n'est résolu, impossible
  sans `CABINETS:READ` ; motif vide, refusé par `min_length=2`.
- Dashboard : `litCabinets` calculé mais jamais câblé sur le `enabled`
  (`dashboard.tsx:244`) ; agenda : praticiens sans `PRATICIENS:READ`.
  Déconnexion volontaire : tableau de bord ; expiration : route restituée.
  **Aucun rendu navigateur déclaré.**
## Tests : instance dédiée
Instance `sysdent_test_pg`, port **55436**, **tmpfs**, base-témoin
`sysdent_instance_test_marker`. `settings` réorienté **avant tout import de
`src`**, garde vérifiant que la redirection a pris ; quatre refus cumulatifs.
**Fuite de bases** : `BASES_CREEES_PAR_LA_SESSION` était déclaré deux fois, un
`set` puis une `list` ; le second écrasait le premier, d'où 16 bases par
exécution, ramenées à **5 avant et après trois exécutions, 0 erreur.** Les
tests de supervision **fabricent leurs propres cas** : l'un passait à vide.
## Tarification et prise en charge : chaînes livrées, rien d'appliqué
`b3d7f1a9c2e4` (4 tables de tarification et de prise en charge) et `c4e7a2b6d9f1`
(catalogue : `ASSURANCE:WRITE` devient `ASSURANCE:WRITE_PATIENT`) sont écrits,
relus et vérifiés sur base jetable. **Aucune n'est appliquée à une base réelle.**
**Chaîne tenant, relue fichier par fichier le 12/10.** Vingt fichiers, **une
seule tête** (`c4e7a2b6d9f1`), **aucune branche**. `b3d7f1a9c2e4.down_revision`
vaut bien `e8b2c4a7d1e5`, **rien ne s'intercale**, et `c4e7a2b6d9f1` **enchaine
directement après** : `upgrade head` l'appliquerait, il faut nommer la cible.
**Instance de développement.** Registre : **122 cabinets `ACTIVE`, 19 bases,
5 dont la base existe, 117 sans base.** Aucune base de cabinet n'est
joignable, avec le même rôle et le même mot de passe que le master :
règle d'accès par base, pas secret erroné.
## Sauvegarde, mesures et dossier de décision, le 12/10
Sauvegarde fraîche **hors dépôt et hors synchronisation**, volume local `C:` :
`C:\sauvegardes_sysdent\cabinet_5bd215_2026-10-12_1844\`. Archive
`cabinet_5bd215.dump`, 262.6 Ko, code de sortie 0, **`pg_restore -l` lisible,
399 entrées**, SHA-256 `1818375ceabe64141bbfeb2a78aaf095848af02385d1b49dd6903a77ab97f6b3`.
Les 4 tables de tarification y sont absentes : l'archive confirme l'état. Dumps
antérieurs intouchés.
**Référence avant écriture** : `e8b2c4a7d1e5`, 49 tables, **patients 33,
utilisateurs 11, consultations 31, factures 43**, 53 lignes de facture, 6 rôles,
45 permissions, 99 liens, 14 actes. **`tarif_base` et
`actes_realises.tarif_applique` présentes**, 4 tables de tarification absentes.
**0 permission du module `ASSURANCE`** : aucun lien `ASSURANCE:WRITE` à reporter
ici. Mesures complètes, sans donnée personnelle : `MESURES_ETAT_ACTUEL.txt`.
**Dossier de décision hors dépôt** : `DEMANDE_AUTORISATION_ALEMBIC.md`, même
dossier. Motif, chemin de l'exécutable bloqué, commande nommant la cible,
garanties, exclusions. Aucun mot de passe ni identifiant : accès par le
socket local du conteneur `sysdent_s0b`.
**Blocage d'exécution** : `alembic.exe` bloqué par une politique de contrôle
d'application chez le propriétaire ; contournement exclu, ni copie d'exécutable
ni modification de politique. **Aucune commande Alembic tentée.**
**Preuves** : 32 tests backend dont le tarif figé (mutation : `15000.00` au
lieu de `7500.00`), 10 de matrice à deux mutations rouges, 62 client verts,
HTTP réel 14/14. Détail : `docs/TARIFICATION.md`.
## Reste à faire
1. **Propriétaire : décider la méthode d'exécution.** Dossier prêt, rien
   d'appliqué, en attente d'une décision écrite.
2. **Cible explicite obligatoire** : `upgrade head` emporterait aussi
   `c4e7a2b6d9f1`, hors périmètre de la première application.
3. **Périmètre réel avant toute migration** : 5 cabinets ont une base sur 122
   déclarés ; les 117 sans base seront arrêtés, pas migrés. Accès aux bases à
   rétablir avant tout comptage avant et après.
4. **Ventilation assurance / patient d'une facture** : hors périmètre, non
   codée. La prise en charge est **enregistrée, pas appliquée** au calcul d'un
   montant. Demande une permission propre : corriger une facture émise après
   l'avoir ventilée n'est pas le même geste que déclarer un droit.
5. Faire consommer `tarifs_actes` par la facturation, `tarif_base` restant lu en
   attendre : transition, pas dual permanent. Puis rechargement forcé du client,
   modification d'une face, `npm run design:parite`, liste des cabinets.