import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Pastille de statut (statut facture, rôle, mode de paiement...).
 * Les couleurs sont sémantiques : on ne colle pas de `bg-emerald-500` dans
 * les pages, on passe `variant="success"`.
 */
const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        neutral: 'bg-muted text-muted-foreground',
        info: 'bg-primary/15 text-primary',
        success: 'bg-success/15 text-success',
        warning: 'bg-warning/15 text-warning',
        danger: 'bg-danger/15 text-danger',
        purple: 'bg-accent-purple/15 text-accent-purple',
        // Variante « pilule rouge » du badge Administrateur (maquette).
        outline: 'border border-danger text-danger',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
