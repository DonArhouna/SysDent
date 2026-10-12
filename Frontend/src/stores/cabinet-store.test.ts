import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth-store'
import { useCabinetStore } from '@/stores/cabinet-store'

/**
 * Un profil sans `CABINETS:READ` ne doit pas déclencher l'appel.
 *
 * **Ce que le propriétaire voyait.** Plusieurs `GET /api/v1/cabinets` en 403 à
 * l'ouverture de l'odontogramme, sur un profil praticien restreint. Le tiroir
 * odontogramme n'affiche aucun site : l'appel ne lui servait à rien. Il
 * échouait quand même, et `chargerCabinets` avalait l'erreur en silence - donc
 * l'interface ne montrait rien, mais l'onglet Réseau répétait le 403.
 *
 * **Ce que le test vérifie.** La permission est lue dans le **profil réellement
 * livré par `/auth/me`**, pas dans une liste de rôles écrite ici. Sans elle,
 * aucun appel ne part : pas de 403, pas de bruit.
 */

const get = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (importOriginal) => {
  const reel = await importOriginal<typeof import('@/lib/api')>()
  return { ...reel, api: { get } }
})

function profil(permissions: string[]) {
  useAuthStore.setState({
    token: 'jeton-de-test',
    profil: {
      id: 'u1',
      email: 'praticien@exemple.com',
      prenom: 'P',
      nom: 'R',
      permissions,
    } as never,
  })
}

describe('cabinet-store : permission CABINETS:READ', () => {
  beforeEach(() => {
    get.mockReset()
    useCabinetStore.getState().vider()
  })

  it('n appelle pas /cabinets sans la permission', async () => {
    profil(['PATIENTS:READ', 'ODONTOGRAMME:WRITE'])

    await useCabinetStore.getState().chargerCabinets()

    expect(get).not.toHaveBeenCalled()
    expect(useCabinetStore.getState().cabinets).toEqual([])
  })

  it('appelle /cabinets quand la permission est presente', async () => {
    profil(['PATIENTS:READ', 'CABINETS:READ'])
    get.mockResolvedValue({
      data: [{ id: 'site-1', nom: 'Site', actif: true }],
    })

    await useCabinetStore.getState().chargerCabinets()

    expect(get).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith('/cabinets')
    expect(useCabinetStore.getState().cabinets).toHaveLength(1)
  })

  it('un 403 ne se traduit ni par une liste vide trompeuse ni par un rejeu', async () => {
    profil(['CABINETS:READ'])
    get.mockRejectedValue(new Error('403'))

    await useCabinetStore.getState().chargerCabinets()

    // Un seul appel : le client ne rejoue pas un 403, qui est une décision
    // d'autorisation et non une panne passagère.
    expect(get).toHaveBeenCalledTimes(1)
    expect(useCabinetStore.getState().cabinets).toEqual([])
    expect(useCabinetStore.getState().chargement).toBe(false)
  })

  it('sans profil chargé, aucun appel ne part non plus', async () => {
    useAuthStore.setState({ token: null, profil: null })

    await useCabinetStore.getState().chargerCabinets()

    expect(get).not.toHaveBeenCalled()
  })
})