import type { ReactNode } from 'react'
import { LifeBuoy } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Bouton d'action flottant (assistant / aide) — bas droite, arrondi plein,
 * pastille de notification optionnelle. Position fixe : il survole le contenu
 * scrollé. Le contenu (menu d'aide) est fourni par la page hôte.
 */
export function FloatingActionButton({
  onClick,
  label = 'Aide & assistance',
  badge = false,
  children,
  className,
}: {
  onClick?: () => void
  label: string
  /** Affiche la pastille de notification en haut à droite. */
  badge?: boolean
  children?: ReactNode
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        'focus-ring fixed bottom-5 right-5 z-30 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-float transition-transform duration-150 hover:scale-105 active:scale-95',
        className,
      )}
    >
      {children ?? <LifeBuoy className="h-5 w-5" aria-hidden />}
      {badge && (
        <span
          className="absolute -right-0.5 -top-0.5 flex h-3 w-3 rounded-full bg-success ring-2 ring-background"
          aria-hidden
        />
      )}
    </button>
  )
}
