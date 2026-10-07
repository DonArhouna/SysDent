/** Types du module Utilisateurs. */

/**
 * Un compte du cabinet. `role` reprend le nom du rôle RBAC : c'est **le rôle**
 * qui porte les permissions, pas le compte.
 */
export interface Utilisateur {
  id: string
  email: string
  prenom: string
  nom: string
  role: string
  actif: boolean
  telephone?: string | null
  /** Site de rattachement principal. */
  cabinet_id?: string | null
  cabinet_nom?: string | null
  deux_facteurs: boolean
  dernier_login?: string | null
  /**
   * Vrai si le compte porte un profil professionnel (titre, spécialité, numéro
   * d'Ordre). Depuis le découplage, ce profil est **facultatif** : être inscrit à
   * l'Ordre n'est pas une condition pour exercer au cabinet.
   */
  a_profil_professionnel: boolean
  numero_ordre?: string | null
  created_at?: string | null
}

export interface UtilisateurCreate {
  email: string
  prenom: string
  nom: string
  mot_de_passe: string
  role: string
  telephone?: string | null
  cabinet_id?: string | null
}

export type UtilisateurUpdate = Partial<Omit<UtilisateurCreate, 'mot_de_passe'>> & {
  actif?: boolean
}

export interface MotDePasseTemporaire {
  temporaire: string
  avertissement: string
}
