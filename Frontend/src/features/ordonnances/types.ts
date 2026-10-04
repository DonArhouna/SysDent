export interface RegleContreIndication {
  condition: string
  gravite: 'INTERDIT' | 'PRECAUTION'
  message: string
}

export interface Medicament {
  id: string
  nom_commercial: string
  dci: string
  forme: string
  dosage?: string | null
  classe_therapeutique?: string | null
  posologie_adulte?: string | null
  precautions?: string | null
  contre_indications?: RegleContreIndication[] | null
  actif: boolean
}

export interface MedicamentCreate {
  nom_commercial: string
  dci: string
  forme?: string
  dosage?: string
  classe_therapeutique?: string
  posologie_adulte?: string
  precautions?: string
  contre_indications?: RegleContreIndication[]
}

export interface AlertePrescription {
  code: string
  gravite: 'INTERDIT' | 'PRECAUTION'
  message: string
  condition?: string
}

export interface ControleContreIndicationResponse {
  prescription_possible: boolean
  justification_requise: boolean
  alertes: AlertePrescription[]
  conditions_actives: Array<{ condition: string; description?: string }>
}

export interface LignePrescriptionCreate {
  medicament_id?: string | null
  medicament_texte?: string | null
  posologie: string
  duree?: string | null
  instructions?: string | null
  quantite: number
  justification_precaution?: string | null
}

export interface LignePrescriptionResponse {
  id: string
  medicament_id?: string | null
  medicament_texte?: string | null
  nom_commercial?: string | null
  dci?: string | null
  posologie: string
  duree?: string | null
  instructions?: string | null
  quantite: number
  justification_precaution?: string | null
}

export interface OrdonnanceCreate {
  patient_id: string
  consultation_id: string
  lignes: LignePrescriptionCreate[]
  notes_generales?: string | null
}

export interface OrdonnanceUpdate {
  notes_generales?: string | null
}

export interface OrdonnanceResponse {
  id: string
  numero: string
  consultation_id: string
  patient_id: string
  praticien_id: string
  date_ordonnance: string
  notes_generales?: string | null
  signe: boolean
  date_signature?: string | null
  lignes: LignePrescriptionResponse[]
  alertes: AlertePrescription[]
  nb_lignes: number
}
