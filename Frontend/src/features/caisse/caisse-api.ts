import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import type {
  ClotureCaissePayload,
  OuvertureCaissePayload,
  PaiementCaisse,
  SessionCaisse,
} from './types'

/**
 * Caisse et clôture — branché sur l'API réelle.
 *
 * Le journal des encaissements reste ailleurs (`/journal-caisse`) : il liste les
 * paiements tous sites confondus. Cette API sert à autre chose : répondre à « la
 * caisse est-elle ouverte ? » et « qu'a donné la journée ? ».
 */

export const caisseApi = {
  /** Session ouverte, ou `null` si le tiroir est fermé. */
  sessionCourante: (cabinetId: string) => {
    return api.get<SessionCaisse | null>('/caisse/session-courante', {
      params: { cabinet_id: cabinetId },
    })
  },

  historique: (cabinetId: string, statut?: string) => {
    // Reponse enveloppe `APIResponse` : sans le `.data` cote appelant, l'historique
    // des journees s'affichait vide.
    return api.get<ApiReponse<SessionCaisse[]>>('/caisse/sessions', {
      params: { cabinet_id: cabinetId, statut: statut || undefined },
    })
  },

  /**
   * Ouvre le tiroir en annonçant les espèces dont le caissier dispose.
   *
   * Ce dépôt lui appartient : il est memorandum du début et de la fin, jamais
   * compté comme recette. C'est pour cela qu'on le demande à l'ouverture et non
   * à la clôture.
   */
  ouvrir: (payload: OuvertureCaissePayload) => {
    return api.post<SessionCaisse>('/caisse/sessions', payload)
  },

  /**
   * Clôture : fige les totaux par mode et calcule l'écart d'espèces.
   *
   * L'écart n'est pas une faute, c'est un fait. Le motif est donc facultatif —
   * forcer un caissier à inventer une explication serait pire que de laisser
   * la case vide.
   */
  cloturer: (sessionId: string, payload: ClotureCaissePayload) => {
    return api.post<SessionCaisse>(`/caisse/sessions/${sessionId}/cloture`, payload)
  },

  paiements: (sessionId: string) => {
    return api.get<PageReponse<PaiementCaisse>>(`/caisse/sessions/${sessionId}/paiements`, {
      // 100 : c'est le plafond de pagination du serveur. Au-delà, la requête
      // est refusée alors même qu'elle a l'air légitime.
      params: { limit: 100 },
    })
  },

  /**
   * Encaissements qui n'appartiennent à aucune session — les paiements
   * antérieurs au déploiement des sessions. On les liste plutôt que de les
   * cacher : une somme qui n'entre dans aucune clôture est une somme dont personne
   * ne répond.
   */
  paiementsHorsSession: (cabinetId: string) => {
    return api.get<PageReponse<PaiementCaisse>>('/caisse/paiements-hors-session', {
      params: { cabinet_id: cabinetId },
    })
  },
}
