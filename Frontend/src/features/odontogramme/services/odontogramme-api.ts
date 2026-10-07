import { api, type ApiReponse } from '@/lib/api'
import type {
  ChartingParodontal,
  ChartingParodontalInput,
  OdontogrammeData,
  ReferentielOdontogramme,
  TypeOdontogramme,
} from '../types'

export const odontogrammeApi = {
  // Référentiel officiel des états dentaires et couleurs
  obtenirReferentiel: async () => {
    return api.get<ApiReponse<ReferentielOdontogramme>>('/odontogramme/referentiel/etats')
  },

  // Obtenir ou créer l'odontogramme d'un patient
  obtenir: async (patientId: string) => {
    return api.get<ApiReponse<OdontogrammeData>>(`/odontogramme/patients/${patientId}`)
  },

  // Création explicite avec choix adulte / enfant
  creer: async (patientId: string, type: TypeOdontogramme = 'ADULTE') => {
    return api.post<ApiReponse<OdontogrammeData>>(`/odontogramme/patients/${patientId}`, {
      type,
      systeme_notation: 'FDI',
    })
  },

  // Modifier l'état global d'une dent
  modifierDent: async (
    patientId: string,
    data: {
      numero_fdi: number
      /** Le champ s'appelle `etat` cote serveur : `etat_actuel` etait ignore. */
      etat: string
      face?: string
      mobilite?: number
      notes?: string
    },
  ) => {
    return api.patch<ApiReponse<OdontogrammeData>>(`/odontogramme/patients/${patientId}/dent`, data)
  },

  // Mettre à jour plusieurs dents d'un coup (ex: détartrage)
  modifierDentsLot: async (
    patientId: string,
    data: {
      dents: Array<{ numero_fdi: number; etat: string; face?: string }>
      notes?: string
    },
  ) => {
    return api.patch<ApiReponse<OdontogrammeData>>(`/odontogramme/patients/${patientId}/dents`, data)
  },

  // Modifier les 5 faces d'une dent
  modifierFaces: async (
    patientId: string,
    numeroFdi: number,
    faces: Array<{ face: string; etat: string; notes?: string }>,
  ) => {
    return api.put<ApiReponse<OdontogrammeData>>(
      `/odontogramme/patients/${patientId}/dent/${numeroFdi}/faces`,
      { faces },
    )
  },

  // Historique global
  historiqueGlobal: async (patientId: string) => {
    return api.get<ApiReponse<any[]>>(`/odontogramme/patients/${patientId}/historique`)
  },

  // Charting parodontal
  enregistrerCharting: async (patientId: string, data: ChartingParodontalInput) => {
    return api.post<ApiReponse<ChartingParodontal>>(
      `/odontogramme/patients/${patientId}/charting`,
      data,
    )
  },

  listerChartings: async (patientId: string) => {
    return api.get<ApiReponse<ChartingParodontal[]>>(`/odontogramme/patients/${patientId}/charting`)
  },
}
