/**
 * Test de contrat de la tarification : chaque corps envoye passe le schema
 * OpenAPI genere.
 *
 * **Pourquoi lire `Backoffice/openapi.json`.** C'est le document produit par
 * `Backend/scripts/exporter_openapi.py` a partir de l'application reelle, et il
 * est versionne. Un corps d'ecrit valide ici est un corps que le serveur
 * acceptera : la comparaison se fait champ par champ contre le vrai schema,
 * pas contre une recopie du type TypeScript, qui peut diverger en meme temps
 * que la verite.
 *
 * **Ce que ce test attrape.** Une cle mal orthographiee, un `tarif_base`
 * envoye en nombre au lieu de chaine, un champ obligatoire oublie, une methode
 * qui n'existe pas sur la route. Aucun de ces cas ne fait echouer `tsc` : le
 * type TypeScript est declare a la main des deux cotes, donc il peut mentir
 * autant que le backend. Ici, une seule des deux sources fait foi.
 *
 * **Les 422 que le client ne peut pas eviter.** Une violation de `pattern`,
 * de `minLength` ou de bornes est refusee. On les declare plutot que de les
 * ignorer : ce sont les regles que le formulaire doit appliquer, et les
 * ignorer rendrait le test muet.
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { CODE_CATEGORIE_STANDARD } from '@/features/tarification/types'

/** Lecture d'un fichier de `src`, pour les gardes qui portent sur la source. */
function io(chemin: string): string {
  return readFileSync(chemin, 'utf-8')
}

const OPENAPI = JSON.parse(
  readFileSync(join(process.cwd(), '..', 'Backoffice', 'openapi.json'), 'utf-8'),
) as {
  paths: Record<string, Record<string, Operation>>
  components: { schemas: Record<string, Schema> }
}

interface Schema {
  type?: string
  format?: string
  properties?: Record<string, Schema>
  required?: string[]
  items?: Schema
  anyOf?: Schema[]
  enum?: string[]
  minimum?: number
  maximum?: number
  minLength?: number
  maxLength?: number
  pattern?: string
  $ref?: string
  default?: unknown
  nullable?: boolean
  additionalProperties?: boolean | Schema
}

interface Operation {
  requestBody?: { content: { 'application/json': { schema: Schema } } }
  parameters?: Array<{ name: string; in: string; required?: boolean; schema: Schema }>
}

function resoudre(schema: Schema): Schema {
  let courant = schema
  const vus = new Set<string>()
  while (courant.$ref) {
    const nom = courant.$ref.replace('#/components/schemas/', '')
    if (vus.has(nom)) throw new Error(`Reference circulaire dans le schema : ${nom}`)
    vus.add(nom)
    courant = OPENAPI.components.schemas[nom]
    if (!courant) throw new Error(`Schema introuvable : ${nom}`)
  }
  return courant
}

/** Schema du corps d'une requete, resolu jusqu'a ses proprietes reelles. */
function schemaCorps(methode: 'post' | 'put' | 'patch', chemin: string): Schema {
  const operation = OPENAPI.paths[chemin]?.[methode]
  if (!operation) {
    throw new Error(`Route absente du contrat : ${methode.toUpperCase()} ${chemin}`)
  }
  const brut = operation.requestBody?.content['application/json']?.schema
  if (!brut) throw new Error(`${methode.toUpperCase()} ${chemin} n'a pas de corps declare.`)
  return resoudre(brut)
}

type Verdict = { ok: true } | { ok: false; raison: string }

function valider(schema: Schema, valeur: unknown, chemin = 'corps'): Verdict {
  const s = resoudre(schema)

  // Un `anyOf` est tranche **avant** le cas `null`. Pydantic produit
  // `anyOf: [{type: string}, {type: null}]` pour un `Optional[str]` : tester
  // `null` avant l'`anyOf` ferait croire que le champ est requis, alors qu'il
  // est justement facultatif. C'est l'ordre inverse qui ment.
  if (s.anyOf) {
    const alternatives = s.anyOf.map(resoudre)
    const raison = alternatives
      .map((a) => valider(a, valeur, chemin))
      .filter((v) => !v.ok)
      .map((v) => (v as { raison: string }).raison)
    if (raison.length < alternatives.length) return { ok: true }
    return { ok: false, raison: `${chemin} : ${raison.join(' ; ')}` }
  }

  if (s.enum) {
    if (typeof valeur !== 'string' || !s.enum.includes(valeur)) {
      return { ok: false, raison: `${chemin} : « ${String(valeur)} » hors de ${s.enum.join(' | ')}` }
    }
    return { ok: true }
  }

  if (s.type === 'null') {
    return valeur === null
      ? { ok: true }
      : { ok: false, raison: `${chemin} : null attendu` }
  }

  // Un champ absent est traite par `required`, pas par une erreur ici.
  if (valeur === null || valeur === undefined) {
    return s.nullable === true
      ? { ok: true }
      : { ok: false, raison: `${chemin} : valeur absente alors qu'elle est requise` }
  }

  switch (s.type) {
    case 'string': {
      if (typeof valeur !== 'string') {
        return { ok: false, raison: `${chemin} : chaine attendue, ${typeof valeur} recu` }
      }
      if (s.minLength !== undefined && valeur.length < s.minLength) {
        return { ok: false, raison: `${chemin} : longueur ${valeur.length} < ${s.minLength}` }
      }
      if (s.maxLength !== undefined && valeur.length > s.maxLength) {
        return { ok: false, raison: `${chemin} : longueur ${valeur.length} > ${s.maxLength}` }
      }
      if (s.pattern && !new RegExp(s.pattern).test(valeur)) {
        return { ok: false, raison: `${chemin} : « ${valeur} » ne respecte pas ${s.pattern}` }
      }
      return { ok: true }
    }
    case 'number':
    case 'integer': {
      if (typeof valeur !== 'number') {
        return { ok: false, raison: `${chemin} : nombre attendu, ${typeof valeur} recu` }
      }
      if (s.minimum !== undefined && valeur < s.minimum) {
        return { ok: false, raison: `${chemin} : ${valeur} < ${s.minimum}` }
      }
      if (s.maximum !== undefined && valeur > s.maximum) {
        return { ok: false, raison: `${chemin} : ${valeur} > ${s.maximum}` }
      }
      return { ok: true }
    }
    case 'boolean': {
      if (typeof valeur !== 'boolean') {
        return { ok: false, raison: `${chemin} : booleen attendu, ${typeof valeur} recu` }
      }
      return { ok: true }
    }
    case 'array': {
      if (!Array.isArray(valeur)) {
        return { ok: false, raison: `${chemin} : tableau attendu` }
      }
      if (s.items) {
        for (const [index, element] of valeur.entries()) {
          const verdict = valider(s.items, element, `${chemin}[${index}]`)
          if (!verdict.ok) return verdict
        }
      }
      return { ok: true }
    }
    case 'object': {
      if (typeof valeur !== 'object' || Array.isArray(valeur)) {
        return { ok: false, raison: `${chemin} : objet attendu` }
      }
      const objet = valeur as Record<string, unknown>
      for (const nom of s.required ?? []) {
        if (objet[nom] === undefined || objet[nom] === null) {
          return { ok: false, raison: `${chemin}.${nom} : champ requis absent` }
        }
      }
      for (const [nom, contenu] of Object.entries(objet)) {
        if (contenu === undefined) continue
        const sous = s.properties?.[nom]
        if (!sous) {
          // `additionalProperties` absent : le champ est en trop.
          if (s.additionalProperties === false) {
            return { ok: false, raison: `${chemin}.${nom} : champ non declare` }
          }
          continue
        }
        const verdict = valider(sous, contenu, `${chemin}.${nom}`)
        if (!verdict.ok) return verdict
      }
      return { ok: true }
    }
    default:
      // Sans `type`, le schema ne dit rien : on ne peut rien interdire.
      return { ok: true }
  }
}

function attendreValide(schema: Schema, corps: unknown): void {
  const verdict = valider(schema, corps)
  if (!verdict.ok) throw new Error(verdict.raison)
}

describe('Contrat de la tarification', () => {
  it('le document OpenAPI contient bien les routes de la tarification', () => {
    const chemins = Object.keys(OPENAPI.paths).filter((c) => c.includes('/tarification/'))
    expect(chemins.length).toBeGreaterThanOrEqual(10)
  })

  it('la creation d\'un acte passe le schema', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/actes')
    attendreValide(schema, {
      code: 'DT01',
      libelle: 'Denture partielle',
      categorie: 'PROTHESE',
      tarif_base: '12500.00',
      duree_estimee_min: 30,
      unitaire: false,
    })
  })

  it('le montant accepte la chaine, et le client envoie la chaine', () => {
    const tarif = resoudre(schemaCorps('post', '/api/v1/tarification/actes')).properties
      ?.tarif_base as Schema
    expect(tarif).toBeDefined()
    // Le serveur accepte les deux formes : Pydantic convertit la chaine en
    // `Decimal`. La chaine reste la forme du client, pour que l'affichage ne
    // depende jamais d'un arrondi de `number`.
    expect(valider(tarif, '12500.00').ok).toBe(true)
    expect(valider(tarif, '12500').ok).toBe(true)
    expect(valider(tarif, 12500).ok).toBe(true)
  })

  it('en forme numerique, le schema refuse un montant negatif', () => {
    const tarif = resoudre(schemaCorps('post', '/api/v1/tarification/actes')).properties
      ?.tarif_base as Schema
    // La borne `minimum: 0` n'existe que sur la branche numerique.
    expect(valider(tarif, -1).ok).toBe(false)
  })

  it('un code trop court est refuse, comme le formulaire doit le faire', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/actes')
    const verdict = valider(schema, {
      code: 'D',
      libelle: 'Denture',
      categorie: 'PROTHESE',
      tarif_base: '100.00',
    })
    expect(verdict.ok).toBe(false)
  })

  it('l\'edition d\'un acte passe le schema et ne porte aucun tarif', () => {
    const schema = schemaCorps('patch', '/api/v1/tarification/actes/{acte_id}')
    attendreValide(schema, { libelle: 'Denture titane', actif: false })

    // Le tarif n'est **pas** dans le schema d'edition. Le serveur l'ignorerait
    // s'il etait envoye : Pydantic ne conserve que les champs declares, donc
    // un `tarif_base` transmis ne change rien et ne signale rien.
    //
    // C'est pour cela que la garde porte sur la **presence du champ** et pas
    // seulement sur le refus d'une valeur : un schema qui refuserait le champ
    // donnerait un 422, un schema qui l'ignore donne un succes trompeur.
    const proprietes = resoudre(schema).properties ?? {}
    expect('tarif_base' in proprietes).toBe(false)
    expect('code' in proprietes).toBe(false)
  })

  it('l\'ecriture d\'un tarif passe le schema', () => {
    const schema = schemaCorps('put', '/api/v1/tarification/actes/{acte_id}/tarifs')
    attendreValide(schema, { categorie_code: CODE_CATEGORIE_STANDARD, montant: '12500.00' })
    const sansMontant = valider(schema, { categorie_code: CODE_CATEGORIE_STANDARD })
    expect(sansMontant.ok).toBe(false)
  })

  it('la creation d\'un organisme passe le schema', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/organismes')
    attendreValide(schema, {
      code: 'mut-test',
      nom: 'Mutuelle fictive',
      type_organisme: 'MUTUELLE',
      actif: true,
    })
    // Une nature hors des deux acceptees doit etre refusee avant l'envoi.
    const mauvaiseNature = valider(schema, {
      code: 'mut-test',
      nom: 'Mutuelle fictive',
      type_organisme: 'CPAM',
    })
    expect(mauvaiseNature.ok).toBe(false)
  })

  it('la creation d\'un droit de prise en charge passe le schema', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/patients/{patient_id}/droits')
    attendreValide(schema, {
      organisme_id: '3f2b9c40-1d2e-4f5a-8b7c-9d0e1f2a3b4c',
      numero_police: '2024-001234',
      taux_prise_en_charge: '70.00',
      priorite: 1,
      actif: true,
    })
  })

  it('le schema ne porte PAS la borne 0-100 sur la forme chaine', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/patients/{patient_id}/droits')
    const taux = resoudre(schema).properties?.taux_prise_en_charge as Schema

    // **Limite reelle du document, mesuree et non supposee.** Le champ est un
    // `anyOf` : un `number` borne, ou une chaine contrainte par un **motif de
    // forme**. Ce motif verifie qu'une chaine ressemble a un nombre decimal ;
    // il ne verifie pas sa valeur.
    //
    // Consequence : le schema OpenAPI **ne peut pas** garantir la borne, ni
    // meme « gratuit ». Pydantic, lui, l'applique apres conversion en
    // `Decimal` - verifie sur le serveur. Un client qui ne valide que par le
    // schema laisse donc passer `101.00`.
    //
    // C'est pourquoi la validation du taux est dans le formulaire, avec ses
    // tests, et pourquoi le `CHECK` de la base reste le dernier rempart. Ce
    // test fixe la limite pour que personne ne croie un jour que le schema
    // suffit.
    const [nombre, chaine] = taux.anyOf!.map(resoudre)
    expect(nombre.minimum).toBe(0)
    expect(nombre.maximum).toBe(100)

    const motif = new RegExp(chaine.pattern as string)
    expect(motif.test('70.00')).toBe(true)
    expect(motif.test('')).toBe(false)
    // Le motif accepte ces deux valeurs : la borne n'est pas dans le schema.
    expect(motif.test('101.00')).toBe(true)
    expect(motif.test('-1.00')).toBe(true)
  })

  it('en forme numerique, le schema refuse ce qui sort des bornes', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/patients/{patient_id}/droits')
    const base = {
      organisme_id: '3f2b9c40-1d2e-4f5a-8b7c-9d0e1f2a3b4c',
      priorite: 1,
    }
    expect(valider(schema, { ...base, taux_prise_en_charge: 100 }).ok).toBe(true)
    expect(valider(schema, { ...base, taux_prise_en_charge: 0 }).ok).toBe(true)
    expect(valider(schema, { ...base, taux_prise_en_charge: 101 }).ok).toBe(false)
    expect(valider(schema, { ...base, taux_prise_en_charge: -1 }).ok).toBe(false)
  })

  it('un numero de police vide est accepte, il est facultatif', () => {
    const schema = schemaCorps('post', '/api/v1/tarification/patients/{patient_id}/droits')
    // Le champ est un `anyOf` chaine / `null` : un numero de police absent se
    // dit `null`, pas une chaine vide. Le client envoie `null` explicitement.
    const police = resoudre(schema).properties?.numero_police as Schema
    expect(police.anyOf?.map(resoudre).map((v) => v.type)).toEqual(['string', 'null'])
    expect(valider(police, null).ok).toBe(true)
    expect(valider(police, '').ok).toBe(true)

    const verdict = valider(schema, {
      organisme_id: '3f2b9c40-1d2e-4f5a-8b7c-9d0e1f2a3b4c',
      numero_police: null,
      taux_prise_en_charge: '50.00',
      priorite: 1,
    })
    expect(verdict.ok).toBe(true)
  })

  it('les routes appelees par le client existent toutes', () => {
    // Chaque couple methode/chemin utilise par `tarification-api.ts`. Une route
    // renommee cote backend casse ici, pas au premier 404 en consultation.
    const attendu: Array<[string, string]> = [
      ['get', '/api/v1/tarification/actes'],
      ['post', '/api/v1/tarification/actes'],
      ['patch', '/api/v1/tarification/actes/{acte_id}'],
      ['get', '/api/v1/tarification/actes/{acte_id}/tarifs'],
      ['put', '/api/v1/tarification/actes/{acte_id}/tarifs'],
      ['delete', '/api/v1/tarification/actes/{acte_id}/tarifs/{tarif_id}'],
      ['get', '/api/v1/tarification/categories'],
      ['post', '/api/v1/tarification/categories'],
      ['patch', '/api/v1/tarification/categories/{code}'],
      ['delete', '/api/v1/tarification/categories/{code}'],
      ['get', '/api/v1/tarification/organismes'],
      ['post', '/api/v1/tarification/organismes'],
      ['patch', '/api/v1/tarification/organismes/{organisme_id}'],
      ['delete', '/api/v1/tarification/organismes/{organisme_id}'],
      ['get', '/api/v1/tarification/patients/{patient_id}/droits'],
      ['post', '/api/v1/tarification/patients/{patient_id}/droits'],
      ['patch', '/api/v1/tarification/droits/{droit_id}'],
      ['delete', '/api/v1/tarification/droits/{droit_id}'],
    ]
    for (const [methode, chemin] of attendu) {
      expect(OPENAPI.paths[chemin]?.[methode], `${methode.toUpperCase()} ${chemin}`).toBeDefined()
    }
  })

  it('les filtres envoyes en requete sont declares par le serveur', () => {
    // Un filtre que le serveur ignore ne rejette pas la requete et ne filtre
    // rien : la liste revient complete et l'ecran croit avoir filtre. Le
    // serveur etant strict sur les parametres inconnus (422), on verifie ici
    // que les noms correspondent.
    const noms = new Set(
      (OPENAPI.paths['/api/v1/tarification/actes']?.get?.parameters ?? []).map(
        (p) => p.name,
      ),
    )
    for (const filtre of ['q', 'categorie', 'actif', 'page', 'limit']) {
      expect(noms.has(filtre), `filtre « ${filtre} » absent du contrat`).toBe(true)
    }
  })

  it('le client n\'ajoute jamais de tarif au PATCH d\'un acte', () => {
    // Le garde sur la **source du client**, pas sur le schema seul.
    //
    // Le schema d'edition ne declare pas `tarif_base` : le serveur l'ignorerait
    // s'il etait transmis, donc un test « le corps passe le schema » ne verrait
    // rien. Il faut lire ce que le client envoie reellement.
    //
    // C'est le piege que la mutation A confirme : ajouter `tarif_base` au PATCH
    // ne fait echouer aucun test base sur le schema, et le prix changerait
    // silencieusement sous les factures emises.
    const source = io(
      join(process.cwd(), 'src', 'features', 'tarification', 'services', 'tarification-api.ts'),
    )
    const patch = source.slice(source.indexOf('modifierActe:'))
    const corps = patch.slice(0, patch.indexOf(',\n\n'))
    expect(corps).toContain('api.patch')
    expect(corps, 'le PATCH d\'un acte ne doit transporter aucun tarif').not.toContain(
      'tarif_base',
    )
  })

  it('le type du corps de PATCH ne declare pas le tarif', () => {
    // Deuxieme garde, sur la declaration de type : c'est elle que le
    // `tsc` verifie. Un `tarif_base?: string` y passerait le type-check et
    // autoriserait n'importe quel appelant a l'envoyer.
    const source = io(
      join(process.cwd(), 'src', 'features', 'tarification', 'types.ts'),
    )
    const debut = source.indexOf('export interface ActeUpdate')
    const interfaceActe = source.slice(debut, source.indexOf('}', debut))
    expect(interfaceActe).not.toContain('tarif_base')
    expect(interfaceActe).toContain('libelle')
  })

  it('aucun DELETE n\'expose la suppression d\'un acte', () => {
    // Un acte cite par une facture ne peut pas disparaitre : il se desactive.
    expect(OPENAPI.paths['/api/v1/tarification/actes/{acte_id}']?.delete).toBeUndefined()
  })
})