import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { StatusBadge } from '@/components/ui/status-badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { estEndpointManquant, stockApi } from '../services/stock-api'
import type { ArticleStock } from '../types'
import { ArticleModal } from '../components/article-modal'
import { MouvementModal } from '../components/mouvement-modal'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Boxes,
  Clock,
  Package,
  PackageX,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  WifiOff,
} from 'lucide-react'

/**
 * Page Stock — module EN ATTENTE côté backend.
 *
 * Aucune route `/stock/*` n'existe dans l'API (cf. Backend/src/api/v1/router.py).
 * Conformément à la règle « pas de mock silencieux » :
 * - le service (`stock-api.ts`) est déjà écrit sur les contrats cibles ;
 * - cette page tente l'appel réel et affiche un état « Non disponible » propre
 *   dès que l'API répond 404/501 — aucune donnée fictive n'est montrée ;
 * - le bandeau d'avertissement explicite la situation et renvoie au plan.
 */
export function StockPage() {
  const [onglet, setOnglet] = useState<'CATALOGUE' | 'MOUVEMENTS'>('CATALOGUE')
  const [recherche, setRecherche] = useState('')
  const [categorieFiltre, setCategorieFiltre] = useState('')
  const [alerteSeul, setAlerteSeul] = useState(false)

  // Modales
  const [isArticleModalOpen, setIsArticleModalOpen] = useState(false)
  const [selectedArticle, setSelectedArticle] = useState<ArticleStock | null>(null)
  const [isMouvementModalOpen, setIsMouvementModalOpen] = useState(false)

  const articlesQuery = useQuery({
    queryKey: ['stock', 'articles', recherche, categorieFiltre, alerteSeul],
    queryFn: () =>
      stockApi.listerArticles({
        q: recherche.trim() || undefined,
        categorie: categorieFiltre || undefined,
        alerte_seuil: alerteSeul || undefined,
      }),
    // Le endpoint n'existe pas encore : inutile de marteler l'API.
    retry: false,
  })

  const mouvementsQuery = useQuery({
    queryKey: ['stock', 'mouvements'],
    queryFn: () => stockApi.listerMouvements(50),
    retry: false,
  })

  const endpointAbsent =
    estEndpointManquant(articlesQuery.error) || estEndpointManquant(mouvementsQuery.error)
  const erreurReseau =
    !endpointAbsent &&
    (articlesQuery.error instanceof ApiError || mouvementsQuery.error instanceof ApiError)

  const articles = articlesQuery.data?.items ?? []
  const mouvements = mouvementsQuery.data?.items ?? []

  // KPIs calculés depuis l'API — 0 tant que l'endpoint n'existe pas.
  const totalArticles = articles.length
  const articlesEnAlerte = articles.filter((a) => a.quantite_stock <= a.seuil_alerte)
  const valeurStockTotale = articles.reduce(
    (acc, a) => acc + a.quantite_stock * (a.prix_achat || 0),
    0,
  )
  const categoriesUniques = Array.from(new Set(articles.map((a) => a.categorie)))

  const recharger = () => {
    void articlesQuery.refetch()
    void mouvementsQuery.refetch()
  }

  // Bandeau module indisponible : endpoint backend absent (404/501).
  if (endpointAbsent) {
    return (
      <div className="space-y-6">
        <PageHeader
          titre="Gestion des Stocks & Consommables"
          sousTitre="Suivi des produits dentaires, seuils de réapprovisionnement et péremptions"
          onRefresh={recharger}
        />

        {/* TODO(backend): endpoints manquants – GET/POST /stock/articles,
            GET/POST /stock/mouvements. Voir PLAN_RESTE_A_FAIRE.md (P0). */}
        <EmptyState
          icon={PackageX}
          titre="Module Stock non disponible"
          description="Le backend n'expose pas encore les endpoints /stock/articles et /stock/mouvements. L'interface est prête et se branchera dès leur livraison — aucune donnée fictive n'est affichée."
        >
          <Button variant="outline" onClick={recharger}>
            <RefreshCw className="h-4 w-4" /> Réessayer
          </Button>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        titre="Gestion des Stocks & Consommables"
        sousTitre="Suivi des produits dentaires, seuils de réapprovisionnement critique et dates de péremption"
        onRefresh={recharger}
      >
        {erreurReseau && (
          <StatusBadge tone="warning">
            <WifiOff className="h-3 w-3" aria-hidden /> API injoignable
          </StatusBadge>
        )}
        <Button
          variant="outline"
          onClick={() => {
            setSelectedArticle(null)
            setIsMouvementModalOpen(true)
          }}
        >
          <SlidersHorizontal /> Mouvement de stock
        </Button>
        <Button
          variant="primary"
          onClick={() => {
            setSelectedArticle(null)
            setIsArticleModalOpen(true)
          }}
        >
          <Plus /> Nouvel article
        </Button>
      </PageHeader>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="floating-panel bg-card/80 p-5 rounded-xl2 border border-border flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
              Références actives
            </span>
            {articlesQuery.isPending ? (
              <Skeleton className="mt-2 h-8 w-16" />
            ) : (
              <span className="text-2xl font-bold text-foreground tabular-nums">
                {totalArticles}
              </span>
            )}
          </div>
          <span className="icon-chip bg-accent-blue/15 text-accent-blue">
            <Package className="h-5 w-5" aria-hidden />
          </span>
        </div>

        <button
          type="button"
          onClick={() => setAlerteSeul(!alerteSeul)}
          aria-pressed={alerteSeul}
          className={`focus-ring p-5 rounded-xl2 border flex items-center justify-between text-left transition-colors ${
            articlesEnAlerte.length > 0
              ? 'bg-danger/10 border-danger/40 hover:bg-danger/15'
              : 'floating-panel bg-card/80 border-border hover:bg-surface-hover'
          }`}
        >
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-danger block">
              Stock critique / réappro
            </span>
            {articlesQuery.isPending ? (
              <Skeleton className="mt-2 h-8 w-16" />
            ) : (
              <span className="text-2xl font-bold text-danger tabular-nums">
                {articlesEnAlerte.length}
              </span>
            )}
            <span className="text-[10px] text-muted-foreground block mt-0.5">
              {alerteSeul ? 'Filtre actif — cliquer pour réinitialiser' : 'Cliquer pour filtrer'}
            </span>
          </div>
          <span className="icon-chip bg-danger/15 text-danger">
            <AlertTriangle className="h-5 w-5" aria-hidden />
          </span>
        </button>

        <div className="floating-panel bg-card/80 p-5 rounded-xl2 border border-border flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block">
              Valeur globale du stock
            </span>
            {articlesQuery.isPending ? (
              <Skeleton className="mt-2 h-8 w-28" />
            ) : (
              <span className="text-2xl font-bold text-primary tabular-nums">
                {new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(
                  valeurStockTotale,
                )}{' '}
                FCFA
              </span>
            )}
          </div>
          <span className="icon-chip bg-accent-green/15 text-accent-green">
            <Boxes className="h-5 w-5" aria-hidden />
          </span>
        </div>
      </div>

      {/* Tabs (pills) */}
      <div
        role="tablist"
        aria-label="Sections du module stock"
        className="inline-flex items-center gap-1 rounded-full border border-surface-border bg-surface/70 p-1"
      >
        {(
          [
            { id: 'CATALOGUE', label: 'Catalogue', icon: Package, count: articles.length },
            { id: 'MOUVEMENTS', label: 'Mouvements', icon: Clock, count: mouvements.length },
          ] as const
        ).map((ongletDef) => {
          const Icone = ongletDef.icon
          const actif = onglet === ongletDef.id
          return (
            <button
              key={ongletDef.id}
              type="button"
              role="tab"
              aria-selected={actif}
              onClick={() => setOnglet(ongletDef.id)}
              className={`focus-ring inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                actif
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icone className="h-3.5 w-3.5" aria-hidden />
              {ongletDef.label} ({ongletDef.count})
            </button>
          )
        })}
      </div>

      {onglet === 'CATALOGUE' && (
        <div className="space-y-4">
          {/* Filtres de recherche */}
          <div className="floating-panel bg-card/80 p-4 rounded-xl2 border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                placeholder="Rechercher désignation ou code…"
                value={recherche}
                onChange={(e) => setRecherche(e.target.value)}
                className="pl-9"
              />
            </div>

            <div className="w-full sm:w-64">
              <select
                aria-label="Filtrer par catégorie"
                className="w-full h-10 px-3 rounded-full border border-border bg-background/60 text-xs text-foreground focus-ring"
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
          <div className="floating-panel bg-card/80 rounded-xl2 border border-border overflow-hidden">
            {articlesQuery.isPending ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : articlesQuery.isError ? (
              /* Un échec réseau n'est pas un catalogue vide : ne pas mentir
                 sur l'état, afficher l'erreur et proposer un nouvel essai. */
              <EmptyState
                icon={WifiOff}
                titre="Catalogue indisponible"
                description="Le catalogue n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
              >
                <Button variant="outline" onClick={recharger}>
                  <RefreshCw className="h-4 w-4" /> Réessayer
                </Button>
              </EmptyState>
            ) : articles.length === 0 ? (
              <EmptyState
                icon={Package}
                titre="Aucun article trouvé"
                description="Ajustez la recherche ou créez le premier article du catalogue."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-card-foreground">
                  <thead className="bg-muted/60 text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                    <tr>
                      <th className="px-4 py-3">Réf / Code</th>
                      <th className="px-4 py-3">Désignation</th>
                      <th className="px-4 py-3">Catégorie</th>
                      <th className="px-4 py-3 text-center">Niveau de stock</th>
                      <th className="px-4 py-3 text-right">P.U achat</th>
                      <th className="px-4 py-3">Péremption</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {articles.map((art) => {
                      const estCritique = art.quantite_stock <= art.seuil_alerte
                      const ratio = Math.min(100, (art.quantite_stock / (art.seuil_alerte * 3)) * 100)

                      return (
                        <tr key={art.id} className="hover:bg-surface-hover transition-colors">
                          <td className="px-4 py-3 font-mono font-bold text-foreground">
                            {art.code}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-semibold text-foreground">{art.designation}</div>
                            {art.emplacement && (
                              <div className="text-[11px] text-muted-foreground mt-0.5">
                                Empl. : {art.emplacement}
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
                                  {art.quantite_stock} {art.unite}(s)
                                </span>
                                {estCritique && (
                                  <StatusBadge tone="danger">
                                    Alerte ≤ {art.seuil_alerte}
                                  </StatusBadge>
                                )}
                              </div>
                              <div className="w-24 bg-muted rounded-full h-1.5 overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-200 ${
                                    estCritique ? 'bg-danger' : 'bg-success'
                                  }`}
                                  style={{ width: `${Math.max(10, ratio)}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right font-mono text-card-foreground tabular-nums">
                            {new Intl.NumberFormat('fr-FR', {
                              maximumFractionDigits: 0,
                            }).format(art.prix_achat)}{' '}
                            FCFA
                          </td>
                          <td className="px-4 py-3 text-muted-foreground text-[11px]">
                            {art.date_peremption
                              ? new Date(art.date_peremption).toLocaleDateString('fr-FR')
                              : '—'}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => {
                                  setSelectedArticle(art)
                                  setIsMouvementModalOpen(true)
                                }}
                              >
                                <RefreshCw className="h-3 w-3" /> Mouvement
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                className="h-7 px-2"
                                onClick={() => {
                                  setSelectedArticle(art)
                                  setIsArticleModalOpen(true)
                                }}
                              >
                                Modifier
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
        <div className="floating-panel bg-card/80 rounded-xl2 border border-border overflow-hidden">
          {mouvementsQuery.isPending ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : mouvements.length === 0 ? (
            <EmptyState
              icon={ArrowUpRight}
              titre="Aucun mouvement de stock"
              description="Les entrées, sorties et ajustements apparaîtront ici."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-card-foreground">
                <thead className="bg-muted/60 text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
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
                      <tr key={m.id} className="hover:bg-surface-hover transition-colors">
                        <td className="px-4 py-3 text-muted-foreground">
                          {new Date(m.date_mouvement).toLocaleDateString('fr-FR')}
                        </td>
                        <td className="px-4 py-3 font-semibold text-foreground">
                          {m.article_designation}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            tone={estEntree ? 'success' : estSortie ? 'danger' : 'info'}
                          >
                            {estEntree ? (
                              <ArrowUpRight className="h-3 w-3" aria-hidden />
                            ) : estSortie ? (
                              <ArrowDownRight className="h-3 w-3" aria-hidden />
                            ) : (
                              <RefreshCw className="h-3 w-3" aria-hidden />
                            )}
                            {m.type_mouvement}
                          </StatusBadge>
                        </td>
                        <td className="px-4 py-3 text-center font-mono font-bold text-foreground tabular-nums">
                          {estEntree ? `+${m.quantite}` : estSortie ? `-${m.quantite}` : m.quantite}
                        </td>
                        <td className="px-4 py-3 text-card-foreground italic">{m.motif || '—'}</td>
                        <td className="px-4 py-3 text-muted-foreground">{m.auteur || '—'}</td>
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
        onSuccess={() => recharger()}
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
        onSuccess={() => recharger()}
      />
    </div>
  )
}
