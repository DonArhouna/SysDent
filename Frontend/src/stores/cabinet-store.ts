import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, type ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

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
        // **Permission vérifiée avant l'appel, pas après.** `/cabinets` exige
        // `CABINETS:READ`. Un profil sans cette permission - un praticien restreint,
        // par exemple - ne peut pas y accéder, et l'appel échoue en 403. Comme
        // le tiroir odontogramme ne montre aucun site, il n'a rien a en faire :
        // l'appel était inutile, et répétait un 403 dans l'onglet Réseau à
        // chaque ouverture de page.
        //
        // La permission vient du profil réellement livré par `/auth/me`, pas
        // d'une liste de rôles écrite ici : la seule constante est celle de
        // l'API, celle que l'endpoint déclare.
        const permissions = useAuthStore.getState().profil?.permissions ?? []
        if (!permissions.includes('CABINETS:READ')) {
          set({ cabinets: [], chargement: false })
          return
        }

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
