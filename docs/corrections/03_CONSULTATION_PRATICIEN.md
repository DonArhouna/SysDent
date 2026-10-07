# Chantier 3 — Découpler la Consultation de l'entité Praticien

> **Statut** : plan écrit, prêt à exécuter. La migration touche des données
> existantes : elle sera testée sur une copie de la base de démonstration avant
> application, avec sauvegarde préalable.

## 1. Le problème, établi par lecture du code

Aujourd'hui, enregistrer *qui* a fait un geste suppose de créer au préalable un
profil `Praticien`. Trois modules l'exigent :

| Module | Refus | Conséquence |
|---|---|---|
| Consultations | `consultations/services.py:248` | impossible d'ouvrir une consultation |
| Odontogramme | `odontogramme/services.py:177` | impossible de consigner un constat |
| Ordonnances | `ordonnances/services.py:242` et `:250` | impossible d'établir une ordonnance |

Or `consultations.praticien_id` est **`NOT NULL`** vers `praticiens.id`.

## 2. Pourquoi c'est un défaut de conception, pas une contrainte métier

Le fait décisif : **`Praticien.numero_ordre` est déjà nullable** dans le modèle.

```
class Praticien:
    numero_ordre: Mapped[str | None] = ...  # nullable=True
```

Un profil praticien **n'exige aucun numéro d'Ordre**. La garde
`PRATICIEN_NON_IDENTIFIE` est donc **plus stricte que le modèle de données
qu'elle prétend protéger** : elle impose de créer une entité réglementaire —
titre, spécialité, rattachement par cabinet, disponibilités — pour la seule
raison de pouvoir enregistrer une authorship.

Ce que cela exclut aujourd'hui, sans aucune raison réglementaire :

- un assistant qui réalise un détartrage sous supervision ;
- un interne ou un stagiaire autorisé ;
- un praticien intérimaire ou en vacation ;
- tout praticien dont le numéro d'Ordre n'a pas encore été saisi — ce qui est
  fréquent, et bloque le cabinet au lieu de le ralentir.

Et ce que cela multiplie : chaque profil practitioner déclenche des
disponibilités, des rattachements par cabinet, une navabilité praticiens dans le
menu. Le coût d'exploitation est réel.

## 3. Ce qui change

**L'auteur d'un acte est le compte authentifié, pas un profil d'Ordre.**

Le compte vient du JWT : il est connu, horodaté, et ne peut pas être inventé. Le
profil `Praticien` devient ce qu'il est réellement — une **attribution
réglementaire optionnelle** : numéro d'Ordre, spécialité, signature.

### Backend

| # | Action | Fichier |
|---|---|---|
| B1 | `consultations.auteur_id` → `utilisateurs.id`, `NOT NULL` | `tenants/models.py` |
| B2 | `consultations.auteur_email` figé, comme sur `paiements` et `sessions_caisse` | `tenants/models.py` |
| B3 | `consultations.praticien_id` passe **nullable** | migration |
| B4 | `ConsultationService._resoudre_praticien` : plus de refus, renvoie `Optional` | `consultations/services.py:248` |
| B5 | La création de consultation attribue l'auteur depuis le JWT | `consultations/services.py:316` |
| B6 | Odontogramme : l'auteur est le compte, le profil reste facultatif | `odontogramme/services.py:177` |
| B7 | Ordonnances : idem, avec le point legal signalé en §5 | `ordonnances/services.py:242` |
| B8 | `ConsultationResponse` expose l'auteur **et** le profil, distincts | `consultations/schemas.py:183` |
| B9 | Le filtre `praticien_id` reste, et gagne `auteur_id` | `consultations/services.py:529` |

### Frontend

| # | Action | Fichier |
|---|---|---|
| F1 | Afficher l'auteur de la consultation, pas seulement son praticien | `consultations-list-page.tsx` |
| F2 | Type `Consultation` : `auteur_email` en plus de `praticien_id` | `consultations/types.ts` |
| F3 | Fiche patient : idem | `patient-detail-page.tsx` |
| F4 | Ordonnance imprimée : prescripteur = auteur, profil si présent | `ordonnance-print-view.tsx` |
| F5 | Agenda : la pastille praticien reste, sans devenir un prérequis | `agenda-page.tsx` |

## 4. Plan de migration

Réversible, additive puis relâchée. Aucune ligne n'est supprimée.

```sql
-- 1. Colonne auteur, nullable d'abord : on ne peut pas l'ajouter NOT NULL
--    tant que les consultations existantes n'ont pas de valeur.
ALTER TABLE consultations ADD COLUMN auteur_id uuid REFERENCES utilisateurs(id);
ALTER TABLE consultations ADD COLUMN auteur_email varchar(150);

-- 2. Remplissage depuis le profil : l'auteur actuel EST le compte lié au
--    praticien. On ne devine rien, on recopie la vérité existante.
UPDATE consultations c
   SET auteur_id = p.utilisateur_id,
       auteur_email = u.email
  FROM praticiens p
  JOIN utilisateurs u ON u.id = p.utilisateur_id
 WHERE c.praticien_id = p.id
   AND c.auteur_id IS NULL;

-- 3. Seule une consultation sans praticien resterait sans auteur.
--    Il doit y en avoir zéro : on refuse la migration plutôt que d'inventer.
-- 4. Verrou : plus de consultation sans auteur.
ALTER TABLE consultations ALTER COLUMN auteur_id SET NOT NULL;
-- 5. Le profil devient facultatif.
ALTER TABLE consultations ALTER COLUMN praticien_id DROP NOT NULL;
```

**Contrôle bloquant** : si l'étape 3 laisse une ligne, la migration s'arrête et
signale le nombre exact. Un auteur inventé serait pire qu'un auteur absent.

**Downgrade** : on repasse `praticien_id` en `NOT NULL` — uniquement possible si
aucune consultation n'a été créée sans profil depuis. Si c'est le cas, le
`downgrade` refuse et le dit, plutôt que de supprimer des consultations.

## 5. Décision à valider 🟡 — l'ordonnance

C'est le seul point où le découplage touche à une obligation légale, et je ne
décide pas à votre place.

L'ordonnance est un **acte médical signé**. Aujourd'hui, l'exigence est
« l'auteur possède un profil praticien ». Après découplage, l'auteur est
toujours identifié (compte + email figé), mais il ne serait plus garanti
inscrit à l'Ordre.

| Option | Description | Conséquence |
|---|---|---|
| **A — comme les autres** | L'ordonnance est attribuable au compte, profil facultatif | Cohérent, mais une ordonnance émise par un non-inscrit devient possible |
| **B — garde spécifique** | L'ordonnance exige un profil `Praticien`, la consultation non | Sécuritaire, mais on maintient un asymétrie à expliquer dans l'UI |
| **C — garde conditionnelle** | Exige le profil **et** un `numero_ordre` renseigné | Le plus rigoureux ; devient bloquant tant que les praticiens n'ont pas leur numéro |

**Recommandation : B en attendant, C comme cible.** Une ordonnance est un
support papier qui sort du cabinet ; la responsabilité y est personnelle. Une
consultation ne l'est pas : elle reste dans le dossier.

Ce choix ne change que `ordonnances/services.py` et la documentation. Il est
isolé, donc décisionnable sans bloquer le reste.

## 6. Ordre d'exécution

1. Écrire la migration et la tester sur une **copie** de la base de démo,
   `downgrade` compris.
2. Appliquer, sauvegarder avant, vérifier les comptes.
3. Backend B1→B9, module consultations d'abord.
4. Frontend F1→F5.
5. `npx tsc -b`, `oxlint`, non-régression complète.
6. Rejouer `_verif_parcours_patient.py` : le dentiste doit pouvoir consulter
   **sans** profil praticien, et l'ordonnance doit toujours être émise.

## 7. Ce que ce chantier ne corrige pas

- **Le module Utilisateurs reste absent** (`POST /rbac/users` → 404). On pourra
  désormais créer une consultation sans profil praticien, mais on ne pourra
  toujours pas créer le compte depuis l'interface.
- **La file d'attente de la secrétaire** reste inexistante.
- La question du rôle « Médecin chef » reste ouverte
  (`docs/corrections/MATRICE_ROLES.md` §4).
