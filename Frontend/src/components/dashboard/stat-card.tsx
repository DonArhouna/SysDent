import { type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AccentStat = 'blue' | 'green' | 'purple' | 'orange'

const BORDURES: Record<AccentStat, string> = {
  blue: 'border-l-accent-blue',
  green: 'border-l-accent-green',
  purple: 'border-l-accent-purple',
  orange: 'border-l-accent-orange',
}

const CHIPS: Record<AccentStat, string> = {
  blue: 'bg-accent-blue/15 text-accent-blue',
  green: 'bg-accent-green/15 text-accent-green',
  purple: 'bg-accent-purple/15 text-accent-purple',
  orange: 'bg-accent-orange/15 text-accent-orange',
}

/**
 * Carte de statistique du tableau de bord : bordure gauche colorée, libellé
 * capitales, grand chiffre, sous-titre et chip d'icône (maquette de réf.).
 * `value` est TOUJOURS fourni par l'UI formaté : la carte ne connaît pas l'API.
 */
export function StatCard({
  label,
  value,
  detail,
  icon: Icone,
  accent,
  hint,
}: {
  label: string
  value: string
  detail: string
  icon: LucideIcon
  accent: AccentStat
  /** Message affiché sous le chiffre en cas d'échec de chargement. */
  hint?: string
}) {
  return (
    <article
      className={cn(
        'flex items-start justify-between gap-4 rounded-card border border-border border-l-4 bg-card p-5 shadow-sm',
        BORDURES[accent],
      )}
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="mt-3 truncate text-3xl font-bold tabular-nums">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint ?? detail}</p>
      </div>
      <span className={cn('icon-chip', CHIPS[accent])} aria-hidden>
        <Icone className="h-5 w-5" />
      </span>
    </article>
  )
}
