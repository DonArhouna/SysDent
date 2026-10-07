# Parcours patient de bout en bout — exécution du 6 octobre 2026

> Ce document est la **sortie réelle** de `Backend/_verif_parcours_patient.py`.
> Il ne s'agit pas d'un scénario théorique : chaque ligne ci-dessous a été
> produite par un appel HTTP contre l'API, sur le tenant de démonstration
> `sysdent_tenant_clinique_cabinet_sn_5bd215`.

## Ce que le parcours démontre

Il ne teste pas des endpoints isolés : il suit **une journée de cabinet** et
vérifie la conséquence observable de chaque geste — pas seulement le code HTTP.
Une réponse 200 ne prouve rien si elle dit le contraire de ce qu'on attend.

| Étape | Acteur | Ce qui est vérifié |
|---|---|---|
| 1 | Secrétaire | création du patient, numérotation du dossier, lecture |
| 2 | Dentiste | ouverture de la consultation, acte avec numéro de dent FDI |
| 2 | Dentiste | **refus de facturer** (403) — le soin et l'argent sont deux pouvoirs |
| 3 | Gestionnaire | sortie de matériel imputée à la consultation, stock décrémenté |
| 3 bis | Dentiste | **facturation refusée avant clôture** et **clôture refusée sans diagnostic** |
| 3 bis | Dentiste | diagnostic posé, consultation clôturée |
| 4 | Secrétaire | facture émise depuis la consultation |
| 5 | Caissier | ouverture du tiroir, **refus d'accès au dossier clinique** (403), encaissement, clôture |
| 6 | Comptable | relecture de la journée, conformité du total, clôture signée |
| 7 | Gestionnaire | le stock du catalogue reflète la sortie |

## Les refus qui comptent

Cinq étapes du parcours sont des **échecs volontaires**. Ce ne sont pas des bugs :
ce sont les garde-fous du produit, et le parcours échoue si l'un d'eux
disparaît.

| Code | Règle métier |
|---|---|
| `PRATICIEN_NON_IDENTIFIE` | un acte doit avoir un auteur clinique rattaché (traçabilité médico-légale) |
| `PERMISSION_DENIED` | le dentiste n'a pas `FACTURATION:CREATE` |
| `DENT_NUMERO_OBLIGATOIRE` | un soin unitaire exige un numéro de dent FDI |
| `CONSULTATION_NON_TERMINEE` | on ne facture pas une séance en cours |
| `DIAGNOSTIC_OBLIGATOIRE` | on ne clôt pas une consultation sans diagnostic |

## Sortie d'exécution

```

=== 1. La secr├®taire cr├®e le patient ===
    OK   patient cr├®├® (201)
    OK   dossier num├®rot├® : PAT-2026-000030
    OK   secr├®taire lit le dossier

=== 2. Le dentier ouvre la consultation et enregistre l'acte ===
    OK   consultation ouverte (201)
    OK   nomenclature lue (1 acte(s))
    OK   acte enregistr├® (201)
    OK   le dentiste ne facture pas (403)

=== 3. La sortie de mat├®riel est imput├®e ├á la consultation ===
    OK   catalogue du site (6 article(s))
    OK   sortie enregistr├®e (201)
    OK   stock 5 -> 4 (attendu 4)
    OK   la sortie cite le dossier

=== 3 bis. Le dentier pose le diagnostic et cl├┤t la consultation ===
    OK   facturation refus├®e avant cl├┤ture (422)
    OK   cl├┤ture refus├®e sans diagnostic (422)
    OK   consultation cl├┤tur├®e (200)

=== 4. La secr├®taire ├®met la facture depuis la consultation ===
    OK   facture ├®mise (201)
    OK   montant total = 20000.00

=== 5. La caissi├¿re ouvre le tiroir, encaisse et cl├┤ture ===
    OK   caisse ouverte (201)
    OK   dossier clinique refus├® au caissier (403)
    OK   encaissement de 20000.00 (201)
    OK   cl├┤ture (200)
    OK   attendu = 30000.00 (d├®p├┤t 10000 + 20000.00)
    OK   ├®cart nul (0.00)
    OK   total encaiss├® = 20000.00

=== 6. Le comptable relit la journ├®e ===
    OK   journal des sessions (200)
    OK   la journ├®e du parcours est retrouv├®e
    OK   la journ├®e vaut 20000.00 (conforme ├á la facture)
    OK   la cl├┤ture est sign├®e

=== 7. Le gestionnaire de stock v├®rifie la sortie ===
    OK   le stock du catalogue refl├¿te la sortie

  PARCOURS PATIENT ÔÇö SYNTH├êSE
  1. La secr├®taire cr├®e le patient
  2. Le dentier ouvre la consultation et enregistre l'acte
  3. La sortie de mat├®riel est imput├®e ├á la consultation
  3 bis. Le dentier pose le diagnostic et cl├┤t la consultation
  4. La secr├®taire ├®met la facture depuis la consultation
  5. La caissi├¿re ouvre le tiroir, encaisse et cl├┤ture
  6. Le comptable relit la journ├®e
  7. Le gestionnaire de stock v├®rifie la sortie

  CONFORME : la journ├®e compl├¿te tient, de l'accueil ├á la cl├┤ture.
```
