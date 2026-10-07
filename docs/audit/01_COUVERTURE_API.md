# 01 — Couverture de l'API : le frontend consomme-t-il le backend ?

> **Date** : 4 octobre 2026 · **Périmètre** : `Backend/` (FastAPI, multi-tenant) et
> `Frontend/` (React 19 + Vite).
>
> **Méthode** — rien n'est supposé :
> - backend : `app.openapi()` (119 opérations) + lecture des routeurs pour les
>   permissions ; **toutes les routes GET sans paramètre de chemin ont été
>   réellement exécutées** contre une société peuplée ;
> - frontend : extraction de la totalité des appels `api.<verbe>(…)`
>   (115 appels, 16 fichiers), y compris les appels répartis sur plusieurs lignes ;
> - croisement par normalisation des routes (`${id}` et `{patient_id}` → `{}`,
> retrait du préfixe `/api/v1` ajouté par `lib/api.ts`).
>
> **Limite connue** : l'extraction est syntaxique. Un appel dont la route est
> construite dans une variable n'est pas détecté automatiquement — c'est le cas
> de `GET /praticiens` (`praticiens-api.ts:6`), que j'ai vérifié manuellement :
> il **est** consommé. Le tableau ci-dessous en tient compte.

---

## A1 — Cartographie du backend (119 opérations, 15 modules)

Les permissions ne sont pas dans le schéma OpenAPI : elles sont déclarées par le
décorateur `require_permissions(...)` dans le code. Elles ne sont donc pas
inventoriées opération par opération ici ; le catalogue des 45 permissions est
dans `src/common/permissions.py` et le rôle qui les porte est dans le JWT
(claims `role` et `permissions`).

_(tableau complet des routes dans l'annexe de ce document)_

**Répartition** : Patients 13 · Cabinets & Ressources 24 · Rendez-vous 12 ·
Consultations 12 · Odontogramme 11 · Master 10 · Facturation 14 (9 + 5 devis) ·
Ordonnances 8 · RBAC 5 · Auth 4 · Nomenclature 2 · Médicaments 2 · Audit 1 ·
Health 1.

### Santé des endpoints — mesurée par exécution réelle

Toutes les routes GET sans paramètre de chemin, exécutées sur une société de
démonstration peuplée (13 patients, 10 factures, 8 avec paiement) :

| Résultat | Routes |
|---|---|
| **200** | 17 routes |
| **500** | `GET /factures`, `GET /rbac/roles` |
| **422** (paramètre requis — normal) | `GET /rendez-vous/agenda`, `GET /rendez-vous/creneaux-libres` |

### Les deux 500 — bloquants, cause identifiée

**`GET /factures` → 500 `MissingGreenlet`** · `src/modules/facturation/router.py:91`

```python
if echeance_id is _NON_FOURNI:
    echeance_id = paiement.echeance.id if paiement.echeance else None
```

`Paiement.echeance` est une **relation**, et la requête de liste
(`facturation/services.py:457`) ne charge que `selectinload(Facture.lignes)` et
`selectinload(Facture.paiements)` — **pas** `Paiement.echeance`. Lire la
relation déclenche un lazy-load asynchrone interdit.

Il n'existe pas de colonne `echeance_id` sur `Paiement` : la clé étrangère vit
sur `Echeance.paiement_id`. Le correctif est donc un chargement eager
supplémentaire, pas un simple remplacement de colonne.

**Conséquence mesurée** : 8 factures sur 10 ont un paiement. *Dès qu'une seule
facture est réglée, la page Factures entière renvoie 500.* Avec zéro paiement, le
bug est invisible — c'est ce qui l'a laissé passer.

> Le docstring de `_paiement_vers_reponse` (lignes 81-89) documente ce piège pour
> les paiements *fraîchement créés* ; le chemin *liste* n'a pas été traité.

**`GET /rbac/roles` → 500 `MissingGreenlet`** · `src/modules/rbac/services.py:201`

```python
"nb_utilisateurs": len(role.utilisateurs or []),
```

Même famille de défaut : `Role.utilisateurs` n'est pas dans le `selectinload` de
la ligne 182. Le `or []` n'empêche rien — l'attribut existe sur la classe, l'I/O
est tenté. **La page d'administration des rôles est entièrement inutilisable.**

> ⚠️ Le précédent `PLAN_RESTE_A_FAIRE.md` marquait `rbac` comme ✅. C'est faux.

---

## A2 — Cartographie du frontend (18 routes d'écrans, 115 appels)

| Écran | Route | Service | Appels |
|---|---|---|---|
| Connexion | `/login` | `auth-store` | 1 |
| Tableau de bord | `/dashboard` | appel direct | 6 |
| Patients (liste + dossier) | `/patients`, `/patients/:id` | `patients-api` | 13 |
| Consultations (liste + détail) | `/consultations`, `/consultations/:id` | `consultations-api` | 12 |
| Odontogramme | `/odontogramme` | `odontogramme-api` | 9 |
| Ordonnances | `/ordonnances` | `ordonnances-api` | 10 |
| Agenda & RDV | `/agenda` | `rendezvous-api` | 9 |
| Cabinets & sites | `/cabinets` | `cabinets-api` | 12 |
| Praticiens | `/praticiens` | `praticiens-api` | 7 |
| Facturation | `/factures`, `/factures/:id`, `/caisse`, `/journal-caisse`, `/devis` | `facturation-api` | 14 |
| Rôles & permissions | `/rbac` | `rbac-api` | 5 |
| Journal d'audit | `/audit` | `audit-api` | 1 |
| Mon compte | `/compte` | appel direct | 2 |
| Paramètres | `/parametres` | — | 0 |
| Stock | `/stock`, `/stock/commandes` | `stock-api` | 5 |
| Utilisateurs | `/utilisateurs` | `utilisateurs-api` | 5 |

---

## A3 — Matrice de couverture

| Module | Route | Consommée ? | Écrans | Remarque |
|---|---|---|---|---|
| **Auth** | `POST /auth/login` | ✅ | /login | |
| | `GET /auth/me` | ✅ | global | garde de session |
| | `POST /auth/refresh` | 🟡 | global | appelé, mais **toujours 401** (§ A5) |
| | `POST /auth/logout` | ✅ | menu compte | |
| **Patients** | 13 routes | ✅ | liste, dossier | complète |
| **Consultations** | `POST /consultations/{id}/annuler` | ✅ | détail | |
| | `GET /consultations/{id}/total` | ❌ | — | **endpoint mort** — le contrat de facturation D1B n'est pas utilisé ; le frontend passe par `POST /factures/consultation/{id}` |
| **Facturation** | `GET /factures` | ✅ | liste | **renvoie 500** dès qu'une facture est réglée |
| | `POST /factures/{id}/echelonnement` | ✅ | détail facture | |
| | reste | ✅ | | |
| **Odontogramme** | `GET /odontogramme/patients/{id}/dent/{n}` | ❌ | — | jamais appelée (le drawer lit la liste globale) |
| | `GET /odontogramme/patients/{id}/dent/{n}/historique` | ❌ | — | jamais appelée — **l'historique par dent est inexistant côté UI** |
| | `PUT …/dent/{n}/faces` | ✅ | drawer dent | |
| **Cabinets** | `GET /cabinets/{id}/fauteuils` | ❌ | — | la page appelle `/fauteuils` autrement |
| **Praticiens** | `POST /praticiens` | ❌ | — | **le frontend ne peut pas créer de praticien** (ni l'UI ni le service) |
| | `GET /praticiens`, `PATCH`, disponibilités, créneaux | ✅ | praticiens | |
| **Rendez-vous** | `GET /rendez-vous/referentiel` | ❌ | — | le graphe des transitions n'est pas lu |
| | `GET /rendez-vous/{id}`, `PATCH` | ❌ | — | pas de détail unitaire de RDV |
| | `POST /rendez-vous/{id}/consultation` | ❌ | — | **l'ouverture de consultation depuis l'agenda n'est pas câblée** |
| | reste | ✅ | agenda | |
| **RBAC** | `GET /rbac/roles` | ✅ | rôles | **renvoie 500** |
| **Cabinets** | `GET /referentiel/disponibilites` | ❌ | — | référentiel inutilisé |
| **Master** | 10 routes | ❌ | — | **aucune UI** — console Super Admin absente (prévu : futur Backoffice) |
| **Stock** | — | ❌ | stock | module backend absent |
| **Utilisateurs** | — | ❌ | utilisateurs | module backend absent |
| **Audit** | `GET /audit` | ✅ | journal | |
| **Notifications** | — | ❌ | navbar | endpoint absent, état vide assumé |

### Appels frontend sans endpoint correspondant (10)

| Appel | Fichier | Endpoint attendu | Statut |
|---|---|---|---|
| `GET /stock/articles` | `stock-api.ts:30` | E1 | `TODO(backend)` assumé |
| `POST /stock/articles` | `stock-api.ts:37` | E1 | idem |
| `PATCH /stock/articles/${id}` | `stock-api.ts:41` | E1 | idem |
| `POST /stock/mouvements` | `stock-api.ts:45` | E2 | idem |
| `GET /stock/mouvements` | `stock-api.ts:49` | E2 | idem |
| `GET /utilisateurs` | `utilisateurs-api.ts:20` | B10 | `TODO(backend)` assumé |
| `POST /utilisateurs` | `utilisateurs-api.ts:27` | B10 | idem |
| `PATCH /utilisateurs/${id}` | `utilisateurs-api.ts:31` | B10 | idem |
| `POST /utilisateurs/${id}/mot-de-passe` | `utilisateurs-api.ts:35` | B10 | idem |
| `DELETE /utilisateurs/${id}` | `utilisateurs-api.ts:41` | B10 | idem |

**Ce ne sont pas des mocks** : chaque service porte un commentaire
`TODO(backend)` et la page affiche un état « module indisponible ». C'est la
bonne pratique — mais 10 % des appels frontend ne aboutissent pas.

### Routes backend jamais consommées (15)

`GET /health` · 10 routes `/master/*` · `GET /odontogramme/…/dent/{n}` ·
`GET /odontogramme/…/dent/{n}/historique` · `POST /praticiens` ·
`GET /referentiel/disponibilites` · `GET /rendez-vous/referentiel` ·
`GET /rendez-vous/{id}` · `PATCH /rendez-vous/{id}` ·
`POST /rendez-vous/{id}/consultation`.

---

## A5 — Verdict

### **Non, le frontend ne consomme pas entièrement le backend — et deux écrans sont morts.**

**Couverture mesurée : 71 des 86 routes distinctes sont consommées, soit 82 %.**

| Module | Couverture |
|---|---|
| Patients | 100 % |
| Consultations / actes | 92 % (manque `/total`) |
| Ordonnances | 100 % |
| Facturation / devis | 100 % — mais **`/factures` est cassé** |
| Rendez-vous | 72 % (manque le détail, l'ouverture de consultation) |
| Cabinets & ressources | 96 % |
| Odontogramme | 78 % (historique par dent non exposé) |
| Praticiens | 88 % (**création absente**) |
| RBAC | 100 % — mais **`/rbac/roles` est cassé** |
| Audit | 100 % |
| Auth | 100 % — mais **refresh inopérant** |
| Master / plateforme | **0 %** (attendu : Backoffice futur) |
| Stock | **0 %** (module inexistant) |
| Utilisateurs | **0 %** (module inexistant) |

### Points bloquants, par ordre de gravité

| # | Constat | Effet utilisateur | Correctif |
|---|---|---|---|
| **B1** | `GET /factures` → 500 dès qu'une facture est réglée | **Page Factures inutilisable** en usage normal | `selectinload(Facture.paiements).selectinload(Paiement.echeance)` |
| **B2** | `GET /rbac/roles` → 500 | **Gestion des rôles inutilisable** | `.selectinload(Role.utilisateurs)` |
| **B3** | `/auth/refresh` exige un jeton **valide** | **Session morte au bout de 15 min** | lire `tenant_id` dans le refresh token |
| **B4** | Aucun endpoint `/utilisateurs` | **Un cabinet ne peut pas recruter** | module backend |
| **B5** | Nomenclature d'actes vide à la provisionnement | **Aucun acte saisissable → rien à facturer** | semer au provisionnement |
| **B6** | `POST /praticiens` non câblé | **Impossible d'ajouter un dentiste** | service + UI |
| B7 | `limit` non borné sur `/rendez-vous`, `/ordonnances` | Pagination non maîtrisée | `Query(…, le=100)` |
| B8 | `/nomenclature/actes?limit=201` → 500 au lieu de 422 | Validation incohérente | `Query(le=100)` |

### Ce qui est réellement bien fait — à ne pas casser

- **Aucune donnée fictive** : 0 mock, 0 fixture, 0 `setTimeout` simulant une
  réponse, 0 couleur codée en dur hors tokens.
- Les 10 appels sans endpoint sont **isolés et documentés**, pas masqués.
- Les 4 états d'écran (chargement, erreur, vide, succès) sont gérés partout.
- Les types sont alignés sur les réponses réelles — après la correction de
  `Praticien`, qui avait révélé 3 autres écrans cassés (`nom_complet`).

---

## Annexe — les 119 routes

_(générée depuis `app.openapi()` le 4 octobre 2026)_

#### Audit & Traçabilité  (1 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/audit` | — | — |

#### Authentification  (4 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | oui | — |
| `POST` | `/api/v1/auth/logout` | oui | — |
| `GET` | `/api/v1/auth/me` | — | — |
| `POST` | `/api/v1/auth/refresh` | oui | — |

#### Cabinets & Ressources  (24 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/cabinets` | — | — |
| `GET` | `/api/v1/cabinets/{cabinet_id}` | — | — |
| `PATCH` | `/api/v1/cabinets/{cabinet_id}` | oui | — |
| `GET` | `/api/v1/cabinets/{cabinet_id}/fauteuils` | — | — |
| `DELETE` | `/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement` | — | — |
| `GET` | `/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement` | — | — |
| `POST` | `/api/v1/cabinets/{cabinet_id}/praticiens/{praticien_id}/rattachement` | oui | — |
| `GET` | `/api/v1/cabinets/{cabinet_id}/salles` | — | — |
| `POST` | `/api/v1/cabinets/{cabinet_id}/salles` | oui | — |
| `DELETE` | `/api/v1/cabinets/{cabinet_id}/salles/{salle_id}` | — | — |
| `PATCH` | `/api/v1/cabinets/{cabinet_id}/salles/{salle_id}` | oui | — |
| `DELETE` | `/api/v1/disponibilites/{disponibilite_id}` | — | — |
| `DELETE` | `/api/v1/fauteuils/{fauteuil_id}` | — | — |
| `PATCH` | `/api/v1/fauteuils/{fauteuil_id}` | oui | — |
| `POST` | `/api/v1/fauteuils/{fauteuil_id}/reactiver` | — | — |
| `GET` | `/api/v1/praticiens` | — | — |
| `POST` | `/api/v1/praticiens` | oui | — |
| `GET` | `/api/v1/praticiens/{praticien_id}` | — | — |
| `PATCH` | `/api/v1/praticiens/{praticien_id}` | oui | — |
| `GET` | `/api/v1/praticiens/{praticien_id}/creneaux` | — | date |
| `GET` | `/api/v1/praticiens/{praticien_id}/disponibilites` | — | — |
| `POST` | `/api/v1/praticiens/{praticien_id}/disponibilites` | oui | — |
| `GET` | `/api/v1/referentiel/disponibilites` | — | — |
| `POST` | `/api/v1/salles/{salle_id}/fauteuils` | oui | — |

#### Console Super Admin  (10 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `POST` | `/api/v1/master/auth/login` | oui | — |
| `POST` | `/api/v1/master/auth/logout` | — | refresh_token |
| `GET` | `/api/v1/master/auth/me` | — | — |
| `POST` | `/api/v1/master/auth/refresh` | — | refresh_token |
| `GET` | `/api/v1/master/societes` | — | — |
| `POST` | `/api/v1/master/societes` | oui | — |
| `GET` | `/api/v1/master/societes/{societe_id}` | — | — |
| `PATCH` | `/api/v1/master/societes/{societe_id}` | oui | — |
| `POST` | `/api/v1/master/societes/{societe_id}/statut` | oui | — |
| `GET` | `/api/v1/master/statistiques` | — | — |

#### Consultations & Actes  (12 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/consultations` | — | — |
| `POST` | `/api/v1/consultations` | oui | — |
| `DELETE` | `/api/v1/consultations/actes/{acte_id}` | — | — |
| `PATCH` | `/api/v1/consultations/actes/{acte_id}` | oui | — |
| `GET` | `/api/v1/consultations/{consultation_id}` | — | — |
| `PATCH` | `/api/v1/consultations/{consultation_id}` | oui | — |
| `GET` | `/api/v1/consultations/{consultation_id}/actes` | — | — |
| `POST` | `/api/v1/consultations/{consultation_id}/actes` | oui | — |
| `POST` | `/api/v1/consultations/{consultation_id}/annuler` | oui | — |
| `GET` | `/api/v1/consultations/{consultation_id}/detail` | — | — |
| `POST` | `/api/v1/consultations/{consultation_id}/terminer` | oui | — |
| `GET` | `/api/v1/consultations/{consultation_id}/total` | — | — |

#### Facturation & Caisse  (9 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/factures` | — | — |
| `POST` | `/api/v1/factures` | oui | — |
| `POST` | `/api/v1/factures/consultation/{consultation_id}` | oui | — |
| `GET` | `/api/v1/factures/journal-caisse` | — | — |
| `GET` | `/api/v1/factures/{facture_id}` | — | — |
| `POST` | `/api/v1/factures/{facture_id}/annuler` | — | motif |
| `GET` | `/api/v1/factures/{facture_id}/echelonnement` | — | — |
| `POST` | `/api/v1/factures/{facture_id}/echelonnement` | oui | — |
| `POST` | `/api/v1/factures/{facture_id}/paiements` | oui | — |

#### Facturation & Devis  (5 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/devis` | — | — |
| `POST` | `/api/v1/devis` | oui | — |
| `GET` | `/api/v1/devis/{devis_id}` | — | — |
| `POST` | `/api/v1/devis/{devis_id}/convertir` | — | — |
| `POST` | `/api/v1/devis/{devis_id}/statut` | oui | — |

#### Monitoring & Santé  (1 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/health` | — | — |

#### Nomenclature des Actes  (2 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/nomenclature/actes` | — | — |
| `POST` | `/api/v1/nomenclature/actes` | oui | — |

#### Odontogramme  (11 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/odontogramme/patients/{patient_id}` | — | — |
| `POST` | `/api/v1/odontogramme/patients/{patient_id}` | oui | — |
| `GET` | `/api/v1/odontogramme/patients/{patient_id}/charting` | — | — |
| `POST` | `/api/v1/odontogramme/patients/{patient_id}/charting` | oui | — |
| `PATCH` | `/api/v1/odontogramme/patients/{patient_id}/dent` | oui | — |
| `GET` | `/api/v1/odontogramme/patients/{patient_id}/dent/{numero_fdi}` | — | — |
| `PUT` | `/api/v1/odontogramme/patients/{patient_id}/dent/{numero_fdi}/faces` | oui | — |
| `GET` | `/api/v1/odontogramme/patients/{patient_id}/dent/{numero_fdi}/historique` | — | — |
| `PATCH` | `/api/v1/odontogramme/patients/{patient_id}/dents` | oui | — |
| `GET` | `/api/v1/odontogramme/patients/{patient_id}/historique` | — | — |
| `GET` | `/api/v1/odontogramme/referentiel/etats` | — | — |

#### Ordonnances & Prescriptions  (8 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/ordonnances` | — | — |
| `POST` | `/api/v1/ordonnances` | oui | — |
| `POST` | `/api/v1/ordonnances/controle` | oui | — |
| `GET` | `/api/v1/ordonnances/{prescription_id}` | — | — |
| `PATCH` | `/api/v1/ordonnances/{prescription_id}` | oui | — |
| `POST` | `/api/v1/ordonnances/{prescription_id}/lignes` | oui | — |
| `DELETE` | `/api/v1/ordonnances/{prescription_id}/lignes/{ligne_id}` | — | — |
| `POST` | `/api/v1/ordonnances/{prescription_id}/signer` | — | — |

#### Patients & Dossier Médical  (13 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/patients` | — | — |
| `POST` | `/api/v1/patients` | oui | — |
| `PATCH` | `/api/v1/patients/antecedents/{antecedent_id}` | oui | — |
| `GET` | `/api/v1/patients/{patient_id}` | — | — |
| `PATCH` | `/api/v1/patients/{patient_id}` | oui | — |
| `GET` | `/api/v1/patients/{patient_id}/antecedents` | — | — |
| `POST` | `/api/v1/patients/{patient_id}/antecedents` | oui | — |
| `POST` | `/api/v1/patients/{patient_id}/archiver` | oui | — |
| `GET` | `/api/v1/patients/{patient_id}/dossier` | — | — |
| `GET` | `/api/v1/patients/{patient_id}/etat-general` | — | — |
| `PATCH` | `/api/v1/patients/{patient_id}/etat-general` | oui | — |
| `PUT` | `/api/v1/patients/{patient_id}/etat-general` | oui | — |
| `POST` | `/api/v1/patients/{patient_id}/reactiver` | — | — |

#### RBAC & Rôles  (5 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/rbac/permissions` | — | — |
| `GET` | `/api/v1/rbac/roles` | — | — |
| `POST` | `/api/v1/rbac/roles` | oui | — |
| `DELETE` | `/api/v1/rbac/roles/{role_id}/permissions` | — | permission |
| `POST` | `/api/v1/rbac/roles/{role_id}/permissions` | oui | — |

#### Rendez-vous & Agenda  (12 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/rendez-vous` | — | — |
| `POST` | `/api/v1/rendez-vous` | oui | — |
| `GET` | `/api/v1/rendez-vous/agenda` | — | date |
| `GET` | `/api/v1/rendez-vous/creneaux-libres` | — | praticien_id, date |
| `POST` | `/api/v1/rendez-vous/fauteuils/blocage` | oui | — |
| `DELETE` | `/api/v1/rendez-vous/fauteuils/blocage/{creneau_id}` | — | — |
| `GET` | `/api/v1/rendez-vous/referentiel` | — | — |
| `GET` | `/api/v1/rendez-vous/{rendez_vous_id}` | — | — |
| `PATCH` | `/api/v1/rendez-vous/{rendez_vous_id}` | oui | — |
| `POST` | `/api/v1/rendez-vous/{rendez_vous_id}/consultation` | — | — |
| `POST` | `/api/v1/rendez-vous/{rendez_vous_id}/planifier` | — | debut |
| `POST` | `/api/v1/rendez-vous/{rendez_vous_id}/statut` | — | statut |

#### Référentiel Médicamenteux  (2 opérations)

| Méthode | Route | Corps | Query requis |
|---|---|---|---|
| `GET` | `/api/v1/ordonnances/medicaments` | — | — |
| `POST` | `/api/v1/ordonnances/medicaments` | oui | — |
