// TODO(backend): module Utilisateurs inexistant côté API.
//
// Vérifié le 4 octobre 2026 : `GET /api/v1/openapi.json` ne déclare NI route
// NI schéma `Utilisateur`. Un compte n'est créé qu'implicitement, à la
// provisionnement d'une société (un seul administrateur). Conséquence
// métier : un cabinet ne peut pas ajouter une secrétaire, un comptable ou un
// assistant — donc pas de deuxième praticien sans passer par undeveloppement.
//
// Le contrat ci-dessous est une PROPOSITION, pas un constat : il faut le valider
// avant d'écrire le module backend, sinon l'écran et l'API divergeraient.
// Cf. PLAN_RESTE_A_FAIRE.md (B10 / P0-4).
//
// Aucune donnée fictive n'est exposée tant que l'API n'existe pas : la page
// affiche un état « module indisponible » explicite.
import { api } from '@/lib/api'
import type { Utilisateur, UtilisateurCreate, UtilisateurUpdate } from '../types'

export const utilisateursApi = {
  lister: (params?: { q?: string; role?: string; actif?: boolean; page?: number; limit?: number }) => {
    return api.get<{ items: Utilisateur[]; meta: { total_records: number } }>('/utilisateurs', {
      params,
      silencieux: true,
    })
  },

  creer: (data: UtilisateurCreate) => {
    return api.post<Utilisateur>('/utilisateurs', data, { silencieux: true })
  },

  modifier: (id: string, data: UtilisateurUpdate) => {
    return api.patch<Utilisateur>(`/utilisateurs/${id}`, data, { silencieux: true })
  },

  reinitialiserMotDePasse: (id: string) => {
    return api.post<{ temporaire: string }>(`/utilisateurs/${id}/mot-de-passe`, undefined, {
      silencieux: true,
    })
  },

  desactiver: (id: string) => {
    return api.delete(`/utilisateurs/${id}`, { silencieux: true })
  },
}

/** `true` tant que le module n'existe pas côté API. */
export function estModuleIndisponible(e: unknown): boolean {
  return (
    typeof e === 'object' &&
    e !== null &&
    'status' in e &&
    (e.status === 404 || e.status === 501)
  )
}