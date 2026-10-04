export type ModePaiement =
  | 'ESPECES'
  | 'CARTE_BANCAIRE'
  | 'CHEQUE'
  | 'VIREMENT'
  | 'MOBILE_MONEY'
  | 'ASSURANCE'

export type StatutFacture =
  | 'BROUILLON'
  | 'EMISE'
  | 'PARTIELLEMENT_PAYEE'
  | 'PAYEE'
  | 'ANNULEE'

export type StatutEcheance = 'EN_ATTENTE' | 'PAYEE' | 'EN_RETARD'

export type FrequenceEchelonnement = 'HEBDOMADAIRE' | 'MENSUEL'

export type StatutDevis = 'BROUILLON' | 'ENVOYE' | 'ACCEPTE' | 'REFUSE' | 'EXPIRE'

export interface LigneFactureResponse {
  id: string
  acte_realise_id?: string | null
  designation: string
  quantite: number
  prix_unitaire: number | string
  montant: number | string
}

export interface PaiementResponse {
  id: string
  facture_id: string
  montant: number | string
  mode: ModePaiement
  reference?: string | null
  recu_numero: string
  date_paiement: string
  echeance_id?: string | null
}

export interface EcheanceResponse {
  id: string
  numero: number
  montant_prevu: number | string
  montant_paye: number | string
  date_prevue: string
  date_paiement?: string | null
  paiement_id?: string | null
  statut: StatutEcheance
}

export interface PlanEchelonnementResponse {
  id: string
  facture_id: string
  montant_total: number | string
  nombre_echeances: number
  date_debut: string
  frequence: FrequenceEchelonnement
  notes?: string | null
  actif: boolean
  echeances: EcheanceResponse[]
}

export interface FactureResponse {
  id: string
  numero: string
  patient_id: string
  cabinet_id: string
  consultation_id?: string | null
  praticien_id?: string | null
  montant_total: number | string
  montant_tva: number | string
  montant_paye: number | string
  montant_restant: number | string
  statut: StatutFacture
  date_emission: string
  date_echeance?: string | null
  lignes: LigneFactureResponse[]
  paiements: PaiementResponse[]
}

export interface LigneFactureEntree {
  designation: string
  quantite: number
  prix_unitaire: number
}

export interface FactureLibreCreate {
  patient_id: string
  cabinet_id?: string | null
  praticien_id?: string | null
  date_echeance?: string | null
  notes?: string | null
  lignes: LigneFactureEntree[]
}

export interface FactureConsultationCreate {
  date_echeance?: string | null
  notes?: string | null
}

export interface PaiementCreate {
  montant: number
  mode: ModePaiement
  reference?: string | null
  echeance_id?: string | null
}

export interface PlanEchelonnementCreate {
  nombre_echeances: number
  date_debut: string
  frequence?: FrequenceEchelonnement
  notes?: string | null
}

export interface LigneDevisEntree {
  acte_id?: string | null
  designation: string
  dent_numero?: number | null
  quantite: number
  prix_unitaire: number
}

export interface LigneDevisResponse {
  id: string
  acte_id?: string | null
  designation: string
  dent_numero?: number | null
  quantite: number
  prix_unitaire: number | string
  montant: number | string
}

export interface DevisCreate {
  patient_id: string
  praticien_id?: string | null
  cabinet_id?: string | null
  date_validite?: string | null
  notes?: string | null
  lignes: LigneDevisEntree[]
}

export interface DevisStatutUpdate {
  statut: StatutDevis
  signature_patient?: boolean
}

export interface DevisResponse {
  id: string
  numero: string
  patient_id: string
  praticien_id?: string | null
  cabinet_id?: string | null
  montant_total: number | string
  statut: StatutDevis
  date_validite?: string | null
  signature_patient: boolean
  date_signature?: string | null
  notes?: string | null
  facture_id?: string | null
  lignes: LigneDevisResponse[]
}

export interface JournalCaisseItem {
  id: string
  facture_id: string
  facture_numero: string
  patient_id: string
  patient_nom: string
  patient_prenom: string
  montant: number | string
  mode: ModePaiement
  reference?: string | null
  recu_numero: string
  date_paiement: string
}
