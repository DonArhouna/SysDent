// TODO: endpoint manquant au backend - implémentation mock locale persistée pour continuité SaaS
import type {
  ArticleStock,
  ArticleStockCreate,
  MouvementStock,
  MouvementStockCreate,
} from '../types'

const STORAGE_KEY_ARTICLES = 'sysdent_stock_articles'
const STORAGE_KEY_MOUVEMENTS = 'sysdent_stock_mouvements'

const INITIAL_ARTICLES: ArticleStock[] = [
  {
    id: 'art-001',
    code: 'ANE-LIDO-01',
    designation: 'Lidocaïne 2% + Adrénaline 1:100 000 (Boîte de 50 cartouches)',
    categorie: 'Anesthésie',
    unite: 'Boîte',
    quantite_stock: 14,
    seuil_alerte: 5,
    prix_achat: 18500,
    date_peremption: '2027-08-31',
    emplacement: 'Armoire A - Étagère 1',
    actif: true,
  },
  {
    id: 'art-002',
    code: 'ANE-ARTI-02',
    designation: 'Articaïne 4% + Adrénaline 1:200 000 (Boîte de 50)',
    categorie: 'Anesthésie',
    unite: 'Boîte',
    quantite_stock: 3,
    seuil_alerte: 5,
    prix_achat: 22000,
    date_peremption: '2026-11-30',
    emplacement: 'Armoire A - Étagère 1',
    actif: true,
  },
  {
    id: 'art-003',
    code: 'PRO-GANT-M',
    designation: 'Gants d\'examen Nitrile non poudrés - Taille M (Boîte de 100)',
    categorie: 'Consommables & Hygiène',
    unite: 'Boîte',
    quantite_stock: 45,
    seuil_alerte: 10,
    prix_achat: 4500,
    date_peremption: '2028-12-31',
    emplacement: 'Réserve Générale - Bac 4',
    actif: true,
  },
  {
    id: 'art-004',
    code: 'RES-COMP-A2',
    designation: 'Composite Nanohybride seringue 4g Teinte A2',
    categorie: 'Matériaux d\'obturation',
    unite: 'Seringue',
    quantite_stock: 2,
    seuil_alerte: 4,
    prix_achat: 16000,
    date_peremption: '2027-04-15',
    emplacement: 'Tiroir Fauteuil 1',
    actif: true,
  },
  {
    id: 'art-005',
    code: 'ENDO-HYPO-5',
    designation: 'Hypochlorite de sodium 3% pour irrigation canalaire (Flacon 1L)',
    categorie: 'Endodontie',
    unite: 'Flacon',
    quantite_stock: 6,
    seuil_alerte: 2,
    prix_achat: 8500,
    date_peremption: '2026-12-31',
    emplacement: 'Armoire Produits Chimiques',
    actif: true,
  },
  {
    id: 'art-006',
    code: 'STE-ROUL-01',
    designation: 'Gaine de stérilisation thermosoudable 75mm x 200m',
    categorie: 'Stérilisation',
    unite: 'Rouleau',
    quantite_stock: 1,
    seuil_alerte: 2,
    prix_achat: 24000,
    date_peremption: '2029-01-01',
    emplacement: 'Salle de Stérilisation',
    actif: true,
  },
]

function getArticlesFromStorage(): ArticleStock[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_ARTICLES)
    if (!raw) {
      localStorage.setItem(STORAGE_KEY_ARTICLES, JSON.stringify(INITIAL_ARTICLES))
      return INITIAL_ARTICLES
    }
    return JSON.parse(raw)
  } catch {
    return INITIAL_ARTICLES
  }
}

function saveArticlesToStorage(articles: ArticleStock[]) {
  localStorage.setItem(STORAGE_KEY_ARTICLES, JSON.stringify(articles))
}

function getMouvementsFromStorage(): MouvementStock[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_MOUVEMENTS)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveMouvementsToStorage(mouvements: MouvementStock[]) {
  localStorage.setItem(STORAGE_KEY_MOUVEMENTS, JSON.stringify(mouvements))
}

export const stockApi = {
  // Liste des articles
  listerArticles: async (params?: {
    q?: string
    categorie?: string
    alerte_seuil?: boolean
  }): Promise<{ items: ArticleStock[]; total: number }> => {
    let articles = getArticlesFromStorage()

    if (params?.q) {
      const q = params.q.toLowerCase()
      articles = articles.filter(
        (a) =>
          a.designation.toLowerCase().includes(q) ||
          a.code.toLowerCase().includes(q) ||
          a.categorie.toLowerCase().includes(q)
      )
    }

    if (params?.categorie) {
      articles = articles.filter((a) => a.categorie === params.categorie)
    }

    if (params?.alerte_seuil) {
      articles = articles.filter((a) => a.quantite_stock <= a.seuil_alerte)
    }

    return { items: articles, total: articles.length }
  },

  // Créer un article
  creerArticle: async (data: ArticleStockCreate): Promise<ArticleStock> => {
    const articles = getArticlesFromStorage()
    const nouvelArticle: ArticleStock = {
      id: `art-${Date.now()}`,
      ...data,
      actif: true,
    }
    articles.push(nouvelArticle)
    saveArticlesToStorage(articles)
    return nouvelArticle
  },

  // Modifier un article
  modifierArticle: async (
    id: string,
    data: Partial<ArticleStockCreate>
  ): Promise<ArticleStock> => {
    const articles = getArticlesFromStorage()
    const index = articles.findIndex((a) => a.id === id)
    if (index === -1) throw new Error('Article non trouvé')
    articles[index] = { ...articles[index], ...data }
    saveArticlesToStorage(articles)
    return articles[index]
  },

  // Enregistrer un mouvement de stock
  enregistrerMouvement: async (data: MouvementStockCreate): Promise<MouvementStock> => {
    const articles = getArticlesFromStorage()
    const article = articles.find((a) => a.id === data.article_id)
    if (!article) throw new Error('Article non trouvé')

    // Ajustement des quantités selon type
    if (data.type_mouvement === 'ENTREE') {
      article.quantite_stock += data.quantite
    } else if (
      data.type_mouvement === 'SORTIE_CONSULTATION' ||
      data.type_mouvement === 'PERTE_PEREMPTION'
    ) {
      article.quantite_stock = Math.max(0, article.quantite_stock - data.quantite)
    } else if (data.type_mouvement === 'AJUSTEMENT_INVENTAIRE') {
      article.quantite_stock = data.quantite
    }

    saveArticlesToStorage(articles)

    const mouvements = getMouvementsFromStorage()
    const nouveauMouvement: MouvementStock = {
      id: `mvt-${Date.now()}`,
      article_id: article.id,
      article_designation: article.designation,
      type_mouvement: data.type_mouvement,
      quantite: data.quantite,
      date_mouvement: new Date().toISOString(),
      motif: data.motif || null,
      auteur: 'Utilisateur connecté',
    }
    mouvements.unshift(nouveauMouvement)
    saveMouvementsToStorage(mouvements)

    return nouveauMouvement
  },

  // Liste des mouvements récents
  listerMouvements: async (limit = 50): Promise<MouvementStock[]> => {
    const mouvements = getMouvementsFromStorage()
    return mouvements.slice(0, limit)
  },
}
