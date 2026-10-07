import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { setPurgeurSession } from '@/stores/auth-store'

/** Client Query unique (règle classique d'une SPA React). */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000, // 30 s : la caisse se recharge vite mais pas à chaque focus
            refetchOnWindowFocus: false,
          },
        },
      }),
  )

  // Purge de session : vider le cache applicatif.
  //
  // **Pas de navigation ici.** Ce composant est monté *au-dessus* de
  // `BrowserRouter` (cf. `main.tsx`) : appeler `useNavigate()` à ce niveau lève
  // « useNavigate() may be used only in the context of a <Router> component » et
  // fait tomber toute l'application au démarrage. Le retour à l'écran de
  // connexion n'a pas à être fait d'ici : la purge met `token` à `null`, et la
  // garde de `AppShell` redirige déjà vers `/login` sur ce changement d'état.
  //
  // Les deux moitiés de la purge sont donc là où chacune a sa place : le cache
  // est ici, la redirection dans `AppShell`, les jetons dans le store.
  useEffect(() => {
    setPurgeurSession(() => client.clear())
    return () => setPurgeurSession(null)
  }, [client])

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
