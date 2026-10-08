import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Contrat de la connexion plateforme.
 *
 * **Le défaut que ce test decrit.** `connexion` testait `!access_token` **avant**
 * de regarder les jetons d'etape, et levait « Identifiants invalides ». Or une
 * reponse portant un jeton d'etape n'a pas d'access_token - c'est meme la
 * garantie qu'aucune session ne s'ouvre avant le second facteur. La branche
 * `jeton_challenge` qui suivait etait donc du code mort : **tout** compte
 * plateforme echouait a l'ecran de connexion, meme apres une reussite serveur.
 *
 * Aucun test ne le voyait : le type `ReponseJeton` declarait `access_token`
 * obligatoire, donc TypeScript validait un code ecrit contre un serveur qui
 * n'envoie pas ce champ. Les trois formes ci-dessous sont les seules que le
 * backend peut produire.
 */

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (importOriginal) => {
  const reel = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...reel,
    api: { post, get },
  }
})

/** Forme reelle du refus : `api.post` leve une ApiError, il ne retourne pas de corps. */
function refusApi(message = 'Identifiants invalides.') {
  return new Error(message)
}

const reponseChallenge = {
  success: true,
  data: { jeton_challenge: 'jeton-de-defi-2fa-1234567890' },
} as unknown as ApiReponse<never>

const reponseEnrolement = {
  success: true,
  data: { jeton_enrolement: 'jeton-denrolement-1234567890' },
} as unknown as ApiReponse<never>

const reponseSession = {
  success: true,
  data: {
    access_token: 'acces-1',
    refresh_token: 'refresh-1',
  },
} as unknown as ApiReponse<never>

describe('connexion plateforme — les trois issues possibles', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, refreshToken: null, profil: null, challenge2fa: null })
    post.mockReset()
    get.mockReset()
    get.mockResolvedValue({
      data: { id: 'u1', email: 'a@b.fr', prenom: 'A', nom: 'B', role: 'SUPER_ADMIN', permissions: [] },
    })
  })

  it('un compte deja configure passe a la saisie du code, sans erreur', async () => {
    post.mockResolvedValue(reponseChallenge)

    const issue = await useAuthStore.getState().connexion('a@b.fr', 'mot-de-passe')

    expect(issue).toBe('challenge')
    expect(useAuthStore.getState().challenge2fa).toBe('jeton-de-defi-2fa-1234567890')
    // **Aucune session** : c'est la garantie que le second facteur est obligatoire.
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('un compte sans secret TOTP passe a l enrolement, sans erreur', async () => {
    post.mockResolvedValue(reponseEnrolement)

    const issue = await useAuthStore.getState().connexion('a@b.fr', 'mot-de-passe')

    expect(issue).toBe('enrolement')
    expect(useAuthStore.getState().jetonEnrolement).toBe('jeton-denrolement-1234567890')
    expect(useAuthStore.getState().token).toBeNull()
    // Le jeton d'enrolement ne remplace jamais le challenge : les deux ne
    // peuvent pas coexister, sinon un ecrait l'autre sans que rien ne le dise.
    expect(useAuthStore.getState().challenge2fa).toBeNull()
  })

  it('une session complete ouvre le jeton et charge le profil', async () => {
    post.mockResolvedValue(reponseSession)

    const issue = await useAuthStore.getState().connexion('a@b.fr', 'mot-de-passe')

    expect(issue).toBe('ok')
    expect(useAuthStore.getState().token).toBe('acces-1')
    expect(useAuthStore.getState().refreshToken).toBe('refresh-1')
    expect(get).toHaveBeenCalledWith('/platform/auth/me')
  })

  it('un refus reel remonte tel quel, sans etre reecrit', async () => {
    post.mockRejectedValue(refusApi())

    await expect(useAuthStore.getState().connexion('a@b.fr', 'faux')).rejects.toThrow(
      'Identifiants invalides.',
    )
  })

  it('un 200 sans aucun jeton ne se déguise pas en refus d identifiants', async () => {
    // Rupture de contrat cote serveur. La dire « identifiants invalides » serait
    // faux, et/debuggerait l operateur dans la mauvaise direction pendant des
    // heures : il reprendrait son mot de passe alors que le serveur est en cause.
    post.mockResolvedValue({ success: true, data: {} } as unknown as ApiReponse<never>)

    await expect(useAuthStore.getState().connexion('a@b.fr', 'mot-de-passe')).rejects.toThrow(
      /aucun jeton/i,
    )
    await expect(useAuthStore.getState().connexion('a@b.fr', 'mot-de-passe')).rejects.not.toThrow(
      /Identifiants invalides/,
    )
  })
})