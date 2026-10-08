/**
 * Client HTTP unique du backoffice.
 *
 * Différences assumées avec l'application client :
 *
 * - **Un seul point d'entrée**, et il est **typé par l'OpenAPI**. Un paramètre
 *   écrit à la main devient une erreur de compilation, et non un 422 à
 *   l'exécution. C'est ce que la décision 7 achète : la classe de dérive
 *   « le frontend envoie un paramètre inexistant » devient impossible à écrire,
 *   là où elle suffisait de le constat��r.
 * - **Base URL vide en développement** : les appels partent en chemin relatif et
 *   le proxy Vite relaie. La requête reste same-origin, aucun CORS n'intervient,
 *   et le port du backend n'est connu que du proxy.
 */

/** Erreur normalisée : `code` = littéral backend. */
export class ApiError extends Error {
  code: string
  status: number
  details?: Record<string, unknown>

  constructor(message: string, code: string, status: number, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

const BASE = import.meta.env.VITE_API_URL ?? ''
const PREFIXE = '/api/v1'

let getToken: () => string | null = () => null
let setTokenProvider: (fn: () => string | null) => void = () => undefined

/** Branché par le store d'authentification : évite un cycle d'import. */
export function setTokenProviderExport(fn: () => string | null): void {
  setTokenProvider = fn
  getToken = fn
}

// ---------------------------------------------------------------------------
// Renouvellement et session morte
// ---------------------------------------------------------------------------

type Rafraichisseur = () => Promise<string | null>
let rafraichisseur: Rafraichisseur | null = null
let promesseRenouvellement: Promise<string | null> | null = null

type GestionnaireSessionMorte = () => void
let surSessionMorte: GestionnaireSessionMorte | null = null

export function setRafraichisseur(fn: Rafraichisseur | null): void {
  rafraichisseur = fn
}

export function setGestionnaireSessionMorte(fn: GestionnaireSessionMorte | null): void {
  surSessionMorte = fn
}

function onSessionMorte(): void {
  surSessionMorte?.()
}

/**
 * Renouvelle le jeton d'accès.
 *
 * **La déduplication n'est pas une optimisation ici.** Un tableau de bord émet
 * plusieurs requêtes en parallèle ; à l'expiration, elles reviennent toutes 401
 * ensemble. Le backend fait tourner le refresh token : sans promesse partagée,
 * six POST partent avec le même jeton, **un seul réussit et cinq sont refusés** —
 * et la session, parfaitement valide, paraît morte.
 */
async function renouvelerTokenAcces(): Promise<string | null> {
  if (!rafraichisseur) return null
  if (!promesseRenouvellement) {
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

// ---------------------------------------------------------------------------

export interface OptionsAppel {
  params?: Record<string, unknown>
  /** Ne remonte pas l'erreur en toast : l'appelant gère son propre état. */
  silencieux?: boolean
  signal?: AbortSignal
}

function buildQueryString(params?: Record<string, unknown>): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.append(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

async function request<T>(
  path: string,
  options: RequestInit & { silencieux?: boolean; _reessai?: boolean } = {},
): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const reponse = await fetch(`${BASE}${PREFIXE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  // 401 métier : le jeton a expiré. On renouvelle **une fois** puis on rejoue.
  // `_reessai` empêche la boucle ; `/platform/auth/*` est exclu car son 401
  // signifie « mauvais mot de passe » ou « code 2FA invalide », pas « jeton périmé ».
  if (reponse.status === 401 && !options._reessai && !path.startsWith('/platform/auth/')) {
    const nouveau = await renouvelerTokenAcces()
    if (nouveau) {
      return request<T>(path, { ...options, _reessai: true })
    }
    // Session morte : on purge et on ne **rejoue pas**. Rejouer avec le jeton
    // mort produit une cascade de 401 puis de 403 qui ne parlent d'aucune
    // permission réelle.
    onSessionMorte()
  }

  let corps: unknown = null
  try {
    corps = await reponse.json()
  } catch {
    /* 204 ou corps non JSON */
  }

  if (!reponse.ok) {
    const erreur = (
      corps as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null
    )?.error
    const message = erreur?.message ?? `Erreur serveur (${reponse.status})`
    const code = erreur?.code ?? 'HTTP_ERROR'
    throw new ApiError(message, code, reponse.status, erreur?.details)
  }

  return corps as T
}

/** Enveloppe de liste paginée. Le contrat est le même partout. */
export interface MetaPagination {
  page: number
  limit: number
  total_records: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface PageReponse<T> {
  success: boolean
  items: T[]
  meta: MetaPagination
}

export interface ApiReponse<T> {
  success: boolean
  message?: string | null
  data: T
}

export const api = {
  get: <T,>(path: string, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'GET',
      signal: options?.signal,
      silencieux: options?.silencieux,
    })
  },
  post: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: options?.signal,
      silencieux: options?.silencieux,
    })
  },
  patch: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'PATCH',
      body: JSON.stringify(body ?? {}),
      signal: options?.signal,
      silencieux: options?.silencieux,
    })
  },
  delete: <T,>(path: string, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, { method: 'DELETE', signal: options?.signal })
  },
}

/** `setTokenProvider` est exporté pour que le store s'inscrive sans cycle. */
export { setTokenProvider }