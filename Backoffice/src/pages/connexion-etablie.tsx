import { Navigate, useLocation } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Première page atteinte après une connexion réussie.
 *
 * **Elle existe, et dit ce qu'elle n'est pas.** Le tableau de bord (Lot 1) et la
 * gestion des cabinets (Lot 2) ne sont pas écrits. Sans cette page, l'enrôlement
 * réussi renvoyait vers `/dashboard`, qui tombait sur la 404 : l'utilisateur
 * venait d'activer son second facteur et sa session, et l'application lui
 * affirmait que l'adresse demandée n'existait pas. Une 404 après une connexion
 * réussie se lit comme un échec de la connexion.
 *
 * Elle ne prétend donc rien : elle confirme que la session est ouverte, et
 * nomme ce qui reste à écrire.
 */
export function ConnexionEtabliePage() {
  const token = useAuthStore((e) => e.token)
  const profil = useAuthStore((e) => e.profil)
  const deconnexion = useAuthStore((e) => e.deconnexion)

  const location = useLocation()
  const vers = (location.state as { depuis?: string } | null)?.depuis ?? '/dashboard'

  if (!token) return <Navigate to={vers} replace />

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Connexion établie</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Session ouverte pour <strong>{profil?.email ?? 'votre compte'}</strong>, second
            facteur actif. L'accès au backoffice est opérationnel.
          </p>

          <div className="rounded-xl border bg-muted/40 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Écrans non encore écrits</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>Tableau de bord (Lot 1)</li>
              <li>Gestion des cabinets (Lot 2)</li>
            </ul>
            <p className="mt-2">
              Ils viendront après ce socle. Cette page n'invente rien : elle
              indique où s'arrête le travail.
            </p>
          </div>

          <Button variant="outline" className="w-full" onClick={deconnexion}>
            Se déconnecter
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}