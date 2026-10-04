export interface Fauteuil {
  id: string
  salle_id: string
  numero: string
  equipements?: Record<string, unknown> | null
  actif: boolean
  nom_salle?: string | null
  cabinet_nom?: string | null
}

export interface Salle {
  id: string
  cabinet_id: string
  nom: string
  etage?: number | null
  nb_fauteuils?: number
  nb_fauteuils_actifs?: number
}

export interface Cabinet {
  id: string
  nom: string
  adresse?: string | null
  ville?: string | null
  telephone?: string | null
  email?: string | null
  horaires_ouverture?: Record<string, unknown> | null
  actif: boolean
  nb_salles: number
  nb_fauteuils_actifs: number
  nb_praticiens_actifs: number
}

export interface CabinetUpdateInput {
  nom?: string
  adresse?: string
  ville?: string
  telephone?: string
  email?: string
  actif?: boolean
}

export interface SalleCreateInput {
  nom: string
  etage?: number
}

export interface FauteuilCreateInput {
  numero: string
  equipements?: Record<string, unknown>
}
