import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { ApiError } from '@/lib/api'
import {
  CODE_SCHEMA_EN_RETARD,
  EtatErreurModule,
  MESSAGE_ERREUR_GENERIQUE,
  MESSAGE_SCHEMA_EN_RETARD,
  estSchemaEnRetard,
} from '@/features/tarification/components/etat-erreur'

function envelopper(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

function erreur(code: string, status: number) {
  return new ApiError('whatever', code, status)
}

describe('etat d erreur d un module de tarification', () => {
  it('un schema en retard affiche le message de mise a jour, pas une panne', () => {
    envelopper(
      <EtatErreurModule
        error={erreur(CODE_SCHEMA_EN_RETARD, 503)}
        libelle="Nomenclature"
        onReessayer={() => {}}
      />,
    )

    expect(screen.getByText(MESSAGE_SCHEMA_EN_RETARD)).toBeTruthy()
  })

  it('le message dit que le module manque, et ne dit pas que le service tombe', () => {
    envelopper(
      <EtatErreurModule
        error={erreur(CODE_SCHEMA_EN_RETARD, 503)}
        libelle="Nomenclature"
        onReessayer={() => {}}
      />,
    )

    const rendu = document.body.textContent ?? ''
    expect(rendu).toContain('mise à jour du schéma')
    expect(rendu).not.toContain(MESSAGE_ERREUR_GENERIQUE)
  })

  it('une panne reste une panne : le message generique, jamais celui du schema', () => {
    envelopper(
      <EtatErreurModule
        error={erreur('INTERNAL_SERVER_ERROR', 500)}
        libelle="Nomenclature"
        onReessayer={() => {}}
      />,
    )

    expect(screen.getByText(MESSAGE_ERREUR_GENERIQUE)).toBeTruthy()
    expect(screen.queryByText(MESSAGE_SCHEMA_EN_RETARD)).toBeNull()
  })

  it('le bouton Reessayer reste disponible dans les deux cas', () => {
    for (const err of [erreur(CODE_SCHEMA_EN_RETARD, 503), erreur('INTERNAL_SERVER_ERROR', 500)]) {
      const { unmount } = envelopper(
        <EtatErreurModule error={err} libelle="Nomenclature" onReessayer={() => {}} />,
      )
      const bouton = screen.getByRole('button', { name: /Réessayer/ })
      expect(bouton).toBeTruthy()
      unmount()
    }
  })

  it("aucun bouton d'ecriture quand le module n'existe pas", () => {
    envelopper(
      <EtatErreurModule
        error={erreur(CODE_SCHEMA_EN_RETARD, 503)}
        libelle="Nomenclature"
        onReessayer={() => {}}
      />,
    )

    expect(screen.queryByRole('button', { name: /Ajouter|Ajouter un acte|Enregistrer/ })).toBeNull()
  })

  it('seul le code du serveur qualifie un ecart de schema', () => {
    // Le code fait foi, pas le statut : c'est tout l'interet d'un code stable.
    // Le serveur garantit 503 et ce code ensemble ; si un jour le statut
    // diverge, le message utile reste preferable a un message generique.
    expect(estSchemaEnRetard(erreur(CODE_SCHEMA_EN_RETARD, 503))).toBe(true)
    expect(estSchemaEnRetard(erreur(CODE_SCHEMA_EN_RETARD, 500))).toBe(true)
    expect(estSchemaEnRetard(erreur('SERVICE_INDISPONIBLE', 503))).toBe(false)
    expect(estSchemaEnRetard(new Error('reseau'))).toBe(false)
  })
})