# SysDent Pro — état de reprise
> Ce qui est **prouvé**, et sa preuve. Détail et historique : `docs/journal/`, et
> `git log -p -- docs/PROGRESS.md`.
## Cabinet 5bd215, état réel
Révisions appliquées le 13/10 par le propriétaire, dans cet ordre : `b3d7f1a9c2e4`,
`c4e7a2b6d9f1`, `f1a7c3d90b28`, `d6a1f4c92b57`. Contrôlé par SQL : **33 patients, 12
utilisateurs, 31 consultations, 43 factures**, compte réel présent et actif,
**`TARIFS:WRITE` au seul `ADMIN_CABINET`**, **`ASSURANCE:WRITE_PATIENT` au seul
`SECRETAIRE`**, **0 doublon** de lien, table de provenance présente.
Sauvegarde de référence `cabinet_5bd215_2026-10-13_1430`, SHA-256 `0bc72666...c08`.
Chaîne tenant, tête en dernier : `e8b2c4a7d1e5`, `b3d7f1a9c2e4`, `c4e7a2b6d9f1`,
`f1a7c3d90b28`, `d6a1f4c92b57`, `c8b2e5f1a73d` (notifications, **non appliquée**).
**Jamais `upgrade head`** : la cible se nomme, sinon la révision suivante part avec.
Politique `alembic.exe` : exécution **autorisée constatée le 13/10**, à signaler à
l'administrateur, qui l'avait bloquée les semaines précédentes.
## Sécurité
Inventaire effectué **sans jamais afficher de valeur** : 3 valeurs concrètes dans
`.env.example` et `_create_cabinet.py`, 13 occurrences du défaut de développement
connu dans 5 fichiers. Toutes remplacées par un gabarit, ou le fichier retiré du
suivi. **Zéro occurrence dans l'arbre suivi.** Rotation des mots de passe : faite
par le propriétaire, hors agent. **Réécriture d'historique : non décidée, non
faite** ; elle ne protège d'ailleurs pas les clones déjà faits.
Retirés du suivi, **présents sur disque** (`e478085`) : `Backend/COMMANDS.md`,
`RAPPORT_AVANCEMENT_SysDent.md` (typographie refusée par le crochet),
`Backend/_create_cabinet.py` (mot de passe d'administrateur en clair).
**Valeurs par défaut de `config.py` à retirer**, avec tests de démarrage : elles
valent `changer-moi`, donc l'application démarrerait encore avec un mot de passe
de développement.
## Prouvé, corrections livrées
**Écart de schéma.** Les 500 de `/tarification/*` venaient des tables absentes,
reproduit sur l'instance de test. Le triage, limité au login, est devenu global
(`src/core/schema_perime.py`) : un écart répond **503 `SCHEMA_EN_RETARD`**, jamais
500. Le journal porte le cabinet et la table manquante, la réponse n'en dit rien.
Le client affiche un message nommant la mise à jour du schéma, avec « Réessayer »
et sans bouton d'écriture. 8 tests backend et 6 client, **chacun avec mutation
rouge**, plus preuve HTTP 503 sur jetable.
**Catalogue.** `GET /rbac/permissions` lit la table `permissions` : le client
n'invente rien. Aucune migration n'inscrivait `TARIFS:*` ni `ASSURANCE:READ`, et
`semer_permissions` n'est appelé qu'au provisionnement. Corrigé par `f1a7c3d90b28`,
puis `d6a1f4c92b57` pour le secrétariat, dont le lien n'avait jamais été reporté.
**Rattachement.** Prouvé sur jetable : cas A lien absent ajouté puis retiré au
`downgrade`, rejeu sans doublon ; cas B lien préexistant conservé à l'`upgrade`
**et** au `downgrade`. Le `downgrade` ne retire que ce qu'il a ajouté, grâce à
une table de provenance.
**Route Stock.** `/stock/fournisseurs` était déclarée sans `AppShell` : la page
prenait tout l'écran. Une route sur trois, les deux autres correctes. Test
structurel sur `App.tsx`, rouge avant et dès qu'on retire une enveloppe.
**Scrollbar.** Règle écrite pour les deux moteurs : Firefox lit `scrollbar-width`
et `scrollbar-color`, Chromium et Safari le pseudo-élément. Poignée de 8 px,
survol par token, déclarée dans `:root` **et** `.dark` avec des valeurs
différentes. 7 tests, **aucune couleur en dur**.
**Défauts d'interface.** Cinq 422 et un 403 : **le garde existait dans le fichier
mais n'était pas branché**. Odontogramme : `SOIGNEE` que `ETATS_DENT` refuse, et
l'état par défaut étant accepté il fallait *changer* une lésion pour y tomber.
**Tests.** Instance `sysdent_test_pg`, port **55436**, **tmpfs**. `settings`
réorienté **avant tout import de `src`**, garde vérifiant la redirection. Fuite de
bases corrigée : **5 avant et après trois exécutions, 0 erreur.** Les tests de
supervision **fabricent leurs propres cas**.
## Non vérifié
- **Contrôle HTTP** sur `5bd215` après les révisions : non fait.
- **Rendu navigateur** : aucun. Aucun pixel vu, en clair comme en sombre.
- **Notifications** : table écrite et prouvée sur jetable, routes et navbar
  absentes. **Émetteurs en attente de décision** sur types et destinataires.
- **Phase B, pagination** : garde backend en place, 6 routes en `xfail` strict
  (`/cabinets`, `/praticiens`, disponibilités, `/alertes`, médicaments,
  `/societes`), 9 listes bornées justifiées par écrit. Routes et écrans non
  paginés. **Décision en attente** sur `/societes`, qui relève de la plateforme.
## Décisions en attente du propriétaire
1. **Réécriture d'historique** : à décider par écrit. Je ne la ferai pas sans
   accord, jamais par force-push.
2. **Retrait des valeurs par défaut de `config.py`**, avec tests de démarrage.
3. **`/societes`** : à paginer, ou hors périmètre plateforme.
4. **Émetteurs de notifications** : quels événements, quels destinataires.
## Reste à faire
- Périmètre réel avant toute migration : 5 cabinets ont une base sur 122
  déclarés, les 117 autres seront arrêtés, pas migrés.
- Ventilation assurance et patient d'une facture : hors périmètre, non codée. La
  prise en charge est **enregistrée, pas appliquée** au calcul d'un montant, et
  demande une permission propre.
- Faire consommer `tarifs_actes` par la facturation, `tarif_base` restant lu en
  attendant : transition, pas dual permanent. Puis rechargement client et parité.