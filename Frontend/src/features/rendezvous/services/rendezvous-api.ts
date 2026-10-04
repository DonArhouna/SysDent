import { api, type ApiReponse } from '@/lib/api'
import type {
  AgendaData,
  CreneauLibre,
  MotifBlocageFauteuil,
  RdvCreateInput,
  RendezVous,
  StatutRdv,
} from '../types'

export const rendezvousApi = {
  // Prise de rendez-vous
  creer: async (data: RdvCreateInput) => {
    return api.post<ApiReponse<RendezVous>>('/rendez-vous', data)
  },

  // Agenda journée
  obtenirAgenda: async (date: string, cabinetId?: string | null, praticienId?: string | null) => {
    const params = new URLSearchParams()
    params.set('date', date)
    if (cabinetId) params.set('cabinet_id', cabinetId)
    if (praticienId) params.set('praticien_id', praticienId)
    return api.get<ApiReponse<AgendaData>>(`/rendez-vous/agenda?${params.toString()}`)
  },

  // Liste globale avec filtres
  lister: async (filtres: {
    patient_id?: string
    praticien_id?: string
    cabinet_id?: string
    fauteuil_id?: string
    du?: string
    au?: string
    statuts?: string[]
  } = {}) => {
    const params = new URLSearchParams()
    if (filtres.patient_id) params.set('patient_id', filtres.patient_id)
    if (filtres.praticien_id) params.set('praticien_id', filtres.praticien_id)
    if (filtres.cabinet_id) params.set('cabinet_id', filtres.cabinet_id)
    if (filtres.fauteuil_id) params.set('fauteuil_id', filtres.fauteuil_id)
    if (filtres.du) params.set('du', filtres.du)
    if (filtres.au) params.set('au', filtres.au)
    return api.get<ApiReponse<RendezVous[]>>(`/rendez-vous?${params.toString()}`)
  },

  // Créneaux libres calculés (heures déclarées MOINS rendez-vous et fauteuils bloqués)
  creneauxLibres: async (
    praticienId: string,
    date: string,
    dureeMinutes = 30,
    cabinetId?: string | null,
    exclureRdvId?: string | null,
  ) => {
    const params = new URLSearchParams()
    params.set('praticien_id', praticienId)
    params.set('date', date)
    params.set('duree_minutes', String(dureeMinutes))
    if (cabinetId) params.set('cabinet_id', cabinetId)
    if (exclureRdvId) params.set('exclure_rendez_vous', exclureRdvId)
    return api.get<ApiReponse<CreneauLibre[]>>(`/rendez-vous/creneaux-libres?${params.toString()}`)
  },

  // Changer statut
  changerStatut: async (rdvId: string, statut: StatutRdv, motif?: string) => {
    const params = new URLSearchParams()
    params.set('statut', statut)
    if (motif) params.set('motif', motif)
    return api.post<ApiReponse<RendezVous>>(`/rendez-vous/${rdvId}/statut?${params.toString()}`)
  },

  // Déplacer / Reporter
  planifier: async (
    rdvId: string,
    debut: string,
    dureeMinutes = 30,
    fauteuilId?: string | null,
    motifReport?: string,
  ) => {
    const params = new URLSearchParams()
    params.set('debut', debut)
    params.set('duree_minutes', String(dureeMinutes))
    if (fauteuilId) params.set('fauteuil_id', fauteuilId)
    if (motifReport) params.set('motif_report', motifReport)
    return api.post<ApiReponse<RendezVous>>(`/rendez-vous/${rdvId}/planifier?${params.toString()}`)
  },

  // Démarrer consultation depuis le RDV
  demarrerConsultation: async (rdvId: string) => {
    return api.post<ApiReponse<{ id: string; consultation_id?: string }>>(
      `/rendez-vous/${rdvId}/consultation`,
    )
  },

  // Blocage de fauteuil
  bloquerFauteuil: async (data: {
    fauteuil_id: string
    debut: string
    fin: string
    motif: MotifBlocageFauteuil
    motif_detail?: string
  }) => {
    return api.post<ApiReponse<unknown>>('/rendez-vous/fauteuils/blocage', data)
  },

  debloquerFauteuil: async (creneauId: string) => {
    return api.delete<void>(`/rendez-vous/fauteuils/blocage/${creneauId}`)
  },
}
