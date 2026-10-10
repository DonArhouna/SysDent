# SysDent Pro — état de reprise

> Une page, ce qui est **prouvé** aujourd'hui. L'historique session par session
> (1461 lignes au 10/10) reste dans l'historique git : `git log -p -- docs/PROGRESS.md`.
> Mis à jour à chaque étape, un commit atomique par étape.

---

## ACCÈS

**Opérationnel.** Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est
restauré, migré à la tête, et son login répond **200**. Le propriétaire doit
vérifier lui-même avec ses comptes — aucun compte réel n'a été utilisé par l'agent.

## Ce qui a été fait le 10/10 (restauration du cabinet 5bd215)

- Base supprimée le 08/10 par la purge de fin de session, qui classait les bases
  par leur **nom seul**. Aucune migration n'était en cause.
- Sauvegardes sorties du conteneur : `C:\sauvegardes_sysdent\cabinet_sn_5bd215\`
  (7 dumps, empreintes SHA-256 vérifiées). Registre `sysdent_master` sauvegardé
  avant toute écriture.
- Restauration depuis `save_avant_users_20261006_181439.sql` : 32 patients,
  10 utilisateurs, 30 consultations, 43 factures. **Exit 0, 0 erreur.**
- Puis `alembic -c alembic_tenant.ini upgrade head` : **2 migrations**
  (`d7f2a9c4b6e1` cabinet_id, `e8b2c4a7d1e5` salle d'attente) → tête `e8b2c4a7d1e5`,
  49 tables, backfill complet, **comptages inchangés**.
- Validation préalable sur base jetable : upgrade → downgrade → upgrade, et
  **0 écart de schéma** contre une base saine (519 colonnes, 230 contraintes,
  191 index). Base jetable supprimée.
- Preuve HTTP : login 200 sur compte de test créé puis supprimé (retour à 10/10/32),
  mauvais mot de passe 401 générique, email inexistant 401.

## Protections ajoutées

| Protection | Commit | Effet |
|---|---|---|
| Garde de purge | `d0774a6` | N'agit que sur une instance de tests **dédiée et marquée** ; jamais une base du registre ni une `sysdent_tenant_*` hors session. **Neutralisée en production par défaut.** |
| Login — base absente | `6f05874` | 503 générique au lieu de 500 ; journal avec l'identifiant du cabinet, jamais de secret |
| Login — schéma périmé | `6f05874` | `UndefinedColumn`/`Table` → 503 contrôlé ; un SQL cassé par le code reste visible |
| Supervision `bases_absentes` | `6f05874` | Liste les lignes du registre dont la base a disparu |
| Supervision `schemas_tenants` | `6f05874` | Écart de révision par cabinet, tête lue sur la chaîne (jamais en dur) |
| Configuration Alembic | `598af6e` | Les trois `env.py` normalisent l'URL ; contrat de `upgrade_tenant_to_head` clarifié |
| Contrôle d'intégrité | `598af6e` | Compilation, une tête par chaîne, caractères d'écritures non latines. Hook pre-commit actif. |

`docs/OPERATIONS.md` : correspondance exacte entre fichier `.ini`, chaîne et base.

## Registre : 129 lignes sans base

| Catégorie | n | Base de la catégorie |
|---|---|---|
| Manifestement de test | 91 | Motif jetable du projet (`tests/conftest.py`) : `partage_[ab]` 62, `cabinet_verif_[bcde]` 24, `onboarding` 4, `recette` 1, `essai` 1 |
| Provisionnement échoué | 2 | Statut `PROVISIONING` : `cabinet_rollback`, 1 `verif_b` |
| **Douteux** | 33 | `clinique_provisionnement_*` : aucun motif connu, 1 compte chacun, **jamais connecté** |
| **Possiblement réel** | 3 | `clinique_cabinet_sn_*` (2f36e8, cb3730, e7cd42) : la famille du propriétaire, PROVISIONING, 0 compte |

**Aucun dump n'existe** pour les 33 douteux ni pour les 3 possiblement réels.
Les seuls dumps disponibles sont ceux de `5bd215`, plus master et plateforme.
**Aucune ligne du registre n'a été supprimée.**

## Corruptions de texte : 9 cas dans 8 fichiers, non corrigés

Relevé par `python Backend/scripts/controle_integrite.py --tout` :

| Fichier | Ligne | Caractères |
|---|---|---|
| `Backend/src/modules/cabinets/services.py` | 855 | CJK (4) |
| `Backend/src/modules/platform/services/support.py` | 186 | CJK (2) |
| `Backend/src/modules/patients/services.py` | 542 | hangul (2) |
| `Backend/src/modules/platform/dependencies.py` | 292 | arabe (3) |
| `Backend/src/modules/platform/services/auth.py` | 356 | U+FFFD (2) |
| `Backoffice/src/lib/api.ts` | 11 | U+FFFD (2) |
| `Backend/tests/platform/test_perimetre_support.py` | 70 | CJK (2) |
| `docs/backoffice/FRONTEND_PLAN.md` | 21 et 238 | CJK (1 et 2) |

**À corriger par restauration depuis l'historique git**, un fichier à la fois.

ATTENTION : une affirmation antérieure disait que
`Backoffice/src/stores/auth-store.ts` contenait des caractères chinois : **c'est
faux, il n'en contient aucun**. Ne pas propager cette affirmation, et ne pas
élargir aux fichiers non listés ci-dessus.

## Règle de rapport

Avant d'écrire un fait dans un document : relire la sortie brute de la commande
qui l'établit. **Ne jamais attribuer un fait à un commit sans avoir vérifié que
l'objet existe** (`git cat-file -t <sha>`). Après chaque écriture ou édition d'un
fichier de code ou de migration, le relire et le compiler.

## Reste à faire

1. **Instance de test dédiée** (`TEST_DATABASE_URL` vers une instance portant la
   base-témoin `sysdent_instance_de_tests`) — sans elle, la purge ne s'exécute
   plus du tout et les bases de test s'accumulent.
2. **Rapprochement du registre** : décider du sort des 33 douteux et des 3
   possiblement réels. Aucun dump disponible, la décision est commerciale.
3. **Corriger les 10 fichiers dégradés** depuis l'historique git.
4. **Backoffice Lots 1 et 2**.
5. Suite complète : à ne relancer qu'une fois l'instance de test dédiée en place.