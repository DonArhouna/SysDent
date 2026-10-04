/**
 * Client HTTP de l'API SysDent Pro.
 *
 * Contrats backend (voir Backend/COMMANDS.md) :
 *  - succès : `{ success, message?, data }` (enveloppe `APIResponse`) ;
 *  - liste  : `{ success, items, meta }` (enveloppe `PaginatedResponse`) ;
 *  - erreur : `{ error: { code, message, details? } }` (RFC 7807 simplifié).
 *
 * Base URL : en développement, elle est **vide**. Les appels partent donc en
 * chemin relatif (`/api/v1/…`) et le proxy Vite les relaie vers FastAPI : la
 * requête reste same-origin, aucun CORS n'intervient, et le port du backend
 * n'est connu que du proxy.
 *
 * `VITE_PROXY_API` n'est PAS reprise ici : c'est la *cible* du proxy, celle que
 * `vite.config.ts` consomme. La réutiliser comme base côté navigateur faisait
 * appeler `http://127.0.0.1:8003/api/v1/…` en absolu, donc en cross-origin —
 * et le préflight se faisait refuser en 400 par le middleware CORS, dont la
 * liste ne contient que 5173 alors que Vite bascule sur 5174 dès que 5173 est
 * occupé. Résultat : toute l'application affichait « API injoignable » alors
 * que le backend répondait 200.
 *
 * `VITE_API_URL` reste le seul moyen de viser une autre origine : c'est le cas
 * d'un déploiement où le SPA et l'API ne partagent pas le domaine. Le CORS doit
 * alors être configuré côté backend pour cette origine.
 */

import { toast } from '@/stores/toast-store'

const BASE = import.meta.env.VITE_API_URL ?? ''

/** Erreur normalisée : `code` = littéral backend (ex: PAIEMENT_TROP_ELEVE). */
export class ApiError extends Error {
  code: string
  status: number
  details?: Record<string, unknown>

  constructor(
    message: string,
    code: string,
    status: number,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

let getToken: () => string | null = () => null

/** Branché par le store d'authentification (évite une dépendance circulaire). */
export function setTokenProvider(provider: () => string | null) {
  getToken = provider
}

function buildQueryString(params?: Record<string, unknown>): string {
  if (!params) return ''
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value))
    }
  }
  const qs = searchParams.toString()
  return qs ? `?${qs}` : ''
}

/**
 * Options communes aux appels.
 *
 * `silencieux` supprime le toast d'erreur. À réserver aux endpoints dont
 * l'absence est connue et assumée — le module Stock tant qu'il n'est pas livré.
 * La page affiche alors son propre état « module non disponible » : un toast
 * « HTTP_404 / Not Found » par requête y était redondant, exposait un détail
 * technique à l'utilisateur, et venait masquer le vrai message d'état.
 */
export interface OptionsAppel {
  params?: Record<string, unknown>
  /** Ne remonte pas l'erreur en toast : l'appelant gère son propre état. */
  silencieux?: boolean
}

// ---------------------------------------------------------------------------
// Renouvellement de session
// ---------------------------------------------------------------------------

/**
 * Le jeton d'accès expire au bout de `ACCESS_TOKEN_EXPIRE_MINUTES` (15 min).
 * Sans appel à `/auth/refresh`, l'application devenait inutilisable au bout de
 * quinze minutes et l'utilisateur devait se reconnecter à la main.
 *
 * ## Pourquoi la déduplication est indispensable
 *
 * Le backend fait tourner le refresh token : `renouveller_session` marque
 * l'ancien `jti` comme révoqué dès la première rotation et refuse ensuite toute
 * réutilisation (`refresh_token_revoque_utilise`).
 *
 * Or le tableau de bord émet six requêtes en parallèle. À l'expiration, les six
 * reviennent 401 ensemble. Sans déduplication, six POST `/auth/refresh` partiraient
 * avec le même refresh token : **un seul réussit, les cinq autres sont refusés** —
 * et les requêtes correspondantes échouent malgré une session parfaitement valide.
 *
 * `promesseRenouvellement` partage donc une seule promesse entre tous les
 * appelants concurrents.
 */
let promesseRenouvellement: Promise<string | null> | null = null

/** Procédure de renouvellement, injectée par le store (dépendance circulaire). */
type Rafraichisseur = () => Promise<string | null>
let rafraichisseur: Rafraichisseur | null = null

/**
 * Signal de session définitivement morte.
 *
 * Injecté comme leRafraichisseur : `api.ts` ne peut pas importer le store,
 * qui l'importe lui-même. Le store s'inscrit ici une fois au chargement.
 */
type GestionnaireSessionMorte = () => void
let surSessionMorte: GestionnaireSessionMorte | null = null

/** Enregistre la procédure de renouvellement (une fois, au chargement du module). */
export function setRafraichisseur(fn: Rafraichisseur | null): void {
  rafraichisseur = fn
}

/** Enregistre le gestionnaire de session morte. */
export function setGestionnaireSessionMorte(fn: GestionnaireSessionMorte | null): void {
  surSessionMorte = fn
}

function onSessionMorte(): void {
  surSessionMorte?.()
}

/**
 * Renouvelle le jeton d'accès. Retourne le nouveau jeton, ou `null` si la
 * session est définitivement morte — il faut alors reconnecter.
 */
async function renouvelerTokenAcces(): Promise<string | null> {
  if (!rafraichisseur) return null
  if (!promesseRenouvellement) {
    // `finally` libère la référence une fois la promesse réglée : les appelants
    // concomitants ont tous reçu la MÊME promesse ; les suivants déclencheront
    // un nouvel essai — comportement voulu après un échec.
    promesseRenouvellement = rafraichisseur().finally(() => {
      promesseRenouvellement = null
    })
  }
  try {
    return await promesseRenouvellement
  } catch {
    return null
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { silencieux?: boolean; _reessai?: boolean } = {},
): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const reponse = await fetch(`${BASE}/api/v1${path}`, {
    ...options,
    headers,
    credentials: 'include', // cookie de session posé par le backend
  })

  // 401 sur une requête métier : le jeton a expiré. On renouvelle UNE fois puis
  // on rejoue la requête. `_reessai` empêche la boucle infinie ; les routes
  // d'authentification sont exclues (leur 401 signifie « mauvais mot de passe »).
  if (reponse.status === 401 && !options._reessai && !path.startsWith('/auth/')) {
    const nouveau = await renouvelerTokenAcces()
    if (nouveau) {
      return request<T>(path, { ...options, _reessai: true })
    }
    // Session morte : on vide l'état, `AppShell` redirigera vers /login.
    onSessionMorte()
  }

  let corps: unknown = null
  try {
    corps = await reponse.json()
  } catch {
    /* réponse vide (204) ou corps non JSON */
  }

  if (!reponse.ok) {
    const erreur = (
      corps as
        | { error?: { code?: string; message?: string; details?: Record<string, unknown> } }
        | null
    )?.error
    const message = erreur?.message ?? `Erreur serveur (${reponse.status})`
    const code = erreur?.code ?? 'HTTP_ERROR'
    
    // Notification toast discrète pour informer l'utilisateur de l'échec.
    // Le 401 reste muet : il a déjà été traité par le renouvellement de session
    // ci-dessus ; une alerte « session expirée » ne ferait que doubler le
    // message d'erreur que l'utilisateur va lire en restant sur la page.
    if (reponse.status !== 401 && !options.silencieux) {
      toast.error(message, code !== 'HTTP_ERROR' ? code : undefined)
    }

    throw new ApiError(
      message,
      code,
      reponse.status,
      erreur?.details,
    )
  }

  return corps as T
}

/** Enveloppe de succès standard `APIResponse[T]`. */
export interface ApiReponse<T> {
  success: boolean
  message?: string | null
  data: T
}

/** Enveloppe de liste `PaginatedResponse[T]`. */
export interface PageReponse<T> {
  success: boolean
  items: T[]
  meta: {
    page: number
    limit: number
    total_records: number
    total_pages: number
    has_next: boolean
    has_previous: boolean
  }
}

export type APIResponse<T> = ApiReponse<T>
export type PaginatedResponse<T> = PageReponse<T>

export const api = {
  get: <T,>(path: string, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, { method: 'GET', silencieux: options?.silencieux })
  },
  post: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
      silencieux: options?.silencieux,
    })
  },
  patch: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'PATCH',
      body: body === undefined ? undefined : JSON.stringify(body),
      silencieux: options?.silencieux,
    })
  },
  put: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'PUT',
      body: JSON.stringify(body ?? {}),
      silencieux: options?.silencieux,
    })
  },
  delete: <T,>(path: string, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, { method: 'DELETE', silencieux: options?.silencieux })
  },
}
