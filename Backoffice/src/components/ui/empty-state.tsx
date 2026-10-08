import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * État vide soigné : icône en pastille, titre, description et action
 * optionnelle. Utilisé par les tableaux, listes et panneaux de toutes les
 * pages — remplace les blocs « rien à afficher » ad hoc.
 */
export function EmptyState({
  icon: Icone,
  titre,
  description,
  children,
  className,
}: {
  icon?: LucideIcon
  titre: string
  description?: string
  /** Action optionnelle sous la description (bouton « Créer… »). */
  children?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-6 py-12 text-center',
        className,
      )}
    >
      {Icone && (
        <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl2 bg-muted text-muted-foreground/70">
          <Icone className="h-5 w-5" aria-hidden />
        </span>
      )}
      <p className="text-sm font-semibold text-foreground">{titre}</p>
      {description && (
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}
