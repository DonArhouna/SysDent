import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'

import { setPurgeurSession } from '@/stores/auth-store'

/**
 * Client Query unique (règle classique d'une SPA React).
 *
 * La purge de session est enregistrée ici, et **seulement** ici : ce composant
 * détient le client.
 *
 * **Pas de navigation dans ce composant.** Il est monté *au-dessus* de
 * `BrowserRouter` (cf. `main.tsx`) ; y appeler `useNavigate()` lève « useNavigate()
 * may be used only in the context of a <Router> component » et fait tomber
 * toute l'application au démarrage. Le retour à `/login` est fait par la garde de
 * route, qui réagit à `token === null`.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  )

  useEffect(() => {
    setPurgeurSession(() => client.clear())
    return () => setPurgeurSession(null)
  }, [client])

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
