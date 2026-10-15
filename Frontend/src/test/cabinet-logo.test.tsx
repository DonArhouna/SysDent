import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CabinetLogo } from '@/components/cabinet-logo'

/** Logo s'il existe, sinon un repère explicite « Aucun logo » (jamais un vide). */
describe('logo du cabinet', () => {
  it('affiche le logo quand il existe', () => {
    render(<CabinetLogo url="/api/v1/logos/t1?v=1" nom="Cabinet Démo SysDent" />)
    expect(screen.getByAltText('Logo de Cabinet Démo SysDent')).toHaveAttribute('src', '/api/v1/logos/t1?v=1')
  })

  it("sans logo : initiales et mention explicite", () => {
    render(<CabinetLogo nom="Cabinet Démo SysDent" legende />)
    expect(screen.getByRole('img', { name: 'Cabinet Démo SysDent : aucun logo' })).toHaveTextContent('CD')
    expect(screen.getByText('Aucun logo')).toBeInTheDocument()
  })

  it('logo cassé : le dit, au lieu d’une image vide', () => {
    render(<CabinetLogo url="/api/v1/logos/t1?v=1" nom="Cabinet Plateau" legende />)
    fireEvent.error(screen.getByAltText('Logo de Cabinet Plateau'))
    expect(screen.getByText('Logo indisponible')).toBeInTheDocument()
  })
})
