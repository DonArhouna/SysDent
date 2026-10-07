# 02 — Données codées en dur dans le frontend

> **Date** : 4 octobre 2026 · **Périmètre** : `Frontend/src` — 106 fichiers
> `.ts`/`.tsx`, **18 028 lignes**, balayés un par un par motif.

---

## Verdict en une ligne

**Il n'y a aucune donnée fictive dans le frontend.** Zéro mock, zéro fixture,
zéro KPI fabriqué, zéro `Promise.resolve({…})`, zéro UUID figé, zéro URL codée en
dur, zéro JWT en clair, zéro jeu d'essai « factice ».

La seule defaultedata réelle est d'une autre nature : **21 tableaux de constantes
littérales**, dont 12 dupliquent des énumérations déjà publiées par le backend.
C'est un risque de dérive, pas une fraude — mais il est réel et mesurable.

---

## 1. Ce que le balayage automatique a trouvé

| Motif recherché | Occurrences | Verdict |
|---|---|---|
| `Promise.resolve({` / `Promise.resolve([` | **0** | ✅ aucun faux service |
| Tableau de démo (`const x = [{…}]`) | 21 | 🟠 12 dupliquent le backend (§ 3) |
| `setTimeout(` | 4 | ✅ **aucun ne simule une réponse** (§ 2) |
| UUID figé | **0** | ✅ |
| URL absolue hors localhost | **0** | ✅ |
| JWT (`eyJ…`) en clair | **0** | ✅ |
| Mot de passe en clair | **0** | ✅ (`MotDePasse` n'apparaît que comme nom de champ TS) |
| Permissions codées en dur | **0** | ✅ catalogue lu côté serveur (§ 4) |

---

## 2. Les 4 `setTimeout` — vérifiés un par un

C'est le motif le plus suspect (un `setTimeout` qui résout une fausse réponse est
le piège classique du « mock discret »). Les quatre occurrences sont légitimes :

| Fichier:ligne | Usage réel | Simulation ? |
|---|---|---|
| `odontogramme-page.tsx:74` | **debounce 250 ms** sur la recherche patient, puis `patientsApi.lister()` réel | ❌ non |
| `rdv-form-modal.tsx:116` | **debounce 250 ms** sur la recherche patient, puis appel réel | ❌ non |
| `ordonnance-modal.tsx:86` | **debounce** avant la vérification d'interaction médicamenteuse (appel réel) | ❌ non |
| `stores/toast-store.ts:31` | minuterie d'**auto-fermeture** d'une notification | ❌ non |

Trois appels API réels sont bien protectorés par debounce, un toast se referme
tout seul. Aucun ne fabrique de données.

---

## 3. Les 21 tableaux littéraux — classement

### 3.1 Données statiques légitimes (à conserver)

Ce sont des données de **structure applicative** ou de **référentiel médical
nuancier** qui n'appartiennent pas au tenant. Les déplacer en base serait une
erreur.

| Fichier:ligne | Constante | Nature |
|---|---|---|
| `lib/navigation.ts:38` | `NAVIGATION` | arborescence de l'application |
| `components/layout/command-palette.tsx:70` | `actions` | commandes de la palette Ctrl+K |
| `components/layout/topbar.tsx:109` | `entreesMenu` | entrées du menu utilisateur |
| `compte/parametres-page.tsx:21,26` | `CHOIX`, `RACCOURCIS` | choix de thème + raccourcis clavier |
| `praticiens-page.tsx:29` | `JOURS_SEMAINE` | index 0-6 de la semaine |
| `odontogramme/dent-drawer.tsx:20` | `FACES_DECOUPEES` | 5 faces FDI (occlusale, vestibulaire, linguale, mésiale, distale) |

### 3.2 Énumérations **dupliquées** du backend — dérive possible 🔴

Chacune de ces listes redit mot pour mot une énumération qui existe côté serveur.
Le jour où le backend ajoute une valeur, le filtre frontend continuera de ne pas
la proposer — **silencieusement**.

| Fichier:ligne | Constante | Duplique | Laisse de côté |
|---|---|---|---|
| `facturation/factures-list-page.tsx:45` | `STATUT_OPTIONS` | `StatutFactureEnum` | statut |
| `facturation/devis-list-page.tsx:326` | `STATUT_DEVIS_DE_CHOIX` | `StatutDevisEnum` | statut |
| `facturation/journal-caisse-page.tsx:23` | `MODES_OPTIONS` | `ModePaiementEnum` | filtre |
| `facturation/components/paiement-modal.tsx:19` | `MODES_PAIEMENT` | `ModePaiementEnum` | saisie |
| `facturation/components/echelonnement-modal.tsx:19` | `FREQUENCES` | `FrequenceEcheanceEnum` | saisie |
| `ordonnances/medicament-modal.tsx:16` | `FORMES` | forme galénique | saisie |
| `ordonnances/medicament-modal.tsx:26` | `CONDITIONS_COURANTES` | conditions d'alerte | saisie |
| `patients/antecedent-modal.tsx:18` | `TYPES_ANTECEDENTS` | types d'antécédent | saisie |
| `rendezvous/blocage-fauteuil-modal.tsx:19` | `MOTIFS_BLOCAGE` | `MotifBlocageFauteuil` | saisie |
| `audit/audit-page.tsx:21` | `RESOURCE_TYPES` | types de ressource journal | filtre |
| `stock/article-modal.tsx:16` | `CATEGORIES` | **n'existe pas côté backend** | saisie libre |
| `stock/article-modal.tsx:26` | `UNITES` | **n'existe pas côté backend** | saisie libre |

**Gravité : 🟠 moyenne.** Ce n'est pas un mensonge affiché à l'utilisateur
aujourd'hui — les valeurs sont correctes. Le risque est **la dérive au fil des
évolutions**, plus un défaut de cohérence si le serveur accepte une valeur que
l'UI ne propose pas.

#### La preuve que l'infrastructure existe déjà et n'est pas utilisée

`GET /api/v1/rendez-vous/referentiel` (`src/modules/rendezvous/router.py`)
publie **exactement** ce dont le frontend a besoin, et mieux :

```python
"statuts": [{"code": code, "libelle": LIBELLES_STATUT[code],
             "terminal": code in ("TERMINEE", "ANNULE", "ABSENT")} for code in STATUTS],
"transitions": {code: sorted(transitions_possibles(code)) for code in STATUTS},
"motifs_blocage": [{"code": code, "libelle": LIBELLES_MOTIF_BLOCAGE[code]} ...]
```

Le docstring du endpoint dit mot pour mot son intention :

> « Publier le graphe des transitions évite que le frontend invente un bouton
> "Terminer" sur un rendez-vous planifié, et montre au secrétariat uniquement
> les actions réellement possibles. »

**Le frontend ne l'appelle pas.** Il conserve ses listes en dur et n'a donc pas
le drapeau `terminal` — c'est-à-dire qu'il ne sait pas quelles actions
proposer, exactement le problème que l'endpoint devait résoudre.

De plus, le backend **renvoie déjà la liste des valeurs valides dans ses erreurs
de validation** (`facturation/services.py:446`) :

```python
raise BusinessRuleViolationException(
    f"Statut inconnu : {statut}.",
    code="STATUT_FACTURE_INCONNU",
    details={"statuts": [s.value for s in StatutFactureEnum]},
)
```

L'information est là ; le frontend ne l'exploite pas.

**Action recommandée** : créer un `GET /referentiel/global` (ou un
`/referentiel/{domaine}` par domaine) regroupant statuts, modes, fréquences et
libellés, puis un hook `useReferentiel()` mis en cache par React Query. Coût : S
(1 endpoint + 1 hook + remplacement de 12 constantes). Supprime définitivement
le risque de dérive.

### 3.3 Libellés d'interface

Les libellés français (`« Total patients »`, `« Gestion Dentaire »`) sont des
**chaînes d'interface**, pas des données. Les mettre en base serait une
sur-ingénierie pour une application monolingue francophone. **Sans action**, sauf
si le multilingual (recommandé au volet C) devient un engagement — auquel cas
ils devraient migrer vers des clés i18n.

---

## 4. Permissions et rôles — vérifié : rien en dur côté front ✅

Point d'attention explicite de la mission. Vérifié :

- `stores/auth-store.ts:169` — le test de permission est
  `profil.permissions.includes(permission)`, le profil venant de
  `GET /auth/me` ;
- `features/rbac/components/permission-matrix.tsx` — la matrice affichée vient
  de `rbacApi.listerCataloguePermissions()` → `GET /rbac/permissions` ;
- la seule occurrence de la chaîne `ADMIN:USER:*` dans tout le front est un
  **texte d'aide** dans `utilisateurs-page.tsx:66` (« Permissions
  `ADMIN:USER:*` dans la matrice RBAC »), pas un garde d'accès.

**Aucun catalogue de permissions n'est dupliqué dans le frontend.** Les
permissions pilotent l'affichage, mais **la décision d'accès reste au serveur** —
ce qui est le seul comportement acceptable.

---

## 5. KPI du tableau de bord — vérifié : dérivés de l'API ✅

C'était le candidat le plus probable à du contenu factice. Vérifié ligne à ligne
(`src/pages/dashboard.tsx`) :

| KPI | Origine de la valeur |
|---|---|
| Total patients | `GET /patients?page=1&limit=1` → `meta.total_records` |
| Factures en attente | `GET /factures?statut=EMISE&limit=1` → `meta.total_records` |
| Devis envoyés | `GET /devis?statut=ENVOYE&limit=1` → `meta.total_records` |
| Encaissements du jour | `GET /factures/journal-caisse` → somme réelle des lignes |

Le tableau `cartes` (ligne 189) ne contient que `{ label, value, detail, icone,
ton }` — **la valeur est calculée à partir de la réponse**, jamais une constante.

> ⚠️ Conséquence du bug B1 : le KPI « Factures en attente » est **permanemment en
> erreur**, puisque `/factures` renvoie 500. Le tableau affiche `-`.

---

## 6. Tableau récapitulatif — Gravité et action

| # | Fichier / ligne | Type | Exemple | Devrait provenir de | Gravité | Action |
|---|---|---|---|---|---|---|
| 1 | `factures-list-page.tsx:45` | liste d'options (statuts) | `EMISE`, `PARTIELLEMENT_PAYEE` | `GET /referentiel` | 🟠 | migrer |
| 2 | `devis-list-page.tsx:326` | liste d'options (statuts devis) | `BROUILLON`, `ACCEPTE` | idem | 🟠 | migrer |
| 3 | `journal-caisse-page.tsx:23` | liste d'options (modes) | `ESPECES`, `MOBILE_MONEY` | idem | 🟠 | migrer |
| 4 | `paiement-modal.tsx:19` | liste d'options (modes) | idem | idem | 🟠 | migrer |
| 5 | `echelonnement-modal.tsx:19` | liste d'options (fréquences) | `MENSUEL`, `HEBDOMADAIRE` | idem | 🟠 | migrer |
| 6 | `dent-drawer.tsx:20` | référentiel FDI | `OCCLUSALE`, `VESTIBULAIRE` | **statique légitime** | 🟢 | aucune |
| 7 | `medicament-modal.tsx:16,26` | listes (formes, conditions) | `SIROP`, `GROSSESSE` | idem | 🟠 | migrer |
| 8 | `antecedent-modal.tsx:18` | liste (types d'antécédent) | `CARDIO`, `DIABETE` | idem | 🟠 | migrer |
| 9 | `blocage-fauteuil-modal.tsx:19` | liste (motifs) | `PANNE`, `DESINFECTION` | **`/rendez-vous/referentiel` existe déjà** | 🔴 | migrer (prioritaire) |
| 10 | `audit-page.tsx:21` | liste (types de ressource) | `Patient`, `Consultation` | idem | 🟡 | migrer |
| 11 | `stock/article-modal.tsx:16,26` | listes libres | `Anesthésie`, `Boîte` | **référentiel à créer** | 🟡 | créer (module stock à faire d'abord) |
| 12 | `dashboard.tsx:189` | structure de KPI | libellés + format | valeurs déjà API | 🟢 | aucune |
| 13 | `lib/navigation.ts:38` | arborescence menus | — | **statique légitime** | 🟢 | aucune |
| 14 | `command-palette.tsx:70`, `topbar.tsx:109` | commandes UI | — | **statique légitime** | 🟢 | aucune |
| 15 | `parametres-page.tsx:21,26` | thème + raccourcis | `Ctrl + K` | **statique légitime** | 🟢 | aucune |
| 16 | `praticiens-page.tsx:29` | jours de semaine | index 0-6 | **statique légitime** | 🟢 | aucune |

**Bilan : 0 gravité 🔴 sur les données elles-mêmes** (aucune donnée fausse
affichée), **9 lignes 🟠** de risque de dérive, **1 🔴 prioritaire** parce que le
référentiel correspondant existe déjà et n'est pas appelé.

---

## 7. Limites de cet audit — ce que je n'ai pas pu vérifier

- **Le balayage est syntaxique.** Une donnée fabriquée via une fonction
  (`function fakeData()`) échappe aux motifs. J'ai relu manuellement les 16
  fichiers contenant des appels API — aucun ne fabrique de réponse.
- **Le backend n'a pas été audité pour le hardcoding** (hors les deux
  `MissingGreenlet` trouvés par exécution réelle). Des données de démonstration
  pourraient y subsister — notamment dans `Backend/_seed_demo.py`, qui est
  **explicitement** un script de remplissage et ne fait aucun écrit direct en
  base : il passe par les endpoints publics, ce qui est la bonne pratique.
- **Les fichiers hors `src/` n'ont pas été balayés** (`vite.config.ts`,
  `tailwind.config`, `components.json` de shadcn) : ce sont de la configuration,
  pas des données.
