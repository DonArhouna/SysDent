import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import type {
  AntecedentMedical,
  EtatGeneral,
  FiltresRecherchePatients,
  Patient,
  PatientCreateInput,
  PatientDossierComplet,
  PatientUpdateInput,
} from '../types'

export const patientsApi = {
  // Liste paginée avec recherche
  lister: async (filtres: FiltresRecherchePatients = {}) => {
    const params = new URLSearchParams()
    if (filtres.q) params.set('q', filtres.q)
    if (filtres.nom) params.set('nom', filtres.nom)
    if (filtres.telephone) params.set('telephone', filtres.telephone)
    if (filtres.numero_dossier) params.set('numero_dossier', filtres.numero_dossier)
    if (filtres.date_naissance) params.set('date_naissance', filtres.date_naissance)
    if (filtres.include_archives) params.set('include_archives', 'true')
    if (filtres.uniquement_archives) params.set('uniquement_archives', 'true')
    params.set('page', String(filtres.page ?? 1))
    params.set('limit', String(filtres.limit ?? 20))

    return api.get<PageReponse<Patient>>(`/patients?${params.toString()}`)
  },

  // Identité simple
  obtenir: async (id: string) => {
    return api.get<ApiReponse<Patient>>(`/patients/${id}`)
  },

  // Dossier médical complet avec alertes et antécédents
  obtenirDossierComplet: async (id: string) => {
    return api.get<ApiReponse<PatientDossierComplet>>(`/patients/${id}/dossier`)
  },

  // Création
  creer: async (data: PatientCreateInput) => {
    return api.post<ApiReponse<Patient>>('/patients', data)
  },

  // Modification
  modifier: async (id: string, data: PatientUpdateInput) => {
    return api.patch<ApiReponse<Patient>>(`/patients/${id}`, data)
  },

  // Archivage
  archiver: async (id: string, motif?: string) => {
    return api.post<ApiReponse<Patient>>(`/patients/${id}/archiver`, { motif })
  },

  // Réactivation
  reactiver: async (id: string) => {
    return api.post<ApiReponse<Patient>>(`/patients/${id}/reactiver`)
  },

  // État général
  obtenirEtatGeneral: async (patientId: string) => {
    return api.get<ApiReponse<EtatGeneral | null>>(`/patients/${patientId}/etat-general`)
  },

  enregistrerEtatGeneral: async (patientId: string, data: Partial<EtatGeneral>) => {
    return api.put<ApiReponse<EtatGeneral>>(`/patients/${patientId}/etat-general`, data)
  },

  modifierEtatGeneral: async (patientId: string, data: Partial<EtatGeneral>) => {
    return api.patch<ApiReponse<EtatGeneral>>(`/patients/${patientId}/etat-general`, data)
  },

  // Antécédents
  listerAntecedents: async (patientId: string) => {
    return api.get<ApiReponse<AntecedentMedical[]>>(`/patients/${patientId}/antecedents`)
  },

  ajouterAntecedent: async (
    patientId: string,
    data: {
      type_antecedent: string
      description: string
      date_survenue?: string | null
      en_cours: boolean
      traitement_associe?: string | null
      notes?: string | null
    },
  ) => {
    return api.post<ApiReponse<AntecedentMedical>>(`/patients/${patientId}/antecedents`, data)
  },

  modifierAntecedent: async (
    antecedentId: string,
    data: Partial<AntecedentMedical>,
  ) => {
    return api.patch<ApiReponse<AntecedentMedical>>(`/patients/antecedents/${antecedentId}`, data)
  },
}
