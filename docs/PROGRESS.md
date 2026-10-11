# SysDent Pro — état de reprise

> Une page, ce qui est **prouvé**. Historique dans `git log -p -- docs/PROGRESS.md`.

## ACCÈS

Le 500 du login avait **deux causes**. La première était l'environnement :
`sysdent_s0b` (port 55435) s'était arrêté le 11/10 à 12:01:43, sans politique
de redémarrage, et le backend l'avait rejoint à 12:16:57. Relancé par le
propriétaire. La seconde était le code, corrigée : un échec d'ouverture de
connexion n'est pas encapsulé par SQLAlchemy et remontait nu ; et l'erreur de
schéma périmé se trouve **deux niveaux** sous le `ProgrammingError`, que le tri
n'examinait pas. Vérifié en HTTP : 500 devenu 503, détails vides.

Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la
tête `e8b2c4a7d1e5`, login **200**. Aucun compte réel n'a jamais été utilisé.

## Tests : ce qui est isolé, et ce qui le prouve

Instance dédiée `sysdent_test_pg`, port **55436**, volume **tmpfs**, base-témoin
`sysdent_instance_test_marker`. `settings` est réorienté **avant tout import de
`src`**, et la garde de démarrage **vérifie que la redirection a pris** : sans
cela, un test lisant `settings` pour se connecter directement pouvait changer de
cible. Quatre refus cumulatifs : URL absente, port du développement, nom de base
réelle, absence du marqueur.

Les tests de supervision **fabricent leurs propres cas** — une base migrée, une
base vide, leurs lignes de registre ACTIVE — et les suppriment en `finally`.
Deux d'entre eux visaient le développement ; un troisième passait **à vide**,
donc vert pour la mauvaise raison. Un test qui dépend de l'état réel d'une autre
machine est une observation, pas un test.

Chaque base créée est enregistrée. En fin de session, les bases hors liste de
protection sont **listées et la session échoue** : rien n'est supprimé à l'aveugle.
`--nettoyer-instance-test` les supprime, après vérification du port 55436 **et**
de la base-témoin.

Preuves : 14 verts sur le fichier de supervision ; 19 verts, **trois exécutions
de suite, 5 bases avant et après** ; une base laissée volontairement fait échouer
la session ; développement inchangé (17 bases, registre 137/137).

## Suite complète : **NON VÉRIFIÉE**

64 % puis **90 minutes** sans finir (objectif : moins de 15). Cause du
ralentissement **non établie**. Un facteur corrigé depuis : la base plateforme
de tests n'était jamais migrée, ce qui levait 4 erreurs au chargement.

Mesures qui **écartent** deux hypothèses : `tmpfs` à 8 %, 6 connexions ouvertes
pour un maximum de 100. Ni saturation, ni pression de connexions. Fuite de bases
**corrigée et prouvée**. Le clonage de modèle, le coût Argon2 et les migrations
rejouées par test n'ont **pas** été mesurés.

## Écart de schéma des cabinets (lecture seule)

12 bases de cabinets existent sur le développement. **5 à la tête**, aucune en
retard parmi les cabinets réels. **5 bases sans table `alembic_version`** : ce
sont des bases de démonstration (`clinique_demo_*`, `clinique_trace_3_*`,
`clinique_diagnostic_dakar_*`, `clinique_d_mo_dakar_*`), pas des cabinets en
service. Une seule base est en retard : `sysdent_tenant_ref`, à `c4f8a2d91e05` —
**le tenant de référence des tests**, pas un client.

Commande, si un accord est donné pour une base réellement en retard :
sauvegarde `pg_dump` puis, depuis `Backend/`, `alembic -c alembic_tenant.ini
upgrade head`. Aucune base n'a été migrée.

## Registre : 129 lignes sans base, toutes conservées

Décision du propriétaire : **aucune suppression**. Ventilation : 91
manifestement de test, 2 provisionnements échoués, 33 douteux
(`clinique_provisionnement_*`), 3 possiblement réels (`clinique_cabinet_sn_*`).
Aucun dump pour ces 36 dernières.

## Backoffice : socle backend fait, écrans non écrits

`/dashboard` affiche encore `ConnexionEtabliePage`. Le store existe (un appel,
états chargement / erreur / vide / prêt, « Réessayer », jamais un zéro pour une
panne), `StatCard` est à parité du client, 21 composants réutilisables.

**Fait, vérifié** : le tableau de bord expose désormais, par statut, `total` et
`dont_base_absente`, lus dans la **même** requête que les absences. Sans cela un
écran affichait « 42 cabinets ACTIVE » sans dire que certains ont un login cassé.
Le compte vient du registre et du catalogue `pg_database` — **aucune connexion à
une base de cabinet**, prouvé par un test qui rend cette connexion impossible. Les
deux comptes viennent du même registre parce que le tableau de bord lit ses
statuts dans la base plateforme et les bases dans la base master : deux tables,
deux vocabulaires.

Types TypeScript régénérés, `npm run verifier` vert, 16 tests cibles verts. Le
hook a refusé deux fois le commit, et avait raison : la ponctuation des fichiers
générés, et deux caractères que j'avais moi-même écrits.

**Non fait** : page du tableau de bord, liste des cabinets, fiche. `/platform/
tenants`, les quotas et l'historique d'abonnement **existent déjà** côté backend ;
c'est l'écran et les filtres qui manquent.

## Reste à faire

1. **Diagnostiquer le ralentissement** : clonage du modèle, Argon2, migrations.
2. Obtenir un verdict réel de la suite complète.
3. **Backoffice Lots 1 et 2**, sans navigateur : parcours à comparer à la main.
4. Rapprochement du registre : arbitrage sur les 36 lignes non jetables.