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
  listerArticles: (params?: {
    q?: string
    categorie?: string
    alerte_seuil?: boolean
    page?: number
    limit?: number
  }) => {
    return api.get<{ items: ArticleStock[]; total: number }>('/stock/articles', { params })
  },

  creerArticle: (data: ArticleStockCreate) => {
    return api.post<ArticleStock>('/stock/articles', data)
  },

  modifierArticle: (id: string, data: Partial<ArticleStockCreate>) => {
    return api.patch<ArticleStock>(`/stock/articles/${id}`, data)
  },

  enregistrerMouvement: (data: MouvementStockCreate) => {
    return api.post<MouvementStock>('/stock/mouvements', data)
  },

  listerMouvements: (limit = 50) => {
    return api.get<{ items: MouvementStock[] }>('/stock/mouvements', {
      params: { limit },
    })
  },
}

/** Erreur normalisée quand le endpoint manque encore (404/501 côté API). */
export function estEndpointManquant(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 404 || e.status === 501)
}
