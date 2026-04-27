# Diagrammes de Cas d'Utilisation

## Vue globale des acteurs

```mermaid
graph LR
    subgraph "Acteurs du système"
        SA["🔑 Super Admin"]
        DM["👔 Directeur Médical"]
        DE["🦷 Dentiste / Praticien"]
        ME["👨‍⚕ Médecin"]
        AS["🩺 Assistant Dentaire"]
        SE["📋 Secrétaire / Accueil"]
        CO["💰 Comptable"]
        GS["📦 Gestionnaire Stock"]
    end
```

## Enregistrement Patient & Dossier Médical

!!! important "Séparation claire"
    La secrétaire **enregistre le patient** (fiche administrative). Le médecin/dentiste **crée le dossier médical** à partir du patient enregistré. La secrétaire **n'a pas accès** aux dossiers médicaux.

```mermaid
graph LR
    SE["📋 Secrétaire"] --> UC1["Enregistrer nouveau patient<br/>(fiche administrative)"]
    SE --> UC2["Rechercher patient"]
    SE --> UC3["Modifier infos administratives"]
    SE --> UC4["Planifier RDV"]
    DE["🦷 Dentiste / Médecin"] --> UC2
    DE --> UC4
    DE --> UC5["Créer dossier médical<br/>(à partir d'un patient existant)"]
    DE --> UC6["Consulter dossier médical"]
    DE --> UC7["Mettre à jour état général"]
    DE --> UC8["Ajouter antécédent médical"]
    DE --> UC9["Exporter dossier PDF"]
    DM["👔 Directeur Médical"] --> UC2
    DM --> UC6
    DM --> UC10["Fusionner doublons"]
    DM --> UC11["Archiver dossier"]
    SE -.->|"❌ PAS D'ACCÈS"| UC6
```

## Consultation & Soins

```mermaid
graph LR
    DE["🦷 Dentiste"] --> UC1["Démarrer consultation"]
    DE --> UC2["Saisir motif consultation"]
    DE --> UC3["Réaliser examen clinique"]
    DE --> UC4["Poser diagnostic"]
    DE --> UC5["Mettre à jour odontogramme"]
    DE --> UC6["Réaliser actes de soins"]
    DE --> UC7["Rédiger ordonnance"]
    DE --> UC8["Saisir recommandations"]
    DE --> UC9["Planifier prochain RDV"]
    DE --> UC10["Saisir charting parodontal"]
    AS["🩺 Assistant"] --> UC11["Préparer actes"]
    AS --> UC12["Consulter dossier"]
    UC7 --> SYS1["⚠ Vérifier interactions"]
    UC7 --> SYS2["⚠ Vérifier contre-indications"]
```

## Facturation & Paiements

!!! important "Droits Secrétaire"
    La secrétaire **crée** les factures mais **ne peut pas les modifier** ni les supprimer. Seuls le comptable et l'admin peuvent modifier/annuler une facture. Le comptable peut également créer des factures si besoin.

```mermaid
graph LR
    SE["📋 Secrétaire"] --> UC1["Créer facture"]
    SE --> UC2["Encaisser paiement"]
    SE --> UC3["Générer reçu"]
    SE -.->|"❌ PAS DE MODIFICATION"| UC_MOD["Modifier/Annuler facture"]
    CO["💰 Comptable"] --> UC1
    CO --> UC2
    CO --> UC_MOD
    CO --> UC_PLAN["Créer plan échelonnement"]
    CO --> UC5["Suivre impayés"]
    CO --> UC6["Consulter rapport caisse"]
    CO --> UC7["Gérer remboursements"]
    CO --> UC8["Gérer devis"]
    DE["🦷 Dentiste / Médecin"] --> UC9["Générer devis"]
    UC2 --> SYS1["Mettre à jour solde"]
    UC_PLAN --> SYS2["Créer échéances automatiques"]
```

## Dépenses, Achats & Stock

```mermaid
graph LR
    GS["📦 Gest. Stock"] --> UC1["Gérer catalogue produits"]
    GS --> UC2["Commander auprès fournisseur"]
    GS --> UC3["Réceptionner commande"]
    GS --> UC4["Suivre stock par cabinet"]
    GS --> UC5["Tracer mouvements stock"]
    GS --> UC6["Enregistrer stérilisation"]
    CO["💰 Comptable"] --> UC7["Enregistrer dépense"]
    CO --> UC8["Gérer fournisseurs"]
    CO --> UC9["Suivre achats"]
    CO --> UC10["Rapport consommation"]
    SYS["⚙ Système"] --> UC11["Alerter stock minimum"]
    SYS --> UC12["Alerter péremption"]
    DE["🦷 Dentiste"] --> UC13["Déclarer matériaux utilisés"]
```

## Gestion des Utilisateurs, Groupes & Rôles

```mermaid
graph LR
    SA["🔑 Super Admin"] --> UC_TENANT["Gérer les Sociétés (Tenants)<br/>(NINEA, Logo, Coordonnées)"]
    SA --> UC1["Créer utilisateur"]
    SA --> UC2["Modifier utilisateur"]
    SA --> UC3["Désactiver utilisateur"]
    SA --> UC4["Créer rôle"]
    SA --> UC5["Configurer permissions par rôle"]
    SA --> UC6["Créer groupe"]
    SA --> UC7["Affecter utilisateur à un groupe"]
    SA --> UC8["Affecter groupe à un cabinet"]
    SA --> UC9["Consulter journal d'activité"]
    SA --> UC10["Réinitialiser mot de passe"]
    DM["👔 Directeur"] --> UC11["Consulter liste utilisateurs"]
    DM --> UC12["Consulter permissions"]
    SYS["⚙ Système"] --> UC13["Vérifier permissions à chaque action"]
    SYS --> UC14["Expirer sessions inactives"]
    SYS --> UC15["Journaliser toutes les actions"]
```
