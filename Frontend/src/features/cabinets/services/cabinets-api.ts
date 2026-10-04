import { api, type ApiReponse } from '@/lib/api'
import type {
  Cabinet,
  CabinetUpdateInput,
  Fauteuil,
  FauteuilCreateInput,
  Salle,
  SalleCreateInput,
} from '../types'

export const cabinetsApi = {
  lister: async (inclureInactifs = false) => {
    return api.get<ApiReponse<Cabinet[]>>(
      `/cabinets?inclure_inactifs=${inclureInactifs ? 'true' : 'false'}`,
    )
  },

  obtenir: async (id: string) => {
    return api.get<ApiReponse<Cabinet>>(`/cabinets/${id}`)
  },

  modifier: async (id: string, data: CabinetUpdateInput) => {
    return api.patch<ApiReponse<Cabinet>>(`/cabinets/${id}`, data)
  },

  // Salles
  listerSalles: async (cabinetId: string) => {
    return api.get<ApiReponse<Salle[]>>(`/cabinets/${cabinetId}/salles`)
  },

  creerSalle: async (cabinetId: string, data: SalleCreateInput) => {
    return api.post<ApiReponse<Salle>>(`/cabinets/${cabinetId}/salles`, data)
  },

  modifierSalle: async (cabinetId: string, salleId: string, data: Partial<SalleCreateInput>) => {
    return api.patch<ApiReponse<Salle>>(`/cabinets/${cabinetId}/salles/${salleId}`, data)
  },

  supprimerSalle: async (cabinetId: string, salleId: string) => {
    return api.delete<void>(`/cabinets/${cabinetId}/salles/${salleId}`)
  },

  // Fauteuils
  listerFauteuils: async (cabinetId: string, inclureInactifs = true) => {
    return api.get<ApiReponse<Fauteuil[]>>(
      `/cabinets/${cabinetId}/fauteuils?inclure_inactifs=${inclureInactifs ? 'true' : 'false'}`,
    )
  },

  creerFauteuil: async (salleId: string, data: FauteuilCreateInput) => {
    return api.post<ApiReponse<Fauteuil>>(`/salles/${salleId}/fauteuils`, data)
  },

  modifierFauteuil: async (fauteuilId: string, data: { numero?: string; actif?: boolean }) => {
    return api.patch<ApiReponse<Fauteuil>>(`/fauteuils/${fauteuilId}`, data)
  },

  reactiverFauteuil: async (fauteuilId: string) => {
    return api.post<ApiReponse<Fauteuil>>(`/fauteuils/${fauteuilId}/reactiver`)
  },

  supprimerFauteuil: async (fauteuilId: string) => {
    return api.delete<void>(`/fauteuils/${fauteuilId}`)
  },
}
