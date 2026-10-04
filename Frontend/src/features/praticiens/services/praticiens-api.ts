import { api, type ApiReponse } from '@/lib/api'
import type { CreneauxResponseData, Disponibilite, Praticien } from '../types'

export const praticiensApi = {
  lister: async (cabinetId?: string | null) => {
    const url = cabinetId ? `/praticiens?cabinet_id=${cabinetId}` : '/praticiens'
    return api.get<ApiReponse<Praticien[]>>(url)
  },

  obtenir: async (id: string) => {
    return api.get<ApiReponse<Praticien>>(`/praticiens/${id}`)
  },

  modifier: async (
    id: string,
    data: {
      titre?: string
      specialite?: string
      numero_ordre?: string
      bio?: string
      signature_url?: string
    },
  ) => {
    return api.patch<ApiReponse<Praticien>>(`/praticiens/${id}`, data)
  },

  // Rattachement à un site
  rattacherAuSite: async (cabinetId: string, praticienId: string, dateDebut?: string) => {
    return api.post<ApiReponse<unknown>>(
      `/cabinets/${cabinetId}/praticiens/${praticienId}/rattachement`,
      { date_debut: dateDebut },
    )
  },

  detacherDuSite: async (cabinetId: string, praticienId: string) => {
    return api.delete<void>(`/cabinets/${cabinetId}/praticiens/${praticienId}/rattachement`)
  },

  // Disponibilités
  listerDisponibilites: async (praticienId: string, cabinetId?: string | null) => {
    const url = cabinetId
      ? `/praticiens/${praticienId}/disponibilites?cabinet_id=${cabinetId}`
      : `/praticiens/${praticienId}/disponibilites`
    return api.get<ApiReponse<Disponibilite[]>>(url)
  },

  creerDisponibilite: async (
    praticienId: string,
    data: {
      cabinet_id?: string | null
      jour_semaine?: number | null
      date_specifique?: string | null
      heure_debut: string
      heure_fin: string
      type: 'CONSULTATION' | 'URGENCE' | 'BLOCKING'
      motif_blocage?: string
    },
  ) => {
    return api.post<ApiReponse<Disponibilite>>(
      `/praticiens/${praticienId}/disponibilites`,
      data,
    )
  },

  supprimerDisponibilite: async (disponibiliteId: string) => {
    return api.delete<void>(`/disponibilites/${disponibiliteId}`)
  },

  // Créneaux libres calculés
  calculerCreneaux: async (
    praticienId: string,
    date: string,
    cabinetId?: string | null,
    dureeMinutes = 30,
  ) => {
    const params = new URLSearchParams()
    params.set('date', date)
    if (cabinetId) params.set('cabinet_id', cabinetId)
    params.set('duree_minutes', String(dureeMinutes))
    return api.get<ApiReponse<CreneauxResponseData>>(
      `/praticiens/${praticienId}/creneaux?${params.toString()}`,
    )
  },
}
