import { cn } from '@/lib/utils'

/**
 * Avatar circulaire avec initiales (AA, SUP, SD...) comme sur la maquette.
 * `photo_url` est prévu par le backend mais jamais requis : les initiales
 * restent le repli systématique.
 */
export function Avatar({
  initials,
  className,
  size = 'md',
}: {
  initials: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}) {
  const tailles = { sm: 'h-7 text-[10px]', md: 'h-9 text-xs', lg: 'h-10 text-sm' }
  return (
    <span
      className={cn(
        'flex select-none items-center justify-center rounded-full bg-primary/15 font-bold uppercase text-primary',
        tailles[size],
        className,
      )}
      aria-hidden
    >
      {initials}
    </span>
  )
}

/** Initiales d'un profil : `AD` pour Aminata Diop, fallback `?`. */
export function initiales(prenom?: string | null, nom?: string | null): string {
  const premier = (prenom ?? '').trim().charAt(0)
  const dernier = (nom ?? '').trim().charAt(0)
  const resultat = `${premier}${dernier}`.toUpperCase()
  return resultat || '?'
}
