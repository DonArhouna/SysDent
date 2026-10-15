import type { paths } from '@/lib/openapi'
/**
 * Client HTTP unique du backoffice.
 *
 * Différences assumées avec l'application client :
 *
 * - **Un seul point d'entrée**, et il est **typé par l'OpenAPI**. Un paramètre
 *   écrit à la main devient une erreur de compilation, et non un 422 à
 *   l'exécution. C'est ce que la décision 7 achète : la classe de dérive
 *   « le frontend envoie un paramètre inexistant » devient impossible à écrire,
 *   là où elle suffisait de le constater.
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

/**
 * Client type par l'OpenAPI.
 *
 * `ReponseDe<'/chemin'>` est calcule a partir de `src/lib/openapi.d.ts`, lui-meme
 * genere depuis `openapi.json`. Un nom de champ ecrit ici mais absent du schema
 * devient donc une **erreur de compilation**, et non un `undefined` lu comme
 * absent a l'execution.
 *
 * C'est ce que la regle du projet exigeait - « noms de champs verifies des deux
 * cotes dans le meme commit » - et ce que le client entierement ecrit a la main
 * ne garantissait pas : `ReponseJeton` declarait `access_token` obligatoire la
 * ou le serveur ne l'envoie jamais, et le type validait l'inverse de la realite.
 */
export type Chemins = keyof paths

type ReponseDeMethode<
  P extends Chemins,
  M extends 'get' | 'post',
> = paths[P] extends { [K in M]: { responses: infer R } } ? R : never

/** Corps JSON d'une reponse 200, pour un chemin et une methode donnes. */
export type ReponseDe<P extends Chemins, M extends 'get' | 'post' = 'get'> =
  ReponseDeMethode<P, M> extends {
    200: { content: { 'application/json': infer Corps } }
  }
    ? Corps
    : never

/** Corps d'une requete (JSON), pour un chemin et une methode donnes. */
export type CorpsDe<P extends Chemins, M extends 'get' | 'post' = 'post'> =
  paths[P] extends { [K in M]: { requestBody: { content: { 'application/json': infer C } } } }
    ? C
    : never

const BASE = import.meta.env.VITE_API_URL ?? ''
const PREFIXE = '/api/v1'

let getToken: () => string | null = () => null

/**
 * Branché par le store d'authentification : évite un cycle d'import.
 *
 * C'était une variable initialisée à une fonction vide : l'appel du store ne
 * branchait donc rien, et aucune requête ne portait le jeton - seul le cookie
 * `platform_access_token` faisait tenir la session.
 */
function setTokenProvider(fn: () => string | null): void {
  getToken = fn
}

/** Alias historique, utilisé par les tests. */
export const setTokenProviderExport = setTokenProvider

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
  /**
   * Jeton `Bearer` a employer pour CET appel, par-dessus la session.
   *
   * L'enrolement 2FA est le cas qui le necessite : il passe par un jeton
   * d'etape, pas par une session - il n'y a donc **aucun jeton de session** a
   * prendre. S'appuyer sur cette absence serait fragile : des la qu'un Super
   * Admin dispose d'une session, l'en-tete de session ecraserait en silence le
   * jeton d'etape, et la requete partirait avec le mauvais identifiant, sans
   * erreur visible.
   */
  bearer?: string
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
  options: RequestInit & { silencieux?: boolean; _reessai?: boolean; bearer?: string } = {},
): Promise<T> {
  const { bearer, ...reste } = options
  const token = bearer ?? getToken()
  const headers = new Headers(reste.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const reponse = await fetch(`${BASE}${PREFIXE}${path}`, {
    ...reste,
    headers,
    credentials: 'include',
  })

  // 401 métier : le jeton a expiré. On renouvelle **une fois** puis on rejoue.
  // `_reessai` empêche la boucle ; `/platform/auth/*` est exclu car son 401
  // signifie « mauvais mot de passe » ou « code 2FA invalide », pas « jeton périmé ».
  if (reponse.status === 401 && !options._reessai && !path.startsWith('/platform/auth/')) {
    const nouveau = await renouvelerTokenAcces()
    if (nouveau) {
      return request<T>(path, { ...reste, _reessai: true, bearer })
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
      bearer: options?.bearer,
    })
  },
  post: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: options?.signal,
      silencieux: options?.silencieux,
      bearer: options?.bearer,
    })
  },
  patch: <T,>(path: string, body?: unknown, options?: OptionsAppel) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'PATCH',
      body: JSON.stringify(body ?? {}),
      signal: options?.signal,
      silencieux: options?.silencieux,
      bearer: options?.bearer,
    })
  },
  /** `body` : certaines suppressions exigent un motif et une confirmation. */
  delete: <T,>(path: string, options?: OptionsAppel & { body?: unknown }) => {
    const qs = buildQueryString(options?.params)
    return request<T>(`${path}${qs}`, {
      method: 'DELETE',
      body: options?.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options?.signal,
      silencieux: options?.silencieux,
      bearer: options?.bearer,
    })
  },
}

/** `setTokenProvider` est exporté pour que le store s'inscrive sans cycle. */
/**
 * Téléchargement authentifié d'un fichier (export CSV…).
 *
 * `api.get` lit du JSON ; un export renvoie un fichier. Le jeton part dans
 * l'en-tête comme pour toute requête - jamais dans l'URL, où il finirait dans
 * l'historique et les journaux du serveur.
 */
export async function telecharger(path: string, nomFichier: string, params?: Record<string, unknown>): Promise<void> {
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const reponse = await fetch(`${BASE}${PREFIXE}${path}${buildQueryString(params)}`, {
    headers,
    credentials: 'include',
  })
  if (!reponse.ok) {
    let message = `Export impossible (${reponse.status})`
    try {
      const corps = (await reponse.json()) as { error?: { message?: string } }
      message = corps.error?.message ?? message
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(message, 'EXPORT_ECHOUE', reponse.status)
  }
  const blob = await reponse.blob()
  const url = URL.createObjectURL(blob)
  const lien = document.createElement('a')
  lien.href = url
  lien.download = nomFichier
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  URL.revokeObjectURL(url)
}

/**
 * Adresse complète d'une ressource servie par l'API (logo…), à partir du chemin
 * relatif qu'elle renvoie (`/api/v1/logos/…`). En développement le proxy de
 * Vite suffit ; en production l'API peut être sur un autre domaine.
 */
export function urlRessource(chemin: string | null | undefined): string | undefined {
  if (!chemin) return undefined
  return /^https?:\/\//.test(chemin) ? chemin : `${BASE}${chemin}`
}

/**
 * Envoi d'un fichier (`multipart/form-data`). `request` impose du JSON :
 * ici le navigateur pose lui-même l'en-tête et la frontière du formulaire.
 */
export async function envoyerFichier<T>(path: string, champ: string, fichier: File): Promise<T> {
  const donnees = new FormData()
  donnees.append(champ, fichier)
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const reponse = await fetch(`${BASE}${PREFIXE}${path}`, { method: 'POST', body: donnees, headers, credentials: 'include' })
  let corps: unknown = null
  try {
    corps = await reponse.json()
  } catch {
    /* corps non JSON */
  }
  if (!reponse.ok) {
    const erreur = (corps as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)?.error
    throw new ApiError(erreur?.message ?? `Envoi impossible (${reponse.status})`, erreur?.code ?? 'HTTP_ERROR', reponse.status, erreur?.details)
  }
  return corps as T
}

export { setTokenProvider }