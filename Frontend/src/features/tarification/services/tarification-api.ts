import { api, type ApiReponse, type PageReponse } from '@/lib/api'

import type {
  ActeCreate,
  ActeNomenclature,
  ActeUpdate,
  CategoriePatient,
  DroitCreate,
  DroitPriseEnCharge,
  DroitUpdate,
  OrganismeAssurance,
  OrganismeCreate,
  OrganismeUpdate,
  TarifActe,
  TarifUpsert,
} from '../types'

/**
 * Client de la tarification et de la prise en charge.
 *
 * **Les filtres partent dans l'URL de la requete**, jamais dans un tri fait
 * cote client. Trier une page de 50 apres coup donne une page de 3 et un total
 * faux : l'ecran affiche « 3 resultats » alors que la liste en compte 400.
 *
 * **Aucun repli fictif.** Un endpoint en erreur remonte une erreur. Une liste
 * vide est vraie ; une liste inventee est un mensonge qui persiste jusqu'au
 * rechargement.
 */

export const TARIFICATION_BASE = '/tarification'

type ParamsListe = {
  page?: number
  limit?: number
}

export const tarificationApi = {
  // ------------------------------------------------------------------ Actes

  listerActes: (params: ParamsListe & { q?: string; categorie?: string; actif?: boolean }) => {
    const query = new URLSearchParams()
    if (params.q) query.set('q', params.q)
    if (params.categorie) query.set('categorie', params.categorie)
    if (params.actif !== undefined) query.set('actif', String(params.actif))
    query.set('page', String(params.page ?? 1))
    query.set('limit', String(params.limit ?? 20))
    return api.get<PageReponse<ActeNomenclature>>(`${TARIFICATION_BASE}/actes?${query}`)
  },

  creerActe: (corps: ActeCreate) =>
    api.post<ApiReponse<ActeNomenclature>>(`${TARIFICATION_BASE}/actes`, corps),

  modifierActe: (acteId: string, corps: ActeUpdate) =>
    api.patch<ApiReponse<ActeNomenclature>>(`${TARIFICATION_BASE}/actes/${acteId}`, corps),

  // ----------------------------------------------------------------- Tarifs

  listerTarifsActe: (acteId: string, params: ParamsListe = {}) => {
    const query = new URLSearchParams()
    query.set('page', String(params.page ?? 1))
    query.set('limit', String(params.limit ?? 50))
    return api.get<PageReponse<TarifActe>>(`${TARIFICATION_BASE}/actes/${acteId}/tarifs?${query}`)
  },

  definirTarif: (acteId: string, corps: TarifUpsert) =>
    api.put<ApiReponse<TarifActe>>(`${TARIFICATION_BASE}/actes/${acteId}/tarifs`, corps),

  supprimerTarif: (acteId: string, tarifId: string) =>
    api.delete<void>(`${TARIFICATION_BASE}/actes/${acteId}/tarifs/${tarifId}`),

  // ------------------------------------------------------------- Categories

  listerCategories: (params: ParamsListe = {}) => {
    const query = new URLSearchParams()
    query.set('page', String(params.page ?? 1))
    query.set('limit', String(params.limit ?? 100))
    return api.get<PageReponse<CategoriePatient>>(`${TARIFICATION_BASE}/categories?${query}`)
  },

  creerCategorie: (corps: { code: string; libelle: string; ordre: number }) =>
    api.post<ApiReponse<CategoriePatient>>(`${TARIFICATION_BASE}/categories`, corps),

  modifierCategorie: (code: string, corps: { libelle?: string; ordre?: number }) =>
    api.patch<ApiReponse<CategoriePatient>>(`${TARIFICATION_BASE}/categories/${code}`, corps),

  supprimerCategorie: (code: string) =>
    api.delete<void>(`${TARIFICATION_BASE}/categories/${code}`),

  // ------------------------------------------------------------ Organismes

  listerOrganismes: (
    params: ParamsListe & { q?: string; type_organisme?: string; actif?: boolean } = {},
  ) => {
    const query = new URLSearchParams()
    if (params.q) query.set('q', params.q)
    if (params.type_organisme) query.set('type_organisme', params.type_organisme)
    if (params.actif !== undefined) query.set('actif', String(params.actif))
    query.set('page', String(params.page ?? 1))
    query.set('limit', String(params.limit ?? 20))
    return api.get<PageReponse<OrganismeAssurance>>(`${TARIFICATION_BASE}/organismes?${query}`)
  },

  creerOrganisme: (corps: OrganismeCreate) =>
    api.post<ApiReponse<OrganismeAssurance>>(`${TARIFICATION_BASE}/organismes`, corps),

  modifierOrganisme: (organismeId: string, corps: OrganismeUpdate) =>
    api.patch<ApiReponse<OrganismeAssurance>>(
      `${TARIFICATION_BASE}/organismes/${organismeId}`,
      corps,
    ),

  supprimerOrganisme: (organismeId: string) =>
    api.delete<void>(`${TARIFICATION_BASE}/organismes/${organismeId}`),

  // ---------------------------------------------------------------- Droits

  listerDroitsPatient: (patientId: string, params: ParamsListe = {}) => {
    const query = new URLSearchParams()
    query.set('page', String(params.page ?? 1))
    query.set('limit', String(params.limit ?? 50))
    return api.get<PageReponse<DroitPriseEnCharge>>(
      `${TARIFICATION_BASE}/patients/${patientId}/droits?${query}`,
    )
  },

  creerDroit: (patientId: string, corps: DroitCreate) =>
    api.post<ApiReponse<DroitPriseEnCharge>>(
      `${TARIFICATION_BASE}/patients/${patientId}/droits`,
      corps,
    ),

  modifierDroit: (droitId: string, corps: DroitUpdate) =>
    api.patch<ApiReponse<DroitPriseEnCharge>>(`${TARIFICATION_BASE}/droits/${droitId}`, corps),

  supprimerDroit: (droitId: string) => api.delete<void>(`${TARIFICATION_BASE}/droits/${droitId}`),
}