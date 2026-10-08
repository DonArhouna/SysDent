import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * Badge de statut sémantique : une seule teinte token par famille d'état.
 * Les pages mappent leurs statuts métier (facture, devis, RDV…) sur ces
 * variantes — plus aucun badge ad hoc avec des couleurs libres.
 */
export type StatusTone =
  | 'neutral' // gris — inactif, brouillon
  | 'info' // bleu — en cours
  | 'success' // vert — validé, payé
  | 'warning' // ambre — à confirmer, en retard
  | 'danger' // rouge — annulé, échec
  | 'purple' // violet — automatique, spécial

const STYLES: Record<StatusTone, string> = {
  neutral: 'border-border bg-muted text-muted-foreground',
  info: 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue',
  success: 'border-success/30 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  danger: 'border-danger/30 bg-danger/10 text-danger',
  purple: 'border-accent-purple/30 bg-accent-purple/10 text-accent-purple',
}

export function StatusBadge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: StatusTone
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold',
        STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
