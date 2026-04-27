# Modèle Logique de Données (MLD)

## Structure Multi-Tenant (Sage X3 Style)

- **societes**(*id*, nom, ninea, logo_url, adresse_siege, ville, pays, telephone, email, site_web, actif, date_creation)

## Utilisateurs, Groupes & Rôles (RBAC)

- **utilisateurs**(*id*, #societe_id, email, mot_de_passe, #role_id, prenom, nom, telephone, photo_url, actif, deux_facteurs, secret_2fa, dernier_login)
- **roles**(*id*, nom, description, niveau_hierarchie)
- **permissions**(*id*, module, action, description)
- **permission_roles**(*#role_id*, *#permission_id*, scope)
- **groupes**(*id*, nom, description, actif)
- **groupe_utilisateurs**(*#groupe_id*, *#utilisateur_id*, date_affectation)
- **groupe_roles**(*#groupe_id*, *#role_id*)
- **groupe_cabinets**(*#groupe_id*, *#cabinet_id*)
- **sessions**(*id*, #utilisateur_id, token, ip_address, user_agent, expire_at)

## Cabinets & Praticiens

- **cabinets**(*id*, #societe_id, nom, adresse, ville, telephone, email, horaires_ouverture[JSON], actif)
- **salles**(*id*, #cabinet_id, nom, etage)
- **fauteuils**(*id*, #salle_id, numero, equipements[JSON], actif)
- **praticiens**(*id*, #utilisateur_id, titre, specialite, numero_ordre, signature_url, bio)
- **cabinet_praticiens**(*id*, #cabinet_id, #praticien_id, date_debut, date_fin, actif)
- **disponibilites**(*id*, #praticien_id, #cabinet_id, jour_semaine, heure_debut, heure_fin, recurrent, date_specifique, type)

## Patients & Dossiers

- **patients**(*id*, #societe_id, numero_dossier[AUTO], prenom, nom, date_naissance, sexe, photo_url, adresse, ville, telephone_1, telephone_2, email, profession, employeur, groupe_sanguin, #enregistre_par, #utilisateur_id, source, notes, actif, archive)
- **assurances_patients**(*id*, #patient_id, organisme, numero_police, taux_prise_en_charge, date_debut, date_fin, actif)
- **documents_patients**(*id*, #patient_id, type, nom_fichier, fichier_url, taille_octets, mime_type, description, #uploaded_by)

- **dossiers_medicaux**(*id*, #patient_id[UNIQUE], #cree_par_praticien_id, #praticien_habituel_id, date_creation, notes)
- **etats_generaux**(*id*, #dossier_medical_id, grossesse, grossesse_terme, allaitement, diabete, diabete_type, diabete_traitement, hta, hta_traitement, allergies[JSON], tabac, alcool, autres_conditions[JSON], examens_complementaires[JSON], #mis_a_jour_par)
- **antecedents_medicaux**(*id*, #dossier_medical_id, type[ENUM], description, date_survenue, en_cours, traitement, notes)

## Consultations & Soins

- **consultations**(*id*, #dossier_medical_id, #praticien_id, #cabinet_id, #rendez_vous_id, #fauteuil_id, motif, motif_detail, anamnese, examen_exobuccal, examen_endobuccal, examen_parodontal, diagnostic_principal, diagnostics_differentiels, codes_cim10[JSON], plan_traitement, recommandations, prochain_rdv_prevu, statut[ENUM], duree_minutes, date_consultation)
- **actes_nomenclature**(*id*, code, libelle, categorie, tarif_base, duree_estimee_min, description, actif)
- **tarifs_praticien**(*id*, #acte_id, #praticien_id, tarif)
- **actes_realises**(*id*, #consultation_id, #acte_id, dent_numero, face, description, tarif_applique, quantite, notes)
- **materiaux_utilises**(*id*, #acte_realise_id, #produit_id, quantite, lot)

## Odontogramme

- **odontogrammes**(*id*, #dossier_medical_id[UNIQUE], type, systeme_notation)
- **dents**(*id*, #odontogramme_id, numero_fdi, numero_universal, etat_actuel[ENUM], mobilite, notes)
- **etats_dents_historique**(*id*, #dent_id, etat[ENUM], face, #consultation_id, #praticien_id, notes, date_constat)
- **faces_dents**(*id*, #dent_id, face, etat[ENUM])
- **chartings_parodontaux**(*id*, #dent_id, #consultation_id, sondages[JSON], nac, recession, saignement_bop, suppuration, mobilite, furcation, plaque_ipv, date_examen)

## Facturation & Paiements

- **factures**(*id*, numero[AUTO], #patient_id, #consultation_id, #cabinet_id, #praticien_id, montant_total, montant_tva, taux_tva, montant_assurance, taux_assurance, montant_paye, montant_restant, statut, date_emission, date_echeance, notes, #emis_par)
- **lignes_facture**(*id*, #facture_id, #acte_realise_id, designation, quantite, prix_unitaire, montant, tva_applicable)
- **paiements**(*id*, #facture_id, #patient_id, montant, mode, reference, date_paiement, recu_numero, notes, #enregistre_par)

## Stock & Dépenses

- **produits**(*id*, #societe_id, reference, nom, #categorie_id, description, unite, prix_achat, seuil_minimum, sterilisable, #fournisseur_principal_id, actif)
- **stock_cabinet**(*id*, #produit_id, #cabinet_id, quantite, lot, date_peremption)
- **mouvements_stock**(*id*, #produit_id, #cabinet_id, type, quantite, lot, #effectue_par)
- **depenses**(*id*, numero, #cabinet_id, #categorie_id, #fournisseur_id, designation, montant_total, date_depense, mode_paiement, #enregistre_par)
- **fournisseurs**(*id*, #societe_id, raison_sociale, contact_nom, telephone, email, actif)
