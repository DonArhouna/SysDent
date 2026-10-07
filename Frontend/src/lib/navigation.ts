import {
  Building2,
  CalendarDays,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Package,
  Pill,
  Receipt,
  ShieldCheck,
  Stethoscope,
  Truck,
  UserRound,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'

/**
 * SOURCE UNIQUE de la navigation (sidebar + futurs menus).
 *
 * Quand un module gagne sa page, on renseigne simplement `href` : l'élément
 * devient cliquable automatiquement (sans href, il reste inerte — jamais de
 * 404 en cours de développement).
 */
export interface EntreeNavigation {
  label: string
  href?: string
  icon: LucideIcon
  /** Permission RBAC minimale pour afficher l'entrée (le backend reste garant). */
  permission?: string
}

export interface SectionNavigation {
  titre: string
  items: EntreeNavigation[]
}

export const NAVIGATION: SectionNavigation[] = [
  {
    titre: 'Tableau de bord',
    items: [{ label: 'Tableau de bord', href: '/dashboard', icon: LayoutDashboard }],
  },
  {
    titre: 'Patients & Soins',
    items: [
      { label: 'Patients', href: '/patients', icon: Users, permission: 'PATIENTS:READ' },
      { label: 'Consultations', href: '/consultations', icon: Stethoscope, permission: 'CONSULTATIONS:READ' },
      { label: 'Odontogramme', href: '/odontogramme', icon: ClipboardList, permission: 'ODONTOGRAMME:READ' },
      { label: 'Ordonnances', href: '/ordonnances', icon: Pill, permission: 'ORDONNANCES:READ' },
    ],
  },
  {
    titre: 'Organisation',
    items: [
      { label: 'Agenda & RDV', href: '/agenda', icon: CalendarDays, permission: 'AGENDA:READ' },
      { label: 'Cabinets', href: '/cabinets', icon: Building2, permission: 'CABINETS:READ' },
      { label: 'Praticiens', href: '/praticiens', icon: Stethoscope, permission: 'PRATICIENS:READ' },
    ],
  },
  {
    titre: 'Finance',
    items: [
      { label: 'Factures', href: '/factures', icon: FileText, permission: 'FACTURATION:READ' },
      { label: 'Caisse', href: '/caisse', icon: Wallet, permission: 'FACTURATION:READ' },
      { label: 'Devis', href: '/devis', icon: Receipt, permission: 'FACTURATION:READ' },
    ],
  },
  {
    titre: 'Stock',
    items: [
      { label: 'Produits', href: '/stock', icon: Package, permission: 'STOCK:READ' },
      { label: 'Commandes', href: '/stock/commandes', icon: Truck, permission: 'STOCK:READ' },
    ],
  },
  {
    titre: 'Administration',
    items: [
      { label: 'Utilisateurs', href: '/utilisateurs', icon: UserRound, permission: 'ADMIN:READ' },
      { label: 'Rôles & Permissions', href: '/rbac', icon: ShieldCheck, permission: 'ADMIN:READ' },
    ],
  },
]
