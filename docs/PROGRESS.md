# SysDent Pro — état de reprise

> Une page, ce qui est **prouvé**. L'historique session par session reste dans
> l'historique git : `git log -p -- docs/PROGRESS.md`.

---

## ACCÈS

**Opérationnel.** Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est
restauré, migré à la tête `e8b2c4a7d1e5`, et son login répond **200**. Vérification
sur compte de test créé puis supprimé ; aucun compte réel utilisé.

## Dégradations de texte : 9 corrigées sur 8 fichiers

Aucune version saine n'existait dans l'historique : le texte a été **reconstitué**
depuis le contexte, pas restauré. Neuf reconstructions, à relire par le
propriétaire :

| Fichier | Texte retenu |
|---|---|
| `cabinets/services.py` | et **brouillent** le calcul |
| `platform/services/support.py` | « **constater** » |
| `patients/services.py` | **Les données** restent |
| `platform/dependencies.py` | un `except Exception` **élargi** |
| `platform/services/auth.py` | deux codes **correspondant simultanément** |
| `Backoffice/src/lib/api.ts` | de le **constater** |
| `test_perimetre_support.py` | n'y est pas **concerné** |
| `FRONTEND_PLAN.md:21` | les deux **ensemble** |
| `FRONTEND_PLAN.md:238` | le backend **aujourd'hui** |

Seule la plage de caractères parasites a été remplacée : 9 lignes, 9 insertions,
9 suppressions. `auth-store.ts` ne contenait **aucun** caractère CJK ; l'affirmation
antérieure qui le citait était fausse.

Contrôle : dépôt entier à **0** caractère suspect. Hook pre-commit actif et testé.

## Instance de tests dédiée : prouvée

| Élément | Valeur |
|---|---|
| Instance | `sysdent_test_pg`, port **55436**, volume **tmpfs** |
| Base-témoin | `sysdent_instance_test_marker`, preuve de l'instance dédiée |
| Bases des tests | `sysdent_master_test`, `sysdent_platform_test`, `sysdent_modele_tenant_test` |

Quatre refus cumulatifs avant le premier test : `TEST_DATABASE_URL` absente, port
du développement, nom de base réelle, absence du marqueur. `settings` est
réorienté vers l'instance de tests **avant tout import de `src`**, sinon les
moteurs globaux de l'application visent le développement.

**Preuve** : 77 tests verts dont 5 créant deux cabinets ; développement inchangé
avant/après (17 bases, liste identique, registre 137/137/105).
Preuve par mutation : garde neutralisée, **11 tests échouent**.

Docs : `docs/TESTS.md`, `docs/OPERATIONS.md`.

## Suite complète : **NON VÉRIFIÉE**

Lancée une fois sur l'instance de tests, elle a atteint **64 %** puis a dépassé
**90 minutes** sans finir (objectif : moins de 15 min). Aucun verdict à annoncer.
Constats : des erreurs et des échecs dès les premiers 14 % ; sur le premier
fichier, 13 tests passent en 71 s, le temps passant en `setup` (2 à 15 s par
test). Cause du ralentissement **non établie**.

## Registre : 129 lignes sans base, toutes conservées

Décision du propriétaire : **aucune suppression**, pas même les 83 de
l'inventaire précédent. Elles restent visibles dans l'écran de santé.

| Catégorie | n |
|---|---|
| Manifestement de test (motif du projet, `tests/conftest.py`) | 91 |
| Provisionnement échoué | 2 |
| Douteux (`clinique_provisionnement_*`, jamais connectés) | 33 |
| Possiblement réel (`clinique_cabinet_sn_*`) | 3 |

Aucun dump pour les 33 douteux ni pour les 3 possiblement réels.

## Backoffice : état des lieux, Lot 1 non fait

`/dashboard` affiche encore `ConnexionEtabliePage` : le tableau de bord a été
annulé en cours de route par l'agent précédent. **Le socle, lui, est intact** :
`dashboard-store.ts` (un seul appel, états chargement / erreur / vide / prêt,
« Réessayer », jamais un zéro pour une panne), `StatCard` à parité du client,
et 21 composants d'interface réutilisables. Les Lots 1 et 2 restent à faire.

## Règle de rapport

Relire la sortie brute avant d'écrire un fait. Vérifier qu'un objet git existe
(`git cat-file -t`) avant de lui attribuer quoi que ce soit. Après chaque
écriture, relire et compiler le fichier.

## Reste à faire

1. **Comprendre le ralentissement de la suite**, puis obtenir un verdict réel.
2. **Backoffice Lots 1 et 2** : tableau de bord sur `/platform/stats/dashboard`,
   puis cabinets en lecture avec badge « base absente ».
3. **Rapprochement du registre** : décider du sort des 33 douteux et des 3
   possiblement réels, après sauvegarde du registre.
4. Faire relire les **9 reconstructions** de texte par le propriétaire.