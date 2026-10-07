export type Sexe = 'M' | 'F'

export type TypePieceIdentite = 'CNI' | 'PASSEPORT' | 'PERMIS' | 'AUTRE'

export interface AllergieItem {
  substance: string
  reaction?: string | null
  severite: 'legere' | 'moderee' | 'grave'
}

export interface ExamenComplementaireItem {
  type: string
  date?: string | null
  resultat?: string | null
  fichier_url?: string | null
}

export interface EtatGeneral {
  id: string
  dossier_medical_id: string
  grossesse: boolean
  grossesse_terme?: string | null
  allaitement: boolean
  diabete: boolean
  diabete_type?: string | null
  hta: boolean
  tabac: boolean
  alcool: boolean
  // Ajoutés par la migration backend d7e4a1b2c9f3 : le serveur les attend,
  // le formulaire du dossier permet de les saisir.
  diabete_traitement?: string | null
  hta_traitement?: string | null
  groupe_sanguin?: string | null
  antecedents_familiaux?: string | null
  allergies?: AllergieItem[] | null
  autres_conditions?: string[] | null
  examens_complementaires?: ExamenComplementaireItem[] | null
  a_jour_le?: string | null
}

export interface AntecedentMedical {
  id: string
  dossier_medical_id: string
  type_antecedent: string
  description: string
  date_survenue?: string | null
  en_cours: boolean
  traitement_associe?: string | null
  notes?: string | null
  created_at: string
}

export interface AlerteMedicale {
  code: string
  niveau: 'INFO' | 'MODERE' | 'GRAVE'
  message: string
  source: 'ETAT_GENERAL' | 'ANTECEDENT'
}

export interface Patient {
  id: string
  numero_dossier: string
  prenom: string
  nom: string
  date_naissance: string
  sexe: Sexe
  type_piece_identite?: TypePieceIdentite | null
  numero_piece_identite?: string | null
  photo_url?: string | null
  adresse?: string | null
  ville?: string | null
  telephone_1: string
  telephone_2?: string | null
  email?: string | null
  profession?: string | null
  employeur?: string | null
  groupe_sanguin?: string | null
  source?: string | null
  notes?: string | null
  actif: boolean
  archive: boolean
  created_at: string
  updated_at: string
}

export interface PatientDossierComplet extends Patient {
  dossier_medical_id: string
  etat_general?: EtatGeneral | null
  antecedents: AntecedentMedical[]
  alertes: AlerteMedicale[]
  nb_consultations: number
  derniere_consultation?: string | null
}

export interface PatientCreateInput {
  prenom: string
  nom: string
  date_naissance: string
  sexe: Sexe
  telephone_1: string
  telephone_2?: string
  type_piece_identite?: TypePieceIdentite
  numero_piece_identite?: string
  adresse?: string
  ville?: string
  email?: string
  profession?: string
  employeur?: string
  groupe_sanguin?: string
  source?: string
  notes?: string
  etat_general?: {
    grossesse: boolean
    grossesse_terme?: string
    allaitement: boolean
    diabete: boolean
    diabete_type?: string
    hta: boolean
    tabac: boolean
    alcool: boolean
    allergies?: AllergieItem[]
    autres_conditions?: string[]
  }
}

export interface PatientUpdateInput {
  prenom?: string
  nom?: string
  date_naissance?: string
  sexe?: Sexe
  telephone_1?: string
  telephone_2?: string
  type_piece_identite?: TypePieceIdentite
  numero_piece_identite?: string
  adresse?: string
  ville?: string
  email?: string
  profession?: string
  employeur?: string
  groupe_sanguin?: string
  source?: string
  notes?: string
}

export interface FiltresRecherchePatients {
  q?: string
  nom?: string
  telephone?: string
  numero_dossier?: string
  date_naissance?: string
  include_archives?: boolean
  uniquement_archives?: boolean
  page?: number
  limit?: number
}
