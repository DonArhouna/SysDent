import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  api,
  setTokenProvider,
  setRafraichisseur,
  setGestionnaireSessionMorte,
  type ApiReponse,
} from '@/lib/api'
import { useCabinetStore } from '@/stores/tenant-store'

/**
 * Session plateforme.
 *
 * Un compte plateforme ouvre la porte à **tous** les cabinets : c'est la partie
 * la plus sensible du produit. Tout ce qui suit est écrit en conséquence.
 *
 * **Ce qui est appris de l'échec de l'application client**, et qui s'y applique :
 *
 * 1. La purge de session est **unique et idempotente**. Six requêtes recevant 401
 *    en même temps n'aboutissent pas à six purges — les 401 arrivent
 *    **échelonnés**, chacun après la promesse de renouvellement partagée, donc un
 *    simple verrou « purge en cours » ne suffit pas. L'état qui compte est
 *    « cette session est **déjà morte** ».
 * 2. La purge **vide le cache** et **purge tous les stores** : le site mémorisé
 *    est un identifiant de tenant, le laisser en place ferait porter les
 *    requêtes du second utilisateur vers le site du premier.
 * 3. Elle se **propage aux autres onglets**. Le `localStorage` partagé ne met pas
 *    à jour un store déjà chargé : sans `BroadcastChannel`, un onglet resté ouvert
 *    continue d'appeler l'API avec un jeton révoqué.
 */

export interface ProfilPlateforme {
  id: string
  email: string
  prenom: string
  nom: string
  role: string
  permissions: string[]
  /** `true` tant que le compte n'a pas confirmé son secret TOTP. */
  deux_facteurs_actif?: boolean
  deux_facteurs_prevu?: boolean
}

interface ReponseJeton {
  access_token: string
  refresh_token: string
  /** Présent au premier contacts : le client doit confirmer le secret TOTP. */
  jeton_challenge?: string
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  profil: ProfilPlateforme | null
  /** Jeton d'étape 2, entre le mot de passe et la saisie du code TOTP. */
  challenge2fa: string | null
  connexion: (email: string, password: string) => Promise<'challenge' | 'ok'>
  valider2fa: (code: string) => Promise<void>
  annuler2fa: () => void
  chargerProfil: () => Promise<void>
  deconnexion: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      profil: null,
      challenge2fa: null,

      connexion: async (email, password) => {
        const reponse = await api.post<ApiReponse<ReponseJeton>>('/platform/auth/login', {
          email,
          password,
        })
        // Message volontairement identique quel que soit le motif du refus :
        // distinguer « compte inconnu » de « mot de passe faux » offre un oracle
        // aux énumérations de comptes.
        if (!reponse?.data?.access_token) {
          throw new Error('Identifiants invalides.')
        }

        // Un compte sans 2FA configuré reçoit un jeton d'étape : la session ne
        // s'ouvre qu'après confirmation du secret TOTP.
        if (reponse.data.jeton_challenge) {
          set({ challenge2fa: reponse.data.jeton_challenge })
          return 'challenge'
        }

        sessionVivante()
        set({
          token: reponse.data.access_token,
          refreshToken: reponse.data.refresh_token,
          challenge2fa: null,
        })
        await get().chargerProfil()
        return 'ok'
      },

      valider2fa: async (code) => {
        const challenge = get().challenge2fa
        if (!challenge) throw new Error('Session de connexion expirée.')
        const reponse = await api.post<ApiReponse<ReponseJeton>>('/platform/auth/2fa', {
          jeton_challenge: challenge,
          code,
        })
        sessionVivante()
        set({
          token: reponse.data.access_token,
          refreshToken: reponse.data.refresh_token,
          challenge2fa: null,
        })
        await get().chargerProfil()
      },

      annuler2fa: () => set({ challenge2fa: null }),

      chargerProfil: async () => {
        const reponse = await api.get<ApiReponse<ProfilPlateforme>>('/platform/auth/me')
        set({ profil: reponse.data })
      },

      deconnexion: () => {
        // Best-effort : la révocation serveur peut échouer hors ligne, et
        // bloquer la déconnexion locale n'est pas une protection.
        const refreshToken = get().refreshToken
        if (refreshToken) {
          api
            .post('/platform/auth/logout', { refresh_token: refreshToken }, { silencieux: true })
            .catch(() => undefined)
        }
        purgerSession()
      },
    }),
    {
      name: 'sysdent-backoffice-auth',
      partialize: (etat) => ({
        token: etat.token,
        refreshToken: etat.refreshToken,
        profil: etat.profil,
        challenge2fa: etat.challenge2fa,
      }),
    },
  ),
)

/** Purgeur enregistré par l'application : vide le cache, ramène à la connexion. */
type PurgeurSession = () => void
let purgeurSession: PurgeurSession | null = null

/**
 * La session a-t-elle déjà été purgée ?
 *
 * Un verrou « purge en cours » serait faux : les 401 arrivent échelonnés, la
 * première purge se termine avant que la suivante n'arrive. L'état juste est
 * « session déjà morte », remis à zéro quand une session **vivante** naît.
 */
let sessionVidee = false

function sessionVivante(): void {
  sessionVidee = false
}

export function setPurgeurSession(fn: PurgeurSession | null): void {
  purgeurSession = fn
}

/** Nom du canal : un même nom = même canal, dans tout le navigateur. */
const CANAL_SESSION = 'sysdent-backoffice-session'

function diffuserPurgeSession(): void {
  if (typeof BroadcastChannel === 'undefined') return
  try {
    const canal = new BroadcastChannel(CANAL_SESSION)
    canal.postMessage('session-purge')
    canal.close()
  } catch {
    /* canal indisponible : la purge locale a déjà eu lieu, c'est l'essentiel */
  }
}

function purgerSession(diffuse = true): void {
  if (sessionVidee) return
  sessionVidee = true

  useAuthStore.setState({
    token: null,
    refreshToken: null,
    profil: null,
    challenge2fa: null,
  })
  // Le site mémorisé est un identifiant de tenant : le conserver ferait porter les
  // requêtes de l'utilisateur suivant vers celui du précédent.
  useCabinetStore.getState().vider()

  try {
    if (diffuse) diffuserPurgeSession()
    purgeurSession?.()
  } catch {
    // Un cache non vidé ne doit jamais empêcher la déconnexion.
  }
}

// Le client HTTP lit le jeton via ce fournisseur, sans capture à l'import.
setTokenProvider(() => useAuthStore.getState().token)

setRafraichisseur(async () => {
  const refreshToken = useAuthStore.getState().refreshToken
  if (!refreshToken) return null
  try {
    const reponse = await api.post<ApiReponse<ReponseJeton>>(
      '/platform/auth/refresh',
      { refresh_token: refreshToken },
      { silencieux: true },
    )
    // La session redevient vivante : une purge ultérieure doit avoir lieu.
    sessionVivante()
    useAuthStore.setState({
      token: reponse.data.access_token,
      // Le backend fait tourner le refresh token : l'ancien ne vaut plus rien.
      refreshToken: reponse.data.refresh_token,
    })
    return reponse.data.access_token
  } catch {
    // Renouvellement impossible : la session est terminée.
    return null
  }
})

setGestionnaireSessionMorte(() => purgerSession())

// Déconnexion dans un onglet = déconnexion et purge dans tous les autres.
if (typeof BroadcastChannel !== 'undefined') {
  try {
    const canal = new BroadcastChannel(CANAL_SESSION)
    canal.onmessage = (evenement: MessageEvent) => {
      if (evenement.data === 'session-purge') purgerSession(false)
    }
  } catch {
    /* même raison que ci-dessus */
  }
}

/** `true` si l'utilisateur possède la permission `"MODULE:ACTION"`. */
export function possedePermission(
  profil: ProfilPlateforme | null,
  permission: string,
): boolean {
  if (!profil) return false
  // Court-circuit des rôles de contrôle : le backend applique la même règle,
  // et deux implémentations divergentes donneraient des boutons visibles qui
  // répondent 403.
  if (profil.role === 'SUPER_ADMIN') return true
  return profil.permissions.includes(permission)
}