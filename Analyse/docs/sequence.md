# Diagrammes de Séquence

## Workflow complet du Dossier Patient (6 étapes)

!!! important "Définition des rôles"
    La secrétaire enregistre le patient (étape 1). Le médecin/dentiste crée le dossier médical et gère les étapes 2 à 6.

```mermaid
sequenceDiagram
    actor SEC as Secrétaire
    actor DEN as Dentiste / Médecin
    participant SYS as Système
    participant DB as Base de données

    Note over SEC,DB: ÉTAPE 1 – Enregistrement Patient (Secrétaire)
    SEC->>SYS: Enregistrer patient (état civil, contact, assurance)
    SYS->>DB: INSERT patients
    DB-->>SYS: numéro dossier auto-généré
    SYS-->>SEC: ✅ Patient PAT-1001 enregistré
    Note over SEC: La secrétaire n'a plus accès au dossier médical

    Note over DEN,DB: CRÉATION DOSSIER MÉDICAL (Praticien)
    DEN->>SYS: Rechercher patient PAT-1001
    SYS-->>DEN: Fiche patient (données admin seulement)
    DEN->>SYS: Créer dossier médical pour ce patient
    SYS->>DB: INSERT dossiers_medicaux
    SYS->>DB: INSERT odontogramme + 32 dents
    SYS-->>DEN: ✅ Dossier médical créé

    Note over DEN,DB: ÉTAPES CLINIQUES (Médecin)
    Note over DEN: Étape 2: État Général
    Note over DEN: Étape 3: Antécédents
    Note over DEN: Étape 4: Motif
    Note over DEN: Étape 5: Diagnostic
    Note over DEN: Étape 6: Traitement
    
    DEN->>SYS: Finaliser consultation
    SYS->>DB: UPDATE consultations (statut: terminee)
    SYS-->>DEN: ✅ Traitement enregistré
```

## Paiement partiel / échelonné

```mermaid
sequenceDiagram
    actor PAT as Patient
    actor SEC as Secrétaire
    participant SYS as Système
    participant DB as Base de données

    SEC->>SYS: Générer facture depuis consultation
    SYS->>DB: INSERT facture + lignes
    SYS-->>SEC: Facture FACT-2026-00042
    PAT->>SEC: Demande paiement échelonné
    SEC->>SYS: Créer plan 3 échéances
    SYS->>DB: INSERT plan_echelonnement
    SYS-->>SEC: ✅ Plan créé
```
