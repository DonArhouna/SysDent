import { useMemo, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { ChevronDown, LogOut, Search, Sparkles } from 'lucide-react'
import { NAVIGATION } from '@/lib/navigation'
import { useAuthStore, possedePermission } from '@/stores/auth-store'
import { Avatar, initiales } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

/**
 * Sidebar flottante de l'application (refonte visuelle 2026-10).
 *
 * Panneau détaché des bords de l'écran, coins fortement arrondis, fond
 * translucide (`.floating-panel`) — cf. capture de référence.
 *
 * - Navigation pilotée par `@/lib/navigation` : une seule source à maintenir ;
 * - filtrage RBAC local avec `possedePermission` (le backend reste garant —
 *   c'est un confort d'affichage, pas une sécurité) ;
 * - recherche de fonction : filtre les entrées en temps réel (les sections
 *   s'auto-déplient quand on cherche) ;
 * - repli en rail d'icônes (chevron de l'en-tête ou de la navbar) ;
 * - animation d'ouverture des sections (grid-template-rows) respectant
 *   `prefers-reduced-motion` via la règle globale.
 */
export function AppSidebar({ collapsed }: { collapsed: boolean }) {
  const profil = useAuthStore((etat) => etat.profil)
  const deconnexion = useAuthStore((etat) => etat.deconnexion)
  const { pathname } = useLocation()
  const [sectionsRepliees, setSectionsRepliees] = useState<Set<string>>(new Set())
  const [recherche, setRecherche] = useState('')

  const sections = useMemo(() => {
    const terme = recherche.trim().toLowerCase()
    return NAVIGATION.map((section) => ({
      ...section,
      items: section.items.filter(
        (item) =>
          (!item.permission || possedePermission(profil, item.permission)) &&
          (terme === '' || item.label.toLowerCase().includes(terme)),
      ),
    })).filter((section) => section.items.length > 0)
  }, [profil, recherche])

  const basculerSection = (titre: string) => {
    setSectionsRepliees((ensemble) => {
      const prochain = new Set(ensemble)
      if (prochain.has(titre)) prochain.delete(titre)
      else prochain.add(titre)
      return prochain
    })
  }

  const nomComplet = profil ? `${profil.prenom} ${profil.nom}`.trim() : '—'
  const roleCourt = profil?.role ?? 'INVITE'
  // Libellé structure : le cabinet est géré par le sélecteur de la navbar.
  const structure = profil?.tenant_id ? 'Cabinet rattaché' : 'Plateforme SysDent'

  return (
    <aside
      className={cn(
        'floating-panel flex h-full shrink-0 flex-col rounded-xl3 transition-[width] duration-200',
        collapsed ? 'w-[80px]' : 'w-[268px]',
      )}
    >
      {/* En-tête : logo + nom + bouton de réduction */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-sm font-black text-primary-foreground shadow-sm">
          SD
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold leading-tight">SysDent Pro</p>
            <p className="flex items-center gap-1 truncate text-[11px] text-muted-foreground">
              <Sparkles className="h-3 w-3 text-accent-purple" aria-hidden />
              Gestion Dentaire Multi-Cabinet
            </p>
          </div>
        )}
      </div>

      {/* Recherche de fonction : filtre réel de la navigation */}
      {!collapsed && (
        <div className="px-4 pb-3">
          <div className="flex h-9 items-center gap-2 rounded-full border border-surface-border bg-background/60 px-3.5 transition-shadow focus-within:ring-2 focus-within:ring-ring/50">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <input
              type="search"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher une fonction…"
              className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              aria-label="Rechercher une fonction"
            />
          </div>
        </div>
      )}

      {/* Sections de navigation repliables */}
      <nav
        className="flex-1 overflow-y-auto overflow-x-hidden px-3 pb-4"
        aria-label="Navigation principale"
      >
        {sections.length === 0 && !collapsed && (
          <p className="px-2 pt-3 text-xs text-muted-foreground">
            Aucune fonction ne correspond à « {recherche} ».
          </p>
        )}
        {sections.map((section) => {
          // Pendant une recherche : tout est déplié pour voir les résultats.
          const repliee =
            recherche.trim() === '' && sectionsRepliees.has(section.titre) && !collapsed
          return (
            <div key={section.titre} className="pt-3">
              <button
                type="button"
                onClick={() => basculerSection(section.titre)}
                className="focus-ring flex w-full items-center justify-between gap-2 rounded-lg px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
                aria-expanded={!repliee}
              >
                <span className="truncate">{section.titre}</span>
                {!collapsed && (
                  <ChevronDown
                    className={cn(
                      'h-3.5 w-3.5 shrink-0 transition-transform duration-200',
                      repliee && '-rotate-90',
                    )}
                    aria-hidden
                  />
                )}
              </button>

              {/* Conteneur animé : grid-rows 0fr→1fr, sans hauteur magique. */}
              <div
                className={cn(
                  'grid transition-[grid-template-rows] duration-200 ease-out',
                  repliee ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]',
                )}
              >
                <div className="overflow-hidden">
                  <ul className="relative ml-3.5 space-y-0.5 border-l border-sidebar-border pl-2">
                    {section.items.map((item) => {
                      const Icone = item.icon
                      const actif = item.href ? pathname.startsWith(item.href) : false

                      if (!item.href) {
                        // Module pas encore de page : inerte, jamais de 404.
                        return (
                          <li
                            key={item.label}
                            title="Module à venir"
                            className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted-foreground/50"
                          >
                            <Icone className="h-4 w-4 shrink-0" aria-hidden />
                            {!collapsed && <span className="truncate">{item.label}</span>}
                          </li>
                        )
                      }

                      return (
                        <li key={item.label}>
                          <NavLink
                            to={item.href}
                            className={cn(
                              'focus-ring relative flex items-center gap-2.5 rounded-full px-2.5 py-2 text-sm transition-colors duration-150',
                              actif
                                ? 'bg-primary font-medium text-primary-foreground shadow-sm'
                                : 'text-sidebar-foreground hover:bg-surface-hover hover:text-foreground',
                            )}
                            title={collapsed ? item.label : undefined}
                            aria-current={actif ? 'page' : undefined}
                          >
                            <Icone className="h-4 w-4 shrink-0" aria-hidden />
                            {!collapsed && <span className="truncate">{item.label}</span>}
                            {actif && !collapsed && (
                              <span
                                className="ml-auto h-1.5 w-1.5 rounded-full bg-white"
                                aria-hidden
                              />
                            )}
                          </NavLink>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              </div>
            </div>
          )
        })}
      </nav>

      {/* Pied de sidebar : carte utilisateur */}
      <div className="p-3">
        <div className="flex items-center gap-3 rounded-xl2 border border-surface-border bg-background/60 px-3 py-2.5">
          <Avatar initials={initiales(profil?.prenom, profil?.nom)} size="lg" />
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold leading-tight">{nomComplet}</p>
                <p className="truncate text-[11px] text-muted-foreground">
                  {roleCourt} • {structure}
                </p>
              </div>
              <button
                type="button"
                aria-label="Se déconnecter"
                title="Se déconnecter"
                onClick={deconnexion}
                className="focus-ring rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-danger"
              >
                <LogOut className="h-4 w-4" aria-hidden />
              </button>
            </>
          )}
        </div>
      </div>
    </aside>
  )
}
