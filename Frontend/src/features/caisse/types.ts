import type { ModePaiement } from '@/features/facturation/types'

export type StatutSessionCaisse = 'OUVERTE' | 'CLOSE'

/**
 * Une session de caisse est la journée de travail d'un caissier.
 *
 * `total_*` sont **figés à la clôture** : ils disent ce qui a été constaté ce
 * jour-là, pas ce qui a été encaissé sur les factures depuis. Un paiement saisi
 * après coup sur une journée close ne les modifie plus — c'est ce qui rend le
 * rapport de caisse une pièce comptable plutôt qu'un simple cumul.
 */
export interface SessionCaisse {
  id: string
  numero: string
  cabinet_id: string
  statut: StatutSessionCaisse
  ouverte_le: string
  /** Qui a ouvert le tiroir. */
  ouverte_par: string | null
  /** Espèces déjà dans le tiroir : le dépôt du caissier, pas une recette. */
  ouverture_especes: number
  close_le: string | null
  close_par: string | null
  /** Ce que le caissier déclare avoir compté. */
  especes_comptees: number | null
  /** Dépôt + encaissements espèces : ce qui devrait être au tiroir. */
  especes_attendues: number
  /** Compté moins attendu. Négatif = manque, positif = excédent. */
  ecart_especes: number | null
  total_especes: number
  total_carte: number
  total_virement: number
  total_mobile_money: number
  total_cheque: number
  total_assurance: number
  total_encaisse: number
  nb_paiements: number
  motif_ecart: string | null
  notes: string | null
}

export interface PaiementCaisse {
  id: string
  facture_id: string
  recu_numero: string
  montant: number
  mode: ModePaiement
  reference: string | null
  auteur: string | null
  date_paiement: string
}

export interface OuvertureCaissePayload {
  cabinet_id: string
  ouverture_especes: number
  notes?: string
}

export interface ClotureCaissePayload {
  especes_comptees: number
  motif_ecart?: string
  notes?: string
}
