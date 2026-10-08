import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Contrat de l'enrolement 2FA.
 *
 * Les formes repondent aux schemas OpenAPI releves dans `openapi.json` :
 * `Activation2FAResponse` pour la preparation, `Enrolement2FAResponse` pour
 * l'activation, dont les champs `access_token`, `refresh_token`, `codes_secour`.
 *
 * **Le piege que ces tests verrouillent.** L'enrolement ne passe par **aucune
 * session** : il porte un jeton d'etape. Or le client HTTP prend son en-tete
 * `Authorization` dans le jeton de session, qui n'existe pas encore a ce moment.
 * Un appel sans porteur explicite partirait donc sans en-tete, et le backend
 * repondrait « jeton invalide » sans qu'aucune erreur locale ne le signale.
 */

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', async (importOriginal) => {
  const reel = await importOriginal<typeof import('@/lib/api')>()
  return { ...reel, api: { post, get } }
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
    expires_in: 900,
    refresh_expires_in: 604800,
    codes_secours: ['ABCD2345', 'EFGH6789', 'JKMN2345'],
  },
} as unknown as ApiReponse<never>

describe('enrolement 2FA', () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: null,
      refreshToken: null,
      profil: null,
      challenge2fa: null,
      jetonEnrolement: 'jeton-denrolement-1234567890',
      preparation2fa: null,
    })
    post.mockReset()
    get.mockReset()
    get.mockResolvedValue({
      data: { id: 'u1', email: 'a@b.fr', prenom: 'A', nom: 'B', role: 'SUPER_ADMIN', permissions: [] },
    })
  })

  it('la preparation porte le jeton d enrollement, pas un jeton de session', async () => {
    get.mockResolvedValue(preparation)

    await useAuthStore.getState().preparerEnrolement()

    expect(get).toHaveBeenCalledWith('/platform/auth/2fa/preparation', {
      bearer: 'jeton-denrolement-1234567890',
    })
    expect(useAuthStore.getState().preparation2fa?.secret).toBe(
      'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP',
    )
  })

  it('une activation reussie ouvre la session et rend les codes de secours', async () => {
    post.mockResolvedValue(activation)

    const codes = await useAuthStore.getState().activerEnrolement('123456')

    expect(post).toHaveBeenCalledWith('/platform/auth/2fa/activation', {
      code: '123456',
      bearer: 'jeton-denrolement-1234567890',
    })
    expect(codes).toEqual(['ABCD2345', 'EFGH6789', 'JKMN2345'])
    expect(useAuthStore.getState().token).toBe('acces-1')
    // Le jeton d enrollement est consomme cote serveur : le garder laisserait
    // rejouer une activation et traînerait un secret dans l etat.
    expect(useAuthStore.getState().jetonEnrolement).toBeNull()
    expect(useAuthStore.getState().preparation2fa).toBeNull()
  })

  it('les codes de secours ne sont pas conserves dans le store', async () => {
    post.mockResolvedValue(activation)

    await useAuthStore.getState().activerEnrolement('123456')

    // Un code de secours dans l etat serait relisible apres coup, par n'importe
    // qui ouvrant l outil de developpement. Ils sont renvoyes, jamais stockes.
    const serialise = JSON.stringify(useAuthStore.getState())
    expect(serialise).not.toContain('ABCD2345')
  })

  it('sans jeton d enrollement, preparer echoue sans appeler le serveur', async () => {
    useAuthStore.setState({ jetonEnrolement: null })

    await expect(useAuthStore.getState().preparerEnrolement()).rejects.toThrow(/expir/i)
    expect(get).not.toHaveBeenCalled()
  })

  it('une activation sans session renvoyee ne pretend pas etre connecte', async () => {
    // L activation a reussi cote serveur, mais sans jeton. Declarer une session
    // quand meme laisserait l ecru ditre connecte alors qu aucune requete ne
    // partirait : c'est un piege que seul le type revele.
    post.mockResolvedValue({
      success: true,
      data: { codes_secours: ['ABCD2345'] },
    } as unknown as ApiReponse<never>)

    await expect(useAuthStore.getState().activerEnrolement('123456')).rejects.toThrow(
      /aucune session/i,
    )
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('un code TOTP errone laisse l enrolement reprenable', async () => {
    // Le secret doit deja etre affiche : c'est lui que l operateur a scanne. Un
    // secret affiche puis rate, suivi d'une preparation qui le regenere, enverrait
    // vers un code que le telephone ne peut pas produire.
    get.mockResolvedValue(preparation)
    await useAuthStore.getState().preparerEnrolement()
    post.mockRejectedValue(new Error('Code de verification invalide.'))

    await expect(useAuthStore.getState().activerEnrolement('000000')).rejects.toThrow(
      /invalide/i,
    )
    // Le secret reste affiche : l operateur doit pouvoir reessayer sans repasser
    // par la preparation, qui regenererait un secret different de celui scanné.
    expect(useAuthStore.getState().preparation2fa).not.toBeNull()
    expect(useAuthStore.getState().jetonEnrolement).toBe('jeton-denrolement-1234567890')
  })
})