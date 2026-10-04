import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, type ApiReponse } from '@/lib/api'

export interface CabinetItem {
  id: string
  nom: string
  ville?: string | null
  adresse?: string | null
  telephone?: string | null
  actif: boolean
  nb_salles?: number
  nb_fauteuils_actifs?: number
  nb_praticiens_actifs?: number
}

interface CabinetState {
  cabinetActifId: string | null // null = "Tous les cabinets" (pour rôles globaux)
  cabinets: CabinetItem[]
  chargement: boolean
  setCabinetActifId: (id: string | null) => void
  chargerCabinets: () => Promise<void>
}

export const useCabinetStore = create<CabinetState>()(
  persist(
    (set, get) => ({
      cabinetActifId: null,
      cabinets: [],
      chargement: false,

      setCabinetActifId: (id) => set({ cabinetActifId: id }),

      chargerCabinets: async () => {
        try {
          set({ chargement: true })
          const res = await api.get<ApiReponse<CabinetItem[]>>('/cabinets')
          const liste = res.data ?? []
          set({ cabinets: liste })

          // Si aucun cabinet sélectionné ou cabinet sélectionné inexistant, sélectionner le 1er cabinet actif
          const actifId = get().cabinetActifId
          if (!actifId && liste.length > 0) {
            const premierActif = liste.find((c) => c.actif) ?? liste[0]
            if (premierActif) {
              set({ cabinetActifId: premierActif.id })
            }
          }
        } catch {
          // Si l'appel échoue (ex: pas encore loggué ou hors-ligne), silencieux
        } finally {
          set({ chargement: false })
        }
      },
    }),
    {
      name: 'sysdent-cabinet-storage',
      partialize: (state) => ({ cabinetActifId: state.cabinetActifId }),
    },
  ),
)
