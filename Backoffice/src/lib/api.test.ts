import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, setTokenProviderExport } from '@/lib/api'

/**
 * Le porteur explicite, vérifié **jusqu'auHeader**.
 *
 * **Le test qui manquait.** Un test du store affirmait « `api.get` a ete appele
 * avec `{ bearer }` » : il verifiait l'intention de l'appelant, pas la requete
 * envoyee. Le mock remplacait `api` entierement, donc la couche transport -
 * celle qui construit les options reelles - n'etait jamais exercee. Or c'est
 * precisement elle qui jetait `bearer` : la requete partait sans en-tete
 * `Authorization` et le backend repondait « authentification requise ».
 *
 * Ces tests interceptent `fetch` : ils regardent ce qui sort reellement.
 */

function entete_authorization(init?: RequestInit): string | null {
  const entetes = new Headers(init?.headers)
  return entetes.get('Authorization')
}

describe('porteur explicite', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ success: true, data: {} }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    // Aucune session : c'est la situation de l enrollement.
    setTokenProviderExport(() => null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GET : le jeton fourni part dans le Header', async () => {
    await api.get('/platform/auth/2fa/preparation', { bearer: 'jeton-denrolement-123' })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(entete_authorization(init)).toBe('Bearer jeton-denrolement-123')
  })

  it('POST : le jeton fourni part dans le Header', async () => {
    await api.post('/platform/auth/2fa/activation', { code: '123456' }, { bearer: 'jeton-denrolement-123' })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(entete_authorization(init)).toBe('Bearer jeton-denrolement-123')
  })

  it('PATCH et DELETE transmettent aussi le jeton', async () => {
    await api.patch('/x', { a: 1 }, { bearer: 'jeton-a' })
    await api.delete('/x', { bearer: 'jeton-b' })

    expect(entete_authorization(fetchMock.mock.calls[0][1] as RequestInit)).toBe('Bearer jeton-a')
    expect(entete_authorization(fetchMock.mock.calls[1][1] as RequestInit)).toBe('Bearer jeton-b')
  })

  it('le jeton fourni prime sur une session ouverte', async () => {
    setTokenProviderExport(() => 'jeton-de-session')

    await api.get('/platform/auth/2fa/preparation', { bearer: 'jeton-denrolement-123' })

    const init = fetchMock.mock.calls[0][1] as RequestInit
    // Sans cela, des la qu un Super Admin dispose d une session, l en-tete de
    // session ecraserait le jeton d etape **en silence**.
    expect(entete_authorization(init)).toBe('Bearer jeton-denrolement-123')
  })

  it("sans jeton et sans session, l'en-tete est absent plutot que vide", async () => {
    await api.get('/platform/auth/me')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(entete_authorization(init)).toBeNull()
  })
})