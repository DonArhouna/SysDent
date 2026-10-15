import { useState } from 'react'

import { urlRessource } from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * Logo du cabinet, ou à défaut un repère EXPLICITE : ses initiales dans un
 * cadre en pointillés, annoncé « Aucun logo » (infobulle et lecteur d'écran).
 * Le logo se définit depuis la console de l'éditeur.
 */
export function CabinetLogo({
  url,
  nom,
  taille = 'md',
  legende = false,
}: {
  url?: string | null
  nom?: string | null
  taille?: 'sm' | 'md' | 'lg'
  /** Affiche « Aucun logo » sous le repère quand il n'y a pas de logo. */
  legende?: boolean
}) {
  const [casse, setCasse] = useState(false)
  const libelle = nom || 'Votre cabinet'
  const dims = taille === 'lg' ? 'h-16 w-16 text-lg' : taille === 'sm' ? 'h-8 w-8 text-[11px]' : 'h-12 w-12 text-sm'
  const src = urlRessource(url)

  if (src && !casse) {
    return (
      <img
        src={src}
        alt={`Logo de ${libelle}`}
        onError={() => setCasse(true)}
        className={cn(dims, 'shrink-0 rounded-xl border border-border bg-white object-contain p-1')}
      />
    )
  }

  const initiales = libelle
    .split(/\s+/)
    .filter((m) => /^[\p{L}\d]/u.test(m))
    .slice(0, 2)
    .map((m) => m[0]?.toUpperCase())
    .join('')
  return (
    <span className="inline-flex flex-col items-center gap-1">
      <span
        role="img"
        aria-label={casse ? `Logo de ${libelle} indisponible` : `${libelle} : aucun logo`}
        title={casse ? 'Logo indisponible' : 'Aucun logo'}
        className={cn(dims, 'flex shrink-0 items-center justify-center rounded-xl border border-dashed border-muted-foreground/40 bg-muted/50 font-bold text-muted-foreground')}
      >
        {initiales || '?'}
      </span>
      {legende && <span className="text-[10px] text-muted-foreground">{casse ? 'Logo indisponible' : 'Aucun logo'}</span>}
    </span>
  )
}
