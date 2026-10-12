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

## Odontogramme et 403 `/cabinets` (12/10)

**422, cause nommée.** Le tiroir de dent envoie **toujours les cinq faces**,
donc un seul code hors nomenclature fait échouer toute la sauvegarde. Quatre
des cinq divergeaient : `OCCLUSALE`, `LINGUALE`, `MESIALE`, `DISTALE` côté
client, contre `OCCLUSAL_INCISAL`, `LINGUAL_PALATIN`, `MESIAL`, `DISTAL` côté
serveur. Le serveur fait autorité. Test de contrat qui lit le `.tsx` **et** le
`.py` : un code changé d'un seul côté fait échouer. Preuve : `MESIALE` rétabli,
le test échoue.

**403, cause nommée.** `GET /cabinets` exige `CABINETS:READ` ; l'odontogramme
n'affiche aucun site, l'appel ne lui servait à rien, et `chargerCabinets`
avalait l'erreur en silence. Permission désormais lue dans le profil livré par
`/auth/me`, sans liste de rôles codée. Un 403 n'est pas rejoué et ne se traduit
pas par une liste vide trompeuse.

16 tests clients verts, lint et build verts. Le client n'a **pas** de script
`verifier` : l'équivalent est `lint` + `test` + `build`.

**Non vérifié** : aucun appel HTTP n'a été rejoué pour ces deux routes, donc le
200 du praticien autorisé n'est pas confirmé par une preuve de bout en bout.

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