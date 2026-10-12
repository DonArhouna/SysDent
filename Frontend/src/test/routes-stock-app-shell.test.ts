import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Chaque route du module Stock doit passer par la coquille applicative.
 *
 * **Le défaut.** `/stock/fournisseurs` etait declaree sans `<AppShell>` : la page
 * prenait tout l'ecran, sans sidebar ni navbar. Une seule route sur trois, les
 * deux autres etant correctes : c'est le genre d'oubli qu'aucun test de rendu
 * ne rattrape, puisque chaque page se rend bien isolement.
 *
 * **Pourquoi un test structurel.** Rendre `/stock/fournisseurs` demande un store
 * de session, un client de requetes et un routeur ; le test passerait surtout a
 * verifier sa propre mise en place. Lire la declaration teste exactement ce
 * qui a ete casse : l'enveloppe, et non le rendu. C'est le meme choix que le
 * test d'alignement de la matrice assurance, qui lit le routeur du serveur.
 *
 * **La lecture est stricte.** Le bloc de chaque route est decoupe sur sa
 * declaration, pas recherche par motif : une recherche par `includes`
 * accepterait une enveloppe appartenant a une autre route voisine.
 */

const SOURCE = resolve(__dirname, '../App.tsx')

function routesDuModuleStock(source: string): { chemin: string; bloc: string }[] {
  // Un bloc va d'un `<Route` au suivant. Couper au premier `/>` ne marche pas :
  // `<StockPage />` en contient un, et le bloc serait tronque avant
  // `</AppShell>`, donc le test echouerait meme sur une route correcte.
  const positions: number[] = []
  const ouverture = /<Route\b/g
  let trouve: RegExpExecArray | null
  while ((trouve = ouverture.exec(source)) !== null) {
    positions.push(trouve.index)
  }

  const routes: { chemin: string; bloc: string }[] = []
  for (let i = 0; i < positions.length; i += 1) {
    const debut = positions[i]
    const fin = i + 1 < positions.length ? positions[i + 1] : source.length
    const bloc = source.slice(debut, fin)
    const chemin = bloc.match(/path="([^"]+)"/)?.[1]
    if (chemin && (chemin === '/stock' || chemin.startsWith('/stock/'))) {
      routes.push({ chemin, bloc })
    }
  }
  return routes
}

describe('routes du module Stock', () => {
  const source = readFileSync(SOURCE, 'utf-8')
  const routes = routesDuModuleStock(source)

  it('trouve les trois routes attendues, sinon le test ne prouve plus rien', () => {
    // Un parseur qui ne verrait rien ferait passer le reste au vert.
    expect(routes.map((r) => r.chemin).sort()).toEqual([
      '/stock',
      '/stock/commandes',
      '/stock/fournisseurs',
    ])
  })

  it.each(['/stock', '/stock/commandes', '/stock/fournisseurs'])(
    'la route %s est enveloppee dans AppShell',
    (chemin) => {
      const route = routes.find((r) => r.chemin === chemin)
      expect(route, `route ${chemin} introuvable`).toBeDefined()
      expect(route!.bloc).toContain('<AppShell>')
      expect(route!.bloc).toContain('</AppShell>')
    },
  )
})