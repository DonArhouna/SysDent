/**
 * Un profil sans droit d'ecriture ne voit aucun bouton qui echouerait, et ne
 * declenche aucun appel mutateur.
 *
 * **Pourquoi tester le composant et non la fonction de permission.** Les deux
 * sont justes, mais une seule des deux tient dans le temps. `possedePermission`
 * ne change pas ; le forgot d'un `&&` autour d'un bouton, si. Ce test monte
 * reellement la page avec un profil limite et compte les requetes emises.
 *
 * **Un 403 n'est pas une erreur de saisie.** Si un bouton s'affiche sans le
 * droit et que l'utilisateur clique, il voit « permission refusee » et conclut
 * que le systeme est en panne. Son profil n'a jamais eu ce droit : l'ecran doit
 * ne rien proposer plutot que proposer et refuser.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TarificationPage } from '@/features/tarification/pages/tarification-page'
import { OrganismesPage } from '@/features/tarification/pages/organismes-page'
import { useAuthStore, type ProfilUtilisateur } from '@/stores/auth-store'

const APPELS: Array<{ methode: string; chemin: string }> = []

vi.mock('@/lib/api', async () => {
  const reel = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...reel,
    api: {
      get: vi.fn((chemin: string) => {
        APPELS.push({ methode: 'GET', chemin })
        // **Une page vide ne prouverait rien pour les colonnes conditionnelles.**
        // Les entetes du tableau sont eux aussi gardes par la permission : avec
        // zero ligne, une garde oubliee resterait invisible. On rend donc une
        // ligne, et la garde se voit.
        return Promise.resolve({
          success: true,
          items: [
            {
              id: 'aaaaaaa1-0000-4000-8000-000000000001',
              code: 'DETART',
              libelle: 'Detartrage monodentaire',
              categorie: 'SOINS',
              tarif_base: '7500.00',
              duree_estimee_min: 15,
              unitaire: true,
              actif: true,
              tarifs: [{ id: 'b', acte_id: 'aaaaaaa1-0000-4000-8000-000000000001', categorie_code: 'standard', montant: '7500.00' }],
            },
          ],
          meta: {
            page: 1,
            limit: 20,
            total_records: 1,
            total_pages: 1,
            has_next: false,
            has_previous: false,
          },
        })
      }),
      post: vi.fn((chemin: string) => {
        APPELS.push({ methode: 'POST', chemin })
        return Promise.resolve({ success: true, data: {} })
      }),
      put: vi.fn((chemin: string) => {
        APPELS.push({ methode: 'PUT', chemin })
        return Promise.resolve({ success: true, data: {} })
      }),
      patch: vi.fn((chemin: string) => {
        APPELS.push({ methode: 'PATCH', chemin })
        return Promise.resolve({ success: true, data: {} })
      }),
      delete: vi.fn((chemin: string) => {
        APPELS.push({ methode: 'DELETE', chemin })
        return Promise.resolve(undefined)
      }),
    },
  }
})

function profil(permissions: string[], role = 'PRATICIEN'): ProfilUtilisateur {
  return {
    id: '3f2b9c40-1d2e-4f5a-8b7c-9d0e1f2a3b4c',
    email: 'profil.limite@exemple.test',
    prenom: 'Profil',
    nom: 'Limite',
    role,
    permissions,
  } as ProfilUtilisateur
}

function monter(element: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/tarification']}>{element}</MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  APPELS.length = 0
  useAuthStore.setState({ profil: null })
})

describe('Ecran Tarification', () => {
  it('un profil sans TARIFS:WRITE ne voit aucun bouton d\'ecriture', async () => {
    useAuthStore.setState({ profil: profil(['TARIFS:READ']) })
    monter(<TarificationPage />)

    await waitFor(() =>
      expect(screen.getAllByText(/Detartrage monodentaire/i).length).toBeGreaterThan(0),
    )

    expect(screen.queryByText(/Nouvel acte/i)).not.toBeInTheDocument()
    // La ligne existe : l'absence de bouton tient donc a la garde, pas a une
    // liste vide.
    expect(screen.getByText('DETART')).toBeInTheDocument()
    expect(screen.queryByText(/Retirer/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Reactiver/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Actions' })).not.toBeInTheDocument()
    // Le panneau de modification des tarifs ne s'affiche pas non plus.
    expect(screen.queryByText(/Tarifs par categorie/i)).not.toBeInTheDocument()
  })

  it('un profil sans TARIFS:WRITE declenche aucun appel mutateur', async () => {
    useAuthStore.setState({ profil: profil(['TARIFS:READ']) })
    const utilisateur = userEvent.setup()
    monter(<TarificationPage />)

    await waitFor(() =>
      expect(screen.getAllByText(/Detartrage monodentaire/i).length).toBeGreaterThan(0),
    )

    // Aucune action n'est proposee : cliquer partout ne doit rien envoyer. Le
    // champ de recherche et la ligne sont cliquables sans danger - ils ne sont
    // pas des actions d'ecriture.
    await utilisateur.click(screen.getByRole('heading', { name: /Actes de nomenclature/i }))
    await utilisateur.click(screen.getByLabelText(/Rechercher un acte/i))
    await utilisateur.type(screen.getByLabelText(/Rechercher un acte/i), 'X')
    await utilisateur.click(screen.getAllByText(/Detartrage monodentaire/i)[0]!)

    const mutateurs = APPELS.filter((a) => a.methode !== 'GET')
    expect(mutateurs).toEqual([])
  })

  it('un profil avec TARIFS:WRITE voit les actions', async () => {
    useAuthStore.setState({ profil: profil(['TARIFS:READ', 'TARIFS:WRITE']) })
    monter(<TarificationPage />)

    await waitFor(() =>
      expect(screen.getAllByText(/Detartrage monodentaire/i).length).toBeGreaterThan(0),
    )

    expect(screen.getByText(/Nouvel acte/i)).toBeInTheDocument()
    expect(screen.getByText(/Tarifs par categorie/i)).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument()
    expect(screen.getByText(/^Retirer$/)).toBeInTheDocument()
  })

  it('un profil sans TARIFS:READ ne voit pas la page du tout', async () => {
    useAuthStore.setState({ profil: profil(['PATIENTS:READ']) })
    monter(<TarificationPage />)

    await waitFor(() => expect(screen.getByText(/Acces non autorise/i)).toBeInTheDocument())
    // Aucune requete n'est partie : la page n'a pas le droit de l'appeler.
    expect(APPELS).toEqual([])
  })
})

describe('Ecran Prise en charge', () => {
  it('le secretariat lit sans voir de bouton d\'ecriture', async () => {
    useAuthStore.setState({ profil: profil(['ASSURANCE:READ', 'ASSURANCE:WRITE'], 'SECRETAIRE') })
    monter(<OrganismesPage />)

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /Organismes payeurs/i })).toBeInTheDocument(),
    )

    // Le secretariat declare un droit **sur un patient** depuis la fiche
    // patient. Il ne cree pas d'organisme : l'ecran ne lui propose donc pas de
    // le faire, meme si sa matrice lui accorde ASSURANCE:WRITE.
    expect(screen.queryByText(/Nouvel organisme/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Desactiver$/)).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Actions' })).not.toBeInTheDocument()
  })

  it('un administrateur voit les boutons d\'ecriture des organismes', async () => {
    useAuthStore.setState({ profil: profil(['TARIFS:WRITE'], 'ADMIN_CABINET') })
    monter(<OrganismesPage />)

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /Organismes payeurs/i })).toBeInTheDocument(),
    )
    expect(screen.getByText(/Nouvel organisme/i)).toBeInTheDocument()
  })

  it('un profil sans ASSURANCE:READ ne declenche aucun appel', async () => {
    useAuthStore.setState({ profil: profil(['PATIENTS:READ']) })
    monter(<OrganismesPage />)

    await waitFor(() => expect(screen.getByText(/Acces non autorise/i)).toBeInTheDocument())
    expect(APPELS).toEqual([])
  })
})