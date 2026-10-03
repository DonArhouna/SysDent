/**
 * Session utilisateur (Zustand + persistance localStorage).
 *
 * Le refresh token n'est PAS stocké ici : il vit dans un cookie HttpOnly
 * côté backend (`credentials: "include"`), invisible pour le JS. Seul
 * l'access token court est gardé pour les appels authentifiés.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, setTokenProvider, type ApiReponse } from '@/lib/api'

export interface ProfilUtilisateur {
  id: string
  email: string
  prenom: string
  nom: string
  role: string
  permissions: string[]
  telephone?: string | null
  photo_url?: string | null
  tenant_id?: string | null
}

interface TokenReponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  tenant_id?: string | null
}

interface AuthState {
  token: string | null
  profil: ProfilUtilisateur | null
  connexion: (email: string, password: string) => Promise<void>
  chargerProfil: () => Promise<void>
  deconnexion: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      profil: null,

      connexion: async (email, password) => {
        const reponse = await api.post<ApiReponse<TokenReponse>>('/auth/login', {
          email,
          password,
        })
        set({ token: reponse.data.access_token, profil: null })
        // Profil complet (rôles, permissions) en une seconde requête : c'est
        // lui qui alimente le RBAC côté UI.
        await get().chargerProfil()
      },

      chargerProfil: async () => {
        const reponse = await api.get<ApiReponse<ProfilUtilisateur>>('/auth/me')
        set({ profil: reponse.data })
      },

      deconnexion: () => {
        // Best-effort : la révocation serveur peut échouer hors ligne.
        api.post('/auth/logout').catch(() => undefined)
        set({ token: null, profil: null })
      },
    }),
    {
      name: 'sysdent-auth',
      partialize: (etat) => ({ token: etat.token, profil: etat.profil }),
    },
  ),
)

// Le client HTTP lit le token via ce fournisseur (pas de capture à l'import).
setTokenProvider(() => useAuthStore.getState().token)

/** `true` si l'utilisateur possède la permission `"MODULE:ACTION"`. */
export function possedePermission(
  profil: ProfilUtilisateur | null,
  permission: string,
): boolean {
  if (!profil) return false
  // ADMIN_CABINET : court-circuit identique au backend.
  if (profil.role === 'ADMIN_CABINET' || profil.role === 'SUPER_ADMIN') return true
  return profil.permissions.includes(permission)
}
