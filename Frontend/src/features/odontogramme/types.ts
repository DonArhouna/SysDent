export type TypeOdontogramme = 'ADULTE' | 'ENFANT' | 'MIXTE'

/**
 * Les cinq faces d'une dent, **telles que le serveur les nomme**.
 *
 * Ce n'est pas une documentation : c'est un type. Une union fait de tout code
 * hors nomenclature une **erreur de compilation**, la ou un commentaire ne
 * fait rien. Le tiroir envoyait des adjectifs francais la ou le serveur attend
 * des codes techniques, et chaque enregistrement se faisait refuser en 422.
 *
 * Les anciens noms ne sont pas ecrits ici, meme en commentaire : le controle
 * de contrat refuse leur presence dans toute la fonction, et il ne distingue
 * pas une prose d'un code envoye. Les citer pour expliquer le defaut
 * suffirait a le faire echouer.
 *
 * La source de verite reste `Backend/src/common/dentaire.py` ; le test
 * `Backend/tests/test_contrat_faces_odontogramme.py` compare les deux.
 */
export type CodeFace = 'MESIAL' | 'DISTAL' | 'VESTIBULAIRE' | 'LINGUAL_PALATIN' | 'OCCLUSAL_INCISAL'

export interface FaceDent {
  face: CodeFace
  /** Abréviation d'affichage : M, D, V, L, O. */
  face_courte: string
  etat: string
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
