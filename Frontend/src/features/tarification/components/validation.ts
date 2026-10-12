/**
 * Validation des saisies de tarification.
 *
 * Ces fonctions sont **pures et testees separement** de l'ecran. Une
 * validation cachee dans un `onChange` de formulaire n'est jamais verifiee :
 * on la change un jour, elle cesse de bloquer, et le serveur renvoie un 422 que
 * personne n'a vu venir. Ici, chaque regle a son test, et le message exact est
 * verifie aussi - un message faux est aussi trompeur qu'une validation absente.
 *
 * Les bornes sont celles des `CHECK` de la base (`taux` entre 0 et 100,
 * `montant` non negatif). Les deux sont appliquees ici **et** par PostgreSQL :
 * le formulaire evite le 422, la base refuse ce qui passerait par une autre
 * porte.
 */

import { MONTANT_MIN, TAUX_MAX, TAUX_MIN } from '../types'

export type ResultatValidation = { valide: true } | { valide: false; message: string }

/** Montant en FCFA : nombre decimal, jamais negatif. */
export function validerMontant(brut: string): ResultatValidation {
  const texte = brut.trim().replace(/\s/g, '').replace(',', '.')
  if (texte === '') return { valide: false, message: 'Le montant est obligatoire.' }
  const valeur = Number(texte)
  if (Number.isNaN(valeur)) {
    return { valide: false, message: 'Le montant doit etre un nombre.' }
  }
  if (valeur < MONTANT_MIN) {
    return { valide: false, message: 'Le montant ne peut pas etre negatif.' }
  }
  if (valeur > 99_999_999_999.99) {
    return { valide: false, message: 'Montant trop grand (maximum 12 chiffres).' }
  }
  return { valide: true }
}

/**
 * Taux de prise en charge : pourcentage de 0 a 100.
 *
 * Une borne de 100 et non de 200 : 200 % signifierait que le payeur rembourse
 * deux fois, et c'est au coeur de la facture, pas un simple affichage.
 */
export function validerTaux(brut: string): ResultatValidation {
  const texte = brut.trim().replace(/\s/g, '').replace(',', '.')
  if (texte === '') return { valide: false, message: 'Le taux est obligatoire.' }
  const valeur = Number(texte)
  if (Number.isNaN(valeur)) return { valide: false, message: 'Le taux doit etre un nombre.' }
  if (valeur < TAUX_MIN || valeur > TAUX_MAX) {
    return {
      valide: false,
      message: `Le taux doit etre compris entre ${TAUX_MIN} et ${TAUX_MAX} %.`,
    }
  }
  return { valide: true }
}

/** Priorite : entier 1 a 99, 1 etant le principal. */
export function validerPriorite(brut: string): ResultatValidation {
  const texte = brut.trim()
  if (texte === '') return { valide: true }
  const valeur = Number(texte)
  if (!Number.isInteger(valeur) || valeur < 1 || valeur > 99) {
    return { valide: false, message: 'La priorite doit etre un entier entre 1 et 99.' }
  }
  return { valide: true }
}

/**
 * Normalise un montant pour l'envoi : point decimal, deux decimales, rien
 * d'autre. Le serveur attend un `Decimal` ; envoyer `1 500,00` produirait un
 * 422, et envoyer `1500,00` aussi.
 */
export function normaliserMontant(brut: string): string {
  const valeur = Number(brut.trim().replace(/\s/g, '').replace(',', '.'))
  if (Number.isNaN(valeur)) return '0.00'
  return valeur.toFixed(2)
}

/** Idem pour le taux : deux decimales suffisent et evitent les flottants longs. */
export function normaliserTaux(brut: string): string {
  const valeur = Number(brut.trim().replace(/\s/g, '').replace(',', '.'))
  if (Number.isNaN(valeur)) return '0'
  return valeur.toFixed(2)
}