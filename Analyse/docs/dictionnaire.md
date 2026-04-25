# Dictionnaire de Données

## Énumérations principales

| Nom | Valeurs |
|-----|---------|
| `sexe` | M, F |
| `specialite` | dentisterie_generale, orthodontie, parodontologie, chirurgie, endodontie, implantologie, pedodontie, prothese, esthetique |
| `type_antecedent` | medical, chirurgical, familial, dentaire, allergique, medicamenteux |
| `etat_dent` | saine, absente_extraite, carie_debutante, couronne, implant, etc. |
| `statut_facture` | brouillon, emise, partiellement_payee, payee, annulee |
| `mode_paiement` | especes, carte_bancaire, virement, mobile_money_wave, mobile_money_orange, cheque, assurance |

## Champs JSON structurés

| Table | Champ | Structure |
|-------|-------|-----------|
| `etats_generaux` | `allergies` | `[{"substance": "str", "reaction": "str", "severite": "legere\|moderee\|grave"}]` |
| `consultations` | `codes_cim10` | `["K02.1", "K05.0"]` |
| `journal_activite` | `details` | `{"champ": "str", "ancien": "any", "nouveau": "any"}` |
