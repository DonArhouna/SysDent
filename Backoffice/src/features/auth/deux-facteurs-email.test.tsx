import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { EnrolementPage } from '@/features/auth/enrolement-page'
import { LoginPage } from '@/features/auth/login-page'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Second facteur par e-mail, en alternative au QR code.
 *
 * Ce qui doit tenir : le code part par la bonne route avec le bon jeton,
 * l'écran ne montre que l'adresse masquée, et le choix « Application » n'est
 * proposé que si le compte en a une.
 */

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())
const navigate = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (importOriginal) => {
  const reel = await importOriginal<typeof import('@/lib/api')>()
  return { ...reel, api: { post, get } }
})

vi.mock('react-router-dom', async (importOriginal) => {
  const reel = await importOriginal<typeof import('react-router-dom')>()
  return { ...reel, useNavigate: () => navigate }
})

const envoi = { success: true, data: { destinataire: 'fa************@gmail.com', expiration_secondes: 300 } }

function etat(partiel: Partial<ReturnType<typeof useAuthStore.getState>>) {
  useAuthStore.setState({
    token: null,
    refreshToken: null,
    profil: null,
    challenge2fa: null,
    jetonEnrolement: null,
    preparation2fa: null,
    methodes2fa: [],
    ...partiel,
  })
}

describe('2FA par e-mail', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
    navigate.mockReset()
    get.mockResolvedValue({
      data: { id: 'u1', email: 'a@b.fr', prenom: 'A', nom: 'B', role: 'SUPER_ADMIN', permissions: [] },
    })
  })

  it("connexion : on bascule sur E-mail, le code part avec le defi, l'adresse est masquee", async () => {
    etat({ challenge2fa: 'defi-1', methodes2fa: ['totp', 'email'] })
    post.mockResolvedValueOnce(envoi)
    render(<MemoryRouter><LoginPage /></MemoryRouter>)

    expect(screen.getByRole('tab', { name: 'Application' })).toHaveAttribute('aria-selected', 'true')
    await userEvent.click(screen.getByRole('tab', { name: 'E-mail' }))
    await userEvent.click(screen.getByRole('button', { name: /envoyer le code par e-mail/i }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/auth/2fa/email', { jeton_challenge: 'defi-1' }),
    )
    expect(await screen.findByRole('status')).toHaveTextContent('fa************@gmail.com')

    post.mockResolvedValueOnce({ success: true, data: { access_token: 'a', refresh_token: 'r' } })
    await userEvent.type(screen.getByLabelText(/code de vérification/i), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Valider' }))
    await waitFor(() =>
      expect(post).toHaveBeenLastCalledWith('/platform/auth/2fa', { jeton_challenge: 'defi-1', code: '123456' }),
    )
  }, 15_000) // parcours long : saturé quand toute la suite tourne

  it("connexion : un compte sans application n'a pas le choix, l'e-mail est direct", () => {
    etat({ challenge2fa: 'defi-1', methodes2fa: ['email'] })
    render(<MemoryRouter><LoginPage /></MemoryRouter>)

    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /envoyer le code par e-mail/i })).toBeInTheDocument()
  })

  it("enrolement : le code part avec le jeton d'enrolement, puis les codes de secours s'affichent", async () => {
    etat({ jetonEnrolement: 'jeton-1', methodes2fa: ['totp', 'email'] })
    render(<MemoryRouter><EnrolementPage /></MemoryRouter>)

    await userEvent.click(screen.getByRole('button', { name: /recevoir un code par e-mail/i }))
    post.mockResolvedValueOnce(envoi)
    await userEvent.click(screen.getByRole('button', { name: /envoyer le code par e-mail/i }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/auth/2fa/activation-email/envoi', {}, { bearer: 'jeton-1' }),
    )

    post.mockResolvedValueOnce({
      success: true,
      data: { access_token: 'a', refresh_token: 'r', codes_secours: ['ABCD2345', 'EFGH6789'] },
    })
    await userEvent.type(screen.getByLabelText(/code reçu par e-mail/i), '654321')
    await userEvent.click(screen.getByRole('button', { name: 'Activer' }))

    await waitFor(() =>
      expect(post).toHaveBeenLastCalledWith(
        '/platform/auth/2fa/activation-email',
        { code: '654321' },
        { bearer: 'jeton-1' },
      ),
    )
    expect(await screen.findByText('ABCD2345')).toBeInTheDocument()
    expect(useAuthStore.getState().token).toBe('a')
    expect(useAuthStore.getState().jetonEnrolement).toBeNull()
  })

  it('un envoi refuse par le serveur reste affiche', async () => {
    etat({ challenge2fa: 'defi-1', methodes2fa: ['email'] })
    post.mockRejectedValueOnce(new Error("L'e-mail n'a pas pu être envoyé."))
    render(<MemoryRouter><LoginPage /></MemoryRouter>)

    await userEvent.click(screen.getByRole('button', { name: /envoyer le code par e-mail/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent("L'e-mail n'a pas pu être envoyé.")
  })
})
