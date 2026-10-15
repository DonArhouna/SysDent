import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AgendaPage } from '@/features/agenda/agenda-page'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Agenda de l'éditeur.
 *
 * Ce qui doit tenir : un rendez-vous s'affiche le bon jour de la semaine, la
 * création envoie l'instant en ISO (heure locale convertie), et l'annulation
 * n'a lieu qu'avec un motif.
 */

const get = vi.hoisted(() => vi.fn())
const post = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async (o) => ({ ...(await o<typeof import('@/lib/api')>()), api: { get, post, patch: vi.fn() } }))

function aujourdhuiA(h: number, m = 0): Date {
  const d = new Date()
  d.setHours(h, m, 0, 0)
  return d
}

const rdv = (statut = 'PLANIFIE') => {
  const debut = aujourdhuiA(10)
  return {
    id: 'r1', titre: 'Installation du logiciel', type_rdv: 'INSTALLATION', statut,
    debut: debut.toISOString(), fin: new Date(debut.getTime() + 3600_000).toISOString(), duree_minutes: 60,
    tenant_id: 't1', tenant_nom: 'Cabinet Plateau', prospect_nom: null, contact_nom: 'Dr Diallo',
    contact_email: 'dr@cabinet.sn', contact_telephone: null, lieu: 'Dakar', lien_visio: null,
    agent_id: 'u1', agent_nom: 'Moussa Fall', notes: null, motif_annulation: null, cree_par: 'a@b.sn', contact_prevenu: false,
  }
}

function afficher() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/agenda']}>
        <AgendaPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("agenda de l'éditeur", () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    useAuthStore.setState({
      token: 'jeton',
      profil: {
        id: 'u1', email: 'a@b.sn', prenom: 'Moussa', nom: 'Fall', roles: ['SUPPORT'],
        permissions: ['platform.agenda.read', 'platform.agenda.write', 'platform.tenants.read'],
      },
    })
    get.mockImplementation((chemin: string) =>
      chemin === '/platform/rendez-vous'
        ? Promise.resolve({ items: [rdv()], meta: { page: 1, limit: 100, total_records: 1, total_pages: 1, has_next: false, has_previous: false } })
        : Promise.resolve({ items: [], meta: {}, data: null }),
    )
  })

  it("affiche le rendez-vous dans la semaine, et l'annulation exige un motif", async () => {
    post.mockResolvedValue({ data: { ...rdv('ANNULE'), contact_prevenu: true } })
    afficher()

    const carte = await screen.findByRole('button', { name: /Installation du logiciel/ }, { timeout: 5000 })
    expect(carte).toHaveTextContent('Cabinet Plateau')
    await userEvent.click(carte)

    await userEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    const dialogue = (await screen.findAllByRole('dialog')).at(-1)!
    const confirmer = within(dialogue).getByRole('button', { name: 'Annuler le rendez-vous' })
    expect(confirmer).toBeDisabled()
    await userEvent.type(within(dialogue).getByLabelText(/Motif/), 'Le docteur est en congé')
    await userEvent.click(confirmer)

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/rendez-vous/r1/statut', { statut: 'ANNULE', motif: 'Le docteur est en congé' }),
    )
  }, 15_000)

  it('planifie avec un prospect : heure locale envoyée en ISO', async () => {
    post.mockResolvedValue({ data: { ...rdv(), contact_prevenu: false } })
    afficher()
    await screen.findByRole('button', { name: /Installation du logiciel/ }, { timeout: 5000 })

    await userEvent.click(screen.getByRole('button', { name: 'Nouveau rendez-vous' }))
    const drawer = (await screen.findAllByRole('dialog')).at(-1)!
    await userEvent.type(within(drawer).getByLabelText(/Objet/), 'Démonstration')
    await userEvent.clear(within(drawer).getByLabelText(/^Date/))
    await userEvent.type(within(drawer).getByLabelText(/^Date/), '2026-11-03')
    await userEvent.click(within(drawer).getByLabelText('Un prospect'))
    await userEvent.type(within(drawer).getByLabelText('Nom du prospect'), 'Clinique Les Almadies')
    await userEvent.click(within(drawer).getByRole('button', { name: 'Planifier' }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    const [chemin, corps] = post.mock.calls[0]
    expect(chemin).toBe('/platform/rendez-vous')
    expect(corps).toMatchObject({ titre: 'Démonstration', prospect_nom: 'Clinique Les Almadies', tenant_id: null, agent_id: 'u1' })
    expect(corps.debut).toBe(new Date('2026-11-03T09:00').toISOString())
  }, 15_000)
})
