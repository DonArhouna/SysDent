export type TypePlageDisponibilite = 'CONSULTATION' | 'URGENCE' | 'BLOCKING'

export interface CabinetRattache {
  cabinet_id: string
  nom: string
  date_debut: string
  date_fin?: string | null
  actif: boolean
}

export interface Praticien {
  id: string
  user_id: string
  nom_complet: string
  email: string
  telephone?: string | null
  titre?: string | null // Dr, Pr
  specialite?: string | null // Chirurgie, Orthodontie, Parodontologie...
  numero_ordre?: string | null // N° Ordre des chirurgiens-dentistes du Sénégal
  signature_url?: string | null
  bio?: string | null
  actif: boolean
  cabinets_rattaches: CabinetRattache[]
}

export interface Disponibilite {
  id: string
  praticien_id: string
  cabinet_id?: string | null
  cabinet_nom?: string | null
  jour_semaine?: number | null // 0 = Lundi, 6 = Dimanche
  date_specifique?: string | null // YYYY-MM-DD
  heure_debut: string // HH:MM
  heure_fin: string // HH:MM
  type: TypePlageDisponibilite
  motif_blocage?: string | null
  actif: boolean
}

export interface CreneauLibreHoraire {
  heure_debut: string
  heure_fin: string
  fauteuils_disponibles: string[]
}

export interface CreneauxResponseData {
  praticien_id: string
  date: string
  creneaux: CreneauLibreHoraire[]
  avertissement?: string | null
}
