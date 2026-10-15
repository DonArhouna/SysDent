import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { CreerCabinetDrawer } from '@/features/cabinets/creer-cabinet-drawer'

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())
const envoyerFichier = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async (o) => ({ ...(await o<typeof import('@/lib/api')>()), api: { post, get }, envoyerFichier }))

/**
 * Logo à la création d'un cabinet : il part APRÈS la création (il faut
 * l'identifiant du cabinet), et un mauvais format est refusé avant l'envoi.
 */
function afficher() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <CreerCabinetDrawer open onClose={() => undefined} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('logo à la création', () => {
  it("envoie le logo après la création du cabinet, avec son identifiant", async () => {
    get.mockResolvedValue({ data: [] })
    post.mockResolvedValue({ data: { tenant: { tenant_id: 'nouveau-1', nom: 'Cabinet Plateau' }, etapes: ['base_creee'], invitation_admin_envoyee: true } })
    envoyerFichier.mockResolvedValue({ data: { logo_url: '/api/v1/logos/nouveau-1?v=1' } })
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:apercu')
    globalThis.URL.revokeObjectURL = vi.fn()
    afficher()

    await userEvent.type(screen.getByLabelText(/Nom du cabinet/), 'Cabinet Plateau')
    await userEvent.upload(screen.getByLabelText('Logo du cabinet'), new File(['png'], 'logo.png', { type: 'image/png' }))
    expect(await screen.findByAltText('Aperçu du logo')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/^Prénom/), 'Awa')
    await userEvent.type(screen.getByLabelText(/^Nom\s*\*?$/), 'Diop')
    await userEvent.type(screen.getByLabelText(/^E-mail/), 'awa@cabinet.sn')
    await userEvent.click(screen.getByRole('button', { name: 'Créer le cabinet' }))

    await waitFor(() => expect(envoyerFichier).toHaveBeenCalledWith('/platform/tenants/nouveau-1/logo', 'fichier', expect.any(File)))
    expect(post.mock.invocationCallOrder[0]).toBeLessThan(envoyerFichier.mock.invocationCallOrder[0])
  }, 15_000)

  it('refuse un format non accepté avant tout envoi', async () => {
    get.mockResolvedValue({ data: [] })
    afficher()
    await userEvent.upload(
      screen.getByLabelText('Logo du cabinet'),
      new File(['<svg/>'], 'logo.svg', { type: 'image/svg+xml' }),
      { applyAccept: false },
    )
    expect(await screen.findByText(/Format non accepté/)).toBeInTheDocument()
    expect(screen.queryByAltText('Aperçu du logo')).not.toBeInTheDocument()
  })
})
