import { api } from '@/lib/api'
import type { APIResponse } from '@/types/api'
import type {
  ControleContreIndicationResponse,
  LignePrescriptionCreate,
  Medicament,
  MedicamentCreate,
  OrdonnanceCreate,
  OrdonnanceResponse,
  OrdonnanceUpdate,
} from '../types'

export const ordonnancesApi = {
  // Référentiel médicamenteux
  listerMedicaments: (params?: {
    q?: string
    forme?: string
    classe?: string
    inclure_inactifs?: boolean
  }) => {
    return api.get<APIResponse<Medicament[]>>('/ordonnances/medicaments', { params })
  },

  creerMedicament: (data: MedicamentCreate) => {
    return api.post<APIResponse<Medicament>>('/ordonnances/medicaments', data)
  },

  // Contrôle à blanc (UC8)
  controlerPrescription: (
    patientId: string,
    ligne: LignePrescriptionCreate
  ) => {
    return api.post<APIResponse<ControleContreIndicationResponse>>('/ordonnances/controle', {
      patient_id: patientId,
      ...ligne,
    })
  },

  // Ordonnances
  lister: (params?: {
    patient_id?: string
    consultation_id?: string
    limite?: number
  }) => {
    return api.get<APIResponse<OrdonnanceResponse[]>>('/ordonnances', { params })
  },

  obtenir: (id: string) => {
    return api.get<APIResponse<OrdonnanceResponse>>(`/ordonnances/${id}`)
  },

  creer: (data: OrdonnanceCreate) => {
    return api.post<APIResponse<OrdonnanceResponse>>('/ordonnances', data)
  },

  signer: (id: string) => {
    return api.post<APIResponse<OrdonnanceResponse>>(`/ordonnances/${id}/signer`, {})
  },

  modifier: (id: string, data: OrdonnanceUpdate) => {
    return api.patch<APIResponse<OrdonnanceResponse>>(`/ordonnances/${id}`, data)
  },

  ajouterLigne: (id: string, ligne: LignePrescriptionCreate) => {
    return api.post<APIResponse<OrdonnanceResponse>>(`/ordonnances/${id}/lignes`, ligne)
  },

  supprimerLigne: (id: string, ligneId: string, motif?: string) => {
    return api.delete<APIResponse<OrdonnanceResponse>>(`/ordonnances/${id}/lignes/${ligneId}`, {
      params: motif ? { motif } : undefined,
    })
  },
}
