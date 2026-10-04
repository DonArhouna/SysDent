import { api } from '@/lib/api'
import type { APIResponse, PaginatedResponse } from '@/types/api'
import type {
  DevisCreate,
  DevisResponse,
  DevisStatutUpdate,
  FactureConsultationCreate,
  FactureLibreCreate,
  FactureResponse,
  JournalCaisseItem,
  PaiementCreate,
  PaiementResponse,
  PlanEchelonnementCreate,
  PlanEchelonnementResponse,
} from '../types'

export const facturationApi = {
  // Factures
  facturerConsultation: (consultationId: string, data: FactureConsultationCreate) => {
    return api.post<APIResponse<FactureResponse>>(`/factures/consultation/${consultationId}`, data)
  },

  facturerLibre: (data: FactureLibreCreate) => {
    return api.post<APIResponse<FactureResponse>>('/factures', data)
  },

  listerFactures: (params?: {
    patient_id?: string
    statut?: string
    q?: string
    date_debut?: string
    date_fin?: string
    page?: number
    limit?: number
  }) => {
    return api.get<PaginatedResponse<FactureResponse>>('/factures', { params })
  },

  obtenirFacture: (id: string) => {
    return api.get<APIResponse<FactureResponse>>(`/factures/${id}`)
  },

  encaisser: (factureId: string, data: PaiementCreate) => {
    return api.post<APIResponse<PaiementResponse>>(`/factures/${factureId}/paiements`, data)
  },

  annulerFacture: (factureId: string, motif: string) => {
    return api.post<APIResponse<FactureResponse>>(`/factures/${factureId}/annuler`, null, {
      params: { motif },
    })
  },

  // Échelonnement
  creerEchelonnement: (factureId: string, data: PlanEchelonnementCreate) => {
    return api.post<APIResponse<PlanEchelonnementResponse>>(
      `/factures/${factureId}/echelonnement`,
      data
    )
  },

  obtenirEchelonnement: (factureId: string) => {
    return api.get<APIResponse<PlanEchelonnementResponse | null>>(
      `/factures/${factureId}/echelonnement`
    )
  },

  // Journal de caisse
  journalCaisse: (params?: {
    date_debut?: string
    date_fin?: string
    mode?: string
    page?: number
    limit?: number
  }) => {
    return api.get<PaginatedResponse<JournalCaisseItem>>('/factures/journal-caisse', { params })
  },

  // Devis
  creerDevis: (data: DevisCreate) => {
    return api.post<APIResponse<DevisResponse>>('/devis', data)
  },

  listerDevis: (params?: {
    patient_id?: string
    statut?: string
    q?: string
    page?: number
    limit?: number
  }) => {
    return api.get<PaginatedResponse<DevisResponse>>('/devis', { params })
  },

  obtenirDevis: (id: string) => {
    return api.get<APIResponse<DevisResponse>>(`/devis/${id}`)
  },

  changerStatutDevis: (id: string, data: DevisStatutUpdate) => {
    return api.post<APIResponse<DevisResponse>>(`/devis/${id}/statut`, data)
  },

  convertirDevis: (id: string) => {
    return api.post<APIResponse<FactureResponse>>(`/devis/${id}/convertir`, {})
  },
}
