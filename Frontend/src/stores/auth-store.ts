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
 * Attention : **Correctif recommandé côté backend** : déposer aussi un cookie
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
import { useCabinetStore } from '@/stores/cabinet-store'

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
  /** Nom du cabinet, pour la barre du haut — disponible meme sans `CABINETS:READ`. */
  cabinet_nom?: string | null
  /** Logo du cabinet (chemin relatif à l'API), s'il en a un. */
  cabinet_logo_url?: string | null
  /** Nom de la société (console), distinct de `cabinet_nom` qui est le site. */
  societe_nom?: string | null
  /** Site de rattachement de l'utilisateur, s'il en a un. */
  cabinet_id?: string | null
  /** Double authentification active sur ce compte. */
  deux_facteurs?: boolean
  /** Méthodes utilisables : `totp` (application), `email`. */
  methodes_2fa?: string[]
  /** Obligatoire pour ce rôle : « Mon compte » ne propose pas de s'en passer. */
  deux_facteurs_obligatoire?: boolean
}

/**
 * Issue d'une connexion ou d'une étape franchie (`LoginEtapeResponse`).
 *
 * `session` : connecté. Sinon, une étape reste à franchir, portée par
 * `jeton_etape` (usage unique, 10 minutes, jamais une session).
 */
export type NomEtape = 'session' | 'changement_mot_de_passe' | 'deux_facteurs' | 'enrolement_2fa'

export interface ReponseEtape {
  etape: NomEtape
  access_token?: string | null
  refresh_token?: string | null
  jeton_etape?: string | null
  methodes?: string[]
  deux_facteurs_recommande?: boolean
  codes_secours?: string[] | null
}

/** Étape en cours, tenue en mémoire seulement (jamais persistée). */
export interface EtapeConnexion {
  etape: Exclude<NomEtape, 'session'>
  jeton: string
  methodes: string[]
}

export interface EnvoiCode {
  destinataire: string
  expiration_secondes: number
}

export interface PreparationTotp {
  secret: string
  uri: string
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
  /** Étape de connexion en cours ; `null` hors connexion. Non persistée. */
  etapeConnexion: EtapeConnexion | null
  /**
   * Codes de secours qui viennent d'être émis, à montrer UNE fois avant de
   * quitter l'écran de connexion. Placés ici AVANT l'ouverture de la session :
   * sinon la page voit la session, redirige, et les codes sont perdus.
   * Mémoire seule, jamais persistés.
   */
  codesSecoursAAfficher: string[] | null
  oublierCodesSecours: () => void
  /** Renvoie l'étape suivante, ou `session` si l'utilisateur est connecté. */
  connexion: (email: string, password: string) => Promise<NomEtape>
  /** Remplace le mot de passe temporaire. */
  changerMotDePasseInitial: (nouveau: string) => Promise<NomEtape>
  /** Code à 6 chiffres envoyé à l'adresse du compte, pour l'étape en cours. */
  envoyerCodeEtape: () => Promise<EnvoiCode>
  /** Code de l'application, code e-mail ou code de secours. */
  validerCodeEtape: (code: string) => Promise<NomEtape>
  /** QR code de la configuration obligatoire. */
  preparerTotpEtape: () => Promise<PreparationTotp>
  /** Active la 2FA pendant la connexion ; les codes vont dans `codesSecoursAAfficher`. */
  activer2faEtape: (methode: 'totp' | 'email', code: string) => Promise<void>
  annulerEtape: () => void
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
      etapeConnexion: null,
      codesSecoursAAfficher: null,

      oublierCodesSecours: () => set({ codesSecoursAAfficher: null }),

      connexion: async (email, password) => {
        const reponse = await api.post<ApiReponse<ReponseEtape>>('/auth/login', {
          email,
          password,
        })
        return appliquerEtape(reponse.data)
      },

      changerMotDePasseInitial: async (nouveau) => {
        const reponse = await api.post<ApiReponse<ReponseEtape>>('/auth/etape/mot-de-passe', {
          jeton_etape: jetonEtape(),
          nouveau,
        })
        return appliquerEtape(reponse.data)
      },

      envoyerCodeEtape: async () => {
        const reponse = await api.post<ApiReponse<EnvoiCode>>('/auth/etape/code-email', {
          jeton_etape: jetonEtape(),
        })
        return reponse.data
      },

      validerCodeEtape: async (code) => {
        const reponse = await api.post<ApiReponse<ReponseEtape>>('/auth/etape/2fa', {
          jeton_etape: jetonEtape(),
          code,
        })
        return appliquerEtape(reponse.data)
      },

      preparerTotpEtape: async () => {
        const reponse = await api.post<ApiReponse<PreparationTotp>>('/auth/etape/2fa/preparation', {
          jeton_etape: jetonEtape(),
        })
        return reponse.data
      },

      activer2faEtape: async (methode, code) => {
        const reponse = await api.post<ApiReponse<ReponseEtape>>('/auth/etape/2fa/activation', {
          jeton_etape: jetonEtape(),
          methode,
          code,
        })
        // Codes d'abord, session ensuite : voir `codesSecoursAAfficher`. Ils
        // ne sont pas persistés et l'écran les efface dès leur confirmation.
        set({ codesSecoursAAfficher: reponse.data.codes_secours ?? [] })
        await appliquerEtape({ ...reponse.data, codes_secours: null })
      },

      annulerEtape: () => set({ etapeConnexion: null }),

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
        purgerSession(true, true)
      },
    }),
    {
      name: 'sysdent-auth',
      // `etapeConnexion` n'est volontairement PAS persistée : un jeton d'étape
      // dans le stockage du navigateur survivrait à la fermeture de l'onglet.
      partialize: (etat) => ({
        token: etat.token,
        refreshToken: etat.refreshToken,
        profil: etat.profil,
      }),
    },
  ),
)

/** Purgeur enregistre par l'application : vide le cache et renvoie a la connexion. */
function jetonEtape(): string {
  const etape = useAuthStore.getState().etapeConnexion
  if (!etape) throw new Error('Session de connexion expirée. Reprenez depuis le début.')
  return etape.jeton
}

/**
 * Applique l'issue d'une étape : session ouverte, ou étape suivante.
 *
 * C'est le seul endroit qui écrit un jeton de session dans le store : une
 * réponse sans `access_token` ne connecte jamais.
 */
async function appliquerEtape(donnees: ReponseEtape): Promise<NomEtape> {
  if (donnees.etape === 'session') {
    if (!donnees.access_token || !donnees.refresh_token) {
      throw new Error('Réponse du serveur inattendue : aucune session. Rechargez la page.')
    }
    sessionVivante()
    useAuthStore.setState({
      token: donnees.access_token,
      refreshToken: donnees.refresh_token,
      profil: null,
      etapeConnexion: null,
    })
    // Profil complet (rôles, permissions) : c'est lui qui alimente le RBAC.
    await useAuthStore.getState().chargerProfil()
    return 'session'
  }
  if (!donnees.jeton_etape) throw new Error('Réponse du serveur inattendue. Rechargez la page.')
  useAuthStore.setState({
    etapeConnexion: { etape: donnees.etape, jeton: donnees.jeton_etape, methodes: donnees.methodes ?? [] },
  })
  return donnees.etape
}

type PurgeurSession = () => void
let purgeurSession: PurgeurSession | null = null

/**
 * La session a-t-elle déjà été purgée ?
 *
 * Un verrou « purge en cours » ne suffit pas, et c'est ce que le premier correctif
 * avait fait : les six requêtes du tableau de bord ne reviennent pas 401 au même
 * instant mais **échelonnées**, chacune après la résolution de la promesse de
 * renouvellement partagée. La première purge se termine et libère le verrou
 * avant que la suivante n'arrive — six purges, six `client.clear()`, six
 * navigations vers `/login`.
 *
 * L'état correct est « cette session est déjà morte », pas « une purge est en
 * cours ». Il est remis à zéro quand une session **vivante** est créée
 * (connexion ou renouvellement réussi), donc une déconnexion ultérieure purge
 * bien de nouveau.
 */
let sessionVidee = false

/**
 * Enregistre le purgeur de session.
 *
 * Le store ne peut pas importer le client React Query — cela créerait un cycle
 * avec `lib/api`. On enregistre donc la procédure depuis le provider, comme pour
 * le renouvellement du jeton.
 */
export function setPurgeurSession(fn: PurgeurSession | null): void {
  purgeurSession = fn
}

/** Marque une session vivante : les purges suivantes redeviennent effectives. */
function sessionVivante(): void {
  sessionVidee = false
}

/** `true` si la session courante a déjà été purgée (évite de purger six fois). */
export function sessionDejaVidee(): boolean {
  return sessionVidee
}

/**
 * Vide le cache applicatif, le site mémorisé, et renvoie à l'écran de connexion.
 *
 * Sans ce nettoyage, deux choses se produisent :
 *
 * - les requêtes déjà en vol continuent d'être lancées avec un jeton mort, ce
 *   qui produit une cascade de 401 puis de 403 **sans rapport avec les
 *   permissions réelles** : l'utilisateur cherche un problème de droits qui
 *   n'existe pas ;
 * - les réponses en cache restent en mémoire. Sur un poste partagé, la personne
 *   qui se connecte ensuite voit les données de la précédente avant même que la
 *   première requête ne revienne.
 *
 * `diffuse` évite la boucle entre onglets : celui qui reçoit le message purge,
 * mais ne le repart pas.
 */
/**
 * La fermeture vient-elle d'une **décision** de l'utilisateur ?
 *
 * Une session qui expire et une déconnexion clicked aboutissent toutes deux à
 * `/login`. Mais elles ne doivent pas se comporter pareil : après une
 * déconnexion, on veut retrouver l'application à sa page d'accueil ; après une
 * expiration, on veut retrouver la page qu'on consultationnait.
 *
 * Sans cette distinction, `AppShell` transmettait `depuis` dans les deux cas, et
 * se reconnecter ramenait à l'ancienne route au lieu du tableau de bord.
 */
let sessionFermeeVolontairement = false

/** La session a-t-elle été fermée par l'utilisateur, et non par expiration ? */
export function sessionFermeeVolontairementVraiment(): boolean {
  return sessionFermeeVolontairement
}

/** Oublie la fermeture volontaire : une nouvelle session ne l'est pas. */
export function oublierFermetureVolontaire(): void {
  sessionFermeeVolontairement = false
}

function purgerSession(diffuse = true, volontaire = false): void {
  if (volontaire) sessionFermeeVolontairement = true
  if (sessionVidee) return
  sessionVidee = true

  useAuthStore.setState({ token: null, refreshToken: null, profil: null })

  // Le site mémorisé est un identifiant de tenant. Le garder ferait porter les
  // requêtes du second utilisateur vers le site du premier : le backend refuse
  // (l'isolation tient), mais l'application demanderait malgré tout une donnée
  // qui n'est pas la sienne, et afficherait une erreur incompréhensible.
  useCabinetStore.getState().vider()

  try {
    if (diffuse) diffuserPurgeSession()
    purgeurSession?.()
  } catch {
    // Un cache non vidé ne doit jamais empêcher la déconnexion.
  }
}

/** Nom du canal : un même nom = même canal, dans tout le navigateur. */
const CANAL_SESSION = 'sysdent-session'

/**
 * Propagation de la purge aux autres onglets.
 *
 * Le `localStorage` partagé ne suffit pas : le store d'un onglet déjà chargé
 * garde son état **en mémoire**. Sans ce canal, un onglet resté ouvert continue
 * d'appeler l'API avec un jeton révoqué côté serveur — l'utilisateur voit des
 * erreurs sur une fenêtre qu'il croit encore valide.
 *
 * `BroadcastChannel` est disponible dans tous les navigateurs d'usage depuis
 * 2022. Son absence n'empêche pas la déconnexion locale : on se contente de ne
 * pas propager.
 */
function diffuserPurgeSession(): void {
  if (typeof BroadcastChannel === 'undefined') return
  try {
    const canal = new BroadcastChannel(CANAL_SESSION)
    canal.postMessage('session-purge')
    canal.close()
  } catch {
    // Canal indisponible : la purge locale a déjà eu lieu, c'est l'essentiel.
  }
}

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
    // La session redevient vivante : une purge ulterieure doit avoir lieu.
    sessionVivante()
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
  // Une session morte doit vider le cache comme une deconnexion : les
  // requetes en vol repartiraient sinon avec un jeton invalide.
  purgerSession()
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