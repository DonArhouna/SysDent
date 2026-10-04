import { useMemo, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { ChevronDown, ChevronsLeft, Search, Sparkles } from 'lucide-react'
import { NAVIGATION } from '@/lib/navigation'
import { useAuthStore, possedePermission } from '@/stores/auth-store'
import { libelleRole } from '@/lib/roles'
import { Avatar, initiales } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

/**
 * Sidebar flottante de l'application.
 *
 * Panneau détaché des bords, coins arrondis **y compris en bas** (24 px), fond
 * translucide (`.floating-panel`) — cf. capture de référence. Police serif
 * (Times New Roman) demandée explicitement.
 *
 * - Navigation pilotée par `@/lib/navigation` : une seule source à maintenir ;
 * - filtrage RBAC local avec `possedePermission` (le backend reste garant) ;
 * - recherche de fonction : filtre les entrées en temps réel, les sections
 *   s'auto-déplient pendant une recherche ;
 * - repli en rail d'icônes, piloté par le chevron de cet en-tête (et non par
 *   la navbar, qui n'a plus de bouton) ;
 * - barre de défilement masquée : `.scrollbar-none` neutralise le visuel sans
 *   empêcher la molette, le tactile ni le clavier.
 *
 * La hauteur est résolue par le parent (`h-full` + `min-h-0`) : sans cela, le
 * `h-full` de ce panneau se résout sur la hauteur de son contenu et la liste
 * déborde au lieu de défiler.
 */
export function AppSidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  /** Replie / déploie le panneau. Appelé par le chevron de l'en-tête. */
  onToggle: () => void
}) {
  const profil = useAuthStore((etat) => etat.profil)
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
  const roleLibelle = libelleRole(profil?.role)
  // Libellé structure : le cabinet est géré par le sélecteur de la navbar.
  const structure = profil?.tenant_id ? 'Cabinet rattaché' : 'Plateforme SysDent'

  return (
    <aside
      className={cn(
        // Coins arrondis sur les quatre angles, bas compris : le panneau
        // flotte, il ne doit pas être coupé net vers le bord de l'écran.
        'floating-panel flex h-full min-h-0 w-full shrink-0 flex-col overflow-hidden rounded-xl3',
        'font-serif',
      )}
    >
      {/* En-tête : logo + libellé (un seul lien) + repli */}
      <div className="flex items-center gap-2 px-4 pt-4 pb-3">
        <Link
          to="/dashboard"
          aria-label="SysDent Pro — aller au tableau de bord"
          title="Tableau de bord"
          className="focus-ring group flex min-w-0 flex-1 items-center gap-3 rounded-lg transition-opacity hover:opacity-80"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-sm font-black text-primary-foreground shadow-sm transition-transform duration-150 group-hover:scale-105">
            SD
          </span>
          {!collapsed && (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-bold leading-tight">
                SysDent Pro
              </span>
              <span className="flex items-center gap-1 truncate text-[10px] text-muted-foreground">
                <Sparkles className="h-3 w-3 shrink-0 text-accent-purple" aria-hidden />
                Gestion Dentaire
              </span>
            </span>
          )}
        </Link>

        {/* Repliage : la navbar n'a plus de bouton (demande explicite). */}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? 'Déplier le menu' : 'Replier le menu'}
          title={collapsed ? 'Déplier le menu' : 'Replier le menu'}
          className="focus-ring shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground"
        >
          <ChevronsLeft
            className={cn('h-4 w-4 transition-transform duration-200', collapsed && 'rotate-180')}
            aria-hidden
          />
        </button>
      </div>

      {/* Recherche de fonction : filtre réel de la navigation */}
      {!collapsed && (
        <div className="px-4 pb-3">
          <div className="flex h-9 items-center gap-2 rounded-full border border-surface-border bg-background/60 px-3.5 transition-all duration-150 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-ring/40">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <input
              type="search"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher une fonction…"
              className="w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
              aria-label="Rechercher une fonction"
            />
          </div>
        </div>
      )}

      {/* Sections de navigation repliables — seule zone qui défile. */}
      <nav
        className="scrollbar-none min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-4"
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
            !collapsed && recherche.trim() === '' && sectionsRepliees.has(section.titre)
          return (
            <div key={section.titre} className="pt-3">
              {/* En rail, le titre est masqué : tronqué à « TAB… » il n'apporte
                  rien. Un simple filet sépare les groupes. */}
              {collapsed ? (
                <div
                  className="mx-2 my-2 border-t border-sidebar-border"
                  role="separator"
                  aria-label={section.titre}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => basculerSection(section.titre)}
                  className="focus-ring flex w-full items-center justify-between gap-2 rounded-lg px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
                  aria-expanded={!repliee}
                >
                  <span className="truncate">{section.titre}</span>
                  <ChevronDown
                    className={cn(
                      'h-3.5 w-3.5 shrink-0 transition-transform duration-200',
                      repliee && '-rotate-90',
                    )}
                    aria-hidden
                  />
                </button>
              )}

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
                            className="flex cursor-default items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] text-muted-foreground/50"
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
                              'focus-ring relative flex items-center gap-2.5 rounded-full px-2.5 py-2 text-[13px] transition-all duration-150',
                              actif
                                ? 'bg-primary font-medium text-primary-foreground shadow-sm'
                                : 'text-sidebar-foreground hover:translate-x-0.5 hover:bg-surface-hover hover:text-foreground',
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

      {/* Pied : carte utilisateur (la déconnexion vit dans le menu de la navbar) */}
      <div className="p-3">
        <div className="flex items-center gap-3 rounded-xl2 border border-surface-border bg-background/60 px-3 py-2.5 transition-colors duration-150 hover:border-primary/30">
          <Avatar initials={initiales(profil?.prenom, profil?.nom)} size="lg" />
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold leading-tight">{nomComplet}</p>
              <p className="truncate text-[10px] leading-tight text-muted-foreground">
                {roleLibelle} • {structure}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}