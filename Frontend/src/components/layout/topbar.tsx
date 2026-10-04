import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  CalendarDays,
  ChevronDown,
  Menu,
  LogOut,
  Search,
  Settings,
  ShieldCheck,
  UserRound,
  type LucideIcon,
} from 'lucide-react'
import { Avatar, initiales } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/layout/theme-toggle'
import { CabinetSelector } from '@/components/layout/cabinet-selector'
import { CommandPalette } from '@/components/layout/command-palette'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'
import { libelleRole, COULEURS_ROLES } from '@/lib/roles'

/**
 * Navbar flottante.
 *
 * - **Pas de bouton de repli** : il vit désormais dans l'en-tête de la sidebar
 *   (demande explicite). Le clic dehors ou `Échap` ferme les panneaux ouverts ;
 * - - **`Ctrl/⌘ + K`** ouvre une palette qui cherche dans toute l'application
 *   (pages + actions), pas seulement parmi les patients ;
 * - - le bloc utilisateur ouvre un menu (Mon compte, Paramètres, Déconnexion).
 */

interface EntreeMenu {
  libelle: string
  icone: LucideIcon
  action: () => void
  danger?: boolean
}

export function Topbar({
  onOpenMenu,
  drawerOuvert = false,
}: {
  /** Ouvre le drawer de navigation. Fourni par AppShell. */
  onOpenMenu: () => void
  /** Le drawer de navigation est-il ouvert (état détenu par AppShell). */
  drawerOuvert?: boolean
}) {
  const profil = useAuthStore((etat) => etat.profil)
  const deconnexion = useAuthStore((etat) => etat.deconnexion)
  const naviguer = useNavigate()

  const nomComplet = profil ? `${profil.prenom} ${profil.nom}`.trim() : '—'
  const roleLibelle = libelleRole(profil?.role)

  const [paletteOuverte, setPaletteOuverte] = useState(false)
  const [menuOuvert, setMenuOuvert] = useState(false)
  const [notifOuvert, setNotifOuvert] = useState(false)
  const refMenu = useRef<HTMLDivElement>(null)
  const refNotif = useRef<HTMLDivElement>(null)

  // Fermeture par le clic dehors — pour chaque panneau ouvert.
  useEffect(() => {
    if (!menuOuvert && !notifOuvert) return
    const surClicExt = (e: MouseEvent) => {
      if (refMenu.current && !refMenu.current.contains(e.target as Node)) setMenuOuvert(false)
      if (refNotif.current && !refNotif.current.contains(e.target as Node)) setNotifOuvert(false)
    }
    document.addEventListener('mousedown', surClicExt)
    return () => document.removeEventListener('mousedown', surClicExt)
  }, [menuOuvert, notifOuvert])

  // Échap ferme le panneau ouvert ; le clavier ne doit jamais rester bloqué.
  useEffect(() => {
    if (!menuOuvert && !notifOuvert) return
    const surEchap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMenuOuvert(false)
        setNotifOuvert(false)
      }
    }
    document.addEventListener('keydown', surEchap)
    return () => document.removeEventListener('keydown', surEchap)
  }, [menuOuvert, notifOuvert])

  // Ctrl/⌘ + K ouvre la palette.
  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOuverte(true)
      }
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [])

  const aujourdhui = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  const couleurRole =
    COULEURS_ROLES[profil?.role ?? ''] ?? 'border-border bg-muted text-foreground'

  const entreesMenu: EntreeMenu[] = [
    { libelle: 'Mon compte', icone: UserRound, action: () => naviguer('/compte') },
    { libelle: 'Paramètres', icone: Settings, action: () => naviguer('/parametres') },
    {
      libelle: 'Se déconnecter',
      icone: LogOut,
      action: () => deconnexion(),
      danger: true,
    },
  ]

  return (
    <>
      <header className="floating-panel flex h-16 shrink-0 items-center gap-2 rounded-xl2 px-3 md:gap-3 md:px-4">
        {/* Mobile uniquement : sans sidebar visible, ce bouton est le seul accès
            à la navigation. Sur desktop, le repli se fait depuis l'en-tête de
            la sidebar — pas de doublon. */}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Ouvrir le menu de navigation"
          aria-expanded={drawerOuvert}
          aria-controls="menu-navigation-mobile"
          onClick={onOpenMenu}
          // `lg:hidden`, et non `md:hidden` : la sidebar reste masquee jusqu'a
          // 1024px (breakpoint `lg` du layout). Avec `md`, la bascule se
          // produisait a 768px — entre les deux, plus aucun acces a la
          // navigation : l'application etait inutilisable sur tablette.
          className="lg:hidden"
        >
          <Menu aria-hidden />
        </Button>

        {/* Recherche globale — le champ n'est qu'un déclencheur : toute la
            logique est dans la palette, qui sait chercher au-delà des pages. */}
        <button
          type="button"
          onClick={() => setPaletteOuverte(true)}
          className="focus-ring group flex h-10 min-w-0 flex-1 items-center gap-2.5 rounded-full border border-surface-border bg-background/60 px-3 transition-all duration-150 hover:border-primary/50 hover:bg-background hover:shadow-float md:max-w-sm md:px-4"
          aria-label="Recherche globale"
          aria-keyshortcuts="Control+K Meta+K"
        >
          <Search
            className="h-4 w-4 shrink-0 text-muted-foreground transition-all duration-150 group-hover:scale-110 group-hover:text-primary"
            aria-hidden
          />
          <span className="min-w-0 flex-1 truncate text-left text-sm text-muted-foreground transition-colors group-hover:text-foreground">
            Rechercher une page, une action…
          </span>
          <kbd className="hidden shrink-0 rounded-md border border-surface-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground transition-colors group-hover:border-primary/30 group-hover:text-foreground sm:inline-block">
            Ctrl K
          </kbd>
        </button>

        <CabinetSelector />

        <div className="ml-auto flex items-center gap-1.5 md:gap-2">
          <Badge variant="outline" className={cn('hidden gap-1.5 border sm:inline-flex', couleurRole)}>
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            {roleLibelle}
          </Badge>

          <Badge variant="neutral" className="hidden gap-1.5 lg:inline-flex">
            <CalendarDays className="h-3.5 w-3.5" aria-hidden />
            {aujourdhui}
          </Badge>

          <ThemeToggle />

          {/* Notifications : endpoint backend absent, état vide documenté. */}
          <div className="relative" ref={refNotif}>
            <button
              type="button"
              onClick={() => setNotifOuvert((v) => !v)}
              aria-haspopup="dialog"
              aria-expanded={notifOuvert}
              aria-label="Notifications"
              className="focus-ring rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Bell className="h-4.5 w-4.5" aria-hidden />
            </button>

            {notifOuvert && (
              <div
                role="dialog"
                aria-label="Notifications"
                className="floating-panel absolute right-0 top-full z-50 mt-2 w-72 animate-in fade-in slide-in-from-top-2 rounded-xl2 p-4 duration-150"
              >
                <p className="text-sm font-semibold">Notifications</p>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  Aucune notification — le module n'est pas encore disponible.
                </p>
                <p className="mt-1 font-mono text-[10px] text-muted-foreground/70">
                  TODO(backend): GET /notifications
                </p>
              </div>
            )}
          </div>

          {/* Bloc utilisateur : cliquable, ouvre le menu de compte. */}
          <div className="relative" ref={refMenu}>
            <button
              type="button"
              onClick={() => setMenuOuvert((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOuvert}
              aria-label={`Compte — ${nomComplet}, ${roleLibelle}`}
              className="focus-ring group flex items-center gap-2 rounded-full border border-transparent py-1 pl-1 pr-2 transition-all duration-150 hover:border-primary/30 hover:bg-surface-hover md:border-l md:border-border md:pl-3 md:pr-3"
            >
              <span className="transition-transform duration-150 group-hover:scale-105">
                <Avatar initials={initiales(profil?.prenom, profil?.nom)} />
              </span>
              <div className="hidden min-w-0 text-left md:block">
                <p className="max-w-[9rem] truncate text-xs font-semibold leading-tight">
                  {nomComplet}
                </p>
                <p className="max-w-[9rem] truncate text-[11px] leading-tight text-muted-foreground">
                  {roleLibelle}
                </p>
              </div>
              <ChevronDown
                className={cn(
                  'hidden h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 md:block',
                  menuOuvert && 'rotate-180',
                )}
                aria-hidden
              />
            </button>

            {menuOuvert && (
              <div
                role="menu"
                aria-label="Menu du compte"
                className="floating-panel absolute right-0 top-full z-50 mt-2 w-60 animate-in fade-in slide-in-from-top-2 overflow-hidden rounded-xl2 p-1.5 duration-150"
              >
                <div className="border-b border-border px-3 py-2.5">
                  <p className="truncate text-sm font-semibold">{nomComplet}</p>
                  <p className="truncate text-[11px] text-muted-foreground">{profil?.email}</p>
                </div>
                {entreesMenu.map(({ libelle, icone: Icone, action, danger }) => (
                  <button
                    key={libelle}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOuvert(false)
                      action()
                    }}
                    className={cn(
                      'focus-ring flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-100',
                      danger
                        ? 'text-danger hover:bg-danger/10'
                        : 'text-foreground hover:bg-surface-hover',
                    )}
                  >
                    <Icone className="h-4 w-4 shrink-0" aria-hidden />
                    {libelle}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </header>

      {paletteOuverte && <CommandPalette onClose={() => setPaletteOuverte(false)} />}
    </>
  )
}