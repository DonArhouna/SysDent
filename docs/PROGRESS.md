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
## Tarification et prise en charge — chaines livrees, rien d applique
Migration `b3d7f1a9c2e4` (tables de tarification et de prise en charge) et
`c4e7a2b6d9f1` (catalogue : `ASSURANCE:WRITE` devient
`ASSURANCE:WRITE_PATIENT`). Les deux sont ecrites, relues et verifiees sur base
jetable. **Aucune n'est appliquee a une base reelle.**
**Chaine tenant, relue fichier par fichier le 12/10.** Vingt fichiers,
**une seule tete** (`c4e7a2b6d9f1`), **aucune branche**. Chemin sans accroche,
de `f4fb61aa2d24` racine a `c4e7a2b6d9f1`. `b3d7f1a9c2e4.down_revision` vaut
bien `e8b2c4a7d1e5`, et **rien ne s intercale** entre les deux.
**`c4e7a2b6d9f1` enchaine directement apres** : `upgrade head` l'appliquerait
aussi. Pour n'appliquer que `b3d7f1a9c2e4`, nommer la cible.
**Instance de developpement.** Registre : **122 cabinets `ACTIVE`, 19 bases, 5
cabinets dont la base existe, 117 sans base.** Aucune base de cabinet n'est
joignable : identifiants de la ligne `tenants_db`, valeurs par defaut du depot et
ceux du master sont tous refuses sur le meme serveur - meme role, meme mot de
passe, succes vers `sysdent_master` et echec vers une base de cabinet. Regle
d'acces par base, pas secret errone. Cabinet
`sysdent_tenant_clinique_cabinet_sn_5bd215` a `e8b2c4a7d1e5`, 49 tables,
`tarifs_actes` absente : origine des 500, `b3d7f1a9c2e4` lui manque.
**Blocage d'execution.** `alembic.exe` est bloque par une politique de controle
d'application sur la machine du proprietaire. Contournement exclu : ni copie
d'executable, ni modification de politique.
**Preuves** : 32 tests backend dont le tarif fige (mutation : `15000.00 au lieu
de 7500.00`), 10 tests de matrice a deux mutations rouges, 62 tests client verts,
HTTP reel 14/14. Detail : `docs/TARIFICATION.md`.
## Reste à faire
1. **Propriétaire : decider la methode d execution**, `alembic.exe` etant
   bloque par une politique de controle d'application. Aucune commande Alembic
   n'a ete tentee, aucun contournement n'a ete cherche.
2. **Cible explicite obligatoire.** `upgrade head` appliquerait aussi
   `c4e7a2b6d9f1`, qui est hors perimetre de la premiere application. Nommer
   `b3d7f1a9c2e4` comme cible.
3. **Perimetre reel avant toute migration** : 5 cabinets ont une base sur 122
   declares. La liste des 117 sans base doit etre arretee, pas migree.
4. **Acces aux bases de cabinet a retablir** avant tout comptage avant / apres :
   il conditionne la sauvegarde, le controle et l'arret sur ecart.
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
