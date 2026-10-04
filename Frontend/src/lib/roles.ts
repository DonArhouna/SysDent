/**
 * Libellés des rôles — source unique.
 *
 * Le rôle est un ENUM technique (`ADMIN_CABINET`) : l'afficher tel quel dans
 * l'interface donne « ADMIN_CABINET • Cabinet rattaché » au bas de la sidebar,
 * ce qui n'apprend rien au secrétariat. Le libellé français vit ici, et les
 * deux endroits qui l'affichent (sidebar, navbar) le prennent.
 *
 * `ADMIN_CABINET` est l'administrateur **du cabinet**, pas un administrateur
 * de la plateforme — ce dernier rôle est `SUPER_ADMIN`. Présenter un directeur
 * de clinique comme un administrateur système, dans une application qui porte
 * des données de santé, affiche le mauvais niveau d'autorité.
 */

export const LIBELLES_ROLES: Record<string, string> = {
  ADMIN_CABINET: 'Administrateur de cabinet',
  SUPER_ADMIN: 'Super Administrateur',
  PRATICIEN: 'Praticien',
  ASSISTANT: 'Assistant Dentaire',
  SECRETAIRE: 'Secrétariat',
  COMPTABLE: 'Comptable',
  GESTIONNAIRE_STOCK: 'Gestionnaire de Stock',
}

/** Libellé lisible d'un rôle, avec repli sur la valeur brute si inconnue. */
export function libelleRole(role: string | null | undefined): string {
  if (!role) return '—'
  return LIBELLES_ROLES[role] ?? role
}

/** Couleur du badge de rôle (tokens uniquement, AA sur les deux thèmes). */
export const COULEURS_ROLES: Record<string, string> = {
  SUPER_ADMIN: 'border-danger/40 bg-danger/10 text-danger',
  ADMIN_CABINET: 'border-primary/40 bg-primary/10 text-primary',
  PRATICIEN: 'border-accent-purple/40 bg-accent-purple/10 text-accent-purple',
  COMPTABLE: 'border-accent-green/40 bg-accent-green/10 text-accent-green',
  SECRETAIRE: 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue',
  ASSISTANT: 'border-accent-orange/40 bg-accent-orange/10 text-accent-orange',
  GESTIONNAIRE_STOCK: 'border-warning/40 bg-warning/10 text-warning',
}