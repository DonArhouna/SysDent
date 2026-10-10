/**
 * Parité des **classes** des composants UI du backoffice avec ceux du client.
 *
 * Ce test ne rend rien : il lit le code source des deux applications et
 * exige que les composants jumeaux **partagent les classes principales**.
 * Un écart doit passer par `scripts/design-ecarts-autorises.json` côté
 * tokens — ici, une divergence de classes est un défaut, pas une évolution.
 */
import fs from 'node:fs'
import path from 'node:path'
import url from 'node:url'
import { describe, expect, it } from 'vitest'

// `__dirname` de Vitest est configurable selon l'environnement ; on part de
// l'emplacement du fichier (src/lib), en remontant vers la racine du projet.
const RACINE_BO = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '..', '..')
const CHEMIN_CLIENT_UI = path.join(RACINE_BO, '..', 'Frontend', 'src', 'components', 'ui')
const CHEMIN_BO_UI = path.join(RACINE_BO, 'src', 'components', 'ui')

function lire(nom: string, chemin: string): string {
  return fs.readFileSync(path.join(chemin, nom), 'utf-8')
}

/** La chaine d'attributs attendue doit figurer dans le fichier. */
function exige(fragment: string) {
  return (source: string, nom: string) =>
    expect(source, `${nom} devrait contenir « ${fragment} » (parité avec le client)`).toContain(
      fragment,
    )
}

const COMPOSANTS_PARITES: Array<{
  nom: string
  fragmentsClient: string[]
  fragmentsBO: string[]
}> = [
  {
    nom: 'status-badge.tsx',
    fragmentsClient: [
      'rounded-full border px-2.5 py-0.5 text-[11px] font-semibold',
      "neutral: 'border-border bg-muted text-muted-foreground'",
      "success: 'border-success/30 bg-success/10 text-success'",
      "warning: 'border-warning/30 bg-warning/10 text-warning'",
      "danger: 'border-danger/30 bg-danger/10 text-danger'",
      "purple: 'border-accent-purple/30 bg-accent-purple/10 text-accent-purple'",
    ],
    fragmentsBO: [
      'rounded-full border px-2.5 py-0.5 text-[11px] font-semibold',
      "neutral: 'border-border bg-muted text-muted-foreground'",
      "info: 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue'",
      "success: 'border-success/30 bg-success/10 text-success'",
      "warning: 'border-warning/30 bg-warning/10 text-warning'",
      "danger: 'border-danger/30 bg-danger/10 text-danger'",
    ],
  },
  {
    nom: 'pagination.tsx',
    fragmentsClient: ['ChevronLeft, ChevronRight', 'PageReponse'],
    fragmentsBO: ['ChevronLeft, ChevronRight', 'PageReponse'],
  },
  {
    nom: 'empty-state.tsx',
    fragmentsClient: [
      'flex flex-col items-center justify-center px-6 py-12 text-center',
      'rounded-xl2 bg-muted text-muted-foreground/70',
    ],
    fragmentsBO: [
      'flex flex-col items-center justify-center px-6 py-12 text-center',
      'rounded-xl2 bg-muted text-muted-foreground/70',
    ],
  },
  {
    nom: 'page-header.tsx',
    fragmentsClient: ['flex flex-wrap items-start justify-between gap-4', 'text-2xl font-bold tracking-tight'],
    fragmentsBO: ['flex flex-wrap items-start justify-between gap-4', 'text-2xl font-bold tracking-tight'],
  },
  {
    nom: 'table.tsx',
    fragmentsClient: [
      'w-full caption-bottom text-sm',
      '[&_tr]:border-b [&_tr]:border-border',
      'hover:bg-muted/50',
      'h-10 px-4 text-left align-middle text-xs font-semibold uppercase tracking-wide text-muted-foreground',
    ],
    fragmentsBO: [
      'w-full caption-bottom text-sm',
      '[&_tr]:border-b [&_tr]:border-border',
      'hover:bg-muted/50',
      'h-10 px-4 text-left align-middle text-xs font-semibold uppercase tracking-wide text-muted-foreground',
    ],
  },
]

const SYNCHRONISATION_STAT = path.join(RACINE_BO, '..', 'Frontend', 'src', 'components', 'dashboard', 'stat-card.tsx')
const SYNCHRONISATION_STAT_BO = path.join(RACINE_BO, 'src', 'components', 'ui', 'stat-card.tsx')

describe.sequential('parité visuelle avec le client (lecture de code, pas de rendu)', () => {
  for (const comp of COMPOSANTS_PARITES) {
    it(`${comp.nom} : classes principales identiques au client`, () => {
      const client = lire(comp.nom, CHEMIN_CLIENT_UI)
      const backoffice = lire(comp.nom, CHEMIN_BO_UI)

      for (const fragment of comp.fragmentsClient) {
        expect(client, `client / ${comp.nom}`).toContain(fragment)
      }
      for (const fragment of comp.fragmentsBO) {
        expect(backoffice, `backoffice / ${comp.nom}`).toContain(fragment)
      }
    })
  }

  it('stat-card.tsx : liseré, label majuscule, valeur, icône en pastille', () => {
    const client = fs.readFileSync(SYNCHRONISATION_STAT, 'utf-8')
    const backoffice = fs.readFileSync(SYNCHRONISATION_STAT_BO, 'utf-8')

    for (const fragment of [
      'flex items-start justify-between gap-4 rounded-xl2 border border-border border-l-4 bg-card p-5 shadow-float transition-shadow duration-200',
      'text-xs font-semibold uppercase tracking-wider text-muted-foreground',
      'icon-chip',
      'animate-pulse rounded-lg bg-muted',
    ]) {
      expect(client, `client / stat-card`).toContain(fragment)
      expect(backoffice, `backoffice / stat-card`).toContain(fragment)
    }
  })
})

// Utilisé pour le typage de `exige` (aucun usage à l'exécution, garantit la
// compilation sans consommateurs morts).
void exige
