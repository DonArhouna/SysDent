import { api, type PageReponse } from '@/lib/api'
import type { MotDePasseTemporaire, Utilisateur, UtilisateurCreate, UtilisateurUpdate } from '../types'

/**
 * Utilisateurs du cabinet — branché sur l'API réelle.
 *
 * `ADMIN:READ/CREATE/UPDATE/DELETE` : les permissions sont vérifiées **par le
 * serveur**. L'écran qui est devant moi n'a aucun moyen d'y échapper, et
 * l'accès direct par URL donne une 403 propre.
 *
 * Un point de vocabulaire, parce qu'il trompe : « supprimer » n'existe pas.
 * `desactiver` coupe l'accès et conserve la trace — une consultation, un acte ou
 * une clôture de caisse référence le compte. Supprimer la ligne effacerait
 * l'auteur d'un acte médical.
 */
export const utilisateursApi = {
  lister: (params?: {
    q?: string
    role?: string
    actif?: boolean
    cabinet_id?: string
    page?: number
    limit?: number
  }) => {
    const query = new URLSearchParams()
    if (params?.q) query.set('q', params.q)
    if (params?.role) query.set('role', params.role)
    if (params?.actif !== undefined) query.set('actif', String(params.actif))
    if (params?.cabinet_id) query.set('cabinet_id', params.cabinet_id)
    query.set('page', String(params?.page ?? 1))
    query.set('limit', String(params?.limit ?? 50))
    return api.get<PageReponse<Utilisateur>>(`/utilisateurs?${query.toString()}`)
  },

  creer: (data: UtilisateurCreate) => api.post<Utilisateur>('/utilisateurs', data),

  modifier: (id: string, data: UtilisateurUpdate) =>
    api.patch<Utilisateur>(`/utilisateurs/${id}`, data),

  /**
   * Réinitialise le mot de passe et rend un mot de passe **temporaire**.
   *
   * Il ne sera plus jamais affiché : le serveur n'en garde que l'empreinte.
   * L'écran doit donc le montrer une fois, clairement, et demander de le
   * communiquer — sinon l'utilisateur croit avoir saisi un mot de passe
   * définitif.
   */
  reinitialiserMotDePasse: (id: string) =>
    api.post<MotDePasseTemporaire>(`/utilisateurs/${id}/mot-de-passe`),

  desactiver: (id: string) => api.delete<Utilisateur>(`/utilisateurs/${id}`),

  revoquerSessions: (id: string) =>
    api.delete<{ revoquees: number }>(`/utilisateurs/${id}/sessions`),
}

/** Rôles système d'un cabinet, dans l'ordre où on les rencontre au quotidien. */
export const ROLES = [
  { value: 'ADMIN_CABINET', label: 'Administrateur du cabinet' },
  { value: 'PRATICIEN', label: 'Médecin (dentiste)' },
  { value: 'SECRETAIRE', label: 'Secrétaire / Assistant(e)' },
  { value: 'ASSISTANT', label: 'Assistant(e) de soins' },
  { value: 'COMPTABLE', label: 'Caissier(ère)' },
  { value: 'GESTIONNAIRE_STOCK', label: 'Gestionnaire de stock' },
] as const

export function libelleRole(nom: string): string {
  return ROLES.find((r) => r.value === nom)?.label ?? nom
}
