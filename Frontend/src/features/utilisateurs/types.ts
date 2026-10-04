/**
 * Types du module Utilisateurs.
 *
 * ⚠️ Contrat PROPOSÉ, aligné sur les conventions déjà en place dans le backend
 * (`Utilisateur` existe comme modèle ; il n'est simplement exposé par aucune
 * route). Voir `services/utilisateurs-api.ts` et PLAN_RESTE_A_FAIRE.md.
 *
 * `role` reprend l'énumération du RBAC — un compte sans rôle n'a aucun accès,
 * et c'est le rôle qui porte les permissions.
 */

export interface Utilisateur {
  id: string
  email: string
  prenom: string
  nom: string
  role: string
  actif: boolean
  telephone?: string | null
  /** Cabinet de rattachement. `null` pour un compte de plateforme. */
  cabinet_id?: string | null
  derniere_connexion?: string | null
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

export type UtilisateurUpdate = Partial<Omit<UtilisateurCreate, 'mot_de_passe'>>
