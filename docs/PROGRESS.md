# SysDent Pro — état de reprise
> Ce qui est **prouvé**, et sa preuve. Le détail est dans `docs/journal/` et
> dans `git log -p -- docs/PROGRESS.md`.
## ACCÈS
Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la
tête `e8b2c4a7d1e5`, login **200**. Aucun compte réel n'a jamais été utilisé.
Le 500 du login avait **deux causes** : le conteneur de développement arrêté
(sans politique de redémarrage), et deux défauts de code — un échec
d'ouverture de connexion n'est pas encapsulé par SQLAlchemy et remontait nu ;
l'erreur de schéma périmé est **deux niveaux** sous le `ProgrammingError`, que
le tri n'examinait pas. Vérifié en HTTP : 500 devenu 503, détails vides.
## 422 de l'odontogramme : **cause nommée**
Le tiroir n'utilisait pas le référentiel pour les faces : cinq options écrites
en dur, dont une que le serveur refuse.
| option | validateur |
|---|---|
| `SAINE`, `CARIE_DEBUTANTE`, `CARIE_AVANCEE`, `COURONNE` | acceptés |
| `SOIGNEE` (« Obturation / Composite ») | **refusé** |
`ETATS_DENT` n'a aucun état de ce nom : les restaurations sont
`OBTURATION_*`, `INLAY`, `ONLAY`, `COURONNE*`. Choisir « Obturation /
Composite » suffisait à déclencher le 422. **L'état par défaut étant accepté, il
fallait changer une lésion pour tomber dessus** — exactement le geste du
praticien.
Corrigé à la racine : les états viennent de `referentielEtats`, comme ceux de
l'état global. Plus aucune liste écrite en dur ; le test l'interdit.
Également corrigés : quatre codes de face hors nomenclature (`MESIALE`,
`DISTALE`, `LINGUALE`, `OCCLUSALE`), et `face` devient le type `CodeFace`,
une union des codes serveur — une faute devient une erreur de compilation.
## 403 sur `/cabinets`
Les logs du navigateur nommaient l'appelant : `dashboard.tsx:244`, pas
l'odontogramme. `litCabinets` y était calculé ligne 205 et utilisé ailleurs,
mais la requête n'avait **pas** de `enabled` — elle partait inconditionnellement.
Garde branché.
## Tests : instance dédiée
Instance `sysdent_test_pg`, port **55436**, **tmpfs**, base-témoin
`sysdent_instance_test_marker`. `settings` réorienté **avant tout import de
`src`**, garde vérifiant que la redirection a pris ; quatre refus cumulatifs.
**Fuite de bases, cause trouvée** : `BASES_CREEES_PAR_LA_SESSION` était
déclaré **deux fois** (un `set`, puis une `list`). Le second écrasait le premier :
`.add` sur une liste lève, **après** la création et **avant** le `finally`.
Mesure : 16 bases par exécution. Après correction : **5 bases avant et après
trois exécutions, 44 tests verts, 0 erreur.**
Les tests de supervision **fabricent leurs propres cas** : trois affirmaient
des faits sur le développement, l'un passant **à vide**, donc vert pour la
mauvaise raison.
## Backoffice
`/dashboard` rend dans `AppShell` ; la page livree precedemment s'en
oubliait, et rien ne le voyait. Deux tests exigent un `aside` et un `header`,
preuve par mutation. Un seul appel, total et part « base absente » sur deux
lignes, « Reessayer » jamais un zero. **47 tests verts**, `verifier` vert.
Le 500 du tableau de bord : `stats.py:354`, `is_(None).invert()` — corrige,
**200 verifie en HTTP** (avant : 500). Couple 401/500 **ecarte par test**.
## Suite complète : **NON VÉRIFIÉE**
64 % puis 90 minutes sans finir. Cause du ralentissement **non établie**.
`tmpfs` à 8 %, 6 connexions sur 100 : ni saturation, ni pression.
## Registre et bases
**129 lignes sans base, toutes conservées** (décision du propriétaire) : 91 de
test, 2 échecs de provisionnement, 33 douteux, 3 possiblement réels. Aucun
cabinet réel en retard de schéma ; 5 bases de démonstration sans
`alembic_version`. Aucune base migrée.
## Non vérifié
- **Rendu navigateur** : jamais contrôlé. Checklist :
  `docs/backoffice/VERIFICATION_NAVIGATEUR.md`.
- **Pas d'i18n** : ni le client ni le backoffice n'en ont. **À trancher.**
- Ralentissement de la suite.
## Défauts d'interface du 12/10 (client)
Cinq symptomes, une meme famille : **le garde existait ailleurs dans le
fichier et n'etait pas branche**. Prouve par lecture, verifie par test.
| symptome | cause |
|---|---|
| 422 odontogramme | etat ecrit en dur absent de la nomenclature ; le defaut passait, il fallait *changer* une lesion |
| 422 odontogramme | quatre codes de face hors nomenclature |
| 422 consultation | `cabinet_id: ''` quand aucun site n'est resolu : impossible pour un profil sans `CABINETS:READ` |
| 422 consultation | motif vide, refuse par `min_length=2` |
| 403 agenda | liste des praticiens demandee sans `PRATICIENS:READ` |
Corrige a la racine : etats venus du referentiel, `face` typee en union,
`cabinet_id` absent plutot que vide, liste des praticiens seulement si le
droit existe. Apres deconnexion volontaire, la connexion va au tableau de
bord ; apres expiration, elle restitue la route. L'identifiant de consultation
n'est plus saisi.
## Reste à faire
1. Rechargement forcé du client, puis test d'une modification de face.
2. `npm run design:parite`, puis la liste des cabinets.
3. Cause du ralentissement, puis verdict réel de la suite.
4. Registre : arbitrage sur les 36 lignes non jetables.
