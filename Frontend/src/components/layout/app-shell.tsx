import { useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/sidebar'
import { Topbar } from '@/components/layout/topbar'
import { ToastContainer } from '@/components/ui/toast'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Coquille applicative : sidebar + topbar + zone de contenu.
 *
 * Garde de session : sans token (ou au premier chargement d'une session
 * persistée), redirection vers /login. `profil === null` avec un token signifie
 * que le profil n'est pas encore chargé : on le charge avant rendu, pour que
 * le RBAC d'affichage (sidebar) démarre avec de bonnes données.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const token = useAuthStore((etat) => etat.token)
  const profil = useAuthStore((etat) => etat.profil)
  const chargerProfil = useAuthStore((etat) => etat.chargerProfil)
  const { pathname } = useLocation()
  const [replie, setReplie] = useState(false)

  if (!token) {
    return <Navigate to="/login" replace state={{ depuis: pathname }} />
  }

  if (!profil) {
    // Chargement initial du profil (fire-and-forget : le store notifie).
    void chargerProfil().catch(() => undefined)
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Chargement de la session…
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={replie} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar collapsed={replie} onToggleSidebar={() => setReplie((v) => !v)} />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">{children}</main>
      </div>
      <ToastContainer />
    </div>
  )
}
