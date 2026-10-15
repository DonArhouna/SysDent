import { useQuery } from '@tanstack/react-query'

import { api, type PageReponse } from '@/lib/api'
import type { Cabinet } from '@/lib/plateforme'

/**
 * Noms des cabinets, par identifiant.
 *
 * Abonnements et factures ne portent que `tenant_id` : sans ce dictionnaire,
 * l'écran afficherait des UUID. Une page de 100 cabinets suffit à l'échelle
 * actuelle ; au-delà, un identifiant absent s'affiche tronqué plutôt que vide.
 */
export function useNomsCabinets() {
  const requete = useQuery({
    queryKey: ['cabinets', 'noms'],
    queryFn: () => api.get<PageReponse<Cabinet>>('/platform/tenants', { params: { limit: 100 } }),
    staleTime: 5 * 60_000,
  })
  const parId = new Map((requete.data?.items ?? []).map((c) => [c.tenant_id, c.nom]))
  return {
    cabinets: requete.data?.items ?? [],
    nom: (id: string) => parId.get(id) ?? `${id.slice(0, 8)}…`,
  }
}
