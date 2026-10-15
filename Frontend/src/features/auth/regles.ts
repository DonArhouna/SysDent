/** Message lisible d'une erreur, avec les règles renvoyées par le serveur. */
export function messageErreur(e: unknown): string {
  if (!(e instanceof Error)) return 'Une erreur est survenue.'
  const details = (e as Error & { details?: Record<string, unknown> }).details
  const regles = Array.isArray(details?.regles) ? (details.regles as string[]) : []
  return regles.length ? `${e.message} ${regles.join(' ')}` : e.message
}

/**
 * Pré-contrôle de la politique du serveur (12 caractères, majuscule,
 * minuscule, chiffre, caractère spécial, sans reprendre l'adresse e-mail).
 * Le serveur reste juge : ceci évite seulement un aller-retour.
 */
export function reglesManquantes(mdp: string, email = ''): string[] {
  const identifiant = email.split('@')[0]?.toLowerCase() ?? ''
  const regles: Array<[boolean, string]> = [
    [mdp.length >= 12, '12 caractères minimum'],
    [/[A-Z]/.test(mdp), 'une majuscule'],
    [/[a-z]/.test(mdp), 'une minuscule'],
    [/\d/.test(mdp), 'un chiffre'],
    [/[^A-Za-z0-9]/.test(mdp), 'un caractère spécial'],
    [!(identifiant.length >= 3 && mdp.toLowerCase().includes(identifiant)), "sans reprendre l'adresse e-mail"],
  ]
  return regles.filter(([ok]) => !ok).map(([, libelle]) => libelle)
}
