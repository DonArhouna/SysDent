import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { Avatar, initiales } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/layout/theme-toggle'
import { CabinetSelector } from '@/components/layout/cabinet-selector'
import { useAuthStore } from '@/stores/auth-store'

/** Libellé court des rôles backend (matrice RBAC, cf. src/common/permissions.py). */
const LIBELLES_ROLES: Record<string, string> = {
  ADMIN_CABINET: 'Administrateur Système',
  SUPER_ADMIN: 'Super Admin Plateforme',
  PRATICIEN: 'Praticien',
  ASSISTANT: 'Assistant Dentaire',
  SECRETAIRE: 'Secrétariat',
  COMPTABLE: 'Comptable',
  GESTIONNAIRE_STOCK: 'Gestionnaire de Stock',
}

/** Couleur du badge de rôle (tokens uniquement, AA sur les 2 thèmes). */
const COULEURS_ROLES: Record<string, { badge: string; pastille: string }> = {
  SUPER_ADMIN: {
    badge: 'border-danger/40 bg-danger/10 text-danger',
    pastille: 'bg-danger text-white',
  },
  ADMIN_CABINET: {
    badge: 'border-primary/40 bg-primary/10 text-primary',
    pastille: 'bg-primary text-primary-foreground',
  },
  PRATICIEN: {
    badge: 'border-accent-purple/40 bg-accent-purple/10 text-accent-purple',
    pastille: 'bg-accent-purple text-white',
  },
  COMPTABLE: {
    badge: 'border-accent-green/40 bg-accent-green/10 text-accent-green',
    pastille: 'bg-accent-green text-white',
  },
  SECRETAIRE: {
    badge: 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue',
    pastille: 'bg-accent-blue text-white',
  },
  ASSISTANT: {
    badge: 'border-accent-orange/40 bg-accent-orange/10 text-accent-orange',
    pastille: 'bg-accent-orange text-white',
  },
  GESTIONNAIRE_STOCK: {
    badge: 'border-warning/40 bg-warning/10 text-warning',
    pastille: 'bg-warning text-white',
  },
}

/**
 * Navbar flottante (refonte visuelle 2026-10) : panneau détaché arrondi
 * (.floating-panel), recherche globale `Ctrl/⌘ + K`, badge de rôle coloré,
 * sélecteur de cabinet, bascule de thème, notifications et profil.
 *
 * Notifications : le backend n'expose pas encore d'endpoint (`/notifications`
 * absent — cf. PLAN_RESTE_A_FAIRE.md). Le panneau affiche un état vide propre
 * plutôt qu'un faux flux : aucune donnée inventée.
 */
export function Topbar({
  onToggleSidebar,
  collapsed,
  mode = 'rail',
}: {
  onToggleSidebar: () => void
  collapsed: boolean
  /**
   * < lg le bouton pilote le drawer superposé, ≥ lg le rail replié.
   * Le libellé accessible doit décrire l'action réelle, pas le repli.
   */
  mode?: 'rail' | 'drawer'
}) {
  const profil = useAuthStore((etat) => etat.profil)
  const naviguer = useNavigate()
  const nomComplet = profil ? `${profil.prenom} ${profil.nom}`.trim() : '—'
  const roleLibelle = profil ? (LIBELLES_ROLES[profil.role] ?? profil.role) : '—'
  const refRecherche = useRef<HTMLInputElement>(null)
  const [notifOuvert, setNotifOuvert] = useState(false)

  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        refRecherche.current?.focus()
      }
    }
    window.addEventListener('keydown', surTouche)
    return () => window.removeEventListener('keydown', surTouche)
  }, [])

  // Fermeture du panneau de notifications au clic extérieur.
  const refNotif = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!notifOuvert) return
    const surClicExt = (e: MouseEvent) => {
      if (refNotif.current && !refNotif.current.contains(e.target as Node)) {
        setNotifOuvert(false)
      }
    }
    document.addEventListener('mousedown', surClicExt)
    return () => document.removeEventListener('mousedown', surClicExt)
  }, [notifOuvert])

  const surRecherche = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const q = refRecherche.current?.value.trim()
    if (!q) return
    naviguer(`/patients?q=${encodeURIComponent(q)}`)
  }

  const aujourdhui = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  const couleurRole = COULEURS_ROLES[profil?.role ?? ''] ?? {
    badge: 'border-border bg-muted text-foreground',
    pastille: 'bg-primary text-primary-foreground',
  }

  return (
    <header className="floating-panel flex h-16 shrink-0 items-center gap-2 rounded-xl2 px-3 md:gap-3 md:px-4">
      <Button
        variant="ghost"
        size="icon"
        aria-label={
          mode === 'drawer'
            ? 'Ouvrir le menu de navigation'
            : collapsed
              ? 'Déplier le menu'
              : 'Replier le menu'
        }
        aria-expanded={mode === 'drawer' ? undefined : !collapsed}
        aria-controls={mode === 'drawer' ? 'menu-navigation-mobile' : undefined}
        onClick={onToggleSidebar}
      >
        {mode === 'drawer' || collapsed ? <ChevronsRight /> : <ChevronsLeft />}
      </Button>

      {/* Recherche globale : Ctrl/⌘+K, Entrée => patients filtrés */}
      <form onSubmit={surRecherche} className="contents">
        <div className="hidden h-10 w-full max-w-sm items-center gap-2 rounded-full border border-surface-border bg-background/60 px-4 transition-shadow focus-within:ring-2 focus-within:ring-ring/50 md:flex">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <input
            ref={refRecherche}
            type="search"
            placeholder="Rechercher patient, acte, facture…"
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            aria-label="Recherche globale"
          />
          <kbd className="rounded-md border border-surface-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            Ctrl K
          </kbd>
        </div>
      </form>

      {/* Sélecteur de cabinet multi-site */}
      <CabinetSelector />

      <div className="ml-auto flex items-center gap-1.5 md:gap-2">
        {/* Rôle courant : badge coloré par rôle */}
        <Badge variant="outline" className={`hidden gap-1.5 border sm:inline-flex ${couleurRole.badge}`}>
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
          {roleLibelle}
        </Badge>

        {/* Date du jour */}
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
            className="focus-ring relative rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Bell className="h-4.5 w-4.5" aria-hidden />
          </button>

          {notifOuvert && (
            <div
              role="dialog"
              aria-label="Notifications"
              className="floating-panel absolute right-0 top-full z-50 mt-2 w-72 rounded-xl2 p-4"
            >
              <p className="text-sm font-semibold">Notifications</p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                Aucune notification — le module n'est pas encore disponible.
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground/70">
                // TODO(backend): endpoint manquant – GET /notifications (flux utilisateur)
              </p>
            </div>
          )}
        </div>

        {/* Bloc utilisateur */}
        <div className="flex items-center gap-2 border-l border-border pl-2 md:pl-3">
          <span
            aria-hidden
            className={`hidden h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold sm:flex ${couleurRole.pastille}`}
          >
            {roleLibelle.slice(0, 2).toUpperCase()}
          </span>
          <Avatar initials={initiales(profil?.prenom, profil?.nom)} />
          <div className="hidden text-right md:block">
            <p className="text-xs font-semibold leading-tight">{nomComplet}</p>
            <p className="text-[11px] leading-tight text-muted-foreground">{roleLibelle}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
