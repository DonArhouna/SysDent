# 00 — Diagnostic : anomalies reproduites par exécution

> **Date** : 5 octobre 2026 · **Mis à jour** : 6 octobre 2026 · **Règle** : aucune
> cause n'est affirmée sans reproduction. Chaque ligne indique le symptôme
> observé, la commande qui le reproduit, la cause racine avec fichier et ligne,
> et le correctif. Ce qui n'a pas été exécuté est marqué **non vérifié**.

## Suite des travaux — 6 octobre 2026

| Point | Cause | État |
|---|---|---|
| **C1** | `facturation/router.py:91` — `paiement.echeance` non préchargé | 🟢 **corrigé et vérifié** : `GET /factures` → 200, 10 factures, paiements sérialisés |
| **Module Stock** | absent de la base | 🟢 **créé et vérifié** : 9 tables, migration `e2f7b3c8a104`, 9 routes, parcours complet testé |
| **C2 — Stock 404** | aucun module | 🟢 résorbé |
| **Clôture de caisse** | aucun modèle, aucune route | 🟢 **créée et vérifiée** : sessions de caisse, 5 routes, migrations `f3a8d5b2c701` + `a4b9e6c3d812` + `b5c0d7e4f923` |
| **B10 — Utilisateurs** | aucun endpoint | 🔴 **toujours manquant** : c'est ce qui a empêché de créer les comptes de test par l'API |

### Défauts trouvés en construisant la clôture de caisse

Tous invisibles avant exécution. Deux d'entre eux auraient produit un **rapport
comptable faux**, ce qui est plus grave qu'une panne visible.

| Symptôme | Cause | Gravité |
|---|---|---|
| `POST /caisse/paiements-hors-session` → 500 | la route appelait le service sans le `cabinet_id` que sa signature exige | panne visible |
| Détail des paiements → 500 | la route lisait `paiement.enregistre_par_email`, **colonne qui n'existait pas** | panne visible |
| **Assurance absente des totaux** | `ASSURANCE` fait partie du catalogue des modes de paiement, mais la clôture ne portait que 5 colonnes : un encaissement assurance était **ignoré au moment de la clôture**, en silence | 🔴 **faux silencieux** |
| `?limit=200` → 422 | la route annonçait `le=500` alors que `PaginationParams` plafonne à 100 : une requête légitime était refusée | contrat incohérent |
| Encaissements cassés après coup | `paiements` n'avait que `enregistre_par_id` : supprimer le compte supprimait la preuve de qui a encaissé | traçabilité |

Le troisième point deserveait d'être lu deux fois. Le rapport de journée
annonçait un chiffre **inférieur au réel, sans aucun signal** : exactement le
genre de défaut qu'un cabinet découvre au moment de compter, et par personne.
Il est depuis verrouillé par `test_tout_mode_de_paiement_a_un_total_de_cloture`,
qui échouera dès qu'un mode sera ajouté sans colonne.

Le quatrième vient d'une **erreur de méthode** : j'ai écrit la limite dans la
route au lieu de la prendre dans `PaginationParams`. La constante
`LIMITE_PAGE_MAX` sert désormais de source unique.

### Une seconde fois où « le test passe » ne voulait rien dire

Dans le même esprit que `tsc --noEmit` (voir plus bas), un de mes propres tests
annonçait `especes_attendues == 20000` alors que la fixture ouvrait la caisse
avec un dépôt de **0**. L'échec venait du test, pas du produit : le serveur
comptait juste. Je l'ai signalé parce que « le test est rouge » ne veut pas dire
« le code a tort » — l'inverse est tout aussi fréquent.

### Défauts trouvés en construisant le module Stock

Aucun n'était visible avant exécution ; ils sont tous apparus au premier
parcours réel.

| Symptôme | Cause | Fichier |
|---|---|---|
| `POST /stock/commandes` → 500 | `select_from()` reçoit une **colonne** au lieu du **modèle** | `stock/services.py:84` |
| `POST /stock/receptions` → 500 | `reception.lignes` lu après le commit : objet expiré, lazy-load interdit | `stock/services.py` (fin de `enregistrer`) |
| Migration échouée sur `DuplicateObject` | SQLAlchemy recrée l'ENUM dans le `CREATE TABLE` alors qu'il est déjà créé | migration `e2f7b3c8a104` |
| Migration : `id` sans défaut serveur | le test insérait en SQL brut sans UUID ; l'ORM le génère | migration `e2f7b3c8a104` |
| ORM : `Mapper[MouvementStock] has no property 'article'` | `back_populates` sans la relation inverse | `tenants/models.py` |
| Listes paginées → 422 | `PaginationMeta` construit à la main, champs manquants | `stock/router.py` |

### Une erreur de ma méthode, à ne pas reproduire

J'ai annoncé « `tsc` propre » après un `npx tsc --noEmit -p tsconfig.json`.
Ce fichier est un **simple redirectionneur** (`"files": []`, `references`) : il ne
type-checkait rien du tout. Le vérificateur réel est `tsc -b` (celui du script
`build`). Après correction, cinq erreurs réelles sont apparues — dont deux
appels d'API cassés dans les modales.

**Règle** : le contrôle TypeScript de ce projet est `npx tsc -b --force`.
Jamais `tsc --noEmit -p tsconfig.json`.

### Incident d'environnement

Le conteneur PostgreSQL `sysdent_s0b` s'est arrêté (code 255) pendant la nuit du
5 au 6 octobre, port 55435 sans écoute. Une suite de tests complète a échoué
avec **295 erreurs** avant que la cause ne soit identifiée.

Les données n'étaient pas perdues : révision `e2f7b3c8a104`, 26 patients,
5 tables Stock, base plateforme intacte. Le conteneur redémarre par
`docker start sysdent_s0b`.

**Règle** : vérifier `docker ps` **avant** de lancer une suite de 25 minutes.

## Reproduction

| Script | Rôle |
|---|---|
| `Backend/_diag_etape0.py` | État des modules annoncés (Facture, Caisse, Produit, Commande, Agenda, Praticiens) |
| `Backend/_diag_etat_frontend.py` | État général avec le **payload réel** du frontend |
| `Backend/_diag_etat_general.py` | État général champ par champ, y compris le vidage |
| `_diag_inventaires.py` | Inventaires Consultation→Praticien, notions plateforme, menu Praticiens |

Les sorties sont dans `Backend/_diag_sortie.txt`, `_diag_etat_general.txt`,
`_diag_etat_general_frontend.txt`, `_diag_inventaires.txt`.

Deux réglages ont été nécessaires pour que le diagnostic voie ce que voit
l'utilisateur, et ils sont notés parce qu'ils masquent sinon la moitié des pannes :

- `ASGITransport(raise_app_exceptions=False)` — sinon httpx relance l'exception
  et le script meurt, au lieu d'enregistrer le 500 que renvoie le serveur ;
- les chemins doivent porter `/api/v1` (ma première version oubliait le préfixe
  et rapportait « 404 » sur toute une API parfaitement saine).

---

## Point 1 — Facture, Caisse, Produit, Commande « non effectifs »

### 1.1 Tenant de démonstration (`admin@cabinet.sn`, `ADMIN_CABINET`)

| Écran | Appel | Résultat observé |
|---|---|---|
| Liste des factures | `GET /factures?page=1&limit=20` | 🔴 **500** `MissingGreenlet` |
| Journal de caisse | `GET /factures/journal-caisse?limit=5` | 🟢 200, 10 lignes |
| Devis | `GET /devis?page=1&limit=5` | 🟢 200, 3 lignes |
| Nomenclature des actes | `GET /nomenclature/actes?limit=5` | 🟢 200, **14 actes** |
| Produits | `GET /stock/articles` | 🔴 **404 — route inexistante** |
| Mouvements de stock | `GET /stock/mouvements` | 🔴 **404** |
| Commandes fournisseurs | `GET /stock/commandes` | 🔴 **404** |
| Fournisseurs | `GET /stock/fournisseurs` | 🔴 **404** |
| Alertes de stock | `GET /stock/alertes` | 🔴 **404** |
| Utilisateurs | `GET /utilisateurs` | 🔴 **404** |
| Journal d'audit | `GET /audit?limit=5` | 🟡 200, **130 lignes exposées au client** |
| Agenda | `GET /rendez-vous/agenda?date=…` | 🟢 200 |
| Praticiens | `GET /praticiens` | 🟢 200, 1 élément |

### 1.2 Causes racines

**C1 — Liste des factures : 500 `MissingGreenlet`** 🔴

```
GET /api/v1/factures → 500
code=INTERNAL_SERVER_ERROR type=MissingGreenlet
```

Cause prouvée par la traceback : `src/modules/facturation/router.py:91`

```python
echeance_id = paiement.echeance.id if paiement.echeance else None
```

appelée depuis `router.py:119` (`paiements=[_paiement_vers_reponse(p) for p in facture.paiements]`).
La requête de liste (`facturation/services.py:457`) charge
`selectinload(Facture.lignes)` et `selectinload(Facture.paiements)`, **pas**
`Paiement.echeance`. Il n'existe pas de colonne `echeance_id` sur `Paiement` :
la clé étrangère vit sur `Echeance.paiement_id`. Le correctif exige donc un
chargement eager supplémentaire, pas un remplacement de colonne.

*Non corrigé à ce jour* — hors du périmètre du Chantier 2.

**C2 — Module Stock : absent, pas en erreur** 🔴

Les cinq routes renvoient `404` avec `code=HTTP_404`, c'est-à-dire « aucune
route enregistrée ». Il n'existe **aucun** dossier `stock` dans
`Backend/src/modules/`. Le frontend appelait déjà 5 endpoints inexistants avec
un état « module indisponible » honnête.

**C3 — Module Utilisateurs : absent** 🔴

`GET /utilisateurs` → `404`. Aucun dossier, aucun schéma, aucun service.
45 permissions et 6 rôles existent, sans personne à qui les attribuer.

**C4 — Nomenclature des actes : présente sur le tenant de démo, à confirmer sur un tenant neuf** 🟡

Le tenant de démo expose 14 actes. L'audit précédent affirmait que la
nomenclature est vide à la provisionnement (`master/services.py:106-108` ne sème
que le formulaire médicaments). **Cette affirmation reste à vérifier sur un
tenant neuf** — non vérifié à ce stade.

**C5 — Contrat commercial absent du `/auth/me` de ce tenant** 🟡

```
GET /auth/me → role=ADMIN_CABINET | plan=None | quotas=0 | features=0
```

`_contrat_du_cabinet` (`auth/router.py:25`) renvoie `{}` quand la base
plateforme ne connaît pas le cabinet. Le tenant de démo est antérieur à la Phase
B : il n'a pas de ligne `tenants_plateforme`. Ce n'est pas un bug du tenant, mais
l'absence du script de rattrapage.

### 1.3 Ce que le module Stock devra fournir

À créer de zéro : `articles` (nom, catégorie, unité, seuil minimum, prix
d'achat), `stock_par_site`, `mouvements` (entrée / sortie / ajustement motivé),
`lots` et dates de péremption, `fournisseurs`, `commandes` + `lignes_commande`,
`receptions` + `lignes_reception` qui créditent le stock, `alertes`.

---

## Point 2 — La modification de l'ÉTAT GÉNÉRAL échoue

**Cause racine principale, prouvée** 🔴

`patient-detail-page.tsx:122` appelle
`PUT /patients/{id}/etat-general` avec la totalité des champs. Le champ
`diabete_type` est une zone de texte initialisée à
`patient.etat_general?.diabete_type ?? ''`, donc **`''` pour un patient non
diabétique**.

Le validateur `patients/schemas.py:48` refusait la chaîne vide :

```python
normalise = v.strip().lower().replace(...)
if normalise not in valides:      # '' n'est pas dans valides
    raise ValueError(...)
```

Résultat mesuré avant correctif : **les 5 scénarios testés renvoyaient 422**,
dont « état vide » et « grossesse seule ». *Toute sauvegarde d'état général
depuis l'interface échouait*, quel que soit le contenu saisi.

**Trois causes secondaires, également prouvées :**

**C6 — Lecture de l'état : 500 `MissingGreenlet`** 🔴

```
GET /patients/{id}/etat-general → 500 MissingGreenlet
```

`patients/services.py:637` (avant correctif) :
`if dossier.etat_general:` — relation non chargée par `_obtenir_dossier`
(`services.py:623`, `select(Patient, DossierMedical)` sans `selectinload`).

**C7 — Le PATCH partiel revalidait à travers le schéma complet** 🔴

```
PATCH /patients/{id}/etat-general {"grossesse_terme": "2026-06-01"} → 500
```

`services.py:718` reconstruisait `EtatGeneralCreate(**data.model_dump(...))`
à partir du **seul fragment reçu**. Le validateur croisé
`coherence_grossesse` (`schemas.py:62`) exige `grossesse` vrai dès lors que
`grossesse_terme` est renseigné ; le fragment seul ne le contient pas, donc la
règle se déclenchait à tort. Le praticien devait renvoyer `grossesse` à chaque
correction du terme.

**C8 — Une erreur de validation métier devenait un 500** 🔴

`exception_handlers.py` traitait `RequestValidationError` (phase de requête)
mais pas `pydantic.ValidationError` levée **à l'intérieur** d'un handler.
Conséquence : une saisie invalide (`diabete_type = "TYPE_INEXISTANT"`)
répondait « une erreur interne inattendue s'est produite » au lieu d'indiquer le
champ fautif.

### 2.1 Correctifs appliqués et vérifiés

| Correctif | Fichier | Vérification |
|---|---|---|
| Chaîne vide = « non renseigné » | `patients/schemas.py:50` | 5/5 scénarios du payload frontend en 200 |
| Lecture sans lazy-load | `patients/services.py:635` | `GET …/etat-general` → 200 |
| PATCH fusionné avec l'état courant | `patients/services.py:705` | `PATCH {"grossesse_terme"}` seul → 200 |
| `ValidationError` métier → 422 | `core/exception_handlers.py` | saisie invalide → 422 + champ nommé |
| `null` sur booléen NOT NULL = `False` | `patients/services.py:776` | `PATCH {"diabete": null}` → 200 |

**Non-régression** : `test_patients_dossier` + `test_patients_numerotation` +
`test_consultations_workflow` → **71 passés**.

### 2.2 Quatre champs cliniques demandés — corrigé par migration `d7e4a1b2c9f3`

La mission exige « diabète + type + traitement, HTA + traitement, allergies
détaillées, antécédents médicaux, groupe sanguin ». Vérification initiale :

| Champ | Schéma | Colonne | Conséquence |
|---|---|---|---|
| `diabete_traitement` | ❌ | ❌ | 200 puis perte |
| `hta_traitement` | ❌ | ❌ | 200 puis perte |
| `groupe_sanguin` | ❌ | ❌ | 200 puis perte |
| `antecedents_familiaux` | ❌ | ❌ | 200 puis perte |

**Actions menées, dans l'ordre du protocole :**

1. **`extra="forbid"`** sur `EtatGeneralBase` et `EtatGeneralUpdate` — vérifié :
   ces quatre noms passent de 200 silencieux à **422 explicite**. La perte
   devient visible avant même que les colonnes existent.
2. **Plan écrit** : `docs/corrections/MIGRATION_ETAT_GENERAL.md`.
3. **Sauvegarde réelle** : `pg_dump` du conteneur, 311,6 Ko, copiée hors
   conteneur (`sauvegarde_sysdent_tenant_clinique_cabinet_sn_5bd215_20261005_214928.sql`).
4. **Test sur copie** (`sysdent_copie_test_etat_general`, créée par
   `CREATE DATABASE … WITH TEMPLATE`) : **17 vérifications, CONFORME** —
   4 colonnes ajoutées, 26 lignes conservées, écriture relue, `downgrade`
   conforme, `re-upgrade` conforme. La base réelle est restée à `c4f8a2d91e05`
   pendant tout le test.
5. **Application sur la base réelle** : révision `d7e4a1b2c9f3`, 26 lignes
   conservées, 4 colonnes présentes.
6. **Câblage** : modèle SQLAlchemy, schémas de saisie **et** de réponse,
   validateur « chaîne vide = non renseigné » sur les quatre champs.

**Vérification par exécution** (`Backend/_verif_champs_cliniques.py`) :

| Contrôle | Résultat |
|---|---|
| `PUT` des quatre champs | 🟢 200, les 4 valeurs retournées |
| `GET` relecture distincte | 🟢 200, les 4 valeurs persistées |
| `PATCH` quatre champs à `""` | 🟢 200, les 4 reviennent à `None` |
| `PATCH` champ inconnu | 🟢 **422** (au lieu d'une perte silencieuse) |

Le même principe que `diabete_type` s'applique : une zone de texte vidée par le
navigateur envoie `''`, et `''` est normalisé en `None` — sinon le dossier
afficherait une ligne vide qui se lirait comme une information manquante.

### 2.3 Formulaire frontend — les quatre champs sont saisissables

Sans cette étape, le serveur stockait les quatre champs mais **le praticien
n'avait aucun moyen de les renseigner** : le chantier aurait été terminé à
moitié. Modifié dans `patient-detail-page.tsx` et `features/patients/types.ts`.

| Ajout | Détail |
|---|---|
| Type de diabète | Liste déroulante (non précisé / type 1 / type 2 / gestationnel) — **il manquait aussi avant** : le backend exige un type valide pour un diabétique, mais aucune zone ne permettait de le choisir |
| Traitement du diabète | Zone texte, affichée si « Diabète » est coché |
| Traitement de l'HTA | Zone texte, affichée si « HTA » est coché |
| Groupe sanguin | Liste déroulante ABO × Rhésus (`GROUPES_SANGUINS`) |
| Antécédents familiaux | Zone texte |

**Cohérence ajoutée** : décocher « Diabète » efface `diabete_type` et
`diabete_traitement` ; décocher « HTA » efface `hta_traitement`. Sans cela le
dossier enregistrait « non diabétique · diabète de type 2 · Metformine », une
contradiction que le praticien relirait sans y voir d'erreur.

Contrôles : `npx tsc --noEmit` sans erreur ; aucune couleur en dur dans le bloc
ajouté (uniquement `text-foreground`, `text-primary`, tokens de bordure) ;
payload réel du formulaire contre l'API → 200, relecture correcte, décochement
bien propagé.

### 2.3 Décision à valider — effacement d'un indicateur clinique

Les colonnes `grossesse`, `diabete`, `hta`, `tabac`, `alcool`, `allaitement`
sont `NOT NULL`. `PATCH {"grossesse": null}` est donc aujourd'hui traduit en
`False`.

Or « pas enceinte » et « on ne sait pas » sont deux informations cliniques
différentes, et la seconde est réelle (un patient qui ne répond pas). Un troisième
état « inconnu » est cliniquement utile mais exige de rendre ces colonnes
nullable.

**Recommandation** : ne pas introduire ce troisième état dans cette version —
il conditionnerait les alertes de contre-indication (une grossesse « inconnue »
ne peut pas être traitée comme une absence de grossesse). Traduire `null` en
`False` et le documenter. À réexaminer avec le module d'alertes.

---

## Point 3 — Inventaire Consultation → Praticien

`praticien_id` apparaît dans **10 fichiers backend** et **6 fichiers frontend**.

**Cœur de la consultation** (ce que le Chantier 3 doit dissoudre) :

| Fichier | Occurrences |
|---|---|
| `consultations/services.py` | 10 |
| `consultations/router.py` | 5 |
| `consultations/schemas.py` | 2 |
| `consultations-list-page.tsx` | 6 |
| `consultations-api.ts` | 4 |
| `consultations/types.ts` | 2 |

**Dépendants** (ne contiennent pas la FK mais référencent le praticien) :
`rendezvous` (45), `odontogramme` (27), `cabinets` (77), `facturation` (17),
`ordonnances` (6), et côté frontend `rdv-form-modal.tsx` (10),
`praticiens-api.ts` (11).

**Constat de risque** : la dissolution du lien `Consultation → Praticien`
touche bien plus que la consultation. C'est cohérent avec la décision métier
(le dentiste *est* un utilisateur), mais cela rend le Chantier 3 **le plus
risqué** de la mission. Le rapport `05_PRATICIENS.md` doit arbitrer.

---

## Point 4 — Notions de plateforme dans l'interface client

| Élément | Fichier | Occurrences | Verdict |
|---|---|---|---|
| « Changer de cabinet » | `components/layout/cabinet-selector.tsx` | 2 | 🔴 **à supprimer** (Chantier 4) |
| Journal d'audit (page) | `features/audit/pages/audit-page.tsx` | 12 | 🔴 **à supprimer du client** |
| Journal d'audit (service) | `features/audit/services/audit-api.ts` | 4 | 🔴 idem |
| Entrées de menu audit | `App.tsx`, `lib/navigation.ts` | 7 | 🔴 idem |
| Route `/audit` | `App.tsx` | 5 | 🔴 idem |
| « plateforme » (libellés) | `sidebar.tsx`, `mon-compte-page.tsx`, `lib/roles.ts` | 4 | 🟡 à relire |
| quotas / plan | `mon-compte-page.tsx` | 2 | 🟢 **autorisé** (bannière d'avertissement) |
| mot « tenant » | `pages/login.tsx` | 1 | 🟡 libellé à remplacer |

L'écran `/audit` est réel et **renvoie 130 lignes** au client : l'exposition est
effective, pas théorique.

---

## Point 5 — Menu « Praticiens & Disponibilités »

Dépendances frontend du menu :

| Fichier | Occurrences |
|---|---|
| `praticiens-page.tsx` | 22 |
| `App.tsx` (routes) | 5 |
| `rdv-form-modal.tsx` | 10 |
| `consultations-list-page.tsx` | 10 |
| `praticiens-api.ts` | 11 |

**À qui sert-il aujourd'hui ?** `GET /praticiens` renvoie 1 élément pour le
tenant de démo — le compte admin, dont le profil praticien a été créé à la
provisionnement (`master/services.py:114`, « admin + son profil praticien »).
L'agenda et le formulaire de RDV sélectionnent un praticien ; la facturation
porte `praticien_id` sur la facture.

**Analyse complète et décision** : `docs/corrections/05_PRATICIENS.md`
(non rédigé à ce stade).

---

## Ce qui n'est pas vérifié

- **Tenant neuf** : ni la nomenclature d'actes, ni l'absence de Stock, ni le
  contrat `/auth/me` n'ont été observés sur un tenant réellement provisionné. La
  piste `_psycopg` bloquée par une politique Windows doit être vérifiée au
  préalable.
- **Rôles autres que `ADMIN_CABINET`** : toute la reproduction s'est faite avec
  l'administrateur. Le comportement de la secrétaire, du caissier et du médecin
  reste **non vérifié** — or c'est précisément ce que la matrice des rôles doit
  établir.
- **Parcours frontend réel** : les constats viennent d'appels API reproduisant
  le payload du frontend, pas d'un navigateur. Le rendu n'a pas été observé.
