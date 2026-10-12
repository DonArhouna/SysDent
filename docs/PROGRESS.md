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
nulle part**. `c4e7a2b6d9f1` aligne le catalogue : elle **n'est pas non plus
appliquee**. Quatre tables : `categories_patient` (`standard` creee par la
migration), `tarifs_actes` (unique sur `(acte_id, categorie_code)`, categorie
referencee par son **code**), `organismes_assurance`, `droits_prise_en_charge`.
`CHECK` taux 0-100 et montant non negatif, `RESTRICT` sur un organisme porte par
un droit. La migration reprend `tarif_base` dans `tarifs_actes` sous
`standard` : rien de deplace. Aller-retour `upgrade`/`downgrade`/`upgrade` et
rejeu sans doublon verifies sur base jetable.
**La nomenclature passe sous `TARIFS:*`** : creer une consultation ne donne plus
le droit de fixer le prix des actes. URL inchangees, reponses typees.

**Matrice assurance, validee et appliquee.** Un droit unique `ASSURANCE:WRITE`
couvrait deux gestes sans rapport. Il est remplace :
`TARIFS:WRITE` pour ecrire un **organisme** (referentiel, admin seul),
`ASSURANCE:WRITE_PATIENT` pour ecrire un **droit de patient** (secretariat et
admin), `ASSURANCE:READ` pour tous. `ASSURANCE:WRITE` a quitte le catalogue :
une session delivree avant ce changement transporte encore ce droit, et elle
n'ecrit plus rien.

**Phase 2** : ecrans `/tarification` et `/prise-en-charge`, onglet de la fiche
patient, filtres dans l'URL, `Pagination` partagee, aucun DELETE sur un acte.

**Preuve** : 32 tests backend dont le tarif fige (mutation : `15000.00 au lieu de
7500.00`), 10 tests de matrice avec **deux mutations rouges**, HTTP reel 14/14.
Cote client **62 tests verts**, `tsc` 0, lint 0 erreur, build vert ; `verifier`
du backoffice vert. Un test lit la source du routeur pour exiger que client et
serveur demandent le meme droit ; il vire au rouge des que l'un change.
**Le schema OpenAPI ne porte pas la borne 0-100 du taux** sur la forme chaine :
`docs/OPERATIONS.md` et le test qui fixe cette limite.
Detail et matrice : `docs/TARIFICATION.md`.
## Reste à faire
1. **Propriétaire : valider et appliquer `b3d7f1a9c2e4`, puis `c4e7a2b6d9f1`.**
   Les deux sont ecrites et verifiees, aucune n'a ete appliquee. La seconde
   retire `ASSURANCE:WRITE` du catalogue : un cabinet qui ne l'applique pas
   garde un droit qui ne protege plus rien.
2. **Tache suivante : la ventilation assurance / patient d'une facture.** Hors
   perimetre des deux phases, non codee. La prise en charge est
   **enregistree, pas appliquee** au calcul d'un montant. Demande une
   permission propre : corriger une facture emise apres l'avoir ventilee n'est
   pas le meme geste que declarer un droit.
3. Faire consommer `tarifs_actes` par la facturation ; `tarif_base` reste lu en
   attendant. Transition, pas dual permanent.
4. Rechargement force du client, test d'une modification de face,
   `npm run design:parite`, liste des cabinets, puis la cause du
   ralentissement de la suite et le verdict reel.
