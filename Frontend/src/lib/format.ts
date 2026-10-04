/**
 * Utilitaires de formatage localisés (Sénégal / UEMOA - Afrique francophone).
 *
 * Règles du CDC :
 * - Montants en FCFA / XOF sans décimales (ex: "15 000 FCFA")
 * - Dates au format jj/mm/aaaa
 * - Heures en format 24h (ex: "14:30")
 */

export function formatFcfa(montant: number | string | null | undefined): string {
  if (montant === null || montant === undefined || montant === '') return '0 FCFA'
  const valeur = typeof montant === 'string' ? parseFloat(montant) : montant
  if (isNaN(valeur)) return '0 FCFA'
  return `${new Intl.NumberFormat('fr-FR', {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  }).format(valeur)} FCFA`
}

export function formatDateFr(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

export function formatDateTimeFr(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '—'
  return `${d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })} à ${d.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })}`
}

export function formatTimeFr(date: string | Date | null | undefined): string {
  if (!date) return '—'
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function calculerAge(dateNaissance: string | Date | null | undefined): string {
  if (!dateNaissance) return '—'
  const naiss = typeof dateNaissance === 'string' ? new Date(dateNaissance) : dateNaissance
  if (isNaN(naiss.getTime())) return '—'
  const diff = Date.now() - naiss.getTime()
  const ageDate = new Date(diff)
  const annees = Math.abs(ageDate.getUTCFullYear() - 1970)
  return `${annees} an${annees > 1 ? 's' : ''}`
}
