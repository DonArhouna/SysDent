import type { CSSProperties } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AccentStat = 'blue' | 'green' | 'purple' | 'orange'

const Liseres: Record<AccentStat, { border: string; chip: string; var: string }> = {
  blue: {
    border: 'border-l-kpi-blue',
    chip: 'bg-accent-blue/15 text-accent-blue',
    var: 'var(--kpi-blue)',
  },
  green: {
    border: 'border-l-kpi-green',
    chip: 'bg-accent-green/15 text-accent-green',
    var: 'var(--kpi-green)',
  },
  purple: {
    border: 'border-l-kpi-purple',
    chip: 'bg-accent-purple/15 text-accent-purple',
    var: 'var(--kpi-purple)',
  },
  orange: {
    border: 'border-l-kpi-orange',
    chip: 'bg-accent-orange/15 text-accent-orange',
    var: 'var(--kpi-orange)',
  },
}

/**
 * Carte KPI (refonte 2026-10) : grands coins arrondis, liseré vertical coloré
 * à gauche (token `--kpi-*`), label en majuscules espacées, icône dans une
 * pastille carrée teintée en haut à droite, grande valeur et légende grise.
 *
 * `value` est TOUJOURS fourni par l'UI formaté : la carte ne connaît pas l'API.
 * Trois états : `chargement` (skeleton), `hint` (erreur API), sinon la valeur.
 */
export function StatCard({
  label,
  value,
  detail,
  icon: Icone,
  accent,
  hint,
  chargement = false,
}: {
  label: string
  value: string
  detail: string
  icon: LucideIcon
  accent: AccentStat
  /** Message affiché sous le chiffre en cas d'échec de chargement. */
  hint?: string
  /** Affiche un skeleton à la place de la valeur pendant le fetch. */
  chargement?: boolean
}) {
  const style = Liseres[accent]

  return (
    <article
      style={{ '--liseré': style.var } as CSSProperties}
      className={cn(
        'flex items-start justify-between gap-4 rounded-xl2 border border-border border-l-4 bg-card p-5 shadow-float transition-shadow duration-200',
        style.border,
      )}
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {chargement ? (
          <div
            className="mt-3 h-9 w-24 animate-pulse rounded-lg bg-muted"
            role="status"
            aria-label="Chargement en cours"
          />
        ) : (
          // Pas de `truncate` ici : un montant réaliste (« 200 000 FCFA »)
          // débordait la carte et se retrouvait coupé en « 200 000 F… ».
          // La valeur passe à la ligne plutôt que de perdre son dernier chiffre.
          <p className="mt-3 break-words text-2xl font-bold leading-tight tabular-nums sm:text-3xl">
            {value}
          </p>
        )}
        <p className="mt-1 truncate text-xs text-muted-foreground">{hint ?? detail}</p>
      </div>
      <span className={cn('icon-chip', style.chip)} aria-hidden>
        <Icone className="h-5 w-5" />
      </span>
    </article>
  )
}
