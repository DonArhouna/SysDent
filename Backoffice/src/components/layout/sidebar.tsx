import { useMemo, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { ChevronDown, ChevronsLeft, Search, ShieldCheck, Sparkles } from 'lucide-react'
import { NAVIGATION } from '@/lib/navigation'
import { libelleRole } from '@/lib/libelles'
import { useAuthStore, possedePermission, rolePrincipal } from '@/stores/auth-store'
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
 * - repli en rail d'icônes, piloté par le chevron de cet en-tête ;
 * - élément actif : fond teinté, filet d'accent et pastille d'icône pleine,
 *   lisibles d'un coup d'œil sans saturer le panneau ;
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
  const roleLibelle = libelleRole(rolePrincipal(profil))

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
      <div
        className={cn(
          'flex items-center gap-2 border-b border-sidebar-border/70 pb-3 pt-4',
          collapsed ? 'flex-col px-2' : 'px-4',
        )}
      >
        <Link
          to="/dashboard"
          aria-label="SysDent Pro — aller au tableau de bord"
          title="Tableau de bord"
          className="focus-ring group flex min-w-0 flex-1 items-center gap-3 rounded-lg transition-opacity hover:opacity-90"
        >
          <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-plateforme text-sm font-black text-white shadow-md shadow-primary/25 transition-transform duration-150 group-hover:scale-105">
            SD
          </span>
          {!collapsed && (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[14px] font-bold leading-tight">SysDent Pro</span>
              <span className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-plateforme/10 px-1.5 py-0.5 text-[10px] font-medium text-plateforme">
                <Sparkles className="h-3 w-3 shrink-0" aria-hidden />
                Console plateforme
              </span>
            </span>
          )}
        </Link>

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
        <div className="px-4 pb-1 pt-3">
          <div className="flex h-9 items-center gap-2 rounded-xl border border-surface-border bg-background/60 px-3 transition-all duration-150 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-ring/30">
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
        className={cn(
          'scrollbar-none min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-4',
          collapsed ? 'px-2' : 'px-3',
        )}
        aria-label="Navigation principale"
      >
        {sections.length === 0 && !collapsed && (
          <p className="px-2 pt-3 text-xs text-muted-foreground">
            {recherche
              ? `Aucune fonction ne correspond à « ${recherche} ».`
              : 'Aucun module accessible avec vos droits.'}
          </p>
        )}
        {sections.map((section) => {
          // Pendant une recherche : tout est déplié pour voir les résultats.
          const repliee =
            !collapsed && recherche.trim() === '' && sectionsRepliees.has(section.titre)
          return (
            <div key={section.titre} className="pt-4">
              {/* En rail, le titre est masqué : tronqué il n'apporte rien. Un
                  simple filet sépare les groupes. */}
              {collapsed ? (
                <div
                  className="mx-2 mb-2 border-t border-sidebar-border"
                  role="separator"
                  aria-label={section.titre}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => basculerSection(section.titre)}
                  className="focus-ring mb-1 flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/80 transition-colors hover:text-foreground"
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
                  <ul className="space-y-1">
                    {section.items.map((item) => {
                      const Icone = item.icon
                      const actif = item.href ? pathname.startsWith(item.href) : false

                      if (!item.href) {
                        // Module pas encore de page : inerte, jamais de 404.
                        return (
                          <li
                            key={item.label}
                            title={collapsed ? `${item.label} — à venir` : 'Module à venir'}
                            className={cn(
                              'flex cursor-default items-center gap-3 rounded-xl px-2 py-1.5 text-[13px] text-muted-foreground/50',
                              collapsed && 'justify-center',
                            )}
                          >
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg">
                              <Icone className="h-4 w-4" aria-hidden />
                            </span>
                            {!collapsed && (
                              <>
                                <span className="truncate">{item.label}</span>
                                <span className="ml-auto rounded-full border border-border px-1.5 text-[9px] uppercase tracking-wide">
                                  Bientôt
                                </span>
                              </>
                            )}
                          </li>
                        )
                      }

                      return (
                        <li key={item.label}>
                          <NavLink
                            to={item.href}
                            className={cn(
                              'focus-ring group relative flex items-center gap-3 rounded-xl px-2 py-1.5 text-[13px] transition-all duration-150',
                              collapsed && 'justify-center',
                              actif
                                ? 'bg-primary/10 font-semibold text-primary dark:bg-primary/15'
                                : 'text-sidebar-foreground hover:bg-surface-hover hover:text-foreground',
                            )}
                            title={collapsed ? item.label : undefined}
                            aria-current={actif ? 'page' : undefined}
                          >
                            {/* Filet d'accent de l'élément actif. */}
                            {actif && !collapsed && (
                              <span
                                className="absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary"
                                aria-hidden
                              />
                            )}
                            <span
                              className={cn(
                                'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors duration-150',
                                actif
                                  ? 'bg-primary text-primary-foreground shadow-sm shadow-primary/30'
                                  : 'bg-muted/60 text-muted-foreground group-hover:bg-background group-hover:text-foreground',
                              )}
                            >
                              <Icone className="h-4 w-4" aria-hidden />
                            </span>
                            {!collapsed && <span className="truncate">{item.label}</span>}
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
      <div className="border-t border-sidebar-border/70 p-3">
        <div
          className={cn(
            'flex items-center gap-3 rounded-xl2 bg-background/60 px-2.5 py-2.5 transition-colors duration-150 hover:bg-surface-hover',
            collapsed && 'justify-center px-0',
          )}
          title={collapsed ? `${nomComplet} — ${roleLibelle}` : undefined}
        >
          <span className="relative shrink-0">
            <Avatar initials={initiales(profil?.prenom, profil?.nom)} size="lg" />
            <span
              className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-card bg-success"
              aria-label="Connecté"
            />
          </span>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold leading-tight">{nomComplet}</p>
              <p className="mt-1 flex items-center gap-1.5">
                <span className="truncate rounded-full bg-plateforme/10 px-1.5 py-0.5 text-[10px] font-medium leading-none text-plateforme">
                  {roleLibelle}
                </span>
                {profil?.deux_facteurs_actif && (
                  <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-success" aria-label="Double authentification active" />
                )}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
