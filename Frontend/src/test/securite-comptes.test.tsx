import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { LoginPage } from '@/pages/login'
import { ActivationPage } from '@/pages/activation'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Sécurité des comptes des cabinets : connexion en étapes et activation.
 *
 * Ce qui doit tenir :
 * - aucune session sans étape franchie ;
 * - les codes de secours s'affichent AVANT de quitter l'écran (la session est
 *   déjà ouverte quand ils arrivent) ;
 * - le lien d'activation fixe le mot de passe choisi par la personne.
 */

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (o) => ({ ...(await o<typeof import('@/lib/api')>()), api: { post, get } }))

const profil = { data: { id: 'u1', email: 'chef@cabinet.sn', prenom: 'Awa', nom: 'Ndiaye', role: 'ADMIN_CABINET', permissions: [] } }

function afficher(chemin = '/login') {
  return render(
    <MemoryRouter initialEntries={[chemin]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/activation" element={<ActivationPage />} />
        <Route path="/dashboard" element={<p>tableau de bord</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function seConnecter() {
  await userEvent.type(screen.getByLabelText('Email professionnel'), 'chef@cabinet.sn')
  await userEvent.type(screen.getByLabelText('Mot de passe'), 'Mot-De-Passe-2026!')
  await userEvent.click(screen.getByRole('button', { name: 'Se connecter' }))
}

describe('connexion en étapes', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
    get.mockResolvedValue(profil)
    useAuthStore.setState({ token: null, refreshToken: null, profil: null, etapeConnexion: null })
  })

  it('administrateur : configuration 2FA par e-mail, puis codes de secours AVANT le tableau de bord', async () => {
    post.mockImplementation((chemin: string) => {
      if (chemin === '/auth/login') return Promise.resolve({ data: { etape: 'enrolement_2fa', jeton_etape: 't1.etape', methodes: ['totp', 'email'] } })
      if (chemin === '/auth/etape/code-email') return Promise.resolve({ data: { destinataire: 'ch**@cabinet.sn', expiration_secondes: 300 } })
      if (chemin === '/auth/etape/2fa/activation')
        return Promise.resolve({ data: { etape: 'session', access_token: 'a', refresh_token: 'r', codes_secours: ['ABCD2345', 'EFGH6789'] } })
      return Promise.reject(new Error(chemin))
    })
    afficher()
    await seConnecter()

    expect(await screen.findByText('Sécurisez votre compte')).toBeInTheDocument()
    expect(useAuthStore.getState().token).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: /Recevoir un code par e-mail/ }))
    await userEvent.click(screen.getByRole('button', { name: /Envoyer le code par e-mail/ }))
    expect(await screen.findByRole('status')).toHaveTextContent('ch**@cabinet.sn')
    await userEvent.type(screen.getByLabelText(/^Code de vérification/), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Activer' }))

    expect(await screen.findByText('ABCD2345')).toBeInTheDocument()
    expect(screen.queryByText('tableau de bord')).not.toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/auth/etape/2fa/activation', { jeton_etape: 't1.etape', methode: 'email', code: '123456' })

    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(await screen.findByText('tableau de bord')).toBeInTheDocument()
  }, 15_000) // parcours long : plusieurs écrans successifs

  it('mot de passe temporaire : changement imposé, puis code', async () => {
    post.mockImplementation((chemin: string) => {
      if (chemin === '/auth/login') return Promise.resolve({ data: { etape: 'changement_mot_de_passe', jeton_etape: 't1.mdp' } })
      if (chemin === '/auth/etape/mot-de-passe') return Promise.resolve({ data: { etape: 'deux_facteurs', jeton_etape: 't1.code', methodes: ['totp', 'email'] } })
      if (chemin === '/auth/etape/2fa') return Promise.resolve({ data: { etape: 'session', access_token: 'a', refresh_token: 'r' } })
      return Promise.reject(new Error(chemin))
    })
    afficher()
    await seConnecter()

    expect(await screen.findByText('Choisissez un nouveau mot de passe')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/^Nouveau mot de passe/), 'Nouveau-Secret-2026!')
    await userEvent.type(screen.getByLabelText(/^Confirmer/), 'Nouveau-Secret-2026!')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer et continuer' }))

    expect(await screen.findByText('Vérification en deux étapes')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Application' })).toHaveAttribute('aria-selected', 'true')
    await userEvent.type(screen.getByLabelText(/^Code de vérification/), '654321')
    await userEvent.click(screen.getByRole('button', { name: 'Valider' }))

    expect(await screen.findByText('tableau de bord')).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/auth/etape/2fa', { jeton_etape: 't1.code', code: '654321' })
  }, 15_000)
})

describe("activation d'un compte", () => {
  beforeEach(() => {
    post.mockReset()
    useAuthStore.setState({ token: null, refreshToken: null, profil: null, etapeConnexion: null })
  })

  it('le lien permet de choisir son mot de passe', async () => {
    post.mockImplementation((chemin: string) =>
      chemin === '/auth/activation/verification'
        ? Promise.resolve({ data: { email: 'fatou@cabinet.sn', prenom: 'Fatou', nom: 'Sarr' } })
        : Promise.resolve({ data: null }),
    )
    afficher('/activation?jeton=t1.secret-du-lien')

    expect(await screen.findByText('Fatou')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/^Nouveau mot de passe/), 'Secretariat-2026!')
    await userEvent.type(screen.getByLabelText(/^Confirmer/), 'Secretariat-2026!')
    await userEvent.click(screen.getByRole('button', { name: 'Activer mon compte' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/auth/activation', { jeton: 't1.secret-du-lien', mot_de_passe: 'Secretariat-2026!' }, { silencieux: true }),
    )
    expect(await screen.findByText(/Votre compte est activé/)).toBeInTheDocument()
  })

  it('un lien sans jeton est signalé, sans appel au serveur', async () => {
    afficher('/activation')
    const alerte = await screen.findByRole('alert')
    expect(within(alerte).getByText(/incomplet/)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
})
