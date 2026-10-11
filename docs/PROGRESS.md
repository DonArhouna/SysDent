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
`src`**, et la garde **vérifie que la redirection a pris**. Quatre refus
cumulatifs : URL absente, port du développement, nom de base réelle, marqueur
absent.

Les tests de supervision **fabricent leurs propres cas** — une base migrée, une
base vide, leurs lignes de registre — et les suppriment en `finally`. Deux
d'entre eux visaient le développement ; un troisième passait **à vide**, donc
vert pour la mauvaise raison. Un test qui dépend de l'état réel d'une autre
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

12 bases existent. **5 à la tête**, aucun cabinet réel en retard. **5 bases sans
table `alembic_version`** : des démonstrations (`clinique_demo_*`,
`clinique_trace_3_*`, `clinique_diagnostic_dakar_*`, `clinique_d_mo_dakar_*`).
Une seule en retard : `sysdent_tenant_ref` (`c4f8a2d91e05`), le **tenant de
référence des tests**. Sur accord : `pg_dump` puis `alembic -c
alembic_tenant.ini upgrade head`. Aucune base migrée.

## Registre : 129 lignes sans base, toutes conservées

Décision du propriétaire : **aucune suppression**. Ventilation : 91
manifestement de test, 2 provisionnements échoués, 33 douteux
(`clinique_provisionnement_*`), 3 possiblement réels (`clinique_cabinet_sn_*`).
Aucun dump pour ces 36 dernières.

## Backoffice : tableau de bord écrit, layout réparé

`/dashboard` rend le tableau de bord **dans `AppShell`**. La page livrée
précédemment s'en oubliait : `AppShell` (sidebar, navbar, thème) n'était
utilisé que par l'écran provisoire qu'elle remplaçait. Le type ne le voyait pas,
les tests passaient. Deux tests exigent désormais un `aside` et un `header`, avec
un témoin sur `AppShell` seul ; **preuve par mutation** : sans enveloppe, le
test échoue.

Le harnais ne simulait pas `window.matchMedia`, que la bascule de thème appelle :
**toute** page rendue dans le layout échouait. C'est là que se expliquaient les
2 tests de bannière en échec depuis le début — ils rendent l'écran provisoire,
qui utilise `AppShell`. **7 fichiers, 42 tests, tous verts.**

Un seul appel, total et part sans base sur deux lignes distinctes, erreur avec
« Réessayer » et jamais un zéro, vide sans « Réessayer », bannière conditionnée.
Pas d'i18n : ni le backoffice ni le client n'en ont — à trancher.

## Le 500 du tableau de bord : **cause nommée, reproduite, corrigée**

Sur le HEAD, instance de test, jeton plateforme valide :

| | avant | après |
|---|---|---|
| sans jeton | 401 | 401 |
| jeton invalide | 401 | 401 |
| login + 2FA | 200 | 200 |
| **tableau de bord** | **500** | **200** |

Traceback : `stats.py:354`, `_cabinets_essai_proches_expiration` —
`TenantPlateforme.date_fin_essai.is_(None).invert()`. `is_(None)` renvoie déjà
un `BinaryExpression`, qu'on ne peut pas inverser. L'appel lève à la
**construction** du `select`, avant tout accès à la base : le 500 ne dépendait
d'aucune donnée. La condition était de plus sans effet — en SQL, comparer
`NULL` donne `NULL`, et les deux conditions de date voisines excluaient déjà
les essais sans date.

Code **antérieur** aux travaux sur le tableau de bord : ce n'est pas une
régression. Le test échouait pour la même raison, au même endroit.

**Fuite trouvée au passage** : la fixture plateforme paramétrée de `conftest`
laisse une base `sysdent_platform_test_<hex>` par paramètre — 6 bases
accumulées. Non corrigée, signalée.

## Couple 401 / 500 : mesuré, et non lié

401 sans jeton et 401 avec jeton invalide, distincts et stables. Le 500 ne
résulte pas d'une requête partie sans authentification : il venait de la
construction d'une requête, comme le prouve le traceback. **L'analyse front du
renouvellement de session n'a pas été faite** — pas de teste, donc rien
n'est affirmé.

**Non fait** : `design:parite`, liste des cabinets. **Aucun rendu déclaré
vérifié** : pas de navigateur.

## Reste à faire

1. **Analyser le 401 côté front** : que fait `api.ts` sur un 401, et le test
   qui le prouve. Rien n'est affirmé aujourd'hui.
2. Corriger la fuite des bases `sysdent_platform_test_<hex>`.
3. `npm run design:parite`, puis la liste des cabinets.
4. Rapprochement du registre : arbitrage sur les 36 lignes non jetables.