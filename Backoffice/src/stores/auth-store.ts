import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  api,
  setTokenProvider,
  setRafraichisseur,
  setGestionnaireSessionMorte,
  type ApiReponse,
} from '@/lib/api'
import type { CorpsDe, ReponseDe } from '@/lib/api'
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
  /**
   * Second facteur actif mais **aucun code de secours utilisable** : compte
   * préexistant sans codes (état legacy) ou liste épuisée.
   *
   * C'est lui qui pilote la bannière du tableau de bord : un téléphone perdu
   * sans codes ne laisse aucune voie de recours.
   */
  codes_secours_a_regenerer?: boolean
}

/**
 * Les jetons sont **absents** selon le cas, jamais tous presents.
 *
 * Ce type les declarait obligatoires, alors que le backend n'ouvre volontairement
 * aucune session avant la confirmation du second facteur. Un type qui promet un
 * champ que le serveur n'envoie pas ne protege de rien : il fait ecrire le code
 * appelant comme si le champ etait la.
 */
/**
 * Les trois issues du login, **tires du schema**.
 *
 * Une interface ecrite a la main promettait `access_token` obligatoire la ou le
 * serveur ne l'envoie jamais, et le type validait donc l'inverse de la realite.
 * Ici, un champ absent du schema est une erreur de compilation : le defaut que
 * nous avons racks caute ne peut pas revenir par la meme porte.
 */
type CheminLogin = '/api/v1/platform/auth/login'
type ReponseLogin = ReponseDe<CheminLogin, 'post'>

/** Champs presents quelle que soit l'issue. */
interface ReponseJeton extends Partial<NonNullable<ReponseLogin['data']>> {}

/**
 * Formes OpenAPI, relevees dans `openapi.json` sur les schemas
 * `Activation2FAResponse`, `Activer2FARequest` et `Enrolement2FAResponse`.
 *
 * Le nom du champ de la requete est celui du backend : `code`, comme dans
 * `Activer2FARequest.code`. Un `code_2fa` aurait ete refuse en 422, et rien dans
 * un appel enveloppe par `api.post` ne l'aurait signale.
 */
/** `/platform/auth/2fa/preparation`, tel que le backend le repond. */
type Preparation2FA = NonNullable<
  ReponseDe<'/api/v1/platform/auth/2fa/preparation', 'get'>['data']
>

/** Reponse de `/platform/auth/2fa/activation`, tiree du schema. */
type Activation = ReponseDe<'/api/v1/platform/auth/2fa/activation', 'post'>

/** Reponse de `/platform/auth/2fa/activation`. */
interface EnrolementTermine extends NonNullable<Activation['data']> {
  /**
   * Codes de secours, **une seule fois**.
   *
   * Ni la base ni le journal ne les conservent en clair. Perdus, ils imposent de
   * repasser par un operateur.
   */
  codes_secours: string[]
}

/** Reponse de `/platform/auth/2fa/codes-secours/regenerer`, tiree du schema. */
type CodesRegeneres = NonNullable<
  ReponseDe<'/api/v1/platform/auth/2fa/codes-secours/regenerer', 'post'>['data']
>

/**
 * Corps de la regeneration, **tire du schema** : `code` et `motif`, rien d'autre.
 *
 * Un champ ecrit a la main mais absent du backend donnerait un 422 sans que
 * rien, ni au compilateur ni a l'ecran, ne le signale.
 */
export type CorpsRegeneration = CorpsDe<
  '/api/v1/platform/auth/2fa/codes-secours/regenerer',
  'post'
>

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
  /** Preparation affichee a l'ecran. `null` tant que le QR n'a pas ete demande. */
  preparation2fa: Preparation2FA | null
  preparerEnrolement: () => Promise<void>
  activerEnrolement: (code: string) => Promise<string[]>
  /**
   * Remplace les codes de secours, apres une session ouverte.
   *
   * Le backend exige en plus un TOTP valide sur le secret **actif** et un motif,
   * consigne au journal : une session seule ne suffit pas. Renvoie les dix
   * nouveaux codes, a afficher une seule fois.
   */
  regenererCodesSecours: (code: string, motif: string) => Promise<string[]>
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
        preparation2fa: null,

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
    annulerEnrolement: () => set({ jetonEnrolement: null, preparation2fa: null }),

    /**
     * Demande le secret TOTP au serveur.
     *
     * Le jeton d'enrolement ouvre cette route et **l'activation** : rien d'autre.
     * Il ne vaut pas session, et le backend le consomme a l'activation.
     *
     * Le secret transite par l'etat du store, donc par la **memoire seule** :
     * `preparation2fa` ne fait pas partie du `partialize`, il disparait a la
     * fermeture de l'onglet. Persiste, il resterait lisible sur le poste et
     * permettrait de fabriquer un code TOTP valide sans jamais l'avoir vu scanner.
     */
    preparerEnrolement: async () => {
      const jeton = get().jetonEnrolement
      if (!jeton) throw new Error("Session de connexion expiree.")
      // `bearer` explicite : ce jeton d'etape n'est pas une session, et il n'y a
      // aucun jeton de session a prendre. Sans lui, la requete partirait sans
      // en-tete et le backend reponderait « jeton invalide ».
      const reponse = await api.get<ApiReponse<Preparation2FA>>('/platform/auth/2fa/preparation', {
        bearer: jeton,
      })
      set({ preparation2fa: reponse.data })
    },

    /**
     * Confirme le code TOTP : active le second facteur, rend les codes de secours
     * **une seule fois**, et ouvre la session.
     *
     * Les codes sont renvoyes a l'appelant plutot que stockes : personne ne doit
     * pouvoir les relire apres coup depuis le store, ni les retrouver apres rechargement.
     */
    activerEnrolement: async (code) => {
      const jeton = get().jetonEnrolement
      if (!jeton) throw new Error("Session de connexion expiree.")
      // `bearer` va dans le **troisieme** argument (les options), pas dans le
      // corps. `api.post(chemin, corps, options)` : place dans le corps, le jeton
      // partait dans le JSON et l en-tete `Authorization` n etait jamais pose.
      // La preparation, elle, fonctionnait : son second argument *est* les
      // options. D ou un QR code visible puis une activation refusee.
      const reponse = await api.post<ApiReponse<EnrolementTermine>>(
        '/platform/auth/2fa/activation',
        { code },
        { bearer: jeton },
      )
      const { codes_secours, ...jetons } = reponse.data
      if (!jetons.access_token || !jetons.refresh_token) {
        // L'activation a reussi cote serveur : impossible d'ecrire un etat
        // « connecte » sans jeton. Le dire, plutot que laisser l'ecran pretendre.
        throw new Error("Activation effectuee, mais le serveur n a renvoye aucune session.")
      }
      sessionVivante()
      set({
        token: jetons.access_token,
        refreshToken: jetons.refresh_token,
        // Le jeton d'enrolement a ete consomme par le serveur : le garder
        // permettrait de rejouer une activation, et de trailer un secret dans l'etat.
        jetonEnrolement: null,
        preparation2fa: null,
        challenge2fa: null,
      })
      await get().chargerProfil()
      return codes_secours
    },

    /**
     * Regenere les codes de secours : session + TOTP actif + motif.
     *
     * Les dix nouveaux codes reviennent a l'appelant et **jamais dans le store** —
     * comme a l'activation, personne ne doit pouvoir les relire apres coup. Le
     * profil est relu juste apres : le serveur a repasse
     * `codes_secours_a_regenerer` a `false`, et une banniere qui survivrait a la
     * regeneration dirait un mensonge a l'ecran.
     */
    regenererCodesSecours: async (code, motif) => {
      // `corps` est tape par le schema ouvert : un champ absent du backend
      // n'est pas un 422 silencieux, c'est une erreur de compilation ici.
      const corps: CorpsRegeneration = { code, motif }
      const reponse = await api.post<ApiReponse<CodesRegeneres>>(
        '/platform/auth/2fa/codes-secours/regenerer',
        corps,
      )
      await get().chargerProfil()
      return reponse.data.codes_secours
    },

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
      /**
     * Ne persiste **que** ce qui survit legitimement a une fermeture d'onglet.
     *
     * Ni `challenge2fa` ni `jetonEnrolement` : ce sont des jetons d'etape, a
     * usage unique et de courte duree. Persistes, ils rouvrent l'ecran sur une
     * etape **que l'utilisateur ne peut pas terminer** - le jeton est deja
     * consomme ou expire, et aucun code ne passera jamais. Concretement :
     * l'ecran s'ouvrait sur « Verification en deux etapes » sans qu'aucune
     * connexion ait eu lieu, et le compte paraissait bloque alors que les
     * identifiants etaient corrects.
     *
     * C'est aussi un porte-credential : un jeton d'etape dans `localStorage`
     * reste lisible sur le poste apres la fin de la session.
     */
    partialize: (etat) => ({
      token: etat.token,
      refreshToken: etat.refreshToken,
      profil: etat.profil,
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