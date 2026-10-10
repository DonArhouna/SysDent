import {
  Building2,
  FileCheck,
  LayoutDashboard,
  MessageSquare,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

/**
 * SOURCE UNIQUE de la navigation (sidebar + futurs menus) — copiée du client.
 *
 * Quand un module gagne sa page, on renseigne simplement `href` : l'élément
 * devient cliquable automatiquement (sans href, il reste inerte — jamais de
 * 404 en cours de développement).
 */
export interface EntreeNavigation {
  label: string
  href?: string
  icon: LucideIcon
  /** Permission plateforme minimale pour afficher l'entrée (le backend reste garant). */
  permission?: string
}

export interface SectionNavigation {
  titre: string
  items: EntreeNavigation[]
}

export const NAVIGATION: SectionNavigation[] = [
  {
    titre: 'Pilotage',
    items: [
      {
        label: 'Tableau de bord',
        href: '/dashboard',
        icon: LayoutDashboard,
        permission: 'PLATEFORME:DASHBOARD:READ',
      },
    ],
  },
  {
    titre: 'Cabinets',
    items: [
      {
        label: 'Cabinets',
        href: '/cabinets',
        icon: Building2,
        permission: 'PLATEFORME:COMPTES:READ',
      },
    ],
  },
  {
    titre: 'Administration',
    items: [
      {
        label: 'Rôles & Permissions',
        icon: ShieldCheck,
      },
      {
        label: 'Annonces',
        icon: MessageSquare,
      },
      {
        label: 'Journal d’audit',
        icon: FileCheck,
      },
    ],
  },
]
