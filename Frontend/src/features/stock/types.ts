export type TypeMouvementStock =
  | 'ENTREE'
  | 'SORTIE_CONSULTATION'
  | 'PERTE_PEREMPTION'
  | 'AJUSTEMENT_INVENTAIRE'

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
  actif: boolean
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
}

export interface MouvementStock {
  id: string
  article_id: string
  article_designation: string
  type_mouvement: TypeMouvementStock
  quantite: number
  date_mouvement: string
  motif?: string | null
  auteur?: string | null
}

export interface MouvementStockCreate {
  article_id: string
  type_mouvement: TypeMouvementStock
  quantite: number
  motif?: string
}
