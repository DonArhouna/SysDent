/**
 * Le client et le serveur doivent demander **exactement le meme droit** pour le
 * meme geste. Ce test le verifie en lisant la source du routeur backend.
 *
 * **Pourquoi une lecture de source plutot qu'un test d'ecran.** Un ecran peut
 * etre correct pendant que la route ne l'est pas, et l'inverse : les deux
 * peuvent diverger sans qu'aucun des deux jeu de tests ne le voie. L'ecart
 * s'est deja produit - le client exigeait `TARIFS:WRITE` pour un organisme
 * pendant que le serveur acceptait `ASSURANCE:WRITE`. Le client etait plus
 * strict, donc rien ne cassait et rien ne le signalait.
 *
 * **Ce que le test compare.** Pour chaque route d'ecriture de la tarification,
 * la permission declaree cote serveur. Puis, pour chaque constante du client,
 * la permission attendue. Les deux listes doivent etre identiques.
 *
 * Une constante renommee cote client, une garde oubliee cote serveur, un droit
 * reintroduit : les trois font echouer ici, avec un message qui nomme la route.
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  PERM_ASSURANCE_READ,
  PERM_ASSURANCE_WRITE,
  PERM_ORGANISMES_WRITE,
  PERM_TARIFS_READ,
  PERM_TARIFS_WRITE,
} from '@/features/tarification/types'

const RACINE = join(process.cwd(), '..')
const ROUTER = join(RACINE, 'Backend', 'src', 'modules', 'tarification', 'router.py')

function source(): string {
  return readFileSync(ROUTER, 'utf-8')
}

/**
 * Permission exigee par une route du serveur.
 *
 * On isole la fonction plutot que de chercher la premiere occurrence du nom :
 * les memes noms de routes apparaissent dans la documentation et dans d'autres
 * decorateurs, et une lecture approximative donnerait un droit faux sans
 * jamais echouer.
 */
function permissionDe(methode: 'post' | 'patch' | 'delete', chemin: string): string {
  const texte = source()
  // Le decorateur **complet**, methode comprise. Chercher le chemin seul
  // prendrait la route de lecture qui precede : `"/organismes"` designe aussi
  // bien le GET que le POST, et le premier trouve est le GET. Une lecture
  // approximative donnerait un droit faux sans jamais echouer.
  const motif = new RegExp(
    '@router\\.' + methode + '\\(\\s*\\n?\\s*"' + chemin.replace(/[{}]/g, '\\$&') + '"',
  )
  const debutRoute = motif.exec(texte)
  if (!debutRoute) {
    throw new Error(`Route absente du routeur : ${methode.toUpperCase()} ${chemin}`)
  }

  const debutFonction = texte.indexOf('\nasync def ', debutRoute.index)
  const fin = texte.indexOf('\n@router.', debutFonction)
  const corps = texte.slice(debutFonction, fin < 0 ? texte.length : fin)

  const garde = /require_permissions\("([A-Z_]+:[A-Z_]+)"\)/.exec(corps)
  if (!garde) throw new Error(`Aucune garde lisible sur ${methode.toUpperCase()} ${chemin}`)
  return garde[1]!
}

/** Ecritures declarees par le serveur, groupees par ressource. */
const ECRITURES = {
  organismes: [
    ['post', '/organismes'],
    ['patch', '/organismes/{organisme_id}'],
    ['delete', '/organismes/{organisme_id}'],
  ],
  droits: [
    ['post', '/patients/{patient_id}/droits'],
    ['patch', '/droits/{droit_id}'],
    ['delete', '/droits/{droit_id}'],
  ],
} as const

describe('Le client et le serveur demandent le meme droit', () => {
  it('ecrire un organisme demande la meme permission des deux cotes', () => {
    for (const [methode, chemin] of ECRITURES.organismes) {
      expect(
        permissionDe(methode, chemin),
        `${methode.toUpperCase()} ${chemin}`,
      ).toBe(PERM_ORGANISMES_WRITE)
    }
  })

  it('ecrire un droit de patient demande la meme permission des deux cotes', () => {
    for (const [methode, chemin] of ECRITURES.droits) {
      expect(
        permissionDe(methode, chemin),
        `${methode.toUpperCase()} ${chemin}`,
      ).toBe(PERM_ASSURANCE_WRITE)
    }
  })

  it('les deux droits d\'ecriture sont bien distincts', () => {
    // Le defaut qu'on corrigeait : un seul droit pour deux gestes sans rapport.
    expect(PERM_ORGANISMES_WRITE).not.toBe(PERM_ASSURANCE_WRITE)
  })

  it('le client ne mentionne plus l\'ancien droit unifie', () => {
    const fichiers = [
      join(process.cwd(), 'src', 'features', 'tarification', 'types.ts'),
      join(process.cwd(), 'src', 'features', 'tarification', 'pages', 'organismes-page.tsx'),
      join(process.cwd(), 'src', 'features', 'tarification', 'pages', 'tarification-page.tsx'),
      join(process.cwd(), 'src', 'features', 'tarification', 'components', 'droits-patient-panel.tsx'),
    ]
    for (const fichier of fichiers) {
      // Le code sans ses commentaires : ceux-ci citent l'ancien droit pour
      // expliquer pourquoi il a disparu, et le citer estexactement ce qu'on
      // veut pouvoir faire. Une chaine simple suffit, l'ancien droit n'a jamais
      // ete affecte.
      const texte = readFileSync(fichier, 'utf-8')
        .split('\n')
        .filter((ligne) => !ligne.trim().startsWith('*') && !ligne.trim().startsWith('//'))
        .join('\n')
      expect(texte, fichier).not.toMatch(/'ASSURANCE:WRITE'/)
    }
  })

  it('le serveur ne declare plus l\'ancien droit unifie', () => {
    expect(source()).not.toContain('require_permissions("ASSURANCE:WRITE")')
  })

  it('les permissions de lecture n\'ont pas bouge', () => {
    expect(PERM_TARIFS_READ).toBe('TARIFS:READ')
    expect(PERM_TARIFS_WRITE).toBe('TARIFS:WRITE')
    expect(PERM_ASSURANCE_READ).toBe('ASSURANCE:READ')
  })
})