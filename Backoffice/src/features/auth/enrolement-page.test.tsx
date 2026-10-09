import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { EnrolementPage } from '@/features/auth/enrolement-page'
import type { ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

/**
 * L'écran d'enrôlement.
 *
 * Ce que les tests du store ne prouve pas : que l'écran appelle vraiment le
 * store, affiche le QR, et ne laisse pas valider tant que les codes de secours
 * n'ont pas été copiés. Une page qui n'appelle rien compile, se construit, et
 * ne fait rien - c'est la panne la plus discrète d'un front.
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

const preparation = {
  success: true,
  data: {
    secret: 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP',
    uri: 'otpauth://totp/SysDent:administrateur?secret=JBSWY3DPEHPK3PXP&issuer=SysDent',
    instruction: 'Scannez ce secret avec une application TOTP.',
  },
} as unknown as ApiReponse<never>

const activation = {
  success: true,
  data: {
    access_token: 'acces-1',
    refresh_token: 'refresh-1',
    codes_secours: ['ABCD2345', 'EFGH6789', 'JKMN2345', 'PRST5678'],
  },
} as unknown as ApiReponse<never>

function afficher() {
  return render(
    <MemoryRouter>
      <EnrolementPage />
    </MemoryRouter>,
  )
}

describe("écran d'enrôlement", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: null,
      refreshToken: null,
      profil: null,
      challenge2fa: null,
      jetonEnrolement: 'jeton-1',
      preparation2fa: null,
    })
    post.mockReset()
    get.mockReset()
    navigate.mockReset()
    get.mockResolvedValue({
      data: { id: 'u1', email: 'a@b.fr', prenom: 'A', nom: 'B', role: 'SUPER_ADMIN', permissions: [] },
    })
  })

  it("demande la preparation, puis affiche le QR du secret renvoye", async () => {
    get.mockResolvedValue(preparation)
    afficher()

    await userEvent.click(screen.getByRole('button', { name: /QR code/i }))

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith('/platform/auth/2fa/preparation', { bearer: 'jeton-1' }),
    )
    expect(await screen.findByRole('img', { name: /qr/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/6 chiffres/i)).toBeInTheDocument()
  })

  it('envoie le code saisi, puis exige la copie des codes de secours', async () => {
    get.mockResolvedValue(preparation)
    post.mockResolvedValue(activation)
    afficher()

    await userEvent.click(screen.getByRole('button', { name: /QR code/i }))
    await screen.findByRole('img', { name: /qr/i })

    await userEvent.type(screen.getByLabelText(/6 chiffres/i), '123456')
    await userEvent.click(screen.getByRole('button', { name: /Activer/i }))

    // Le jeton dans les **options**, pas dans le corps : c est la distinction qui
    // a cout deux sessions. `{ code, bearer }` passe le test et part sans
    // en-tete.
    expect(post).toHaveBeenCalledWith(
      '/platform/auth/2fa/activation',
      { code: '123456' },
      { bearer: 'jeton-1' },
    )

    // Les codes sont a l'ecran...
    expect(await screen.findByText('ABCD2345')).toBeInTheDocument()
    // ...et le bouton Terminer reste bloque tant que la case n'est pas cochee.
    const terminer = screen.getByRole('button', { name: /Terminer/i })
    expect(terminer).toBeDisabled()

    await userEvent.click(screen.getByRole('checkbox'))
    expect(terminer).toBeEnabled()
  })

  it("sans jeton d'enrôlement, propose de reprendre l'identification", async () => {
    useAuthStore.setState({ jetonEnrolement: null })
    afficher()

    // La seule action proposee doit etre de reprendre l'identification : c'est
    // le seul iyemin quand le jeton d enrollement n'existe plus.
    await userEvent.click(
      await screen.findByRole('button', { name: /Revenir . la connexion/i }),
    )
    expect(navigate).toHaveBeenCalledWith('/login', { replace: true })
    expect(get).not.toHaveBeenCalled()
  })

  it("un code refusé reste affiché, et ne fait pas perdre le secret scanné", async () => {
    get.mockResolvedValue(preparation)
    post.mockRejectedValue(new Error('Code de vérification invalide.'))
    afficher()

    await userEvent.click(screen.getByRole('button', { name: /QR code/i }))
    await screen.findByRole('img', { name: /qr/i })
    await userEvent.type(screen.getByLabelText(/6 chiffres/i), '000000')
    await userEvent.click(screen.getByRole('button', { name: /Activer/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalide/i)
    // Le secret reste affiche : le telephone n'a pas change, seule la saisie etait
    // fausse. Regenerer le secret enverrait vers un code impossible a produire.
    expect(screen.getByRole('img', { name: /qr/i })).toBeInTheDocument()
  })
})