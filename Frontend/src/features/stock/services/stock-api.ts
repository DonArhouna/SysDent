// TODO(backend): endpoint manquant – module Stock inexistant côté API
// (aucune route /stock dans Backend/src/api/v1/router.py). Le service est
// isolé ici : la page affiche un état « Non disponible » tant que le backend
// n'expose pas /stock/articles et /stock/mouvements. AUCUNE donnée fictive :
// ni localStorage, ni tableau de démo. Cf. PLAN_RESTE_A_FAIRE.md (P0 Stock).
import { api, ApiError } from '@/lib/api'
import type {
  ArticleStock,
  ArticleStockCreate,
  MouvementStock,
  MouvementStockCreate,
} from '../types'

/**
 * Contrats alignés sur le modèle métier (cf. types.ts) — à faire valider par
 * les schémas Pydantic quand le module backend sera écrit.
 */
export const stockApi = {
  // Tous les appels passent en `silencieux` : l'absence du module est un état
  // ATTENDU, affiché proprement par la page. Sans cela, chaque lecture levait
  // un toast rouge « HTTP_404 / Not Found » qui masquait le vrai message
  // « Module Stock non disponible » et exposait un détail technique à l'écran.
  listerArticles: (params?: {
    q?: string
    categorie?: string
    alerte_seuil?: boolean
    page?: number
    limit?: number
  }) => {
    return api.get<{ items: ArticleStock[]; total: number }>('/stock/articles', {
      params,
      silencieux: true,
    })
  },

  creerArticle: (data: ArticleStockCreate) => {
    return api.post<ArticleStock>('/stock/articles', data, { silencieux: true })
  },

  modifierArticle: (id: string, data: Partial<ArticleStockCreate>) => {
    return api.patch<ArticleStock>(`/stock/articles/${id}`, data, { silencieux: true })
  },

  enregistrerMouvement: (data: MouvementStockCreate) => {
    return api.post<MouvementStock>('/stock/mouvements', data, { silencieux: true })
  },

  listerMouvements: (limit = 50) => {
    return api.get<{ items: MouvementStock[] }>('/stock/mouvements', {
      params: { limit },
      silencieux: true,
    })
  },
}

/** Erreur normalisée quand le endpoint manque encore (404/501 côté API). */
export function estEndpointManquant(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 404 || e.status === 501)
}
