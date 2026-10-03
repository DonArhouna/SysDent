import { CalendarDays, ChevronsLeft, ChevronsRight, Search, ShieldCheck } from 'lucide-react'
import { Avatar, initiales } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/layout/theme-toggle'
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

/**
 * Topbar : recherche globale, badge de rôle, date du jour, bascule de thème,
 * profil — mêmes emplacements que la maquette.
 */
export function Topbar({
  onToggleSidebar,
  collapsed,
}: {
  onToggleSidebar: () => void
  collapsed: boolean
}) {
  const profil = useAuthStore((etat) => etat.profil)
  const nomComplet = profil ? `${profil.prenom} ${profil.nom}`.trim() : '—'
  const roleLibelle = profil ? (LIBELLES_ROLES[profil.role] ?? profil.role) : '—'

  const aujourdhui = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur md:px-6">
      <Button
        variant="ghost"
        size="icon"
        aria-label={collapsed ? 'Déplier le menu' : 'Replier le menu'}
        onClick={onToggleSidebar}
      >
        {collapsed ? <ChevronsRight /> : <ChevronsLeft />}
      </Button>

      {/* Recherche globale (raccourci visuel) */}
      <div className="hidden h-9 w-full max-w-md items-center gap-2 rounded-full border border-border bg-card px-3 md:flex">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          type="search"
          placeholder="Rechercher patient, acte, facture..."
          className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          aria-label="Recherche globale"
        />
        <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          Ctrl K
        </kbd>
      </div>

      <div className="ml-auto flex items-center gap-2 md:gap-3">
        {/* Rôle courant */}
        <Badge variant="outline" className="hidden gap-1.5 sm:inline-flex">
          <ShieldCheck className="h-3.5 w-3.5" />
          {roleLibelle}
        </Badge>

        {/* Date du jour */}
        <Badge variant="neutral" className="hidden gap-1.5 lg:inline-flex">
          <CalendarDays className="h-3.5 w-3.5" />
          {aujourdhui}
        </Badge>

        <ThemeToggle />

        <div className="flex items-center gap-2 border-l border-border pl-2 md:pl-3">
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
