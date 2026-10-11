# SysDent Pro — état de reprise

> Une page, ce qui est **prouvé**. Historique session par session dans
> `git log -p -- docs/PROGRESS.md`.

## URGENT — le 500 du login : deux causes

**1. La base de développement est arrêtée. C'est la cause du 500 constaté.**
`sysdent_s0b` (port **55435**) s'est arrêté le 11/10 à **12:01:43**, sans
politique de redémarrage. Le backend, démarré à 12:16:57, s'est levé devant une
base morte, et la réponse exposait l'hôte et le port du serveur en clair.

**Action du propriétaire : `docker start sysdent_s0b`** — non destructif, rien
n'est créé ni supprimé. Le backend n'a pas besoin d'être redémarré : il s'est
rechargé seul (worker 14736 puis 5364).

**2. Deux défauts de code, corrigés.** Le 500 ne devait pas être possible.

- *Registre injoignable* : une panne d'ouverture de connexion n'est **pas**
  encapsulée par SQLAlchemy, elle remonte nue (`ConnectionRefusedError`, ou
  `OSError` quand l'hôte résout en deux adresses). Aucune des deux ne passait la
  liste fermée. Traduit en 503 générique, sans hôte ni port.
- *Schéma périmé* : mesuré sur une base réelle, l'erreur asyncpg est à **deux
  niveaux** sous le `ProgrammingError` attrapé ; le tri s'arrêtait au premier.
  Les tests existants passaient parce qu'ils **fabriquent** une forme que
  SQLAlchemy ne produit pas — une simulation ne prouve que ce que son auteur a
  cru écrire.

**Preuves** : 5 tests rouges avant, 9 verts après ; reproduction **réelle** sur
une base jetable dont on a vraiment supprimé une colonne ; preuve par mutation
(liste neutralisée, 2 tests échouent) ; en HTTP, base toujours arrêtée,
**500 → 503, détails vides**. 88 tests ciblés verts. Aucune liste d'exceptions
élargie : seules les formes réellement observées qui manquaient.

**2 échecs subsistent** dans `test_sante_bases_absentes.py`, **antérieurs**,
prouvés par mise de côté du correctif : ils visent une base du développement.

## ACCÈS

Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la
tête `e8b2c4a7d1e5`, login **200** — vérifié le 10/10 sur compte de test créé
puis supprimé, aucun compte réel utilisé.

## Instance de tests dédiée : prouvée

Instance `sysdent_test_pg`, port **55436**, volume **tmpfs**, base-témoin
`sysdent_instance_test_marker` ; bases `sysdent_master_test`,
`sysdent_platform_test`, `sysdent_modele_tenant_test`. Quatre refus cumulatifs
avant le premier test : URL absente, port du développement, nom de base réelle,
absence du marqueur. `settings` est réorienté **avant tout import de `src`**,
sinon les moteurs globaux visent le développement. Preuve : 77 tests verts dont
5 créant deux cabinets ; développement inchangé avant/après (17 bases, registre
137/137/105) ; garde neutralisée, **11 tests échouent**. Voir `docs/TESTS.md`.

## Suite complète : **NON VÉRIFIÉE**

Lancée une fois, elle a atteint **64 %** puis a dépassé **90 minutes** sans finir
(objectif : moins de 15 min) : aucun verdict. Sur le premier fichier, 13 tests
passent en 71 s, le temps passant en `setup` (2 à 15 s par test) ; **cause du
ralentissement non établie**. Un facteur trouvé et corrigé depuis :
`sysdent_platform_test` était créée mais jamais migrée, ce qui levait 4 erreurs
au chargement ; `tests/platform` passe de 30 à 34 tests, sans erreur.

## Dégradations de texte : 9 corrigées sur 8 fichiers

Aucune version saine dans l'historique : le texte a été **reconstitué**, pas
restauré. Neuf reconstructions, **à relire par le propriétaire** — fichier :
texte retenu. `cabinets/services.py` et **brouillent** ;
`platform/services/support.py` « **constater** » ; `patients/services.py`
**Les données** ; `platform/dependencies.py` un `except Exception` **élargi** ;
`platform/services/auth.py` deux codes **correspondant simultanément** ;
`Backoffice/src/lib/api.ts` de le **constater** ;
`test_perimetre_support.py` n'y est pas **concerné** ;
`FRONTEND_PLAN.md` **ensemble** / **aujourd'hui**. Seule la plage de caractères
parasites a été remplacée : 9 lignes, 9 insertions, 9 suppressions. `auth-store.ts`
ne contenait **aucun** caractère CJK ; l'affirmation antérieure était fausse.
Dépôt entier à **0** caractère suspect.

## Registre : 129 lignes sans base, toutes conservées

Décision du propriétaire : **aucune suppression**, pas même les 83 de
l'inventaire précédent ; elles restent visibles dans l'écran de santé.
Ventilation : 91 manifestement de test, 2 provisionnements échoués, 33 douteux
(`clinique_provisionnement_*`, jamais connectés), 3 possiblement réels
(`clinique_cabinet_sn_*`). Aucun dump pour ces 36 dernières.

## Backoffice : état des lieux, Lot 1 non fait

`/dashboard` affiche encore `ConnexionEtabliePage` : le tableau de bord a été
annulé en cours de route par l'agent précédent. **Le socle est intact** :
`dashboard-store.ts` (un seul appel, états chargement / erreur / vide / prêt,
« Réessayer », jamais un zéro pour une panne), `StatCard` à parité du client,
21 composants réutilisables. Lots 1 et 2 à faire.

## Reste à faire

1. **Comprendre le ralentissement de la suite**, puis obtenir un verdict réel.
2. Corriger les 2 tests de `test_sante_bases_absentes.py` : ils visent une base
   du développement, ils doivent viser l'instance de tests.
3. **Backoffice Lots 1 et 2**, et rapprochement du registre (36 lignes).
4. Faire relire les **9 reconstructions** de texte.