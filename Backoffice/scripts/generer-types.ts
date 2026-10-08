/**
 * Generation et verification du client TypeScript depuis l'OpenAPI du backend.
 *
 * **Pourquoi ce script existe.** `package.json` declarait `types:generer` et
 * `contrat:verifier` en appelant ce fichier, qui n'existait pas : les deux
 * commandes echouaient en `ERR_MODULE_NOT_FOUND`. La regle du projet - « noms de
 * champs verifies des deux cotes dans le meme commit » - etait donc invérifiable,
 * et rien ne la faisait. C'est exactement ce qui a permis a un test d'ecran de
 * mentir : la reponse de login etait declaree `APIResponse[dict]`, donc absente
 * du schema, donc invérifiable des deux cotes.
 *
 * **Deux modes.**
 *
 * - `types:generer`  : ecrit `src/lib/openapi.d.ts` depuis `openapi.json`.
 * - `contrat:verifier`: regenere en memoire et **echoue** si le fichier versionne
 *   ne correspond pas. C'est le controle a passer en CI et avant commit : une
 *   modification d'API non reportee dans le front doit casser la verification,
 *   pas passer en silence jusqu'au premier 422 en production.
 *
 * `openapi.json` se regenere cote backend :
 *
 * ```powershell
 * cd Backend
 * python scripts/exporter_openapi.py
 * ```
 */

import { readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import openapiTS, { astToString, type OpenAPITSOptions } from 'openapi-typescript'

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..')
const SCHEMA = join(RACINE, 'openapi.json')
const CIBLE = join(RACINE, 'src', 'lib', 'openapi.d.ts')

const verifier = process.argv.includes('--verifier')

/**
 * `emptyObjectsUnknown` : le backend renvoie des `dict` non types sur 9 routes.
 * Les laisser en `unknown` ferait echouer le type-check des que le front touche
 * une de ces reponses, ce qui est **voulu** : tant qu'elles ne sont pas typees,
 * le front ne doit pas pouvoir ecrire `data.champ` au hasard.
 */
const options: OpenAPITSOptions = {
  emptyObjectsUnknown: true,
  alphabetize: true,
}

async function generer(): Promise<string> {
  if (!existsSync(SCHEMA)) {
    console.error(
      `\n  openapi.json absent : ${SCHEMA}\n` +
        `  Le generer depuis le backend :\n\n` +
        `      cd Backend\n` +
        `      .\\.venv\\Scripts\\python.exe scripts\\exporter_openapi.py\n`,
    )
    process.exit(2)
  }
  const brut = await readFile(SCHEMA, 'utf-8')
  // v7 renvoie un **AST** TypeScript, pas une chaine : sans `astToString`, la
  // sortie etait `[object Object]` repete, soit un fichier vide qui compilait
  // encore - le pire des deux.
  return astToString(await openapiTS(JSON.parse(brut), options))
}

async function main(): Promise<void> {
  const genere = await generer()
  const entete =
    '/* Fichier genere. Ne pas editer a la main.\n' +
    '   Source : openapi.json (Backend/scripts/exporter_openapi.py)\n' +
    '   Regenerer : npm run types:generer\n' +
    '   Verifier  : npm run contrat:verifier */\n'

  if (verifier) {
    if (!existsSync(CIBLE)) {
      console.error(
        '\n  src/lib/openapi.d.ts est absent.\n' +
          '  Le client TypeScript genere n a jamais ete produit :\n\n' +
          '      npm run types:generer\n',
      )
      process.exit(1)
    }
    const versionne = await readFile(CIBLE, 'utf-8')
    // La comparaison porte sur `entete + genere` : le fichier ecrit commence par
    // l'entete, comparer seulement `genere` faisait echouer la verification en
    // permanence. Un controle qui echoue toujours est un controle qu'on ignore -
    // pire que pas de controle du tout.
    if (versionne !== entete + genere) {
      console.error(
        '\n  CONTRAT PERIME : src/lib/openapi.d.ts ne correspond plus a openapi.json.\n' +
          "  L'API a change sans que le client TypeScript soit regenere.\n" +
          '  Regenerez : npm run types:generer\n',
      )
      process.exit(1)
    }
    console.log('  contrat a jour : le client TypeScript correspond a openapi.json')
    return
  }

  await writeFile(CIBLE, entete + genere, 'utf-8')
  console.log(`  ecrit : src/lib/openapi.d.ts`)
}

main().catch((e: unknown) => {
  console.error(e)
  process.exit(1)
})