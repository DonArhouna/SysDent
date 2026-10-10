import { create } from 'zustand'
import { api, ApiError, type ApiReponse } from '@/lib/api'
import type { ReponseDe } from '@/lib/api'

/**
 * Réponse de `GET /platform/stats/dashboard`, tirée du schéma openapi.
 * Un seul appel sert tout l'écran : la latence d'agrégation est payée côté
 * serveur une fois, jamais quatre.
 */
export type VueDashboard = NonNullable<
  ReponseDe<'/api/v1/platform/stats/dashboard', 'get'>['data']
>

/**
 * Trois états distincts, pas deux :
 * - `chargement` → skeletons, jamais un zéro ;
 * - `erreur` → message d'erreur explicite et **bouton « Réessayer »** : une
 *   panne présentée comme un zéro invente un mensonge statistique ;
 * - `vide` → la plateforme n'a aucun cabinet : EmptyState, pas d'erreur.
 */
export type EtatDashboard = 'chargement' | 'erreur' | 'vide' | 'pret'

interface DashboardState {
  etat: EtatDashboard
  vue: VueDashboard | null
  messageErreur: string | null
  charger: () => Promise<void>
  reessayer: () => Promise<void>
}

export const useDashboardStore = create<DashboardState>()((set, get) => ({
  etat: 'chargement',
  vue: null,
  messageErreur: null,

  charger: async () => {
    set({ etat: 'chargement', messageErreur: null })
    try {
      const reponse = await api.get<ApiReponse<VueDashboard>>(
        '/platform/stats/dashboard',
      )
      const vue = reponse.data
      if (!vue) throw new Error('réponse sans données')
      set({
        vue,
        etat: (vue.total_cabinets ?? 0) === 0 ? 'vide' : 'pret',
        messageErreur: null,
      })
    } catch (e) {
      set({
        etat: 'erreur',
        // Un seul message, jamais un zéro : la panne est une panne.
        messageErreur:
          e instanceof ApiError ? e.message : 'Le serveur ne répond pas.',
      })
    }
  },

  reessayer: async () => {
    await get().charger()
  },
}))
