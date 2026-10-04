/**
 * Session utilisateur (Zustand + persistance localStorage).
 *
 * ## Le refresh token
 *
 * Il est stocké ici, malgré le commentaire d'origine qui annonçait un cookie HttpOnly.
 * Raison vérifiée dans le code backend : `POST /auth/refresh` exige
 * `refresh_token` **dans le corps** (`schemas.py:22`, `refresh_token: str`
 * obligatoire) et le backend ne dépose aucun cookie de refresh — le cookie
 * `access_token` contient le jeton d'accès, expirant au bout de 15 minutes.
 * Sans conserver le refresh token côté client, le renouvellement était
 * impossible : l'application expirait au bout de 15 minutes.
 *
 * ⚠️ **Correctif recommandé côté backend** : déposer aussi un cookie
 * `refresh_token` HttpOnly à la connexion, et rendre le champ du corps
 * facultatif avec repli sur le cookie. Le refresh token est un secret de
 * 7 jours ; le garder dans le localStorage le rend lisible par un XSS, alors
 * qu'un cookie HttpOnly ne l'est pas. C'est la seule réserve de sécurité qui
 * subsiste ici.
 *
 * Le token d'accès, lui, reste court (15 min) : le garder en mémoire suffit,
 * mais il est persisté pour ne pas redemander un jeton à chaque rechargement.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  api,
  setTokenProvider,
  setRafraichisseur,
  setGestionnaireSessionMorte,
  type ApiReponse,
} from '@/lib/api'

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
  refreshToken: string | null
  profil: ProfilUtilisateur | null
  connexion: (email: string, password: string) => Promise<void>
  chargerProfil: () => Promise<void>
  deconnexion: () => void
}

/** Message d'erreur normalisé, sans dépendre de `ApiError` (import circulaire). */
function messageErreur(e: unknown): string {
  if (e && typeof e === 'object' && 'message' in e) return String(e.message)
  return 'Erreur inconnue'
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      profil: null,

      connexion: async (email, password) => {
        const reponse = await api.post<ApiReponse<TokenReponse>>('/auth/login', {
          email,
          password,
        })
        set({
          token: reponse.data.access_token,
          refreshToken: reponse.data.refresh_token,
          profil: null,
        })
        // Profil complet (rôles, permissions) en une seconde requête : c'est
        // lui qui alimente le RBAC côté UI.
        await get().chargerProfil()
      },

      chargerProfil: async () => {
        const reponse = await api.get<ApiReponse<ProfilUtilisateur>>('/auth/me')
        set({ profil: reponse.data })
      },

      deconnexion: () => {
        // Best-effort : la révocation serveur peut échouer hors ligne. On ne
        // bloque pas la déconnexion locale pour autant.
        const refreshToken = get().refreshToken
        if (refreshToken) {
          api
            .post('/auth/logout', { refresh_token: refreshToken }, { silencieux: true })
            .catch(() => undefined)
        }
        set({ token: null, refreshToken: null, profil: null })
      },
    }),
    {
      name: 'sysdent-auth',
      partialize: (etat) => ({
        token: etat.token,
        refreshToken: etat.refreshToken,
        profil: etat.profil,
      }),
    },
  ),
)

// Le client HTTP lit le jeton via ce fournisseur (pas de capture à l'import).
setTokenProvider(() => useAuthStore.getState().token)

/**
 * Renouvellement du jeton d'accès, appelé par `api.ts` sur un 401.
 *
 * Appelé potentiellement en parallèle par six requêtes : `api.ts` partage une
 * seule promesse, donc un seul POST `/auth/refresh` part. Sans cela, le backend
 * — qui fait tourner le refresh token — refuserait cinq des six.
 *
 * Retourne le nouveau jeton, ou `null` si la session est morte.
 */
setRafraichisseur(async () => {
  const refreshToken = useAuthStore.getState().refreshToken
  if (!refreshToken) return null

  try {
    const reponse = await api.post<ApiReponse<TokenReponse>>(
      '/auth/refresh',
      { refresh_token: refreshToken },
      { silencieux: true },
    )
    const nouveau = reponse.data.access_token
    useAuthStore.setState({
      token: nouveau,
      // Le backend fait tourner le refresh token : l'ancien ne vaut plus rien.
      refreshToken: reponse.data.refresh_token,
    })
    return nouveau
  } catch (e) {
    // Renouvelement impossible : la session est terminée.
    console.warn('[auth] renouvellement impossible :', messageErreur(e))
    return null
  }
})

// Session morte (refresh refusé ou absent) : on purge, `AppShell` redirigera.
setGestionnaireSessionMorte(() => {
  useAuthStore.getState().deconnexion()
})

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