import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import type {
  AlerteStock,
  ArticleStock,
  ArticleStockCreate,
  CommandeFournisseur,
  Fournisseur,
  MouvementStock,
  MouvementStockCreate,
  ReceptionFournisseur,
} from '../types'

/**
 * Module Stock — branché sur l'API réelle.
 *
 * Le stock est réparti par site : presque tous les appels portent donc
 * `cabinet_id`, le site dont on veut la quantité. C'est ce qui permet de savoir
 * où chercher une ampoule en urgence, et pas seulement combien il en reste.
 *
 * Aucune donnée de repli n'est fournie : un endpoint en erreur remonte une
 * erreur, jamais un jeu de données fictif.
 */

/** Extrait `meta.total_records` d'une réponse paginée. */
function total(pagination: PageReponse<unknown>): number {
  return pagination.meta?.total_records ?? 0
}

export const stockApi = {
  // ---------------------------------------------------------------- Articles

  listerArticles: (params: {
    cabinetId: string
    q?: string
    categorie?: string
    alerteSeuil?: boolean
    peremptionProche?: boolean
    page?: number
    limit?: number
  }) => {
    const query = new URLSearchParams({ cabinet_id: params.cabinetId })
    if (params.q) query.set('q', params.q)
    if (params.categorie) query.set('categorie', params.categorie)
    if (params.alerteSeuil) query.set('alerte_seuil', 'true')
    if (params.peremptionProche) query.set('peremption_proche', 'true')
    query.set('page', String(params.page ?? 1))
    query.set('limit', String(params.limit ?? 50))

    return api
      .get<PageReponse<ArticleStock>>(`/stock/articles?${query.toString()}`)
      .then((reponse) => ({
        items: reponse.items ?? [],
        total: total(reponse),
      }))
  },

  creerArticle: (cabinetId: string, data: ArticleStockCreate) => {
    return api.post<ArticleStock>(`/stock/articles?cabinet_id=${cabinetId}`, data)
  },

  modifierArticle: (id: string, data: Partial<ArticleStockCreate>) => {
    return api.patch<ArticleStock>(`/stock/articles/${id}`, data)
  },

  // -------------------------------------------------------------- Mouvements

  enregistrerMouvement: (data: MouvementStockCreate) => {
    return api.post<MouvementStock>('/stock/mouvements', data)
  },

  listerMouvements: (params: { articleId?: string; cabinetId?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params.articleId) query.set('article_id', params.articleId)
    if (params.cabinetId) query.set('cabinet_id', params.cabinetId)
    query.set('limit', String(params.limit ?? 50))
    return api
      .get<PageReponse<MouvementStock>>(`/stock/mouvements?${query.toString()}`)
      .then((reponse) => ({ items: reponse.items ?? [], total: total(reponse) }))
  },

  // ---------------------------------------------------------------- Alertes

  listerAlertes: (cabinetId: string) => {
    // La reponse est une enveloppe `APIResponse` : sans le `.data`, le compteur
    // d'alertes vaut 0 sans lever la moindre erreur.
    return api.get<ApiReponse<AlerteStock[]>>(`/stock/alertes?cabinet_id=${cabinetId}`)
  },

  // ------------------------------------------------------------ Fournisseurs

    /**
     * Fournisseurs, paginés.
     *
     * L'API renvoie `{ items, meta }` et non plus `{ data }`. Lire `.data`
     * renvoyait `undefined` — d'où des listes vides sans message d'erreur.
     */
    listerFournisseurs: (params: { q?: string; page?: number; limit?: number } = {}) => {
      const query = new URLSearchParams()
      if (params.q) query.set('q', params.q)
      if (params.page) query.set('page', String(params.page))
      if (params.limit) query.set('limit', String(params.limit))
      return api.get<PageReponse<Fournisseur>>(`/stock/fournisseurs?${query.toString()}`)
    },

  creerFournisseur: (data: Partial<Fournisseur>) => {
    return api.post<Fournisseur>('/stock/fournisseurs', data)
  },

  modifierFournisseur: (id: string, data: Partial<Fournisseur>) => {
    return api.patch<Fournisseur>(`/stock/fournisseurs/${id}`, data)
  },

  // -------------------------------------------------------------- Commandes

    /** Commandes, paginées — voir `listerFournisseurs` pour le contrat. */
    listerCommandes: (params: { statut?: string; page?: number; limit?: number } = {}) => {
      const query = new URLSearchParams()
      if (params.statut) query.set('statut', params.statut)
      if (params.page) query.set('page', String(params.page))
      if (params.limit) query.set('limit', String(params.limit))
      return api.get<PageReponse<CommandeFournisseur>>(`/stock/commandes?${query.toString()}`)
    },

  creerCommande: (data: {
    fournisseur_id: string
    notes?: string
    lignes: Array<{ article_id: string; quantite: number; prix_unitaire?: number }>
  }) => {
    return api.post<CommandeFournisseur>('/stock/commandes', data)
  },

  changerStatutCommande: (id: string, statut: string) => {
    return api.patch<CommandeFournisseur>(`/stock/commandes/${id}`, { statut })
  },

  // ------------------------------------------------------------- Réceptions

  /**
   * Enregistre une réception. Le stock est crédité immédiatement, sans
   * validation à deux mains : la traçabilité (qui, quand, quelle commande)
   * remplace le second regard, qui dans un cabinet d'une ou deux personnes
   * empêcherait la réception et rendrait le stock faux.
   */
  enregistrerReception: (commandeId: string, siteId: string, data: {
    notes?: string
    lignes: Array<{
      ligne_commande_id: string
      quantite_recue: number
      lot_code?: string
      date_peremption?: string
    }>
  }) => {
    const query = new URLSearchParams({ commande_id: commandeId, site_id: siteId })
    return api.post<ReceptionFournisseur>(`/stock/receptions?${query.toString()}`, data)
  },
}
