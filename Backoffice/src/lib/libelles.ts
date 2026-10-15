import type { StatusTone } from '@/components/ui/status-badge'

/**
 * Libellés et tons des valeurs renvoyées par l'API plateforme.
 *
 * Une valeur inconnue de ces tables s'affiche telle que le serveur l'a nommée,
 * en ton neutre : un statut ajouté côté backend reste visible, il n'est jamais
 * masqué ni réinterprété.
 */
export interface Libelle {
  texte: string
  ton: StatusTone
}

function lire(table: Record<string, Libelle>, valeur: string | null | undefined): Libelle {
  if (!valeur) return { texte: '—', ton: 'neutral' }
  return table[valeur] ?? { texte: valeur, ton: 'neutral' }
}

const STATUTS_CABINET: Record<string, Libelle> = {
  ESSAI: { texte: 'Essai', ton: 'info' },
  ACTIF: { texte: 'Actif', ton: 'success' },
  // « Désactivé » pour l'écran ; le backend nomme cet état SUSPENDU.
  SUSPENDU: { texte: 'Désactivé', ton: 'warning' },
  RESILIE: { texte: 'Résilié', ton: 'danger' },
}
export const statutCabinet = (v?: string | null) => lire(STATUTS_CABINET, v)

const STATUTS_COMPTE: Record<string, Libelle> = {
  ACTIF: { texte: 'Actif', ton: 'success' },
  DESACTIF: { texte: 'Désactivé', ton: 'neutral' },
  VERROUILLE: { texte: 'Verrouillé', ton: 'warning' },
}
export const statutCompte = (v?: string | null) => lire(STATUTS_COMPTE, v)

const STATUTS_ABONNEMENT: Record<string, Libelle> = {
  ESSAI: { texte: 'Essai', ton: 'info' },
  ACTIF: { texte: 'Actif', ton: 'success' },
  SUSPENDU: { texte: 'Suspendu', ton: 'warning' },
  EXPIRE: { texte: 'Expiré', ton: 'danger' },
  RESILIE: { texte: 'Résilié', ton: 'danger' },
}
export const statutAbonnement = (v?: string | null) => lire(STATUTS_ABONNEMENT, v)

const STATUTS_FACTURE: Record<string, Libelle> = {
  BROUILLON: { texte: 'Brouillon', ton: 'neutral' },
  EMISE: { texte: 'Émise', ton: 'info' },
  PAYEE: { texte: 'Payée', ton: 'success' },
  EN_RETARD: { texte: 'En retard', ton: 'warning' },
  ANNULEE: { texte: 'Annulée', ton: 'danger' },
}
export const statutFacture = (v?: string | null) => lire(STATUTS_FACTURE, v)

const TYPES_RDV: Record<string, Libelle> = {
  DEMO: { texte: 'Démonstration', ton: 'purple' },
  INSTALLATION: { texte: 'Installation', ton: 'info' },
  FORMATION: { texte: 'Formation', ton: 'success' },
  SUPPORT: { texte: 'Support', ton: 'warning' },
  COMMERCIAL: { texte: 'Commercial', ton: 'purple' },
  AUTRE: { texte: 'Autre', ton: 'neutral' },
}
export const typeRendezVous = (v?: string | null) => lire(TYPES_RDV, v)
export const TYPES_RENDEZ_VOUS = Object.entries(TYPES_RDV).map(([value, l]) => ({ value, label: l.texte }))

const STATUTS_RDV: Record<string, Libelle> = {
  PLANIFIE: { texte: 'Planifié', ton: 'info' },
  CONFIRME: { texte: 'Confirmé', ton: 'success' },
  EFFECTUE: { texte: 'Effectué', ton: 'neutral' },
  ANNULE: { texte: 'Annulé', ton: 'danger' },
}
export const statutRendezVous = (v?: string | null) => lire(STATUTS_RDV, v)

/** Heure locale « 09:30 ». */
export function heure(valeur: string | null | undefined): string {
  if (!valeur) return '—'
  const d = new Date(valeur)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

const ROLES: Record<string, string> = {
  SUPER_ADMIN_PLATEFORME: 'Super Admin',
  SUPPORT: 'Support',
  FACTURATION: 'Facturation',
  COMMERCIAL: 'Commercial',
  AUDITEUR: 'Auditeur',
}
export function libelleRole(role: string | null | undefined): string {
  if (!role) return '—'
  return ROLES[role] ?? role
}

const PERIODICITES: Record<string, string> = {
  MENSUEL: 'Mensuel',
  ANNUEL: 'Annuel',
  GRATUIT: 'Gratuit',
}
export const libellePeriodicite = (v?: string | null) => (v ? (PERIODICITES[v] ?? v) : '—')

/** Date courte française ; `—` si absente ou illisible. */
export function date(valeur: string | null | undefined): string {
  if (!valeur) return '—'
  const d = new Date(valeur)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

/** Date et heure françaises ; `—` si absente ou illisible. */
export function dateHeure(valeur: string | null | undefined): string {
  if (!valeur) return '—'
  const d = new Date(valeur)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

/** Montant dans sa devise. Le serveur envoie les montants en chaîne décimale. */
export function montant(valeur: string | number | null | undefined, devise = 'XOF'): string {
  const n = typeof valeur === 'string' ? Number(valeur) : valeur
  if (typeof n !== 'number' || !Number.isFinite(n)) return '—'
  try {
    return n.toLocaleString('fr-FR', { style: 'currency', currency: devise, maximumFractionDigits: 0 })
  } catch {
    return `${n.toLocaleString('fr-FR')} ${devise}`
  }
}

/**
 * Message lisible d'une erreur quelconque, **avec le détail du serveur**.
 *
 * « Mot de passe non conforme » seul laisse deviner quelle règle a échoué ; le
 * backend envoie les règles (`details.regles`) ou les champs invalides
 * (`details.errors`) : ils sont ajoutés au message.
 */
export function messageErreur(e: unknown): string {
  if (!(e instanceof Error)) return 'Une erreur est survenue.'
  const details = (e as Error & { details?: Record<string, unknown> }).details
  const precisions: string[] = []
  if (Array.isArray(details?.regles)) precisions.push(...details.regles.map(String))
  if (Array.isArray(details?.errors)) {
    for (const err of details.errors as Array<{ field?: string; message?: string }>) {
      if (err?.message) precisions.push(err.field ? `${err.field} : ${err.message}` : err.message)
    }
  }
  return precisions.length ? `${e.message} ${precisions.join(' ')}` : e.message
}
