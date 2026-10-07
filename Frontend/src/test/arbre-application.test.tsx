import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { BrowserRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { QueryProvider } from '@/providers/query-provider'
import { ThemeProvider } from '@/providers/theme-provider'

/**
 * L'arbre de fournisseurs doit-il monter ?
 *
 * Ce test existe parce d'un plantage réel : `QueryProvider` est monté **au-dessus**
 * de `BrowserRouter` (cf. `main.tsx`), et un `useNavigate()` appelé à ce niveau lève
 * « useNavigate() may be used only in the context of a <Router> component ».
 * L'application ne démarrait plus du tout — et ni `tsc -b` ni `oxlint` ne le
 * signalaient, l'erreur n'apparaît qu'à l'exécution dans un navigateur.
 *
 * Il vérifie aussi que la purge enregistrée par le provider fonctionne **sans**
 * routeur autour d'elle, ce qui est la vraie raison de l'en avoir retiré.
 */
describe('Arbre de fournisseurs', () => {
  it('monte dans l’ordre de main.tsx, QueryProvider avant BrowserRouter', () => {
    // Un composant qui consomme le routeur : c'est le motif qui avait fait tomber
    // l'application, mais **placé où un routeur l'englobe**. Il ne doit planter que
    // si l'ordre des fournisseurs est faux.
    function EnfantQuiConsommeLeRouteur() {
      const location = useLocation()
      return <p>chemin : {location.pathname}</p>
    }

    expect(() =>
      render(
        <ThemeProvider>
          <QueryProvider>
            <BrowserRouter>
              <EnfantQuiConsommeLeRouteur />
            </BrowserRouter>
          </QueryProvider>
        </ThemeProvider>,
      ),
    ).not.toThrow()

    // L'enfant a bien rendu : l'arbre a été construit de bout en bout, pas
    // seulement le fournisseur.
    expect(screen.getByText('chemin : /')).toBeInTheDocument()
  })

  it('enregistre une purge qui vide le cache sans avoir besoin d’un routeur', async () => {
    // On reproduit ici le registre du module plutôt que de dépendre de l'ordre
    // d'import des tests précédents : ce qui compte est que la fonction
    // enregistrée vide réellement le cache.
    const client = new QueryClient()
    client.setQueryData(['patients'], [{ id: 'p1' }])
    expect(client.getQueryData(['patients'])).toHaveLength(1)

    vi.stubGlobal('BroadcastChannel', undefined)
    const { setPurgeurSession, useAuthStore } = await import('@/stores/auth-store')

    // Simule ce que `QueryProvider` enregistre : plus de navigation.
    setPurgeurSession(() => client.clear())
    useAuthStore.setState({ token: 'jeton' })
    useAuthStore.getState().deconnexion()

    expect(client.getQueryData(['patients'])).toBeUndefined()
    expect(useAuthStore.getState().token).toBeNull()
  })
})