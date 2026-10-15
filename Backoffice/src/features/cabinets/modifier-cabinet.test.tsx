import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import { ModifierCabinetDrawer } from '@/features/cabinets/modifier-cabinet-drawer'
import type { CabinetDetail } from '@/lib/plateforme'

const patch = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api', async (o) => ({ ...(await o<typeof import('@/lib/api')>()), api: { patch } }))

// Les valeurs exactes du cabinet de démonstration réel.
const cabinet = {
  tenant_id: 'f2a2ba81', nom: 'Cabinet Démo SysDent', ville: 'Dakar', pays: 'Sénégal', telephone: null,
  email: 'admin.demo@sysdent.local', statut: 'ACTIF', adresse_siege: null, site_web: null, ninea: null,
} as unknown as CabinetDetail

describe('modifier un cabinet', () => {
  it("enregistre un changement de ville sur le cabinet de démonstration", async () => {
    patch.mockResolvedValue({ data: cabinet })
    const fermer = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ModifierCabinetDrawer cabinet={cabinet} onClose={fermer} onModifie={() => undefined} />
      </QueryClientProvider>,
    )
    const ville = screen.getByLabelText('Ville')
    await userEvent.clear(ville)
    await userEvent.type(ville, 'Thiès')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(patch).toHaveBeenCalledWith('/platform/tenants/f2a2ba81', { ville: 'Thiès', motif: null }))
    expect(fermer).toHaveBeenCalled()
  })
})
