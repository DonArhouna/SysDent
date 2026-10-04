import { useEffect, useRef, useState } from 'react'
import { Building2, ChevronDown, Check } from 'lucide-react'
import { useCabinetStore } from '@/stores/cabinet-store'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'

/**
 * Sélecteur de cabinet actif (multi-site).
 *
 * Ouverture au clic (jouable au doigt sur tablette) : fermeture par Escape,
 * clic extérieur et re-sélection. Le choix est persisté par le store et
 * propagé aux requêtes API par les services qui lisent `cabinetActifId`.
 */
export function CabinetSelector() {
  const profil = useAuthStore((s) => s.profil)
  const { cabinetActifId, cabinets, chargement, setCabinetActifId, chargerCabinets } =
    useCabinetStore()
  const [ouvert, setOuvert] = useState(false)
  const refConteneur = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (cabinets.length === 0) {
      void chargerCabinets()
    }
  }, [cabinets.length, chargerCabinets])

  // Fermeture : clic extérieur + Escape (accessibilité clavier).
  useEffect(() => {
    if (!ouvert) return
    const surClicExt = (e: MouseEvent) => {
      if (refConteneur.current && !refConteneur.current.contains(e.target as Node)) {
        setOuvert(false)
      }
    }
    const surEchap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOuvert(false)
    }
    document.addEventListener('mousedown', surClicExt)
    document.addEventListener('keydown', surEchap)
    return () => {
      document.removeEventListener('mousedown', surClicExt)
      document.removeEventListener('keydown', surEchap)
    }
  }, [ouvert])

  const cabinetActif = cabinets.find((c) => c.id === cabinetActifId)
  const estAdmin =
    profil?.role === 'ADMIN_CABINET' ||
    profil?.role === 'SUPER_ADMIN' ||
    profil?.role === 'COMPTABLE'

  if (cabinets.length === 0 && !chargement) return null

  return (
    <div className="relative" ref={refConteneur}>
      <button
        type="button"
        onClick={() => setOuvert((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={ouvert}
        className="flex items-center gap-2 rounded-lg border border-border bg-card/80 px-2.5 py-1.5 text-xs text-foreground shadow-sm transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        <Building2 className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="flex flex-col text-left">
          <span className="max-w-[130px] truncate font-semibold sm:max-w-[180px]">
            {cabinetActif ? cabinetActif.nom : estAdmin ? 'Tous les cabinets' : 'Sélectionner site'}
          </span>
          {cabinetActif?.ville && (
            <span className="truncate text-[10px] leading-none text-muted-foreground">
              {cabinetActif.ville}
            </span>
          )}
        </span>
        <ChevronDown
          className={cn('ml-1 h-3 w-3 text-muted-foreground transition-transform', ouvert && 'rotate-180')}
        />
      </button>

      {/* Menu déroulant */}
      {ouvert && (
        <div
          role="listbox"
          aria-label="Changer de cabinet"
          className="absolute left-0 top-full z-50 mt-1 w-56 rounded-xl border border-border bg-card p-1.5 shadow-xl"
        >
          <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Changer de cabinet
          </p>

          {estAdmin && (
            <button
              type="button"
              role="option"
              aria-selected={cabinetActifId === null}
              onClick={() => {
                setCabinetActifId(null)
                setOuvert(false)
              }}
              className={cn(
                'flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium transition-colors hover:bg-muted',
                cabinetActifId === null && 'bg-primary/10 font-semibold text-primary',
              )}
            >
              <span>Tous les cabinets</span>
              {cabinetActifId === null && <Check className="h-3.5 w-3.5 text-primary" />}
            </button>
          )}

          {cabinets.map((c) => {
            const isActif = c.id === cabinetActifId
            return (
              <button
                key={c.id}
                type="button"
                role="option"
                aria-selected={isActif}
                onClick={() => {
                  setCabinetActifId(c.id)
                  setOuvert(false)
                }}
                className={cn(
                  'flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium transition-colors hover:bg-muted',
                  isActif && 'bg-primary/10 font-semibold text-primary',
                )}
              >
                <span className="flex min-w-0 flex-col pr-2 text-left">
                  <span className="truncate">{c.nom}</span>
                  {c.ville && <span className="truncate text-[10px] text-muted-foreground">{c.ville}</span>}
                </span>
                {isActif && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
