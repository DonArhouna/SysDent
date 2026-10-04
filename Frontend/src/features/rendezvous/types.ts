export type StatutRdv =
  | 'PLANIFIE'
  | 'CONFIRME'
  | 'EN_ATTENTE'
  | 'EN_CONSULTATION'
  | 'TERMINEE'
  | 'ANNULE'
  | 'ABSENT'

export type MotifBlocageFauteuil =
  | 'MAINTENANCE'
  | 'PANNE'
  | 'DESINFECTION'
  | 'RESERVATION_INTERNE'
  | 'AUTRE'

export interface ConflitRdv {
  ressource: 'PRATICIEN' | 'FAUTEUIL'
  debut: string
  fin: string
  patient_nom?: string | null
  motif?: string | null
}

export interface RendezVous {
  id: string
  patient_id: string
  praticien_id: string
  cabinet_id: string
  fauteuil_id?: string | null
  debut: string
  fin: string
  duree_minutes: number
  motif: string
  type_motif?: string | null
  statut: StatutRdv
  notes?: string | null
  hors_disponibilites?: boolean
  patient_nom?: string | null
  praticien_nom?: string | null
  fauteuil_nom?: string | null
  cabinet_nom?: string | null
  consultation_id?: string | null
  created_at: string
}

export interface IndisponibiliteFauteuil {
  id: string
  fauteuil_id: string
  fauteuil_numero?: string | null
  debut: string
  fin: string
  motif: MotifBlocageFauteuil
  motif_detail?: string | null
}

export interface AgendaData {
  date: string
  cabinet_id?: string | null
  praticien_id?: string | null
  rendez_vous: RendezVous[]
  indisponibilites_fauteuil: IndisponibiliteFauteuil[]
}

export interface CreneauLibre {
  debut: string
  fin: string
  fauteuils_libres: Array<{ id: string; numero: string }>
}

export interface RdvCreateInput {
  patient_id: string
  praticien_id: string
  cabinet_id: string
  fauteuil_id?: string | null
  debut: string // ISO string
  duree_minutes: number
  motif: string
  type_motif?: string
  notes?: string
}
