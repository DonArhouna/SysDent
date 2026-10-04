export type TypeOdontogramme = 'ADULTE' | 'ENFANT' | 'MIXTE'

export interface FaceDent {
  face: string // VESTIBULAIRE, LINGUALE, MESIALE, DISTALE, OCCLUSALE, INCISIVE
  face_courte: string // V, L, M, D, O, I
  etat: string // SAINE, CARIE_DEBUTANTE, SOIGNEE, OBTURATION, COURONNE...
  notes?: string | null
}

export interface DentOdontogramme {
  id: string
  numero_fdi: number // 11 à 48 (adulte) ou 51 à 85 (enfant)
  numero_universal?: number | null
  etat_actuel: string
  etat_libelle?: string | null
  mobilite?: number | null // 0, 1, 2, 3
  notes?: string | null
  faces: FaceDent[]
  a_alerte: boolean
}

export interface OdontogrammeData {
  id: string
  patient_id?: string | null
  dossier_medical_id: string
  type: TypeOdontogramme
  systeme_notation: string
  nb_dents: number
  dents: DentOdontogramme[]
  nb_dents_soignees: number
  nb_dents_a_traiter: number
  nb_dents_absentes: number
  resume?: string | null
}

export interface EtatReferentiel {
  code: string
  libelle: string
  couleur: string
  categorie: 'SAINE' | 'SOIGNEE' | 'ATTENTION' | 'AUTRE'
}

export interface ReferentielOdontogramme {
  etats: EtatReferentiel[]
  faces: Array<{ code: string; court: string }>
}

export interface ChartingParodontalInput {
  dent_id?: string
  numero_fdi?: number
  sondage_mesio_vestibulaire?: number
  sondage_vestibulaire?: number
  sondage_disto_vestibulaire?: number
  sondage_mesio_lingual?: number
  sondage_lingual?: number
  sondage_disto_lingual?: number
  recession_gingivale?: number
  saignement_sondage?: boolean
  mobilite?: number
  furcation?: number
  notes?: string
}

export interface ChartingParodontal {
  id: string
  patient_id: string
  numero_fdi?: number | null
  sondage_mesio_vestibulaire?: number | null
  sondage_vestibulaire?: number | null
  sondage_disto_vestibulaire?: number | null
  sondage_mesio_lingual?: number | null
  sondage_lingual?: number | null
  sondage_disto_lingual?: number | null
  recession_gingivale?: number | null
  saignement_sondage: boolean
  mobilite?: number | null
  furcation?: number | null
  notes?: string | null
  date_releve: string
}
