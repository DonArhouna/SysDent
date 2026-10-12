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
## Tarification — phase 1 **livrée, non appliquée**
Migration `b3d7f1a9c2e4` (chaîne tenant). **Vérifiée sur base jetable,
appliquée nulle part** : le propriétaire valide le plan et le diff avant.
Quatre tables : `categories_patient` (`standard` créée par la migration),
`tarifs_actes` (unique sur `(acte_id, categorie_code)`, catégorie référencée
par son **code**), `organismes_assurance` (assurance et mutuelle ont les mêmes
données ; `type_organisme` porte la différence), `droits_prise_en_charge`.
`CHECK` taux 0-100 et montant non négatif, `RESTRICT` sur un organisme porté par
un droit. La migration reprend `tarif_base` dans `tarifs_actes` sous
`standard` au moment où elle est appliquée : rien n'est déplacé ni supprimé.
Aller-retour `upgrade`/`downgrade`/`upgrade` : 53 tables, aucune résiduelle
après downgrade, actes conservés, type enum supprimé, reprise des 3 actes à
l'identique, quatre contraintes refusées par PostgreSQL.
`TARIFS:READ`/`TARIFS:WRITE` et `ASSURANCE:READ`/`ASSURANCE:WRITE` au
catalogue. `TARIFS:WRITE` : `ADMIN_CABINET` seul. `ASSURANCE:WRITE` aussi
`SECRETAIRE`, qui saisit la carte de mutuelle à la création de fiche — pas les
organismes, pas les taux. **La nomenclature passe sous `TARIFS:*`** : elle
demandait `CONSULTATIONS:READ` et `CONSULTATIONS:CREATE`, donc créer une
consultation suffisait à fixer le prix des actes. URL inchangées, droit changé,
réponses typées (elles étaient en `dict`). Praticiens, assistants, secrétaires
et comptables gardent la lecture : le dentiste doit voir le prix pour le
facturer au patient.
**Preuve** : 22 tests verts, dont le tarif figé (par mutation : `15000.00 au
lieu de 7500.00`). HTTP réel sur l'instance de test : **14 appels, 14 résultats
attendus, 0 écart**, dont les 403 de `PRATICIEN`. 130 tests verts au total.
Routes et matrice : `docs/TARIFICATION.md`.
## Non vérifié
**Backoffice** : `/dashboard` rend dans `AppShell`, la page livrée s'en
oubliait ; deux tests l'exigent, preuve par mutation. **47 tests verts**, le
500 du tableau de bord (`stats.py:354`) est **200 en HTTP**, couple 401/500
écarté par test.
**Rendu navigateur** : jamais contrôlé, checklist
`docs/backoffice/VERIFICATION_NAVIGATEUR.md`. **Pas d'i18n** : ni le client ni
le backoffice n'en ont, **à trancher**. **Suite complète jamais jouée** : 64 %
puis 90 minutes sans finir, cause non établie. **Registre** : 129 lignes sans
base, conservées (décision du propriétaire) ; aucune base migrée.
## Reste à faire
1. **Propriétaire : valider le plan de migration `b3d7f1a9c2e4`, puis le diff.**
2. **Propriétaire : valider la phase 1 par écrit**, avant toute phase 2.
3. Ventilation assurance / patient d'une facture : hors périmètre, non codée. La
   prise en charge est **enregistrée, pas appliquée** au calcul d'un montant.
4. Faire consommer `tarifs_actes` par la facturation ; `tarif_base` reste lu en
   attendant. Transition, pas dual permanent.
5. Phase 2 (menu Tarification, menu Prise en charge) après validation.
6. Rechargement forcé du client, test d'une modification de face,
   `npm run design:parite`, liste des cabinets, puis la cause du
   ralentissement de la suite et le verdict réel.
