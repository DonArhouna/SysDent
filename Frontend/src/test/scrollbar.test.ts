import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * La scrollbar doit rester une affaire de tokens.
 *
 * **Ce que le test garde.** Une couleur ecrite en dur dans `::-webkit-scrollbar`
 * passerait le type-check, le lint et le build : le CSS n'est pas type. Elle
 * passerait aussi le regard, tant que le theme ne change pas. Le seul moment ou
 * le defaut saute, c'est en mode sombre, devant un ecran. D'ou une regle.
 *
 * **Les deux engines.** Firefox ignore `::-webkit-scrollbar` et lit
 * `scrollbar-width` / `scrollbar-color` ; Chromium n'ignore que le
 * pseudo-element. Un test qui n'en verrait qu'un autoriserait une feuille qui
 * marche dans un navigateur et pas dans l'autre, sans que rien ne le signale.
 */

const CSS = readFileSync(resolve(__dirname, '../index.css'), 'utf-8')

/**
 * Le bloc d'un selecteur, du selecteur jusqu'a la prochaine accolade fermante.
 *
 * Le selecteur est cherche avec son accolade ouvrante : `.dark` apparait aussi
 * dans un commentaire en tete de fichier, qui expliquait le mecanisme de theme.
 * Chercher le seul mot slicing jusqu'a la premiere accolade y renvoyait le bloc
 * `:root`, et les deux themes semblaient alors avoir la meme poignee.
 */
function bloc(selecteur: string): string {
  const debut = CSS.indexOf(`${selecteur} {`)
  if (debut === -1) throw new Error(`selecteur absent : ${selecteur}`)
  const fin = CSS.indexOf('}', debut)
  return CSS.slice(debut, fin + 1)
}

describe('scrollbar fine', () => {
  it('les deux themes declarent les tokens de la poignee', () => {
    for (const theme of [':root', '.dark']) {
      const contenu = bloc(theme)
      expect(contenu, `${theme} ne declare pas la poignee`).toContain('--scrollbar-thumb:')
      expect(contenu, `${theme} ne declare pas le survol`).toContain('--scrollbar-thumb-hover:')
    }
  })

  it('les deux themes donnent une poignee differente', () => {
    const clair = bloc(':root').match(/--scrollbar-thumb:\s*([^;]+);/)?.[1].trim()
    const sombre = bloc('.dark').match(/--scrollbar-thumb:\s*([^;]+);/)?.[1].trim()
    // Sans cela, la poignee garde la meme valeur la nuit et disparait sur le navy.
    expect(clair).toBeTruthy()
    expect(sombre).toBeTruthy()
    expect(clair).not.toBe(sombre)
  })

  it('Firefox recoit scrollbar-width et scrollbar-color', () => {
    expect(CSS).toMatch(/scrollbar-width:\s*thin/)
    expect(CSS).toMatch(/scrollbar-color:\s*hsl\(var\(--scrollbar-thumb\)\)\s*transparent/)
  })

  it('les moteurs WebKit recoivent la largeur et la poignee arrondie', () => {
    const barre = bloc('*::-webkit-scrollbar')
    expect(barre).toMatch(/width:\s*8px/)

    const poignee = bloc('*::-webkit-scrollbar-thumb')
    expect(poignee).toMatch(/hsl\(var\(--scrollbar-thumb\)\)/)
    expect(poignee).toMatch(/border-radius:\s*9999px/)

    const survol = bloc('*::-webkit-scrollbar-thumb:hover')
    expect(survol).toMatch(/hsl\(var\(--scrollbar-thumb-hover\)\)/)
  })

  it('la transition est declaree sous prefers-reduced-motion', () => {
    expect(CSS).toContain('prefers-reduced-motion: no-preference')
    // La media query doit contenir la transition, sinon elle s'applique partout.
    const debut = CSS.indexOf('prefers-reduced-motion: no-preference')
    const media = CSS.slice(debut, CSS.indexOf('}', debut))
    expect(media).toContain('transition')
  })

  it('aucune couleur en dur dans les regles de scrollbar', () => {
    const debut = CSS.indexOf('::-webkit-scrollbar')
    const fin = CSS.indexOf('.scrollbar-none')
    const zone = CSS.slice(debut, fin === -1 ? undefined : fin)
    // Un triplet HSL est un token de Tailwind et se declare dans :root ou .dark.
    expect(zone).not.toMatch(/#[0-9a-f]{3,8}\b/i)
    expect(zone).not.toMatch(/\brgba?\(/)
    expect(zone).not.toMatch(/\bhsla?\(\s*\d/)
  })

  it('le masquage existant reste disponible pour la navigation laterale', () => {
    // `.scrollbar-none` est pose sur la navigation du rail, qui masque sa barre.
    // Les deux cohabitent : la regle globale est en base, celle-ci en components.
    expect(CSS).toMatch(/\.scrollbar-none\s*\{[^}]*scrollbar-width:\s*none/)
  })
})