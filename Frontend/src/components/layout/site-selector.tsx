import { useEffect, useRef, useState } from 'react'
import { Building2, Check, ChevronDown } from 'lucide-react'
import { useCabinetStore } from '@/stores/cabinet-store'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'

/**
 * Identification du site, dans la barre du haut.
 *
 * **Ce n'est pas un sélecteur de cabinet.** Un utilisateur appartient à **un seul
 * tenant** : il n'existe aucune bascule entre cabinets clients, et afficher
 * « Tous les cabinets » —— un agrégat qui enjambe l'isolation entre
 * tenants — n'aurait aucun sens dans l'application du cabinet.
 *
 * Ce qui est multi-site, en revanche, est **le site** à l'intérieur d'un même
 * cabinet. D'où la règle appliquée ici :
 *
 * - **un seul site** → le nom est affiché, en lecture seule. Un sélecteur qui
 *   n'a qu'une option est un clic inutile qui fait croire à un choix possible ;
 * - **plusieurs sites** → un sélecteur, libellé « Site », qui ne propose que
 *   des sites réels. Jamais « tous », jamais « aucun » : « aucun » ferait
 *   afficher au cabinet la comptabilité d'un autre site.
 */
export function SiteSelector() {
  const { cabinetActifId, cabinets, chargement, setCabinetActifId, chargerCabinets } =
    useCabinetStore()
  // Un role sans `CABINETS:READ` — le caissier, le gestionnaire de stock — ne peut
  // pas appeler `GET /cabinets`. `/auth/me` porte deja le nom du cabinet : c'est
  // lui qui garde le repere « ou suis-je » pour ces roles.
  const nomCabinet = useAuthStore((s) => s.profil?.cabinet_nom ?? null)
  const [ouvert, setOuvert] = useState(false)
  const refConteneur = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (cabinets.length === 0) {
      void chargerCabinets()
    }
  }, [cabinets.length, chargerCabinets])

  // Fermeture : clic extérieur et touche Échap, pour rester jouable au clavier.
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

  if (chargement && cabinets.length === 0) return null
  if (cabinets.length === 0) {
    // Aucun site charge — role sans droit de lecture, ou chargement impossible.
    // Le nom du cabinet suffit : un menu deroulant d'une seule option est un clic
    // inutile qui laisse croire a un choix possible.
    if (!nomCabinet) return null
    return (
      <div
        className="flex items-center gap-2 rounded-lg border border-border bg-card/80 px-2.5 py-1.5 text-xs shadow-sm"
        title="Votre cabinet"
      >
        <Building2 className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
        <span className="max-w-[160px] truncate font-semibold">{nomCabinet}</span>
      </div>
    )
  }

  const siteActif = cabinets.find((c) => c.id === cabinetActifId)

  // --- Un seul site : simple repere, aucune interaction ------------------------
  if (cabinets.length === 1) {
    return (
      <div
        className="flex items-center gap-2 rounded-lg border border-border bg-card/80 px-2.5 py-1.5 text-xs shadow-sm"
        title="Votre cabinet"
      >
        <Building2 className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
        <span className="flex flex-col text-left">
          <span className="max-w-[130px] truncate font-semibold sm:max-w-[190px]">
            {siteActif?.nom ?? cabinets[0].nom}
          </span>
          {siteActif?.ville && (
            <span className="truncate text-[10px] leading-none text-muted-foreground">
              {siteActif.ville}
            </span>
          )}
        </span>
      </div>
    )
  }

  // --- Plusieurs sites : un vrai choix, limite aux sites reels -----------------
  return (
    <div className="relative" ref={refConteneur}>
      <button
        type="button"
        onClick={() => setOuvert((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={ouvert}
        className="flex items-center gap-2 rounded-lg border border-border bg-card/80 px-2.5 py-1.5 text-xs text-foreground shadow-sm transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        <Building2 className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
        <span className="flex flex-col text-left">
          <span className="text-[9px] uppercase leading-none tracking-wider text-muted-foreground">
            Site
          </span>
          <span className="max-w-[130px] truncate font-semibold sm:max-w-[180px]">
            {siteActif?.nom ?? cabinets[0].nom}
          </span>
        </span>
        <ChevronDown
          className={cn(
            'ml-1 h-3 w-3 text-muted-foreground transition-transform',
            ouvert && 'rotate-180',
          )}
          aria-hidden
        />
      </button>

      {ouvert && (
        <div
          role="listbox"
          aria-label="Choisir le site"
          className="absolute left-0 top-full z-50 mt-1 w-60 rounded-xl border border-border bg-card p-1.5 shadow-xl"
        >
          <p className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Site
          </p>
          {cabinets.map((c) => {
            const estActif = c.id === cabinetActifId
            return (
              <button
                key={c.id}
                type="button"
                role="option"
                aria-selected={estActif}
                onClick={() => {
                  setCabinetActifId(c.id)
                  setOuvert(false)
                }}
                className={cn(
                  'flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium transition-colors hover:bg-muted',
                  estActif && 'bg-primary/10 font-semibold text-primary',
                )}
              >
                <span className="flex min-w-0 flex-col pr-2 text-left">
                  <span className="truncate">{c.nom}</span>
                  {c.ville && (
                    <span className="truncate text-[10px] text-muted-foreground">{c.ville}</span>
                  )}
                </span>
                {estActif && <Check className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
