import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import type {
  ActeNomenclature,
  ActeRealise,
  ActeRealiseCreateInput,
  Consultation,
  ConsultationCreateInput,
  ConsultationDetail,
  ConsultationUpdateInput,
} from '../types'

export const consultationsApi = {
  // Liste des consultations
  lister: async (filtres: {
    patient_id?: string
    praticien_id?: string
    statut?: string
    date_debut?: string
    date_fin?: string
    page?: number
    limit?: number
  } = {}) => {
    const params = new URLSearchParams()
    if (filtres.patient_id) params.set('patient_id', filtres.patient_id)
    if (filtres.praticien_id) params.set('praticien_id', filtres.praticien_id)
    if (filtres.statut) params.set('statut', filtres.statut)
    if (filtres.date_debut) params.set('date_debut', filtres.date_debut)
    if (filtres.date_fin) params.set('date_fin', filtres.date_fin)
    params.set('page', String(filtres.page ?? 1))
    params.set('limit', String(filtres.limit ?? 20))
    return api.get<PageReponse<Consultation>>(`/consultations?${params.toString()}`)
  },

  // Détail complet avec actes et total facturable
  obtenirDetail: async (id: string) => {
    return api.get<ApiReponse<ConsultationDetail>>(`/consultations/${id}/detail`)
  },

  // Démarrer consultation
  demarrer: async (data: ConsultationCreateInput) => {
    return api.post<ApiReponse<Consultation>>('/consultations', data)
  },

  // Mettre à jour examen / diagnostic
  mettreAJour: async (id: string, data: ConsultationUpdateInput) => {
    return api.patch<ApiReponse<Consultation>>(`/consultations/${id}`, data)
  },

  // Clôturer la consultation
  terminer: async (
    id: string,
    data: {
      diagnostic_principal: string
      plan_traitement?: string
      recommandations?: string
      prochain_rdv_prevu?: string
    },
  ) => {
    return api.post<ApiReponse<ConsultationDetail>>(`/consultations/${id}/terminer`, data)
  },

  // Annuler
  annuler: async (id: string, motif?: string) => {
    return api.post<ApiReponse<Consultation>>(`/consultations/${id}/annuler`, { motif })
  },

  // Actes de la consultation
  listerActes: async (consultationId: string) => {
    return api.get<ApiReponse<ActeRealise[]>>(`/consultations/${consultationId}/actes`)
  },

  ajouterActe: async (consultationId: string, data: ActeRealiseCreateInput) => {
    return api.post<ApiReponse<ActeRealise>>(`/consultations/${consultationId}/actes`, data)
  },

  modifierActe: async (acteId: string, data: Partial<ActeRealiseCreateInput>) => {
    return api.patch<ApiReponse<ActeRealise>>(`/consultations/actes/${acteId}`, data)
  },

  supprimerActe: async (acteId: string, motif?: string) => {
    const params = motif ? `?motif=${encodeURIComponent(motif)}` : ''
    return api.delete<void>(`/consultations/actes/${acteId}${params}`)
  },

  totalConsultation: async (consultationId: string) => {
    return api.get<ApiReponse<{ total_actes: string | number; nb_actes: number; devise: string }>>(
      `/consultations/${consultationId}/total`,
    )
  },

  // Nomenclature des actes
  listerNomenclature: async (q?: string, categorie?: string) => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (categorie) params.set('categorie', categorie)
    params.set('limit', '100')
    return api.get<PageReponse<ActeNomenclature>>(`/nomenclature/actes?${params.toString()}`)
  },
}
