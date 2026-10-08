import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Cabinet actuellement consulté.
 *
 * C'est un **identifiant de tenant**, donc la donnée la plus sensible qui
 * survive à une déconnexion : laissé en place, il ferait porter les requêtes de
 * l'utilisateur suivant vers le cabinet du précédent. La purge de session le
 * remet donc explicitement à `null`.
 */
interface TenantState {
  tenantCourantId: string | null
  setTenantCourantId: (id: string | null) => void
  /** Oublie le cabinet consulté : fin de session. */
  vider: () => void
}

export const useCabinetStore = create<TenantState>()(
  persist(
    (set) => ({
      tenantCourantId: null,
      setTenantCourantId: (id) => set({ tenantCourantId: id }),
      vider: () => set({ tenantCourantId: null }),
    }),
    { name: 'sysdent-backoffice-tenant' },
  ),
)
