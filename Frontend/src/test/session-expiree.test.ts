import { QueryClient } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Preuve du correctif de session expirée.
 *
 * Le défaut d'origine : à l'expiration du jeton, la requête recevait 401, le
 * renouvellement échouait, et l'application **continuait d'appeler l'API avec un
 * jeton mort**. Résultat : une cascade de 401 puis de 403 qui ne parlaient
 * d'aucune permission réelle — l'utilisateur partait chercher une panne de droits
 * inexistante. Le chemin de correction est aussi un défaut de sécurité : le cache
 * React Query n'était pas vidé, donc sur un poste partagé la personne suivante
 * voyait les données de la précédente.
 *
 * Ces tests s'appuient sur un `fetch` piloté à la main plutôt que sur un
 * intercepteur réseau. C'est délibéré : ce qui doit être prouvé est le
 * **mécanisme de `api.ts`** (nombre d'appels, nombre de purges, présence d'un
 * rejeu), pas l'encodage HTTP d'un intercepteur tiers.
 */

/** Compteur d'appels par chemin : la preuve est dans le nombre, pas dans le code. */
type Journal = { chemin: string; methode: string }

function reponseJson(statut: number, corps: unknown): Response {
  return new Response(JSON.stringify(corps), {
    status: statut,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** 401 : c'est la réponse qui déclenche le renouvellement puis la purge. */
const EN_TETE_401 = () =>
  reponseJson(401, { error: { code: 'NON_AUTHENTIFIE', message: 'Jeton expiré' } })

/**
 * Charge `api.ts` et le store dans un module neuf.
 *
 * Le rechargement est indispensable : les deux modules gardent des singletons
 * (promesse de renouvellement, gestionnaire de session morte) qui survivraient
 * d'un test à l'autre et masqueraient les défauts.
 */
async function chargerModules() {
  vi.resetModules()
  const api = await import('@/lib/api')
  const store = await import('@/stores/auth-store')
  return { api, store }
}

beforeEach(() => {
  localStorage.clear()
})

describe('Session expirée', () => {
  it('purge une seule fois, ne rejoue pas la requête et ne cascadule plus', async () => {
    const journal: Journal[] = []
    // Toute requête métier renvoie 401 ; le renouvellement échoue aussi.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        const chemin = String(_url).replace('/api/v1', '')
        journal.push({ chemin, methode: init?.method ?? 'GET' })
        return EN_TETE_401()
      }),
    )

    const { api, store } = await chargerModules()
    const purges: number[] = []
    store.setPurgeurSession(() => purges.push(1))

    store.useAuthStore.setState({ token: 'jeton-mort', refreshToken: 'refresh-mort' })

    await expect(api.api.get('/patients')).rejects.toThrow()

    // 1. La purge a eu lieu, exactement une fois.
    expect(purges).toHaveLength(1)

    // 2. La requête n'a pas été rejouée avec le jeton mort : deux appels seulement,
    //    le métier puis le renouvellement. C'est le cœur du défaut observé.
    expect(journal.map((a) => a.chemin)).toEqual(['/patients', '/auth/refresh'])

    // 3. Plus aucun jeton en mémoire ni sur le disque.
    const etat = store.useAuthStore.getState()
    expect(etat.token).toBeNull()
    expect(etat.refreshToken).toBeNull()
    expect(etat.profil).toBeNull()
    // Zustand sérialise `{ state, version }` : c'est `state` qui porte les jetons.
    expect(JSON.parse(localStorage.getItem('sysdent-auth') ?? '{}').state).toMatchObject({
      token: null,
      refreshToken: null,
      profil: null,
    })
  })

  it('ne déclenche qu’un seul renouvellement pour six requêtes simultanées', async () => {
    const journal: Journal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        const chemin = String(_url).replace('/api/v1', '')
        journal.push({ chemin, methode: init?.method ?? 'GET' })
        return EN_TETE_401()
      }),
    )

    const { api, store } = await chargerModules()
    const purges: number[] = []
    store.setPurgeurSession(() => purges.push(1))
    store.useAuthStore.setState({ token: 'jeton-mort', refreshToken: 'refresh-mort' })

    // Le tableau de bord émet six requêtes en parallèle. Le backend fait tourner
    // le refresh token : six POST /auth/refresh, un seul succeed et cinq sont
    // refusés. La déduplication est donc obligatoire, pas une optimisation.
    const resultats = await Promise.allSettled([
      api.api.get('/cabinets'),
      api.api.get('/patients'),
      api.api.get('/rendez-vous'),
      api.api.get('/stock/alertes'),
      api.api.get('/caisse/sessions'),
      api.api.get('/factures'),
    ])

    expect(resultats.every((r) => r.status === 'rejected')).toBe(true)

    const refresh = journal.filter((a) => a.chemin === '/auth/refresh')
    expect(refresh).toHaveLength(1)
    expect(journal).toHaveLength(7) // 6 requêtes métier + 1 renouvellement
    expect(purges).toHaveLength(1)
  })

  it('laisse une session valide survivre au renouvellement', async () => {
    const journal: Journal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        const chemin = String(url).replace('/api/v1', '')
        journal.push({ chemin, methode: init?.method ?? 'GET' })
        if (chemin === '/auth/refresh') {
          return reponseJson(200, {
            success: true,
            data: { access_token: 'neuf', refresh_token: 'refresh-neuf' },
          })
        }
        // `/patients` tombe d'abord (jeton expiré), puis répond au rejeu. Sans ce
        // refus initial, il n'y aurait jamais de renouvellement à prouver.
        if (chemin === '/patients') {
          const dejaRejoue = journal.filter((a) => a.chemin === '/patients').length > 1
          return dejaRejoue
            ? reponseJson(200, { success: true, data: { items: [] } })
            : EN_TETE_401()
        }
        return EN_TETE_401()
      }),
    )

    const { api, store } = await chargerModules()
    const purges: number[] = []
    store.setPurgeurSession(() => purges.push(1))
    store.useAuthStore.setState({ token: 'périmé', refreshToken: 'refresh-v1' })

    await api.api.get('/patients')

    expect(journal.map((a) => a.chemin)).toEqual(['/patients', '/auth/refresh', '/patients'])
    expect(purges).toHaveLength(0)
    expect(store.useAuthStore.getState().token).toBe('neuf')
    expect(store.useAuthStore.getState().refreshToken).toBe('refresh-neuf')
  })
})

describe('Purge des données entre deux utilisateurs', () => {
  it('vide le cache React Query : le second utilisateur ne voit rien du premier', async () => {
    const { store } = await chargerModules()
    const client = new QueryClient()

    // Une donnée de santé du premier utilisateur, en cache.
    client.setQueryData(['patients', 'liste'], [{ id: 'p1', nom: 'Awa Diop' }])
    expect(client.getQueryData(['patients', 'liste'])).toHaveLength(1)

    // Branchement réel du purgeur, comme `QueryProvider` le fait.
    store.setPurgeurSession(() => client.clear())
    store.useAuthStore.setState({ token: 'jeton-1', refreshToken: 'refresh-1' })

    store.useAuthStore.getState().deconnexion()

    // Le cache est purgé **au moment** de la déconnexion, pas à la navigation
    // suivante : sinon la nouvelle page s'affiche avec les données de l'ancien.
    expect(client.getQueryData(['patients', 'liste'])).toBeUndefined()
  })

  it('purge aussi le site mémorisé, qui est une donnée de tenant', async () => {
    const { store } = await chargerModules()
    const cabinet = await import('@/stores/cabinet-store')

    // Un site mémorisé est un identifiant de tenant. Laissé dans le
    // `localStorage`, il ferait porter les requêtes du second utilisateur vers le
    // site du premier — une tentative de fuite inter-tenant, même si le backend
    // la refuse.
    cabinet.useCabinetStore.setState({ cabinetActifId: 'site-du-premier-cabinet' })
    expect(cabinet.useCabinetStore.getState().cabinetActifId).toBe('site-du-premier-cabinet')

    store.useAuthStore.setState({ token: 'jeton-1', refreshToken: 'refresh-1' })
    store.useAuthStore.getState().deconnexion()

    expect(cabinet.useCabinetStore.getState().cabinetActifId).toBeNull()
    expect(JSON.parse(localStorage.getItem('sysdent-cabinet-storage') ?? '{}')).toMatchObject({
      state: { cabinetActifId: null },
    })
  })
})

describe('Session morte dans un onglet', () => {
  it('propage la purge aux autres onglets du même navigateur', async () => {
    // `BroadcastChannel` n'existe pas toujours (Safari ancien, Node sans DOM) :
    // le produit doit pouvoir s'en passer sans casser la déconnexion.
    type Canal = { nom: string; onmessage: ((e: MessageEvent) => void) | null }
    const canaux: Canal[] = []
    class FauxCanal {
      onmessage: ((e: MessageEvent) => void) | null = null
      nom: string
      constructor(nom: string) {
        this.nom = nom
        canaux.push(this as unknown as Canal)
      }
      postMessage(_donnees: unknown) {
        /* routage réel branché sur le prototype ci-dessous */
      }
      close() {
        /* sans objet dans le test */
      }
    }
    // Un vrai routage entre canaux du même nom : c'est ce que fait le navigateur.
    FauxCanal.prototype.postMessage = function (donnees: unknown) {
      for (const autre of canaux) {
        if (autre !== this && autre.nom === this.nom && autre.onmessage) {
          autre.onmessage(new MessageEvent('message', { data: donnees }))
        }
      }
    }
    vi.stubGlobal('BroadcastChannel', FauxCanal)

    // Les deux onglets sont ouverts et connectés — l'ordre compte : un onglet créé
    // *après* la déconnexion ne peut pas avoir reçu le message, et le test ne
    // prouverait rien.
    const ongletA = await chargerModules()
    const cacheA = new QueryClient()
    cacheA.setQueryData(['patients'], [{ id: 'p1', nom: 'Awa Diop' }])
    ongletA.store.setPurgeurSession(() => cacheA.clear())
    ongletA.store.useAuthStore.setState({ token: 'jeton', refreshToken: 'refresh' })

    // Onglet B : il a sa propre copie **en mémoire** du jeton — c'est le piège, le
    // `localStorage` partagé ne met pas à jour un store déjà chargé. Sans
    // propagation, il resterait « connecté », garderait ses données en cache et
    // continuerait d'appeler l'API avec un jeton révoqué côté serveur.
    const ongletB = await chargerModules()
    const cacheB = new QueryClient()
    cacheB.setQueryData(['patients'], [{ id: 'p2', nom: 'Moussa Ba' }])
    ongletB.store.setPurgeurSession(() => cacheB.clear())
    ongletB.store.useAuthStore.setState({ token: 'jeton', refreshToken: 'refresh' })
    expect(ongletB.store.useAuthStore.getState().token).toBe('jeton')

    // **Sans** appeler la déconnexion de l'onglet B : c'est l'onglet A qui part.
    ongletA.store.useAuthStore.getState().deconnexion()

    expect(canaux.length).toBeGreaterThan(0)
    expect(cacheA.getQueryData(['patients'])).toBeUndefined()
    expect(cacheB.getQueryData(['patients'])).toBeUndefined()
    expect(ongletB.store.useAuthStore.getState().token).toBeNull()
  })
})