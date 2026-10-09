import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CodesSecoursPage } from '@/features/auth/codes-secours-page'
import { ConnexionEtabliePage } from '@/pages/connexion-etablie'
import type { ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

/**
 * La regeneration des codes de secours.
 *
 * Ce que les tests du store ne prouve pas : que la banniere n'apparait QUE si
 * le serveur le signale, qu'elle mene bien a l'ecran, que l'ecran envoie le
 * corps attendu (`code` + `motif`), et que les dix nouveaux codes ne se relisent
 * pas apres coup. Un ecran qui compile et n'appelle rien est la panne la plus
 * discrete d'un front — ici, elle laisserait un compte sans sauvegarde en croyant
 * l'avoir.
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

const profil = (aRegenerer: boolean) =>
  ({
    success: true,
    data: {
      id: 'u1',
      email: 'a@b.fr',
      prenom: 'A',
      nom: 'B',
      roles: [],
      permissions: [],
      deux_facteurs_actif: true,
      codes_secours_a_regenerer: aRegenerer,
    },
  }) as unknown as ApiReponse<never>

const regeneration = {
  success: true,
  data: { codes_secours: ['AAAA1111', 'BBBB2222', 'CCCC3333'] },
} as unknown as ApiReponse<never>

function afficher(ecran: 'tableau' | 'regeneration') {
  const Composant = ecran === 'tableau' ? ConnexionEtabliePage : CodesSecoursPage
  return render(
    <MemoryRouter>
      <Composant />
    </MemoryRouter>,
  )
}

describe('regeneration des codes de secours', () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: 'session-1',
      refreshToken: 'refresh-1',
      profil: null,
      challenge2fa: null,
      jetonEnrolement: null,
      preparation2fa: null,
    })
    post.mockReset()
    get.mockReset()
    navigate.mockReset()
  })

  it("la banniere n'apparait que si le serveur le signale, et mene a l'ecran", async () => {
    get.mockResolvedValue(profil(true))
    afficher('tableau')

    // Le profil arrive par la requete que la page impose au montage : sans elle,
    // un profil conserve en memoire deciderait de la banniere a sa place.
    await waitFor(() => expect(get).toHaveBeenCalledWith('/platform/auth/me'))

    const banniere = await screen.findByRole('status')
    expect(banniere).toHaveTextContent(/codes de secours à régénérer/i)

    await userEvent.click(screen.getByRole('button', { name: /Régénérer mes codes/i }))
    expect(navigate).toHaveBeenCalledWith('/codes-secours')
  })

  it("sans l'indicateur, aucune banniere", async () => {
    get.mockResolvedValue(profil(false))
    afficher('tableau')

    await waitFor(() => expect(get).toHaveBeenCalledWith('/platform/auth/me'))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('envoie code + motif, puis affiche les nouveaux codes une seule fois', async () => {
    get.mockResolvedValue(profil(false))
    post.mockResolvedValue(regeneration)
    afficher('regeneration')

    await userEvent.type(screen.getByLabelText(/6 chiffres/i), '123456')
    await userEvent.type(screen.getByLabelText(/motif/i), 'Téléphone perdu')
    await userEvent.click(screen.getByRole('button', { name: /^Régénérer$/i }))

    // Corps verifie des deux cotes : `code` et `motif`, rien d'autre. Un champ
    // absent du backend y serait un 422 sans que rien ne le signale ici.
    expect(post).toHaveBeenCalledWith(
      '/platform/auth/2fa/codes-secours/regenerer',
      { code: '123456', motif: 'Téléphone perdu' },
    )

    expect(await screen.findByText('AAAA1111')).toBeInTheDocument()
    const terminer = screen.getByRole('button', { name: /Terminer/i })
    expect(terminer).toBeDisabled()

    await userEvent.click(screen.getByRole('checkbox'))
    expect(terminer).toBeEnabled()
  })

  it("un refus serveur s'affiche, sans que rien de nouveau paraisse a l'ecran", async () => {
    get.mockResolvedValue(profil(false))
    post.mockRejectedValue(new Error('Code de vérification invalide.'))
    afficher('regeneration')

    await userEvent.type(screen.getByLabelText(/6 chiffres/i), '123456')
    await userEvent.type(screen.getByLabelText(/motif/i), 'Téléphone perdu')
    await userEvent.click(screen.getByRole('button', { name: /^Régénérer$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalide/i)
    expect(screen.queryByText('AAAA1111')).not.toBeInTheDocument()
  })
})
