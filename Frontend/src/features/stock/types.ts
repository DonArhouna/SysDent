export type TypeMouvementStock =
  | 'ENTREE'
  | 'SORTIE_CONSULTATION'
  | 'PERTE_PEREMPTION'
  | 'AJUSTEMENT_INVENTAIRE'

export type StatutCommande =
  | 'BROUILLON'
  | 'ENVOYEE'
  | 'PARTIELLEMENT_REÇUE'
  | 'RECUE'
  | 'ANNULEE'

/** Répartition de la quantité d'un article sur un site. */
export interface StockSite {
  cabinet_id: string
  quantite: number
}

export interface ArticleStock {
  id: string
  code: string
  designation: string
  categorie: string
  unite: string
  quantite_stock: number
  seuil_alerte: number
  prix_achat: number
  date_peremption?: string | null
  emplacement?: string | null
  gere_par_lot: boolean
  actif: boolean
  stocks_sites?: StockSite[]
}

export interface ArticleStockCreate {
  code: string
  designation: string
  categorie: string
  unite: string
  quantite_stock: number
  seuil_alerte: number
  prix_achat: number
  date_peremption?: string | null
  emplacement?: string | null
  gere_par_lot?: boolean
  motif_initial?: string
}

export interface MouvementStock {
  id: string
  article_id: string
  article_designation?: string | null
  article_code?: string | null
  cabinet_id: string
  type_mouvement: TypeMouvementStock
  quantite: number
  /** Stock du site avant et après le mouvement : l'écart est explicable ligne par ligne. */
  stock_avant: number
  stock_apres: number
  motif?: string | null
  auteur_email?: string | null
  commande_id?: string | null
  date_mouvement: string
}

export interface MouvementStockCreate {
  article_id: string
  cabinet_id: string
  type_mouvement: TypeMouvementStock
  quantite: number
  lot_id?: string
  motif?: string
}

export interface AlerteStock {
  article_id: string
  code: string
  designation: string
  type: 'SEUIL_MINIMUM' | 'PEREMPTION_PROCHE' | 'PERIM_E'
  niveau: 'URGENT' | 'AVERTISSEMENT'
  stock_actuel: number
  seuil?: number | null
  unite: string
  date_peremption?: string | null
  jours_restants?: number | null
  message: string
}

export interface Fournisseur {
  id: string
  nom: string
  contact?: string | null
  telephone?: string | null
  email?: string | null
  adresse?: string | null
  notes?: string | null
  actif: boolean
}

export interface LigneCommande {
  id: string
  article_id: string
  article_code?: string | null
  article_designation?: string | null
  quantite_commandee: number
  quantite_recue: number
  prix_unitaire: number
}

export interface CommandeFournisseur {
  id: string
  numero: string
  fournisseur_id: string
  fournisseur_nom?: string | null
  statut: StatutCommande
  date_commande: string
  notes?: string | null
  auteur?: string | null
  lignes: LigneCommande[]
  montant_total: number
}

export interface LigneReception {
  id: string
  ligne_commande_id: string
  quantite_recue: number
  lot_code?: string | null
  date_peremption?: string | null
}

export interface ReceptionFournisseur {
  id: string
  numero: string
  commande_id: string
  date_reception: string
  notes?: string | null
  /** Qui a réceptionné : la traçabilité remplace la double validation. */
  auteur?: string | null
  lignes: LigneReception[]
}
