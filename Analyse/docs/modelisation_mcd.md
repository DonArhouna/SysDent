# Modèle Conceptuel de Données (MCD)

## Architecture Multi-Tenant (Structure Sage X3)

Le système est conçu pour être SaaS. Chaque "Société" (Tenant) est isolée des autres.

```mermaid
erDiagram
    SOCIETE ||--o{ CABINET : "possède (Sites)"
    SOCIETE ||--o{ UTILISATEUR : "emploie"
    SOCIETE ||--o{ PATIENT : "gère"
    SOCIETE ||--o{ FOURNISSEUR : "travaille avec"
    
    SOCIETE {
        string nom
        string ninea
        string logo_url
        string adresse_siege
        string telephone
        string email
    }
```

## Noyau Patient & Médical

!!! important "Provenance des données"
    Le **Patient** (fiche administrative) est créé par la secrétaire. Le **dossier médical** est créé et géré **exclusivement par le médecin/dentiste** à partir d'un patient existant.

```mermaid
erDiagram
    PATIENT ||--o| DOSSIER_MEDICAL : "a un (créé par le médecin)"
    DOSSIER_MEDICAL ||--|| ETAT_GENERAL : "contient"
    DOSSIER_MEDICAL ||--o{ ANTECEDENT_MEDICAL : "contient"
    DOSSIER_MEDICAL ||--|| ODONTOGRAMME : "contient"
    DOSSIER_MEDICAL ||--o{ CONSULTATION : "contient"

    PATIENT ||--o{ ASSURANCE_PATIENT : "couvert par"
    PATIENT ||--o{ DOCUMENT_PATIENT : "a des"
    PATIENT ||--o{ RENDEZ_VOUS : "prend"

    CONSULTATION }o--|| PRATICIEN : "réalisée par"
    CONSULTATION }o--|| CABINET : "dans"
    CONSULTATION ||--o{ ACTE_REALISE : "comprend"
    CONSULTATION ||--o{ PRESCRIPTION : "génère"

    ODONTOGRAMME ||--o{ DENT : "contient"
    DENT ||--o{ ETAT_DENT_HISTORIQUE : "trace"
    DENT ||--o{ FACE_DENT : "a des"
    DENT ||--o{ CHARTING_PARODONTAL : "mesuré par"

    ACTE_REALISE }o--|| ACTE_NOMENCLATURE : "référence"
    ACTE_REALISE ||--o{ MATERIAU_UTILISE : "consomme"

    PRESCRIPTION ||--o{ LIGNE_PRESCRIPTION : "contient"
    LIGNE_PRESCRIPTION }o--o| MEDICAMENT : "prescrit"
```

## Facturation & Paiements

```mermaid
erDiagram
    CONSULTATION ||--o{ FACTURE : "facturée par"
    PATIENT ||--o{ FACTURE : "reçoit"
    FACTURE ||--o{ LIGNE_FACTURE : "contient"
    FACTURE ||--o{ PAIEMENT : "réglée par"
    FACTURE ||--o| PLAN_ECHELONNEMENT : "échelonnée via"

    PLAN_ECHELONNEMENT ||--o{ ECHEANCE : "composé de"
    ECHEANCE }o--o| PAIEMENT : "payée par"

    PATIENT ||--o{ DEVIS : "reçoit"
    DEVIS ||--o{ LIGNE_DEVIS : "contient"
    LIGNE_DEVIS }o--|| ACTE_NOMENCLATURE : "concerne"

    FACTURE ||--o{ REMBOURSEMENT : "peut avoir"

    LIGNE_FACTURE }o--o| ACTE_REALISE : "correspond à"
```

## Dépenses, Achats & Stock

```mermaid
erDiagram
    FOURNISSEUR ||--o{ COMMANDE_FOURNISSEUR : "reçoit"
    COMMANDE_FOURNISSEUR ||--o{ LIGNE_COMMANDE : "contient"
    LIGNE_COMMANDE }o--|| PRODUIT : "concerne"

    PRODUIT ||--o{ STOCK_CABINET : "stocké dans"
    PRODUIT ||--o{ MOUVEMENT_STOCK : "tracé par"
    PRODUIT ||--o{ CYCLE_STERILISATION : "stérilisé"
    PRODUIT }o--|| CATEGORIE_PRODUIT : "classé dans"
    PRODUIT }o--o| FOURNISSEUR : "fourni par"

    CABINET ||--o{ STOCK_CABINET : "dispose de"
    CABINET ||--o{ COMMANDE_FOURNISSEUR : "commande pour"

    CATEGORIE_DEPENSE ||--o{ DEPENSE : "classifie"
    DEPENSE ||--o{ LIGNE_DEPENSE : "détaillée en"
    DEPENSE }o--o| FOURNISSEUR : "payée à"
    DEPENSE }o--|| CABINET : "impute à"

    MATERIAU_UTILISE }o--|| PRODUIT : "est un"
```

## Utilisateurs, Groupes & Rôles

```mermaid
erDiagram
    UTILISATEUR }o--o{ GROUPE : "appartient à"
    UTILISATEUR }o--|| ROLE : "a un"
    GROUPE }o--o{ ROLE : "hérite des permissions de"
    GROUPE }o--o{ CABINET : "a accès à"
    ROLE ||--o{ PERMISSION_ROLE : "accorde"
    PERMISSION_ROLE }o--|| PERMISSION : "sur"

    PRATICIEN ||--|| UTILISATEUR : "est un"
    PRATICIEN ||--o{ CABINET_PRATICIEN : "affecté à"
    PRATICIEN ||--o{ DISPONIBILITE : "a des"
    PRATICIEN ||--o{ TARIF_PRATICIEN : "définit"

    CABINET ||--o{ CABINET_PRATICIEN : "contient"
    SOCIETE ||--o{ CABINET : "possède"
    CABINET ||--o{ SALLE : "dispose de"
    CABINET {
        string nom
        string adresse
        string telephone
        string email
        string logo_url
    }
    SALLE ||--o{ FAUTEUIL : "équipée de"

    RENDEZ_VOUS }o--|| PRATICIEN : "avec"
    RENDEZ_VOUS }o--|| CABINET : "dans"
    RENDEZ_VOUS }o--o| FAUTEUIL : "sur"

    UTILISATEUR ||--o{ JOURNAL_ACTIVITE : "tracé dans"
    UTILISATEUR ||--o{ NOTIFICATION : "reçoit"
    UTILISATEUR ||--o{ MESSAGE_INTERNE : "envoie/reçoit"
```
