import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
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

  // Purge de session : vider le cache **et** revenir a la connexion.
  //
  // Vider sans revenir laisserait l'utilisateur devant une page vide ; revenir
  // sans vider lui montrerait les donnees de la session precedente.
  const naviguer = useNavigate()
  useEffect(() => {
    setPurgeurSession(() => {
      client.clear()
      void naviguer('/login', { replace: true })
    })
    return () => setPurgeurSession(null)
  }, [client, naviguer])

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
