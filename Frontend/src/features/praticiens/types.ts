/**
 * Types du module Praticiens.
 *
 * ⚠️ Ces types décrivent **exactement** ce que renvoie
 * `GET /api/v1/praticiens` — vérifié le 4 octobre 2026.
 *
 * Ils étaient auparavant écrits « de mémoire » et ne correspondaient à rien :
 * `nom_complet`, `user_id`, `actif`, `telephone`, `cabinets_rattaches` n'existent
 * pas dans la réponse. TypeScript ne pouvait pas le signaler, car la réponse
 * est simplement `cast`ée dans le service. Résultat à l'écran : la page
 * Praniticiens levait `Cannot read properties of undefined (reading 'length')`
 * et s'affichait entièrement blanche — l'API renvoyant bien 200.
 *
 * La payload réelle (extrait) :
 * ```json
 * { "id": "…", "utilisateur_id": "…", "titre": "Dr",
 *   "specialite": "Chirurgien-Dentiste", "numero_ordre": null,
 *   "signature_url": null, "bio": null,
 *   "prenom": "Administrateur", "nom": "Clinique",
 *   "email": "admin@cabinet.sn", "compte_actif": true,
 *   "cabinets": ["<uuid>"], "nb_disponibilites": 5 }
 * ```
 * Noter `cabinets` : ce sont des **identifiants**, pas des objets. Le nom
 * affiché est résolu côté client via le store des cabinets.
 */

export type TypePlageDisponibilite = 'CONSULTATION' | 'URGENCE' | 'BLOCKING'

export interface Praticien {
  id: string
  utilisateur_id: string
  prenom: string
  nom: string
  email: string
  /** Le compte est-il actif ? (le praticien peut exister sans compte associé) */
  compte_actif: boolean
  /** Dr, Pr… — l'API ne renvoie pas de valeur par défaut. */
  titre?: string | null
  specialite?: string | null
  /** N° d'inscription à l'Ordre des chirurgiens-dentistes. */
  numero_ordre?: string | null
  signature_url?: string | null
  bio?: string | null
  /** Identifiants des cabinets de rattachement — PAS des objets. */
  cabinets: string[]
  nb_disponibilites: number
}

export interface Disponibilite {
  id: string
  praticien_id: string
  cabinet_id?: string | null
  cabinet_nom?: string | null
  jour_semaine?: number | null // 0 = Lundi, 6 = Dimanche
  date_specifique?: string | null // YYYY-MM-DD
  heure_debut: string // HH:MM
  heure_fin: string // HH:MM
  type: TypePlageDisponibilite
  motif_blocage?: string | null
  actif: boolean
}

export interface CreneauLibreHoraire {
  heure_debut: string
  heure_fin: string
  fauteuils_disponibles: string[]
}

export interface CreneauxResponseData {
  praticien_id: string
  date: string
  creneaux: CreneauLibreHoraire[]
  avertissement?: string | null
}

/**
 * Nom complet d'un praticien.
 *
 * L'API renvoie `prenom` et `nom` séparément — et peut renvoyer l'un des deux
 * vide. `nomComplet` évite de dupliquer cette logique dans chaque écran.
 */
export function nomComplet(praticien: {
  prenom?: string | null
  nom?: string | null
  titre?: string | null
}): string {
  const nom = [praticien.titre, praticien.prenom, praticien.nom].filter(Boolean).join(' ')
  return nom || 'Praticien'
}
