import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatFcfa, formatDateFr } from '@/lib/format'
import { stockApi } from '../services/stock-api'
import type { ArticleStock, MouvementStock } from '../types'
import { ArticleModal } from '../components/article-modal'
import { MouvementModal } from '../components/mouvement-modal'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Boxes,
  Clock,
  Edit2,
  Package,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from 'lucide-react'

export function StockPage() {
  const [articles, setArticles] = useState<ArticleStock[]>([])
  const [mouvements, setMouvements] = useState<MouvementStock[]>([])
  const [loading, setLoading] = useState(true)
  const [onglet, setOnglet] = useState<'CATALOGUE' | 'MOUVEMENTS'>('CATALOGUE')

  // Filtres
  const [recherche, setRecherche] = useState('')
  const [categorieFiltre, setCategorieFiltre] = useState('')
  const [alerteSeul, setAlerteSeul] = useState(false)

  // Modales
  const [isArticleModalOpen, setIsArticleModalOpen] = useState(false)
  const [selectedArticle, setSelectedArticle] = useState<ArticleStock | null>(null)
  const [isMouvementModalOpen, setIsMouvementModalOpen] = useState(false)

  const chargerDonnees = async () => {
    try {
      setLoading(true)
      const [resArticles, resMouvements] = await Promise.all([
        stockApi.listerArticles({
          q: recherche.trim() || undefined,
          categorie: categorieFiltre || undefined,
          alerte_seuil: alerteSeul || undefined,
        }),
        stockApi.listerMouvements(50),
      ])
      setArticles(resArticles.items)
      setMouvements(resMouvements)
    } catch {
      //
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerDonnees()
  }, [recherche, categorieFiltre, alerteSeul])

  // KPIs
  const totalArticles = articles.length
  const articlesEnAlerte = articles.filter((a) => a.quantite_stock <= a.seuil_alerte)
  const valeurStockTotale = articles.reduce(
    (acc, a) => acc + a.quantite_stock * (a.prix_achat || 0),
    0
  )

  const categoriesUniques = Array.from(new Set(articles.map((a) => a.categorie)))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2.5">
            <Boxes className="w-6 h-6 text-primary" />
            Gestion des Stocks & Consommables
          </h1>
          <p className="text-sm text-muted-foreground">
            Suivi des produits dentaires, seuils de réapprovisionnement critique et dates de péremption.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            className="flex items-center gap-1.5 text-xs border-border"
            onClick={() => {
              setSelectedArticle(null)
              setIsMouvementModalOpen(true)
            }}
          >
            <SlidersHorizontal className="w-4 h-4 text-primary" /> Mouvement de stock
          </Button>
          <Button
            variant="primary"
            className="flex items-center gap-1.5 text-xs"
            onClick={() => {
              setSelectedArticle(null)
              setIsArticleModalOpen(true)
            }}
          >
            <Plus className="w-4 h-4" /> Nouvel article
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card p-4 rounded-xl border border-border flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">Références actives</span>
            <span className="text-2xl font-bold text-foreground font-mono">{totalArticles}</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-card-foreground">
            <Package className="w-5 h-5" />
          </div>
        </div>

        <div
          onClick={() => setAlerteSeul(!alerteSeul)}
          className={`p-4 rounded-xl border flex items-center justify-between cursor-pointer transition-colors ${
            articlesEnAlerte.length > 0
              ? 'bg-danger/15 border-danger/40 hover:bg-danger/15'
              : 'bg-card border-border'
          }`}
        >
          <div>
            <span className="text-xs text-danger block font-medium">Stock Critique / Réappro</span>
            <span className="text-2xl font-bold text-danger font-mono">
              {articlesEnAlerte.length}
            </span>
            <span className="text-[10px] text-muted-foreground block mt-0.5">
              {alerteSeul ? 'Filtre actif (cliquer pour réinitialiser)' : 'Cliquer pour filtrer'}
            </span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-danger/15 border border-danger/40 flex items-center justify-center text-danger">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-card p-4 rounded-xl border border-border flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">Valeur globale du stock</span>
            <span className="text-2xl font-bold text-primary font-mono">
              {formatFcfa(valeurStockTotale)}
            </span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-primary/15 border border-primary/40 flex items-center justify-center text-primary">
            <Boxes className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border space-x-6 text-sm">
        <button
          onClick={() => setOnglet('CATALOGUE')}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            onglet === 'CATALOGUE'
              ? 'text-primary border-b-2 border-primary/40'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <Package className="w-4 h-4" /> Catalogue & Disponibilités ({articles.length})
        </button>
        <button
          onClick={() => setOnglet('MOUVEMENTS')}
          className={`pb-3 font-semibold transition-colors flex items-center gap-2 ${
            onglet === 'MOUVEMENTS'
              ? 'text-primary border-b-2 border-primary/40'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <Clock className="w-4 h-4" /> Historique des Mouvements ({mouvements.length})
        </button>
      </div>

      {onglet === 'CATALOGUE' && (
        <div className="space-y-4">
          {/* Filtres de recherche */}
          <div className="bg-card p-4 rounded-xl border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
              <Input
                placeholder="Rechercher désignation ou code..."
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
                className="pl-9"
              />
            </div>

            <div className="w-64">
              <select
                className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-xs text-foreground"
                value={categorieFiltre}
                onChange={(e) => setCategorieFiltre(e.target.value)}
              >
                <option value="">Toutes les catégories</option>
                {categoriesUniques.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Tableau des articles */}
          <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
            {loading ? (
              <div className="p-8 text-center text-sm text-muted-foreground">Chargement du stock...</div>
            ) : articles.length === 0 ? (
              <div className="p-12 text-center text-sm text-muted-foreground">
                Aucun article ne correspond à votre recherche.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-card-foreground">
                  <thead className="bg-muted text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                    <tr>
                      <th className="px-4 py-3">Réf / Code</th>
                      <th className="px-4 py-3">Désignation</th>
                      <th className="px-4 py-3">Catégorie</th>
                      <th className="px-4 py-3 text-center">Niveau de Stock</th>
                      <th className="px-4 py-3 text-right">P.U Achat</th>
                      <th className="px-4 py-3">Péremption</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {articles.map((art) => {
                      const estCritique = art.quantite_stock <= art.seuil_alerte
                      const ratio = Math.min(100, (art.quantite_stock / (art.seuil_alerte * 3)) * 100)

                      return (
                        <tr key={art.id} className="hover:bg-muted transition-colors">
                          <td className="px-4 py-3 font-mono font-bold text-foreground">
                            {art.code}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-semibold text-foreground">{art.designation}</div>
                            {art.emplacement && (
                              <div className="text-[11px] text-muted-foreground mt-0.5">
                                Empl.: {art.emplacement}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{art.categorie}</td>
                          <td className="px-4 py-3">
                            <div className="flex flex-col items-center">
                              <div className="flex items-center gap-1.5 mb-1">
                                <span
                                  className={`font-mono font-bold text-xs ${
                                    estCritique ? 'text-danger' : 'text-foreground'
                                  }`}
                                >
                                  {art.quantite_stock} {art.unite}s
                                </span>
                                {estCritique && (
                                  <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-danger/15 text-danger border border-danger/40">
                                    Alerte &lt;= {art.seuil_alerte}
                                  </span>
                                )}
                              </div>
                              <div className="w-24 bg-muted rounded-full h-1.5 overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    estCritique ? 'bg-danger' : 'bg-success'
                                  }`}
                                  style={{ width: `${Math.max(10, ratio)}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-card-foreground">
                            {formatFcfa(art.prix_achat)}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground text-[11px]">
                            {art.date_peremption ? formatDateFr(art.date_peremption) : '-'}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-xs h-7 px-2 text-primary border-primary/40"
                                onClick={() => {
                                  setSelectedArticle(art)
                                  setIsMouvementModalOpen(true)
                                }}
                              >
                                <RefreshCw className="w-3 h-3 mr-1" /> Mouvement
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                className="text-xs h-7 px-2"
                                onClick={() => {
                                  setSelectedArticle(art)
                                  setIsArticleModalOpen(true)
                                }}
                              >
                                <Edit2 className="w-3 h-3" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {onglet === 'MOUVEMENTS' && (
        <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
          {mouvements.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              Aucun mouvement de stock enregistré.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-card-foreground">
                <thead className="bg-muted text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                  <tr>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Article</th>
                    <th className="px-4 py-3">Type de mouvement</th>
                    <th className="px-4 py-3 text-center">Quantité</th>
                    <th className="px-4 py-3">Motif / Justification</th>
                    <th className="px-4 py-3">Auteur</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {mouvements.map((m) => {
                    const estEntree = m.type_mouvement === 'ENTREE'
                    const estSortie =
                      m.type_mouvement === 'SORTIE_CONSULTATION' ||
                      m.type_mouvement === 'PERTE_PEREMPTION'

                    return (
                      <tr key={m.id} className="hover:bg-muted transition-colors">
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatDateFr(m.date_mouvement)}
                        </td>
                        <td className="px-4 py-3 font-semibold text-foreground">
                          {m.article_designation}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                              estEntree
                                ? 'bg-success/15 border border-success/40 text-success'
                                : estSortie
                                ? 'bg-danger/15 border border-danger/40 text-danger'
                                : 'bg-primary/15 border border-primary/40 text-primary'
                            }`}
                          >
                            {estEntree ? (
                              <ArrowUpRight className="w-3 h-3" />
                            ) : estSortie ? (
                              <ArrowDownRight className="w-3 h-3" />
                            ) : (
                              <RefreshCw className="w-3 h-3" />
                            )}
                            {m.type_mouvement}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center font-mono font-bold text-foreground">
                          {estEntree ? `+${m.quantite}` : estSortie ? `-${m.quantite}` : m.quantite}
                        </td>
                        <td className="px-4 py-3 text-card-foreground italic">{m.motif || '-'}</td>
                        <td className="px-4 py-3 text-muted-foreground">{m.auteur || 'Praticien'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modale Article */}
      <ArticleModal
        isOpen={isArticleModalOpen}
        onClose={() => {
          setIsArticleModalOpen(false)
          setSelectedArticle(null)
        }}
        article={selectedArticle}
        onSuccess={() => chargerDonnees()}
      />

      {/* Modale Mouvement */}
      <MouvementModal
        isOpen={isMouvementModalOpen}
        onClose={() => {
          setIsMouvementModalOpen(false)
          setSelectedArticle(null)
        }}
        articles={articles}
        articleInitial={selectedArticle}
        onSuccess={() => chargerDonnees()}
      />
    </div>
  )
}
