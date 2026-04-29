# Règles de Gestion

Le système SysDent Pro repose sur **23 règles de gestion** critiques garantissant l'intégrité des données et le respect du workflow métier.

| ID | Règle | Module |
|----|-------|--------|
| RG01 | Chaque patient a un numéro de dossier unique auto-généré | Patients |
| RG02 | La secrétaire enregistre le patient mais ne crée PAS le dossier médical | Patients / RBAC |
| RG03 | Le dossier médical est créé exclusivement par un médecin/dentiste | Dossier Médical |
| RG04 | La secrétaire n'a aucun accès aux dossiers médicaux | RBAC |
| RG05 | La secrétaire peut créer des factures mais ne peut PAS les modifier | Facturation |
| RG06 | L'état général doit être mis à jour à chaque consultation | Dossier Médical |
| RG07 | Les allergies déclenchent des alertes automatiques | Ordonnances |
| RG08 | Les contre-indications bloquent certains médicaments | Ordonnances |
| RG09 | Un acte réalisé décrémente automatiquement le stock | Stock |
| RG10 | Alerte de stock bas sous le seuil minimum | Stock |
| RG11 | Reste à payer auto-calculé : total - assurance - payé | Facturation |
| RG12 | Plan échelonné génère des échéances automatiques | Paiements |
| RG13 | Retard de paiement = notification SMS auto | Paiements |
| RG14 | Historique horodaté des modifications dentaires | Odontogramme |
| RG15 | Standard : 32 dents adultes / 20 dents enfants | Odontogramme |
| RG16 | Traçabilité complète des actions (Audit Log) | Sécurité |
| RG17 | Permissions = Rôles + Groupes + Cabinets | RBAC |
| RG18 | Multi-groupes possibles pour un utilisateur | RBAC |
| RG19 | Conversion Devis -> Facture automatique | Facturation |
| RG20 | Rappels RDV SMS/Email 24h avant | RDV |
| RG21 | Disponibilités praticien respectées par l'agenda | RDV |
| RG22 | Réception commande = Stock à jour auto | Stock |
| RG23 | Session expire après inactivité | Sécurité |
| RG24 | Toutes les tables disposent de champs `created_at` et `updated_at` | Audit |

## Matrice de Permissions

| Module | Admin | Dentiste | Secrétaire | Comptable |
|--------|:---:|:---:|:---:|:---:|
| Enregistrement Patient | ✅ | ✅ | **✅** | ❌ |
| **Dossier Médical** | ✅ | **✅** | **❌** | ❌ |
| **Facturation (Création)** | ✅ | 👁 | **✅** | **✅** |
| **Facturation (Modifier)** | ✅ | ❌ | **❌** | **✅** |
| Stock | ✅ | 👁 | ❌ | ❌ |
| Config Accès | ✅ | ❌ | ❌ | ❌ |
