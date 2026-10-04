export type StatutConsultation =
  | 'PLANIFIEE'
  | 'EN_ATTENTE'
  | 'EN_COURS'
  | 'TERMINEE'
  | 'ANNULEE'

export interface ActeRealise {
  id: string
  consultation_id: string
  acte_id: string
  code_acte: string
  libelle_acte: string
  dent_numero?: number | null
  face?: string | null
  description?: string | null
  tarif_applique: string | number
  quantite: number
  montant: string | number
  notes?: string | null
  created_at: string
}

export interface Consultation {
  id: string
  dossier_medical_id: string
  patient_id?: string | null
  patient_numero_dossier?: string | null
  praticien_id: string
  cabinet_id: string
  motif: string
  type_motif?: string | null
  motif_detail?: string | null
  anamnese?: string | null
  examen_exobuccal?: string | null
  examen_endobuccal?: string | null
  diagnostic_principal?: string | null
  diagnostics_differentiels?: string[] | null
  codes_cim10?: string[] | null
  plan_traitement?: string | null
  recommandations?: string | null
  prochain_rdv_prevu?: string | null
  statut: StatutConsultation
  date_consultation: string
  duree_minutes?: number | null
  created_at: string
  updated_at: string
}

export interface ConsultationDetail extends Consultation {
  actes: ActeRealise[]
  total_actes: string | number
  nb_actes: number
  duree_reelle_minutes?: number | null
  etat_general_a_verifier: boolean
  alertes?: Array<{ code: string; niveau: string; message: string }>
}

export interface ActeNomenclature {
  id: string
  code: string
  libelle: string
  categorie: string
  tarif_base: string | number
  duree_estimee_min: number
  unitaire: boolean
  actif: boolean
}

export interface ConsultationCreateInput {
  patient_id: string
  praticien_id: string
  cabinet_id?: string
  motif: string
  type_motif?: string
  motif_detail?: string
  anamnese?: string
}

export interface ConsultationUpdateInput {
  motif?: string
  anamnese?: string
  examen_exobuccal?: string
  examen_endobuccal?: string
  diagnostic_principal?: string
  diagnostics_differentiels?: string[]
  codes_cim10?: string[]
  plan_traitement?: string
  recommandations?: string
  prochain_rdv_prevu?: string
}

export interface ActeRealiseCreateInput {
  acte_id: string
  dent_numero?: number
  face?: string
  tarif_applique?: number
  quantite?: number
  notes?: string
}
