# SysDent Pro — état de reprise
> Ce qui est **prouvé**, et sa preuve. Détail : `docs/journal/`, et
> `git log -p -- docs/PROGRESS.md`.
## ACCÈS
Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la
tête `e8b2c4a7d1e5`, login **200**. Aucun compte réel n'a jamais été utilisé.
Le 500 du login avait **deux causes** : le conteneur de développement arrêté
(action du propriétaire), et deux défauts de code — un échec de connexion pas
encapsulé par SQLAlchemy, et une erreur de schéma **deux niveaux** sous le
`ProgrammingError`, que le tri n'examinait pas. 500 -> 503.
## Défauts d'interface, tous només
Cinq 422 et un 403, une famille : **le garde existait ailleurs dans le fichier
et n'était pas branché**. Prouvé par lecture, vérifié par test.
- Odontogramme : cinq états écrits en dur, dont `SOIGNEE` que `ETATS_DENT`
  refuse. **L'état par défaut étant accepté, il fallait *changer* une lésion**
  pour tomber dessus — le geste du praticien. Les états viennent de
  `referentielEtats`. Également quatre faces hors nomenclature, et `face`
  devient le type `CodeFace` : une faute devient une erreur de compilation.
- Consultation : `cabinet_id: ''` quand aucun site n'est résolu — impossible
  sans `CABINETS:READ` ; motif vide, refusé par `min_length=2`.
- Dashboard : `litCabinets` calculé mais jamais câblé sur le `enabled`
  (`dashboard.tsx:244`). Agenda : praticiens listés sans `PRATICIENS:READ`.
- Après déconnexion volontaire la connexion va au tableau de bord, après
  expiration elle restitue la route. **Aucun rendu navigateur déclaré.**
## Tests : instance dédiée
Instance `sysdent_test_pg`, port **55436**, **tmpfs**, base-témoin
`sysdent_instance_test_marker`. `settings` réorienté **avant tout import de
`src`**, garde vérifiant que la redirection a pris ; quatre refus cumulatifs.
**Fuite de bases** : `BASES_CREEES_PAR_LA_SESSION` était déclaré deux fois (un
`set`, puis une `list`) ; le second écrasait le premier, d'où 16 bases par
exécution. Après correction : **5 bases avant et après trois exécutions, 0
erreur.** Les tests de supervision **fabricent leurs propres cas** : l'un
passait à vide, donc vert pour la mauvaise raison.
## Tarification et prise en charge — phases 1 et 2 livrees
Migration `b3d7f1a9c2e4` (chaine tenant), **verifiee sur base jetable, appliquee
nulle part** : le proprietaire valide le plan et le diff avant. Quatre tables :
`categories_patient` (`standard` creee par la migration), `tarifs_actes` (unique
sur `(acte_id, categorie_code)`, categorie referencee par son **code**),
`organismes_assurance`, `droits_prise_en_charge`. `CHECK` taux 0-100 et montant
non negatif, `RESTRICT` sur un organisme porte par un droit. La migration
reprend `tarif_base` dans `tarifs_actes` sous `standard` : rien de deplace.
Aller-retour `upgrade`/`downgrade`/`upgrade` : 53 tables, aucune residuelle, actes
conserves, type enum supprime, reprise des 3 actes a l'identique, quatre
contraintes refusees par PostgreSQL.
**La nomenclature passe sous `TARIFS:*`** : elle demandait `CONSULTATIONS:READ`
et `CONSULTATIONS:CREATE`, donc creer une consultation suffisait a fixer le prix
des actes. URL inchangees, droit change, reponses typees (elles etaient en
`dict`). Praticiens, assistants, secretaires et comptables gardent la lecture.
**Phase 2** : ecrans `/tarification` et `/prise-en-charge`, onglet de la fiche
patient, filtres dans l'URL, `Pagination` partagee, aucun DELETE sur un acte.
`Backoffice/openapi.json` et ses types regenres : ils dataient d'avant les dix
routes de la phase 1, donc son « contrat a jour » pouvait passer a cote.

**Preuve** : 22 tests backend dont le tarif fige (mutation : `15000.00 au lieu de
7500.00`), HTTP reel 14/14. Cote client 40 nouveaux tests, **deux mutations
rouges** (un `tarif_base` au PATCH, une garde de bouton retiree), **56 tests
verts**, `tsc` 0, lint 0 erreur, build vert, `verifier` du backoffice vert.
Une limite mesuree : le schema OpenAPI ne porte **pas** la borne 0-100 du taux
sur la forme chaine - le motif verifie la forme, pas la valeur. Pydantic
l'applique. Test qui le fixe.
Detail et matrice : `docs/TARIFICATION.md`.
## Reste à faire
1. **Propriétaire : valider le plan de migration `b3d7f1a9c2e4`, puis le diff.**
2. **Propriétaire : trancher l'ecart de matrice signale.** Le serveur accorde
   `ASSURANCE:WRITE` au secretariat sur les organismes ; l'ecran utilise
   `TARIFS:WRITE` (admin seul). Le client est plus strict que le backend.
3. **Tache suivante : la ventilation assurance / patient d'une facture.**
   Hors perimetre des deux phases, non codee. La prise en charge est
   **enregistree, pas appliquee** au calcul d'un montant. Demande une
   permission propre : corriger une facture emise apres l'avoir ventilee n'est
   pas le meme geste que declarer un droit.
4. Faire consommer `tarifs_actes` par la facturation ; `tarif_base` reste lu en
   attendant. Transition, pas dual permanent.
5. Rechargement force du client, test d'une modification de face,
   `npm run design:parite`, liste des cabinets, puis la cause du
   ralentissement de la suite et le verdict reel.
