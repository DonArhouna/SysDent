import type { ReactNode } from 'react'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

/**
 * En-tête de page standard : grand titre + sous-titre gris, actions à droite
 * (bouton « Actualiser » en pill si `onRefresh` fourni, sinon slots libres).
 * Toutes les pages l'utilisent — zéro header ad hoc.
 */
export function PageHeader({
  titre,
  sousTitre,
  retour,
  onRefresh,
  libelleRefresh = 'Actualiser',
  children,
  className,
}: {
  titre: ReactNode
  sousTitre?: ReactNode
  /**
   * Lien de retour affiché à gauche du titre (pages de détail).
   * Le titre est alors rendu sans troncature pour rester lisible.
   */
  retour?: { to: string; label?: string }
  /** Affiche le bouton pill « Actualiser » branché sur le refetch. */
  onRefresh?: () => void
  libelleRefresh?: string
  /** Actions additionnelles à droite (créer, exporter…). */
  children?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-4',
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {retour && (
          <Link
            to={retour.to}
            title={retour.label ?? 'Retour'}
            aria-label={retour.label ?? 'Retour'}
            className="focus-ring mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
          </Link>
        )}
        <div className="min-w-0">
          <h1
            className={cn(
              'text-2xl font-bold tracking-tight text-foreground md:text-3xl',
              !retour && 'truncate',
            )}
          >
            {titre}
          </h1>
          {sousTitre && (
            <p className="mt-1 text-sm text-muted-foreground">{sousTitre}</p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {children}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
            {libelleRefresh}
          </button>
        )}
      </div>
    </div>
  )
}
