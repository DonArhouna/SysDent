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
  /**
   * Site courant. `null` signifie « pas encore résolu » — le chargement des
   * sites est en cours, ou a échoué.
   *
   * Ce n'est **pas** « tous les cabinets » : un cabinet appartient à un seul
   * tenant, et afficher un agrégat inter-sites reviendrait à montrer à
   * l'utilisateur la comptabilité d'un autre site.
   */
  cabinetActifId: string | null
  cabinets: CabinetItem[]
  chargement: boolean
  setCabinetActifId: (id: string | null) => void
  /** Oublie le site courant et la liste des sites : fin de session. */
  vider: () => void
  chargerCabinets: () => Promise<void>
}

export const useCabinetStore = create<CabinetState>()(
  persist(
    (set, get) => ({
      cabinetActifId: null,
      cabinets: [],
      chargement: false,

      setCabinetActifId: (id) => set({ cabinetActifId: id }),

      vider: () => set({ cabinetActifId: null, cabinets: [], chargement: false }),

      chargerCabinets: async () => {
        try {
          set({ chargement: true })
          const res = await api.get<ApiReponse<CabinetItem[]>>('/cabinets')
          const liste = res.data ?? []
          set({ cabinets: liste })

          // Le site mémorisé peut ne plus exister : désactivé entre deux sessions,
          // ou supprimé. Sans cette vérification, `cabinetActifId` garderait un
          // identifiant mort et toutes les requêtes du cabinet partiraient vers
          // un site qui n'est plus là.
          const actifId = get().cabinetActifId
          const toujoursValide =
            !!actifId && liste.some((c) => c.id === actifId && c.actif !== false)
          if (!toujoursValide && liste.length > 0) {
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
