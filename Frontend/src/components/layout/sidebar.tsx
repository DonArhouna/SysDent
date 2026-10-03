import { useMemo, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { ChevronDown, ChevronsLeft, LogOut, Search, Sparkles } from 'lucide-react'
import { NAVIGATION } from '@/lib/navigation'
import { useAuthStore, possedePermission } from '@/stores/auth-store'
import { Avatar, initiales } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

/**
 * Sidebar de l'application (maquette EduManage adaptée SysDent).
 *
 * - Navigation pilotée par `@/lib/navigation` : une seule source à maintenir ;
 * - filtrage RBAC local avec `possedePermission` (le backend reste garant —
 *   c'est un confort d'affichage, pas une sécurité) ;
 * - repli en rail d'icônes (chevron d'en-tête).
 */
export function Sidebar({ collapsed }: { collapsed: boolean }) {
  const profil = useAuthStore((etat) => etat.profil)
  const deconnexion = useAuthStore((etat) => etat.deconnexion)
  const { pathname } = useLocation()
  const [sectionsRepliees, setSectionsRepliees] = useState<Set<string>>(new Set())

  const sections = useMemo(
    () =>
      NAVIGATION.map((section) => ({
        ...section,
        items: section.items.filter(
          (item) => !item.permission || possedePermission(profil, item.permission),
        ),
      })).filter((section) => section.items.length > 0),
    [profil],
  )

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

  return (
    <aside
      className={cn(
        'flex h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200',
        collapsed ? 'w-[76px]' : 'w-[264px]',
      )}
    >
      {/* En-tête : logo + nom + repli */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-black text-white">
          SD
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold">SysDent Pro</p>
            <p className="flex items-center gap-1 truncate text-[11px] text-muted-foreground">
              <Sparkles className="h-3 w-3 text-accent-purple" />
              Gestion Dentaire Multi-Cabinet
            </p>
          </div>
        )}
      </div>

      {/* Recherche de fonction (visuelle pour le socle) */}
      {!collapsed && (
        <div className="px-4 pb-3">
          <div className="flex h-9 items-center gap-2 rounded-lg border border-sidebar-border bg-background px-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input
              type="search"
              placeholder="Rechercher une fonction..."
              className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              aria-label="Rechercher une fonction"
            />
          </div>
        </div>
      )}

      {/* Sections de navigation */}
      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {sections.map((section) => {
          const repliee = sectionsRepliees.has(section.titre) && !collapsed
          return (
            <div key={section.titre} className="pt-3">
              <button
                type="button"
                onClick={() => basculerSection(section.titre)}
                className="flex w-full items-center justify-between px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                aria-expanded={!repliee}
              >
                <span className="truncate">{section.titre}</span>
                {!collapsed && (
                  <ChevronDown
                    className={cn('h-3.5 w-3.5 transition-transform', repliee && '-rotate-90')}
                  />
                )}
              </button>

              {!repliee &&
                section.items.map((item) => {
                  const Icone = item.icon
                  const actif = item.href ? pathname.startsWith(item.href) : false

                  if (!item.href) {
                    // Module pas encore de page : inerte, jamais de 404.
                    return (
                      <span
                        key={item.label}
                        title="Module à venir"
                        className="flex cursor-default items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground/50"
                      >
                        <Icone className="h-4 w-4 shrink-0" />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </span>
                    )
                  }

                  return (
                    <NavLink
                      key={item.label}
                      to={item.href}
                      className={cn(
                        'relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                        actif
                          ? 'bg-primary font-medium text-primary-foreground'
                          : 'text-sidebar-foreground hover:bg-muted',
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      <Icone className="h-4 w-4 shrink-0" />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                      {actif && !collapsed && (
                        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-white" aria-hidden />
                      )}
                    </NavLink>
                  )
                })}
            </div>
          )
        })}
      </nav>

      {/* Bloc utilisateur */}
      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-card border border-sidebar-border bg-background px-3 py-2">
          <Avatar initials={initiales(profil?.prenom, profil?.nom)} size="lg" />
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{nomComplet}</p>
                <p className="truncate text-[11px] text-muted-foreground">{roleCourt}</p>
              </div>
              <button
                type="button"
                aria-label="Se déconnecter"
                title="Se déconnecter"
                onClick={deconnexion}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-danger"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
        {!collapsed && (
          <p className="mt-2 px-1 text-[10px] text-muted-foreground/70">
            <ChevronsLeft className="inline h-3 w-3" /> Utilisez le menu pour naviguer
          </p>
        )}
      </div>
    </aside>
  )
}
