/**
 * Types de la tarification et de la prise en charge (CDC 5.6 et 5.7).
 *
 * Les montants sont des **chaines**, pas des nombres. Le serveur les renvoie en
 * `Decimal` et les accepte en `Decimal` : un `number` en JavaScript perd la
 * précision sur un montant de facture, et un arrondi ne se voit qu'a la
 * comparaison. La conversion en nombre se fait au moment de l'affichage, une
 * fois, et jamais pour recomparer.
 *
 * Aucun code de catégorie, de type d'organisme ou d'état n'est écrit en dur
 * ici : la catégorie se liste, l'organisme aussi. Le seul code figé est
 * `standard`, parce qu'il est créé par la migration et qu'un acte doit toujours
 * avoir un tarif de référence.
 */

/** Catégorie de référence, créée automatiquement pour tout cabinet. */
export const CODE_CATEGORIE_STANDARD = 'standard'

/** Permissions qui conditionnent l'affichage des boutons d'écriture. */
export const PERM_TARIFS_WRITE = 'TARIFS:WRITE'
export const PERM_TARIFS_READ = 'TARIFS:READ'
export const PERM_ASSURANCE_READ = 'ASSURANCE:READ'
/**
 * Ecriture d'un **droit de prise en charge**, pour un patient donne.
 *
 * Ce n'est pas la meme chose qu'ecrire un organisme, et la confusion a
 * reellement existe cote serveur : un `ASSURANCE:WRITE` unique couvrait les
 * deux. Le secretariat pouvait donc creer un organisme payeur - un referentiel
 * dont une erreur se propage a tous les patients - alors que sa mission est de
 * saisir une carte de mutuelle.
 *
 * Le droit a ete separe : `ASSURANCE:WRITE_PATIENT` couvre le droit d'un
 * patient, un organisme exige `TARIFS:WRITE` comme la nomenclature.
 */
export const PERM_ASSURANCE_WRITE = 'ASSURANCE:WRITE_PATIENT'

/**
 * Ecriture d'un **organisme payeur**, et non d'un droit de patient.
 *
 * Ce n'est pas `ASSURANCE:WRITE_PATIENT`. Un organisme est un referentiel du
 * cabinet, comme la nomenclature : le creer ou le renommer change ce que tous
 * les patients pourront designer, et une erreur se propage a chaque facture. Un
 * droit de prise en charge, lui, ne concerne qu'une fiche.
 *
 * Le separateur utilise ici est donc `TARIFS:WRITE`, accorde a `ADMIN_CABINET`
 * seul, et c'est **le separateur que le serveur verifie** sur ces routes depuis
 * la matrice validee. Le client n'est plus en avant du serveur : les deux sont
 * d'accord. `test_matrice-assurance-alignee.test.ts` echoue des que l'un des
 * deux change.
 */
export const PERM_ORGANISMES_WRITE = PERM_TARIFS_WRITE

/** Type d'un organisme payeur. Les deux viennent du serveur, jamais d'une liste locale. */
export type TypeOrganisme = 'ASSURANCE' | 'MUTUELLE'

export interface TarifActe {
  id: string
  acte_id: string
  categorie_code: string
  /** Montant en FCFA, sous forme de chaine pour préserver la précision. */
  montant: string
}

export interface ActeNomenclature {
  id: string
  code: string
  libelle: string
  categorie: string
  tarif_base: string
  duree_estimee_min: number
  unitaire: boolean
  actif: boolean
  tarifs: TarifActe[]
}

export interface CategoriePatient {
  id: string
  code: string
  libelle: string
  ordre: number
  par_defaut: boolean
}

export interface OrganismeAssurance {
  id: string
  code: string
  nom: string
  type_organisme: string
  actif: boolean
}

export interface DroitPriseEnCharge {
  id: string
  patient_id: string
  organisme_id: string
  numero_police: string | null
  taux_prise_en_charge: string
  priorite: number
  actif: boolean
  organisme_nom: string | null
  organisme_code: string | null
}

// ---------------------------------------------------------------------------
// Corps d'ecriture. Un type par operation : c'est ce que la garde de contrat
// compare au schema OpenAPI, champ par champ.
// ---------------------------------------------------------------------------

export interface ActeCreate {
  code: string
  libelle: string
  categorie: string
  tarif_base: string
  duree_estimee_min: number
  unitaire: boolean
}

export interface ActeUpdate {
  libelle?: string
  categorie?: string
  duree_estimee_min?: number
  unitaire?: boolean
  actif?: boolean
}

export interface TarifUpsert {
  categorie_code: string
  montant: string
}

export interface OrganismeCreate {
  code: string
  nom: string
  type_organisme: string
  actif?: boolean
}

export interface OrganismeUpdate {
  nom?: string
  type_organisme?: string
  actif?: boolean
}

export interface DroitCreate {
  organisme_id: string
  numero_police?: string | null
  taux_prise_en_charge: string
  priorite: number
  actif?: boolean
}

export interface DroitUpdate {
  organisme_id?: string
  numero_police?: string | null
  taux_prise_en_charge?: string
  priorite?: number
  actif?: boolean
}

/** Bornes de validation, alignees sur les `CHECK` de la base. */
export const TAUX_MIN = 0
export const TAUX_MAX = 100
export const MONTANT_MIN = 0

export function formaterMontant(montant: string | number | null | undefined): string {
  if (montant === null || montant === undefined || montant === '') return '-'
  const nombre = typeof montant === 'number' ? montant : Number(montant)
  if (Number.isNaN(nombre)) return '-'
  return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(nombre)} FCFA`
}