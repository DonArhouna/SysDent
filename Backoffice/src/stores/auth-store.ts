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

/**
 * Les jetons sont **absents** selon le cas, jamais tous presents.
 *
 * Ce type les declarait obligatoires, alors que le backend n'ouvre volontairement
 * aucune session avant la confirmation du second facteur. Un type qui promet un
 * champ que le serveur n'envoie pas ne protege de rien : il fait ecrire le code
 * appelant comme si le champ etait la.
 */
interface ReponseJeton {
  /** Absent tant que le second facteur n'est pas confirme. */
  access_token?: string
  /** Absent tant que le second facteur n'est pas confirme. */
  refresh_token?: string
  /** Etape 2 : le client doit confirmer le secret TOTP d'un compte deja configure. */
  jeton_challenge?: string
  /** Etape 2 : le compte n'a encore aucun secret TOTP ; il doit s'enroler. */
  jeton_enrolement?: string
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  profil: ProfilPlateforme | null
  /** Jeton d'étape 2, entre le mot de passe et la saisie du code TOTP. */
  challenge2fa: string | null
  /**
   * Jeton d'enrolement : **tenu en memoire uniquement**, jamais persiste.
   *
   * Il n'ouvre que la preparation et l'activation du second facteur. Persiste, il
   * survivrait a la fermeture de l'onglet et rouvrirait une porte que la session,
   * elle, a fermee.
   */
  jetonEnrolement: string | null
  connexion: (email: string, password: string) => Promise<'challenge' | 'enrolement' | 'ok'>
  valider2fa: (code: string) => Promise<void>
  annuler2fa: () => void
  annulerEnrolement: () => void
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
        jetonEnrolement: null,

      connexion: async (email, password) => {
        const reponse = await api.post<ApiReponse<ReponseJeton>>('/platform/auth/login', {
          email,
          // Le backend nomme le champ `mot_de_passe`, pas `password`. Trouve par
          // execution : l'ecran renvoyait 422 et rien dans le type TypeScript ne
          // pouvait le dire, l'appel passant par une enveloppe generique.
          mot_de_passe: password,
        })
        // **Un refus reel ne passe pas par ici.** `api.post` leve deja une
        // `ApiError` sur une 4xx, et le backend y met le meme message unique quel
        // que soit le motif : « compte inconnu » et « mot de passe faux » doivent
        // rester indistinguables.
        //
        // Ce qui se passait avant : le test « pas d'access_token » levait
        // « Identifiants invalides » sur une reponse **200**. Or une reponse
        // portant un jeton d'etape n'a pas d'access_token, par construction - c'est
        // meme la garantie qu'aucune session ne s'ouvre avant le second facteur.
        // La branche `jeton_challenge` en dessous etait donc du **code mort** :
        // tout compte plateforme, 2FA comprise, echouait a l'ecran de connexion
        // alors que le serveur venait d'ouvrir une etape. Le journal d'audit
        // enregistrait des connexions reussies cote serveur, et l'ecran
        // affirmait le contraire.
        const donnees = reponse?.data

        // 1. Compte deja configure : il doit confirmer son secret TOTP.
        if (donnees?.jeton_challenge) {
          set({ challenge2fa: donnees.jeton_challenge, jetonEnrolement: null })
          return 'challenge'
        }

        // 2. Compte sans aucun secret : il doit s'enroler. Ce jeton ouvre la
        // preparation et l'activation, et ne vaut pas session.
        if (donnees?.jeton_enrolement) {
          set({ challenge2fa: null, jetonEnrolement: donnees.jeton_enrolement })
          return 'enrolement'
        }

        // 3. Session complete.
        if (donnees?.access_token && donnees?.refresh_token) {
          sessionVivante()
          set({
            token: donnees.access_token,
            refreshToken: donnees.refresh_token,
            challenge2fa: null,
            jetonEnrolement: null,
          })
          await get().chargerProfil()
          return 'ok'
        }

        // 4. 200 sans aucun jeton exploitable : ce n'est **pas** un refus
        // d'identifiants, et le dire serait faux. C'est une rupture de contrat
        // cote serveur, et elle doit se voir comme telle.
        throw new Error('Reponse du serveur inattendue : aucun jeton. Rechargez la page.')
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
    annulerEnrolement: () => set({ jetonEnrolement: null }),

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
    const { access_token, refresh_token } = reponse.data
    // Un 200 sans jeton n'est pas un renouvellement : c'est une rupture de contrat
    // cote serveur. Le traiter comme un succes ecrirait `token: undefined`, et
    // l'ecran semblerait connecte alors qu'aucune requete ne partirait plus.
    if (!access_token || !refresh_token) {
      throw new Error("Renouvellement refuse : le serveur n'a renvoye aucun jeton.")
    }
    useAuthStore.setState({
      token: access_token,
      // Le backend fait tourner le refresh token : l'ancien ne vaut plus rien.
      refreshToken: refresh_token,
    })
    return access_token
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