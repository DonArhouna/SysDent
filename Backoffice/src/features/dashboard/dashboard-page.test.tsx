import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DashboardPage } from '@/features/dashboard/dashboard-page'
import { ApiError } from '@/lib/api'
import type { ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Le tableau de bord.
 *
 * Ce que ces tests doivent prouver, et que la compilation ne prouve pas :
 *
 * - **le total et la part sans base sont deux nombres distincts a l'ecran** ;
 * - **une panne n'est jamais un zero** : pas de « 0 cabinet », pas de « aucune
 *   donnee », un message et un bouton « Reessayer » qui redemande ;
 * - la banniere des codes de secours n'apparait que si le serveur le signale ;
 * - **un seul appel** : quatre requetes pour quatre cartes payeraient quatre
 *   fois la latence d'une agregation serveur.
 */

const get = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (importOriginal) => {
  const reel = await importOriginal<typeof import('@/lib/api')>()
  return { ...reel, api: { get } }
})

const vue = {
  total_cabinets: 12,
  total_bases_absentes: 3,
  par_statut: { ACTIVE: 12 },
  par_statut_base: { ACTIVE: { total: 12, dont_base_absente: 3 } },
  par_formule: { PRO: 9 },
  nouveaux_30j: 2,
  essais_restants_jours: 14,
  essais_proches_expiration: [],
  proches_du_quota: [],
  inactifs_30j: [],
  sante: { statut: 'ok' },
  annonces: [],
  audit: [],
}

function repondre(donnees: unknown) {
  get.mockResolvedValue({ data: donnees } as ApiReponse<never>)
}

function afficher() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

function profil(aRegenerer: boolean) {
  useAuthStore.setState({
    profil: {
      id: 'u1',
      email: 'a@b.fr',
      prenom: 'A',
      nom: 'B',
      role: 'SUPER_ADMIN',
      permissions: [],
      codes_secours_a_regenerer: aRegenerer,
    },
  })
}

describe('tableau de bord', () => {
  beforeEach(() => {
    get.mockReset()
    profil(false)
    repondre(vue)
  })

  it('affiche le total et la part sans base comme deux nombres distincts', async () => {
    afficher()

    await waitFor(() => expect(screen.getByText('3 sans base')).toBeTruthy())

    // « 12 » apparait deux fois : total general, puis total du statut ACTIVE.
    // C'est le comportement voulu - les deux cartes sont distinctes. On
    // verifie qu'il y en a bien deux, et non pas qu'il n'y en a aucune.
    expect(screen.getAllByText('12', { exact: true }).length).toBe(2)
    expect(screen.getByText('3 sans base')).toBeTruthy()
    // Un compte qui n'indique pas l'absence de base serait le mensonge que ce
    // tableau de bord existe pour eviter. « 9 » serait le total des cabinets
    // qui fonctionnent : il n'est affiche nulle part.
    expect(screen.queryByText('9')).toBeNull()
  })

  it('ne fait qu un seul appel', async () => {
    afficher()

    await waitFor(() => expect(screen.getByText('3 sans base')).toBeTruthy())
    expect(get).toHaveBeenCalledTimes(1)
    expect(get.mock.calls[0][0]).toBe('/platform/stats/dashboard')
  })

  it('une panne affiche un message et Reessayer, jamais un zero', async () => {
    get.mockRejectedValue(new ApiError('Service indisponible', 'SERVICE_INDISPONIBLE', 503))

    afficher()

    await waitFor(() =>
      expect(
        screen.getByText("Le tableau de bord n'a pas pu être chargé"),
      ).toBeTruthy(),
    )
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeTruthy()
    // Le piege : un ecran qui affiche 0 cabinet pendant une panne affirme que
    // la plateforme est vide. Ce n'est pas la meme information.
    expect(screen.queryByText('0', { exact: true })).toBeNull()
  })

  it('Reessayer redemande les donnees', async () => {
    get.mockRejectedValueOnce(new ApiError('Service indisponible', 'SERVICE_INDISPONIBLE', 503))
    afficher()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Réessayer' })).toBeTruthy(),
    )

    repondre(vue)
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => expect(screen.getByText('3 sans base')).toBeTruthy())
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('une plateforme sans cabinet affiche un etat vide, pas une erreur', async () => {
    repondre({
      ...vue,
      total_cabinets: 0,
      total_bases_absentes: 0,
      par_statut: {},
      par_statut_base: {},
    })

    afficher()

    await waitFor(() => expect(screen.getByText('Aucun cabinet')).toBeTruthy())
    expect(screen.queryByText('Réessayer')).toBeNull()
  })

  it('affiche la banniere des codes de secours quand le serveur la signale', async () => {
    profil(true)

    afficher()

    await waitFor(() =>
      expect(screen.getByText('Codes de secours à régénérer.')).toBeTruthy(),
    )
  })

  it('n affiche pas la banniere quand le serveur ne la signale pas', async () => {
    profil(false)

    afficher()

    await waitFor(() => expect(screen.getByText('3 sans base')).toBeTruthy())
    expect(screen.queryByText('Codes de secours à régénérer.')).toBeNull()
  })

  it('une section sans donnees ne casse pas le reste du tableau de bord', async () => {
    // `sante` vide, listes absentes : le reste doit rester lisible.
    repondre({
      ...vue,
      sante: {},
      annonces: undefined,
      audit: undefined,
      inactifs_30j: undefined,
    })

    afficher()

    await waitFor(() => expect(screen.getByText('3 sans base')).toBeTruthy())
    expect(screen.getAllByText('Non disponible').length).toBeGreaterThan(0)
    expect(screen.getByText('Aucune annonce active.')).toBeTruthy()
  })
})