import type { ReactNode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AppSidebar } from '@/components/layout/sidebar'
import { CabinetDetailPage } from '@/features/cabinets/cabinet-detail-page'
import { PermissionGuard } from '@/guards/route-guard'
import { useAuthStore, type ProfilPlateforme } from '@/stores/auth-store'

/**
 * Écrans d'administration.
 *
 * Ce qui est verrouillé ici :
 * - la navigation lit les permissions **du backend** (`platform.*`) et le rôle
 *   dans `roles` : avec les anciens codes, Tableau de bord et Cabinets étaient
 *   masqués à tout le monde, Super Admin compris ;
 * - la fiche d'un cabinet ne propose que les transitions renvoyées par le
 *   serveur, et n'envoie une action qu'avec un motif.
 */

const get = vi.hoisted(() => vi.fn())
const post = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (importOriginal) => {
  const reel = await importOriginal<typeof import('@/lib/api')>()
  return { ...reel, api: { get, post, patch: vi.fn(), delete: vi.fn() } }
})

function connecter(permissions: string[], extra: Partial<ProfilPlateforme> = {}) {
  useAuthStore.setState({
    token: 'jeton',
    profil: {
      id: 'u1',
      email: 'admin@sysdent.pro',
      prenom: 'Awa',
      nom: 'Diop',
      roles: ['SUPER_ADMIN_PLATEFORME'],
      permissions,
      deux_facteurs_actif: true,
      ...extra,
    },
  })
}

function avecRequetes(enfant: ReactNode, chemin = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[chemin]}>{enfant}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('barre latérale', () => {
  it('affiche les modules dont le compte porte la permission backend, et masque les autres', () => {
    connecter(['platform.stats.read', 'platform.tenants.read'])
    avecRequetes(<AppSidebar collapsed={false} onToggle={() => undefined} />)

    const nav = screen.getByRole('navigation', { name: 'Navigation principale' })
    expect(within(nav).getByRole('link', { name: /Tableau de bord/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Cabinets/ })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /Équipe/ })).not.toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: /Factures/ })).not.toBeInTheDocument()
  })

  it('lit le rôle dans `roles` et affiche son libellé', () => {
    connecter([])
    avecRequetes(<AppSidebar collapsed={false} onToggle={() => undefined} />)
    expect(screen.getByText('Super Admin')).toBeInTheDocument()
  })
})

describe('garde de permission', () => {
  beforeEach(() => get.mockReset())

  it("attend le profil au lieu d'envoyer sur 403", async () => {
    useAuthStore.setState({ token: 'jeton', profil: null })
    get.mockResolvedValue({ data: { id: 'u1', email: 'a@b.fr', prenom: 'A', nom: 'B', roles: [], permissions: ['platform.audit.read'] } })

    avecRequetes(
      <Routes>
        <Route path="/audit" element={<PermissionGuard permission="platform.audit.read"><p>contenu protégé</p></PermissionGuard>} />
        <Route path="/403" element={<p>interdit</p>} />
      </Routes>,
      '/audit',
    )

    expect(screen.getByRole('status')).toHaveTextContent('Chargement du profil')
    expect(await screen.findByText('contenu protégé')).toBeInTheDocument()
    expect(screen.queryByText('interdit')).not.toBeInTheDocument()
  })
})

describe("fiche d'un cabinet", () => {
  const fiche = {
    tenant_id: 't1',
    nom: 'Cabinet Dakar Plateau',
    statut: 'ACTIF',
    archivable: false,
    transitions_possibles: ['SUSPENDU', 'RESILIE'],
    abonnement: null,
  }

  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    connecter(['platform.tenants.read', 'platform.tenants.suspend', 'platform.tenants.terminate', 'platform.tenants.activate'])
    get.mockImplementation((chemin: string) => {
      if (chemin === '/platform/tenants/t1') return Promise.resolve({ data: fiche })
      if (chemin.endsWith('/historique')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: null })
    })
  })

  function afficher() {
    return avecRequetes(
      <Routes>
        <Route path="/cabinets/:id" element={<CabinetDetailPage />} />
      </Routes>,
      '/cabinets/t1',
    )
  }

  it('ne propose que les transitions renvoyées par le serveur', async () => {
    afficher()
    expect(await screen.findByRole('heading', { name: 'Cabinet Dakar Plateau' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Désactiver/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Résilier/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Réactiver|Passer en actif/ })).not.toBeInTheDocument()
  })

  it("exige un motif avant d'envoyer la désactivation", async () => {
    post.mockResolvedValue({ data: fiche })
    afficher()
    await userEvent.click(await screen.findByRole('button', { name: /Désactiver/ }))

    const dialogue = await screen.findByRole('dialog')
    const confirmer = within(dialogue).getByRole('button', { name: 'Désactiver' })
    expect(confirmer).toBeDisabled()

    await userEvent.type(within(dialogue).getByLabelText(/Motif/), 'Impayé depuis 3 mois')
    expect(confirmer).toBeEnabled()
    await userEvent.click(confirmer)

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/tenants/t1/suspension', { motif: 'Impayé depuis 3 mois' }),
    )
  })
})

describe('mon compte', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
    get.mockResolvedValue({ data: null })
  })

  async function afficher(extra: Partial<ProfilPlateforme> = {}) {
    const { ComptePage } = await import('@/features/compte/compte-page')
    connecter(['platform.stats.read'], { statut: 'ACTIF', methodes_2fa: ['email'], ...extra })
    return avecRequetes(<ComptePage />)
  }

  it('affiche la methode de 2FA du compte, sans proposer la regeneration sans application', async () => {
    await afficher()
    expect(screen.getByText('Non configurée')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Régénérer les codes/ })).not.toBeInTheDocument()
  })

  it("n'envoie le changement de mot de passe que conforme et confirme", async () => {
    post.mockResolvedValue({ data: null })
    await afficher()
    const bouton = screen.getByRole('button', { name: 'Changer le mot de passe' })

    await userEvent.type(screen.getByLabelText(/Mot de passe actuel/), 'Ancien-Mot-2026!')
    await userEvent.type(screen.getByLabelText(/^Nouveau mot de passe/), 'court')
    expect(screen.getByText(/Il manque/)).toBeInTheDocument()
    expect(bouton).toBeDisabled()

    await userEvent.clear(screen.getByLabelText(/^Nouveau mot de passe/))
    await userEvent.type(screen.getByLabelText(/^Nouveau mot de passe/), 'Nouveau-Solide-2026!')
    await userEvent.type(screen.getByLabelText(/Confirmer/), 'Nouveau-Solide-2026!')
    await userEvent.click(bouton)

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/auth/mot-de-passe', {
        ancien: 'Ancien-Mot-2026!',
        nouveau: 'Nouveau-Solide-2026!',
      }),
    )
  })
})

describe("rôles d'un cabinet", () => {
  const matrice = {
    roles: [
      { id: 'r-admin', nom: 'ADMIN_CABINET', niveau_hierarchie: 1, permissions: [], nb_utilisateurs: 1, modifiable: false },
      { id: 'r-sec', nom: 'SECRETAIRE', niveau_hierarchie: 3, permissions: ['PATIENTS:READ'], nb_utilisateurs: 2, modifiable: true },
    ],
    catalogue: [
      { code: 'PATIENTS:READ', module: 'PATIENTS', action: 'READ', description: 'Consulter les patients', disponible: true },
      { code: 'PATIENTS:DELETE', module: 'PATIENTS', action: 'DELETE', description: 'Supprimer un patient', disponible: true },
    ],
  }

  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    get.mockImplementation((chemin: string) => {
      if (chemin === '/platform/tenants') return Promise.resolve({ items: [{ tenant_id: 't1', nom: 'Cabinet Plateau' }], meta: {} })
      if (chemin === '/platform/tenants/t1/rbac') return Promise.resolve({ data: matrice })
      return Promise.resolve({ data: null })
    })
  })

  async function afficher(permissions: string[]) {
    const { RolesCabinet } = await import('@/features/equipe/roles-cabinet')
    connecter(permissions)
    return avecRequetes(<RolesCabinet cabinetInitial="t1" />)
  }

  it("accorde une permission apres un motif, par la route du cabinet", async () => {
    post.mockResolvedValue({ data: { role_id: 'r-sec', permissions: ['PATIENTS:READ', 'PATIENTS:DELETE'] } })
    await afficher(['platform.tenants.read', 'platform.tenants.rbac'])

    await userEvent.click(await screen.findByRole('button', { name: /PATIENTS:DELETE pour Secrétaire : non accordée/ }))
    const dialogue = await screen.findByRole('dialog')
    await userEvent.type(within(dialogue).getByLabelText(/Motif/), 'Demande du cabinet')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Accorder' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/tenants/t1/rbac/roles/r-sec/permissions', {
        permission: 'PATIENTS:DELETE',
        motif: 'Demande du cabinet',
      }),
    )
  })

  it("verrouille l'administrateur, et ne rend rien cliquable sans le droit dedie", async () => {
    await afficher(['platform.tenants.read'])
    await screen.findByText('Consulter les patients')
    expect(screen.queryByRole('button', { name: /pour Secrétaire/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /pour Administrateur/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Lecture seule/)).toBeInTheDocument()
  })
})

describe("administrateurs d'un cabinet", () => {
  const admin = {
    id: 'adm1', email: 'chef@cabinet.sn', prenom: 'Awa', nom: 'Ndiaye', actif: true,
    activation_requise: false, doit_changer_mot_de_passe: false, deux_facteurs: true, dernier_login: null,
  }

  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    get.mockResolvedValue({ data: [admin] })
  })

  async function afficher(permissions: string[]) {
    const { AdminsCabinet } = await import('@/features/cabinets/admins-cabinet')
    connecter(permissions)
    return avecRequetes(<AdminsCabinet tenantId="t1" />)
  }

  it('le mot de passe temporaire s’affiche une fois, après un motif', async () => {
    post.mockResolvedValue({ data: { compte: { ...admin, doit_changer_mot_de_passe: true }, mot_de_passe_temporaire: 'K7mPq2Xz9WbR4n' } })
    await afficher(['platform.tenants.read', 'platform.tenants.reset_access'])

    await userEvent.click(await screen.findByRole('button', { name: /Mot de passe temporaire/ }))
    const dialogue = await screen.findByRole('dialog')
    await userEvent.type(within(dialogue).getByLabelText(/Motif/), 'Mot de passe oublié')
    await userEvent.click(within(dialogue).getByRole('button', { name: 'Générer' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/tenants/t1/administrateurs/adm1/acces', { action: 'temporaire', motif: 'Mot de passe oublié' }),
    )
    expect(await screen.findByText('K7mPq2Xz9WbR4n')).toBeInTheDocument()
  })

  it('sans le droit dédié, aucune action n’est proposée', async () => {
    await afficher(['platform.tenants.read'])
    expect(await screen.findByText('chef@cabinet.sn')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Lien de réinitialisation/ })).not.toBeInTheDocument()
  })
})

describe("e-mail de connexion d'un administrateur", () => {
  it('envoie la nouvelle adresse et le motif à la route dédiée', async () => {
    const admin = {
      id: 'adm1', email: 'admin.demo@sysdent.sn', prenom: 'Awa', nom: 'Diallo', actif: true,
      activation_requise: false, doit_changer_mot_de_passe: false, deux_facteurs: false, dernier_login: null,
    }
    get.mockReset()
    post.mockReset()
    get.mockResolvedValue({ data: [admin] })
    post.mockResolvedValue({ data: { ...admin, email: 'sadikh@example.com', activation_requise: true } })
    const { AdminsCabinet } = await import('@/features/cabinets/admins-cabinet')
    connecter(['platform.tenants.read', 'platform.tenants.reset_access'])
    avecRequetes(<AdminsCabinet tenantId="t1" />)

    await userEvent.click(await screen.findByRole('button', { name: /Changer l'e-mail/ }))
    const dialogue = await screen.findByRole('dialog')
    await userEvent.type(within(dialogue).getByLabelText(/Nouvelle adresse/), 'Sadikh@Example.com')
    await userEvent.type(within(dialogue).getByLabelText(/Motif/), 'Adresse personnelle')
    await userEvent.click(within(dialogue).getByRole('button', { name: "Changer l'adresse" }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/platform/tenants/t1/administrateurs/adm1/email', {
        nouvel_email: 'sadikh@example.com',
        motif: 'Adresse personnelle',
      }),
    )
  })
})
