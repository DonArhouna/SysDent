# SysDent Pro — état de reprise

> Ce qui est **prouvé**, et sa preuve. Le détail des sessions est dans
> `docs/journal/` et dans `git log -p -- docs/PROGRESS.md`.

## ACCÈS

Le cabinet `sysdent_tenant_clinique_cabinet_sn_5bd215` est restauré, migré à la
tête `e8b2c4a7d1e5`, login **200**. Aucun compte réel n'a jamais été utilisé.

Le 500 du login avait **deux causes** : le conteneur de développement arrêté
(politique de redémarrage absente), et deux défauts de code — un échec
d'ouverture de connexion n'est pas encapsulé par SQLAlchemy et remontait nu ;
l'erreur de schéma périmé se trouve **deux niveaux** sous le `ProgrammingError`,
que le tri n'examinait pas. Vérifié en HTTP : 500 devenu 503, détails vides.

## Tests : instance dédiée

Instance `sysdent_test_pg`, port **55436**, volume **tmpfs**, base-témoin
`sysdent_instance_test_marker`. `settings` réorienté **avant tout import de
`src`**, et la garde **vérifie que la redirection a pris** ; quatre refus
cumulatifs.

Les tests de supervision **fabricent leurs propres cas** et les suppriment en
`finally` : trois affirmaient des faits sur le développement, l'un passant
**à vide**, donc vert pour la mauvaise raison.

**Fuite de bases, cause trouvée.** `BASES_CREEES_PAR_LA_SESSION` était déclaré
**deux fois** (un `set`, puis une `list`). Le second écrasait le premier :
`_enregistrer` faisait `.add` sur une liste, levait, **après** avoir créé la
base et **avant** d'atteindre le `finally`. Mesure : 16 bases par exécution et
17 erreurs de setup — la même cause. Après correction : **5 bases avant et
après trois exécutions, 44 tests verts, 0 erreur.**

Preuves : trois exécutions de suite sans variation ; une base laissée
volontairement fait échouer la session ; développement inchangé (17 bases,
registre 137/137).

## Suite complète : **NON VÉRIFIÉE**

64 % puis **90 minutes** sans finir (objectif : moins de 15). Cause du
ralentissement **non établie**. `tmpfs` à 8 %, 6 connexions sur 100 : ni
saturation, ni pression. Clonage de modèle, coût Argon2 et migrations rejouées
par test **non mesurés**.

## Backoffice : tableau de bord écrit et testé

`/dashboard` rend le tableau de bord **dans `AppShell`** — la page livrée
précédemment s'en oubliait, et rien ne le voyait. Deux tests exigent désormais
un `aside` et un `header` ; **preuve par mutation** : sans enveloppe, le test
échoue. Le harnais ne simulait pas `window.matchMedia`, ce qui faisait échouer
**toute** page rendue dans le layout.

Un seul appel ; total et part « base absente » sur **deux lignes distinctes** ;
erreur avec « Réessayer », **jamais un zéro** ; vide sans « Réessayer » ;
bannière des codes de secours conditionnée par le profil.

**47 tests fronts verts sur 8 fichiers**, `npm run verifier` vert.

## Le 500 du tableau de bord : **cause nommée, reproduite, corrigée**

| requête | avant | après |
|---|---|---|
| sans jeton | 401 | 401 |
| jeton invalide | 401 | 401 |
| login + 2FA | 200 | 200 |
| **tableau de bord** | **500** | **200** |

`stats.py:354`, `_cabinets_essai_proches_expiration` :
`TenantPlateforme.date_fin_essai.is_(None).invert()`. `is_(None)` renvoie déjà
un `BinaryExpression`, qu'on ne peut pas inverser. L'appel lève à la
**construction** du `select`, donc avant tout accès à la base : le 500 ne
dépendait d'aucune donnée. La condition était de plus sans effet. Code
**antérieur** aux travaux sur le tableau de bord.

**Couple 401/500 : hypothèse écartée par test.** `api.ts` renouvelle une fois
et rejoue une fois ; si le renouvellement échoue, la session est purgée et la
requête **n'est pas rejouée**. `/platform/auth/*` n'est jamais rejoué. Preuve
par mutation : le garde retiré, son test échoue.

## Registre et bases

**129 lignes sans base, toutes conservées** (décision du propriétaire) : 91 de
test, 2 provisionnements échoués, 33 douteux, 3 possiblement réels. Aucun dump
pour ces 36 dernières.

Écart de schéma : aucun cabinet réel en retard. Cinq bases de démonstration
n'ont pas de table `alembic_version`. `sysdent_tenant_ref` est le tenant de
référence des tests. Aucune base migrée.

## Odontogramme et 403 `/cabinets` (12/10, réactualisé)

**403 — corrigé au bon endroit.** Les logs du navigateur nomment l'appelant :
`api.ts:249` puis `dashboard.tsx:244`. C'était le **tableau de bord**, pas
l'odontogramme ; le correctif de la veille visait un autre appel, sur une autre
page. La cause y était visible : `litCabinets = possedePermission(profil,
'CABINETS:READ')` était calculé ligne 205 et utilisé ailleurs, mais la requête
`/cabinets` n'avait **pas** de `enabled` — elle partait inconditionnellement.
Garde branché.

**422 — le contrat n'est plus en cause.** Le corps exact produit par le tiroir
passe la validation serveur (`FacesMiseAJour`, 5 faces acceptées). Un 422 naît
de la validation d'entrée, avant tout accès à la base : ce corps ne peut donc
pas le produire. Les états proposés par l'interface et ceux acceptés par le
validateur sont **37 de chaque côté, écart nul** — deux tables séparées que le
test verrouille désormais.

Le test de contrat lit le `.tsx` **et** le `.py`, vérifie que le corps du client
passe, et que tous les états de l'interface sont valides.

**Non vérifié, et c'est important** : le 422 du propriétaire **n'est pas
reproduit**. Il vient d'un autre corps — bundle antérieur, ou valeur différente.
Il faut son corps de réponse exact, pas une devination.

16 tests clients verts, lint et build verts. Le client n'a **pas** de script
`verifier` : l'équivalent est `lint` + `test` + `build`.

## Non vérifié

- **Rendu navigateur** : jamais contrôlé. Checklist dans
  `docs/backoffice/VERIFICATION_NAVIGATEUR.md`.
- **Pas d'i18n** : ni le backoffice ni le client n'en ont. **À trancher.**
- Cause du ralentissement de la suite.

## Reste à faire

1. Vérification navigateur, checklist en main.
2. `npm run design:parite`, puis la liste des cabinets.
3. Cause du ralentissement de la suite, puis verdict réel.
4. Registre : arbitrage sur les 36 lignes non jetables.