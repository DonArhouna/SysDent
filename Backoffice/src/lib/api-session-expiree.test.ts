import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  api,
  setGestionnaireSessionMorte,
  setRafraichisseur,
  setTokenProviderExport,
} from '@/lib/api'

/**
 * Une session expirée doit produire une **redirection**, jamais une seconde
 * requête dégradée.
 *
 * **Ce que le propriétaire a cru voir.** Sur la même requête, des 401 puis un
 * 500. L'hypothèse naturelle : le client rejoue la requête sans jeton frais,
 * et la seconde passe dégradée. Il fallait le vérifier plutôt que de le
 * supposer — c'est ce que ces tests font.
 *
 * **Ce qu'ils prouvent, exactement :**
 *
 * - le rejeu n'a lieu qu'**une** fois, et uniquement si le renouvellement a
 *   réussi ; un 401 simple ne déclenche pas de boucle ;
 * - quand le renouvellement échoue, la session est purgée et **la requête n'est
 *   pas rejouée** : c'est ce qui évite le couple 401 puis 500 décrit plus haut ;
 * - les routes `/platform/auth/*` ne sont jamais rejouées : leur 401 veut dire
 *   « mauvais mot de passe », pas « jeton périmé » ;
 * - le rejeu part avec le jeton **nouveau**, pas avec celui qui a expiré.
 *
 * Chaque test compte les appels : c'est le seul moyen de prouver qu'une
 * requête n'a pas été faite.
 */

const reponses = vi.hoisted(
  () => [] as { url: string; entetes: string; status: number }[],
)

/** Simule un serveur : chaque appel est journalisé, puis répond `statut`. */
function serveur(statuts: number[]) {
  let index = 0
  return vi.fn(async (chemin: string, init?: RequestInit) => {
    // On journalise les en-tetes **tels quels**, sans deviner la casse ni la
    // forme : `Headers` et un objet simple ne se lisent pas pareil, et un test
    // qui suppose la forme echoue sur le test, pas sur le code.
    const entetes =
      init?.headers instanceof Headers
        ? [...init.headers.entries()]
        : Object.entries((init?.headers ?? {}) as Record<string, string>)
    reponses.push({
      url: chemin,
      entetes: JSON.stringify(entetes).toLowerCase(),
      status: statuts[Math.min(index, statuts.length - 1)],
    })
    const statut = statuts[Math.min(index, statuts.length - 1)]
    index += 1
    return {
      ok: statut >= 200 && statut < 300,
      status: statut,
      json: async () => ({
        success: statut < 400,
        data: statut < 400 ? { ok: true, autorise: true } : null,
        error:
          statut >= 400
            ? { code: 'X', message: `Erreur ${statut}`, details: {} }
            : undefined,
      }),
    } as unknown as Response
  })
}

let rafraichisseurAppele = 0
let sessionMorte = 0

/**
 * Le jeton courant, comme dans l'application.
 *
 * Un fournisseur **constant** ne verrait rien : le rejeu redemande le jeton au
 * fournisseur, et si celui-ci repond toujours la meme chose, le rejeu part avec
 * le jeton perime - ce qui n'est pas un defaut du client mais du test. Le
 * renouvellement met donc a jour la meme source que celle que le client relit,
 * exactement comme le fait le store d'authentification.
 */
let jetonCourant = 'jeton-expire'

describe('session expiree', () => {
  beforeEach(() => {
    reponses.length = 0
    rafraichisseurAppele = 0
    sessionMorte = 0
    jetonCourant = 'jeton-expire'
    vi.stubGlobal('fetch', serveur([401]))
    setTokenProviderExport(() => jetonCourant)
    setRafraichisseur(async () => {
      rafraichisseurAppele += 1
      jetonCourant = 'jeton-neuf'
      return jetonCourant
    })
    setGestionnaireSessionMorte(() => {
      sessionMorte += 1
    })
  })

  afterEach(() => {
    setRafraichisseur(null)
    setGestionnaireSessionMorte(null)
  })

  it('renouvelle une fois et rejoue avec le jeton neuf', async () => {
    vi.stubGlobal('fetch', serveur([401, 200]))

    // `api.get` renvoie le corps entier de la reponse, pas `corps.data` :
    // c'est le store qui developpe. On verifie donc le corps.
    const resultat = await api.get<{ success: boolean; data: { ok: boolean } }>(
      '/platform/stats/dashboard',
    )

    expect(resultat.success).toBe(true)
    expect(resultat.data.ok).toBe(true)
    expect(reponses).toHaveLength(2)
    // Le premier appel part avec le jeton expire, le second avec le neuf.
    expect(reponses[0].entetes).toContain('jeton-expire')
    expect(reponses[1].entetes).toContain('jeton-neuf')
    expect(sessionMorte).toBe(0)
  })

  it('quand le renouvellement echoue, purge la session et NE REJOUE PAS', async () => {
    setRafraichisseur(async () => {
      rafraichisseurAppele += 1
      throw new Error('refresh refuse')
    })

    // C'est le cas redige : le 401 se reproduirait si le client rejouait.
    await expect(
      api.get('/platform/stats/dashboard'),
    ).rejects.toBeInstanceOf(ApiError)

    expect(reponses).toHaveLength(1)
    expect(rafraichisseurAppele).toBe(1)
    expect(sessionMorte).toBe(1)
  })

  it('ne boucle pas : un rejeu refuse ne declenche pas un second renouvellement', async () => {
    // Le serveur refuse toujours : sans garde, chaque rejeu renouvellerait.
    vi.stubGlobal('fetch', serveur([401]))

    await expect(api.get('/platform/stats/dashboard')).rejects.toBeInstanceOf(ApiError)

    expect(rafraichisseurAppele).toBe(1)
    expect(reponses).toHaveLength(2)
  })

  it('ne rejoue jamais une route d authentification', async () => {
    vi.stubGlobal('fetch', serveur([401]))

    await expect(
      api.post('/platform/auth/login', { email: 'a@b.fr', mot_de_passe: 'x' }),
    ).rejects.toBeInstanceOf(ApiError)

    // Un 401 sur /auth/login signifie « mauvais mot de passe » : le rejouer
    // ne rendrait pas la session et pourrait boucler sur le formulaire.
    expect(reponses).toHaveLength(1)
    expect(rafraichisseurAppele).toBe(0)
  })

  it('un 403 ne provoque ni renouvellement ni rejeu', async () => {
    vi.stubGlobal('fetch', serveur([403]))

    await expect(
      api.get('/platform/stats/dashboard'),
    ).rejects.toBeInstanceOf(ApiError)

    // Le 403 est une reponse metier : la session est valide.
    expect(rafraichisseurAppele).toBe(0)
    expect(reponses).toHaveLength(1)
  })
})