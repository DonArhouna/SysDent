/**
 * Parité des tokens entre l'application client et le backoffice.
 *
 * Compare les variables extraites de `../Frontend/src/index.css` et
 * `src/index.css`. Tout écart fait échouer le script — sauf s'il figure dans
 * `scripts/design-ecarts-autorises.json`, avec justification obligatoire.
 *
 * Usage : `npm run design:parite`
 */
import fs from 'node:fs'
import path from 'node:path'
import url from 'node:url'

const __dirname = path.dirname(url.fileURLToPath(import.meta.url))
const racineProjet = path.resolve(__dirname, '..')

const CHEMIN_CLIENT = path.join(racineProjet, '..', 'Frontend', 'src', 'index.css')
const CHEMIN_BO = path.join(racineProjet, 'src', 'index.css')
const CHEMIN_ECARTS = path.join(__dirname, 'design-ecarts-autorises.json')

function lireTokens(fichier) {
  const texte = fs.readFileSync(fichier, 'utf-8')
  const tokens = new Map()
  // Les variables clair / sombre portent le même nom. Pour distinguer, on
  // découpe le CSS sur les blocs `:root { ... }` et `.dark { ... }`, et on
  // préfixe la clé de bloc. La comparaison sera bloc par bloc.
  const BLOCS = [':root', '.dark']
  for (const nomDuBloc of BLOCS) {
    // `:root {` ... `}` , avec la suite du fichier pour .dark.
    const m = texte.match(new RegExp(
      `${nomDuBloc.replace('.', '\\.')}\\s*\\{([\\s\\S]*?)\\n\\s*\\}`,
    ))
    if (!m) continue
    for (const v of m[1].matchAll(/(^|\n)\s*(--[\w-]+)\s*:\s*([^;]+);/g)) {
      tokens.set(
        `${nomDuBloc} ${v[2]}`,
        v[3].trim().replace(/\s*\/\*.*$/, '').trim(),
      )
    }
  }
  return tokens
}

const client = lireTokens(CHEMIN_CLIENT)
const backoffice = lireTokens(CHEMIN_BO)

const DONNEES_ECARTS = JSON.parse(fs.readFileSync(CHEMIN_ECARTS, 'utf-8'))
const ecartsAutorises = DONNEES_ECARTS.ecarts_autorises ?? {}

// Tokens propres au backoffice (l'inverse de « copié à l'identique »).
const PROPRES_BO = [':root --plateforme', ':root --plateforme-foreground', '.dark --plateforme', '.dark --plateforme-foreground']

let ecarts = []

// 1. Chaque token du client doit exister à la même valeur dans le backoffice.
for (const [nom, valeur] of client) {
  if (PROPRES_BO.includes(nom)) continue
  if (!backoffice.has(nom)) {
    ecarts.push(`absent au backoffice : ${nom}`)
    continue
  }
  if (backoffice.get(nom) !== valeur) {
    ecarts.push(
      `valeur différente : ${nom} : client "${valeur}" ≠ backoffice "${backoffice.get(nom)}"`,
    )
  }
}

// 2. Un token autorisé à différer mais absent des deux côtés est aussi une anomalie.
for (const cle of Object.keys(ecartsAutorises)) {
  if (!client.has(cle)) {
    ecarts.push(`token autorisé à différer mais introuvable chez le client : ${cle}`)
  }
}

if (ecarts.length > 0) {
  console.error('PARITÉ DES TOKENS ROMPUE :')
  for (const e of ecarts) console.error('  -', e)
  console.error('')
  console.error(`Écarts autorisés : ${CHEMIN_ECARTS} (justification obligatoire par entrée).`)
  process.exit(1)
}

const debut = Date.now()
console.log(`Parité vérifiée : ${client.size} tokens identiques (clair et sombre), ${Object.keys(ecartsAutorises).length} écarts autorisés. Durée : ${Date.now() - debut} ms`)
