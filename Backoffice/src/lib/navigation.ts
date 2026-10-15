import {
  Activity,
  CalendarDays,
  Building2,
  FileCheck,
  KeyRound,
  LayoutDashboard,
  Megaphone,
  Package,
  Receipt,
  Repeat,
  Users,
  type LucideIcon,
} from 'lucide-react'

import { PERMISSIONS } from '@/lib/plateforme'

/**
 * SOURCE UNIQUE de la navigation (sidebar + palette de commandes).
 *
 * Quand un module gagne sa page, on renseigne simplement `href` : l'élément
 * devient cliquable automatiquement (sans href, il reste inerte — jamais de
 * 404 en cours de développement).
 *
 * Les permissions sont celles du backend (`platform.<ressource>.<action>`) : la
 * table `PERMISSIONS` est la même que celle des gardes de route.
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
      { label: 'Tableau de bord', href: '/dashboard', icon: LayoutDashboard, permission: PERMISSIONS.stats },
      { label: 'Agenda', href: '/agenda', icon: CalendarDays, permission: PERMISSIONS.agendaLire },
      { label: 'Santé du système', href: '/sante', icon: Activity, permission: PERMISSIONS.sante },
    ],
  },
  {
    titre: 'Cabinets',
    items: [
      { label: 'Cabinets', href: '/cabinets', icon: Building2, permission: PERMISSIONS.cabinetsLire },
      { label: 'Abonnements', href: '/abonnements', icon: Repeat, permission: PERMISSIONS.abonnementsLire },
    ],
  },
  {
    titre: 'Offres & facturation',
    items: [
      { label: 'Plans', href: '/plans', icon: Package, permission: PERMISSIONS.plansLire },
      { label: 'Factures', href: '/factures', icon: Receipt, permission: PERMISSIONS.facturationLire },
    ],
  },
  {
    titre: 'Administration',
    items: [
      { label: 'Équipe', href: '/equipe', icon: Users, permission: PERMISSIONS.equipeLire },
      { label: 'Rôles & permissions', href: '/roles', icon: KeyRound, permission: PERMISSIONS.equipeLire },
      { label: 'Journal d’audit', href: '/audit', icon: FileCheck, permission: PERMISSIONS.auditLire },
      { label: 'Annonces', icon: Megaphone },
    ],
  },
]
