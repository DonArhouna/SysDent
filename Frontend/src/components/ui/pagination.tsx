import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { PageReponse } from '@/lib/api'

/** Métadonnées de pagination telles que les renvoie l'API. */
type Meta = PageReponse<unknown>['meta']

/**
 * Barre de pagination des listes.
 *
 * Elle existait écrite à la main sur la seule page patients. C'était le seul
 * endroit paginé de l'application : les consultations, les devis, les
 * ordonnances, les factures, les fournisseurs et les commandes renvoyaient
 * tout ou se bornaient à un plafond invisible — et dans ce dernier cas la
 * liste était **tronquée sans le dire**, ce qui est la famille de défaut la plus
 * coûteuse : une donnée absente présentée comme un zéro.
 *
 * La mutualiser évite d'écrire la cinquième variante. Elle ne porte aucun
 * style en dur : uniquement les jetons du design system.
 */
export function Pagination({
  meta,
  page,
  limit,
  onPageChange,
  /** Accord du nom des objets comptés, au pluriel : « dossiers », « factures »… */
  libelle = 'éléments',
  /** Rappelé quand la page demandée n'existe plus (données supprimées entre-temps). */
  onPageHorsBornes,
}: {
  meta: Meta | undefined
  page: number
  limit: number
  onPageChange: (page: number) => void
  libelle?: string
  onPageHorsBornes?: () => void
}) {
  if (!meta || meta.total_records === 0) return null

  // Des données peuvent avoir disparu entre deux requêtes : la page 12 d'un
  // fichier réduit à 3 pages n'existe plus. Renvoyer vers la dernière page est
  // le comportement attendu plutôt qu'une page vide sans explication.
  if (page > meta.total_pages) {
    onPageHorsBornes?.()
    return null
  }

  const premier = (page - 1) * limit + 1
  const dernier = Math.min(page * limit, meta.total_records)
  const plusieursPages = meta.total_pages > 1

  return (
    <div className="flex flex-col gap-2 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <p className="text-xs text-muted-foreground">
        Affichage de <span className="font-semibold text-foreground">{premier}</span> à{' '}
        <span className="font-semibold text-foreground">{dernier}</span> sur{' '}
        <span className="font-semibold text-foreground">{meta.total_records}</span> {libelle}
      </p>

      {plusieursPages && (
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={!meta.has_previous}
          >
            <ChevronLeft className="h-4 w-4" />
            Précédent
          </Button>
          <span className="px-3 text-xs font-semibold text-foreground">
            Page {page} / {meta.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(Math.min(meta.total_pages, page + 1))}
            disabled={!meta.has_next}
          >
            Suivant
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}