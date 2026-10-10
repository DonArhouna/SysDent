import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { AppSidebar } from '@/components/layout/sidebar'
import { Topbar } from '@/components/layout/topbar'
import { ToastContainer } from '@/components/ui/toast'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'

/**
 * Coquille applicative — layout flottant (refonte visuelle 2026-10).
 *
 * La fenêtre ne scrolle jamais entière : la page est un cadre plein écran
 * avec gouttières (p-3/p-4) dans lequel la sidebar et la navbar « flottent »
 * (panneaux translucides arrondis). Seul <main> défile.
 *
 * Garde de session : sans token (ou au premier chargement d'une session
 * persistée), redirection vers /login. `profil === null` avec un token signifie
 * que le profil n'est pas encore chargé : on le charge avant rendu, pour que
 * le RBAC d'affichage (sidebar) démarre avec de bonnes données.
 *
 * Responsive : ≥ lg la sidebar est ancrée à gauche (rétractable en rail) ;
 * < lg elle devient un drawer avec overlay (bouton de la navbar).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const token = useAuthStore((etat) => etat.token)
  const profil = useAuthStore((etat) => etat.profil)
  const chargerProfil = useAuthStore((etat) => etat.chargerProfil)
  const { pathname } = useLocation()
  const [replie, setReplie] = useState(false)
  const [drawerMobile, setDrawerMobile] = useState(false)

  // En repassant en grand écran, un drawer resté ouvert n'aurait plus d'ancre.
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)')
    const surChangement = (e: MediaQueryListEvent) => {
      if (!e.matches) setDrawerMobile(false)
    }
    mq.addEventListener('change', surChangement)
    return () => mq.removeEventListener('change', surChangement)
  }, [])

  // Échap ferme le drawer ; la navigation le ferme aussi (sinon il masque la page).
  useEffect(() => {
    if (!drawerMobile) return
    const surEchap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerMobile(false)
    }
    window.addEventListener('keydown', surEchap)
    return () => window.removeEventListener('keydown', surEchap)
  }, [drawerMobile])

  useEffect(() => {
    setDrawerMobile(false)
  }, [pathname])

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
    <div className="relative flex h-screen overflow-hidden bg-background p-3 md:p-4">
      {/* Sidebar ancrée (≥ lg) */}
      {/* La largeur est portée par CE wrapper, pas par le panneau : sans cela le
          rail restait sur 268 px et laissa derrière lui une bande vide que ni la
          navbar ni le contenu ne réquisitionnaient. La colonne principale est
          en `flex-1` : elle occupe automatiquement tout l'espace libéré.
          `h-full` + `min-h-0` règlent la hauteur du panneau (sans quoi `h-full`
          se résolvait sur la hauteur du contenu et la liste ne défilerait pas). */}
      <div
        className={cn(
          'mr-3 hidden shrink-0 transition-[width] duration-200 lg:mr-4 lg:block',
          replie ? 'w-[80px]' : 'w-[268px]',
        )}
      >
        <div className="h-full min-h-0 w-full">
          <AppSidebar collapsed={replie} onToggle={() => setReplie((v) => !v)} />
        </div>
      </div>

      {/* Drawer mobile (< lg) avec overlay */}
      {drawerMobile && (
        <div
          id="menu-navigation-mobile"
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Menu de navigation"
        >
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
            onClick={() => setDrawerMobile(false)}
            aria-hidden
          />
          <div className="absolute inset-y-3 left-3 w-[268px] animate-in slide-in-from-left duration-200">
            <AppSidebar collapsed={false} onToggle={() => setDrawerMobile(false)} />
          </div>
        </div>
      )}

      {/* Colonne principale : navbar + contenu scrollable */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          onOpenMenu={() => setDrawerMobile(true)}
          drawerOuvert={drawerMobile}
        />
        {/* `pb-20` : le bouton d'aide flottant est fixe, en bas à droite. Sans cette
            réserve, il recouvre en permanence le dernier contenu de la page —
            sur mobile, le lien « Voir tout → » d'un panneau. */}
        <main className="mt-3 flex-1 overflow-y-auto rounded-xl2 pb-20 md:mt-4">
          {children}
        </main>
      </div>
      <ToastContainer />
    </div>
  )
}
