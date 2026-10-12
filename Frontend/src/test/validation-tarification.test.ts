/**
 * Les validateurs de saisie de la tarification, testes sans navigateur.
 *
 * **Pourquoi tester une fonction pure plutot que le formulaire.** Une regle
 * cachee dans un `onChange` n'est jamais verifiee : on la change un jour, elle
 * cesse de bloquer, et le serveur renvoie un 422 que personne n'a vu venir. Ces
 * fonctions sont separees du composant precisement pour etre testables, et le
 * composant les appelle sans les recopier.
 *
 * **Chaque borne existe deux fois.** Ici, pour l'utilisateur qui tape ; dans le
 * `CHECK` de la base, pour celui qui passe par une autre porte. Un test qui ne
 * verifie que la premiere donnerait une garantie partielle.
 */

import { describe, expect, it } from 'vitest'

import {
  normaliserMontant,
  normaliserTaux,
  validerMontant,
  validerPriorite,
  validerTaux,
} from '@/features/tarification/components/validation'

describe('Validation du montant', () => {
  it('accepte un montant entier et un montant decimal', () => {
    expect(validerMontant('15000').valide).toBe(true)
    expect(validerMontant('15000.50').valide).toBe(true)
    expect(validerMontant('0').valide).toBe(true)
    expect(validerMontant('0.00').valide).toBe(true)
  })

  it('accepte la virgule decimal, que le francais tape', () => {
    expect(validerMontant('15000,50').valide).toBe(true)
  })

  it('refuse un montant vide', () => {
    const resultat = validerMontant('')
    expect(resultat.valide).toBe(false)
    expect(resultat.valide === false && resultat.message).toBeTruthy()
  })

  it('refuse un montant negatif, avec un message qui le dit', () => {
    const resultat = validerMontant('-1')
    expect(resultat.valide).toBe(false)
    expect(resultat.valide === false && resultat.message).toContain('negatif')
  })

  it('refuse ce qui n\'est pas un nombre', () => {
    expect(validerMontant('gratuit').valide).toBe(false)
    expect(validerMontant('12abc').valide).toBe(false)
  })

  it('refuse un montant au-dela de ce que la colonne accepte', () => {
    // La colonne est un NUMERIC(12, 2) : douze chiffres, deux decimales.
    expect(validerMontant('99999999999.99').valide).toBe(true)
    expect(validerMontant('999999999999.99').valide).toBe(false)
  })

  it('normalise en point decimal et deux decimales', () => {
    // Le serveur attend un Decimal : `15000,50` ou `15000.5` produirait un 422.
    expect(normaliserMontant('15000')).toBe('15000.00')
    expect(normaliserMontant('15000,50')).toBe('15000.50')
    expect(normaliserMontant('15000.5')).toBe('15000.50')
    expect(normaliserMontant('0')).toBe('0.00')
  })

  it('normalise une saisie invalide en zero plutot que NaN', () => {
    // `NaN` dans un corps de requete devient `null` cote JSON, et le serveur
    // repond 422 avec un message incomprehensible. Zero est au moins explicite.
    expect(normaliserMontant('abc')).toBe('0.00')
  })
})

describe('Validation du taux de prise en charge', () => {
  it('accepte les bornes et l\'interieur', () => {
    expect(validerTaux('0').valide).toBe(true)
    expect(validerTaux('0.00').valide).toBe(true)
    expect(validerTaux('70').valide).toBe(true)
    expect(validerTaux('100').valide).toBe(true)
  })

  it('refuse un taux au-dela de 100', () => {
    const resultat = validerTaux('101')
    expect(resultat.valide).toBe(false)
    expect(resultat.valide === false && resultat.message).toContain('100')
  })

  it('refuse un taux negatif', () => {
    expect(validerTaux('-1').valide).toBe(false)
    expect(validerTaux('-0.01').valide).toBe(false)
  })

  it('refuse un taux vide et ce qui n\'est pas un nombre', () => {
    expect(validerTaux('').valide).toBe(false)
    expect(validerTaux('moitié').valide).toBe(false)
  })

  it('normalise en deux decimales', () => {
    expect(normaliserTaux('70')).toBe('70.00')
    expect(normaliserTaux('70,5')).toBe('70.50')
  })
})

describe('Validation de la priorite', () => {
  it('accepte un entier de 1 a 99', () => {
    expect(validerPriorite('1').valide).toBe(true)
    expect(validerPriorite('99').valide).toBe(true)
  })

  it('accepte une priorite vide, le serveur saura mettre 1', () => {
    // Champ facultatif : bloquer une saisie vide obligerait l'utilisateur a
    // taper un chiffre pour un droit qu'il ne sait pas encore classer.
    expect(validerPriorite('').valide).toBe(true)
  })

  it('refuse zero, un negatif, un decimal et une lettre', () => {
    expect(validerPriorite('0').valide).toBe(false)
    expect(validerPriorite('-1').valide).toBe(false)
    expect(validerPriorite('1.5').valide).toBe(false)
    expect(validerPriorite('première').valide).toBe(false)
    expect(validerPriorite('100').valide).toBe(false)
  })
})