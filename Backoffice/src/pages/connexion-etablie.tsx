import { useEffect } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/stores/auth-store'
import { AppShell } from '@/components/layout/app-shell'


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
  const chargerProfil = useAuthStore((e) => e.chargerProfil)

  const navigate = useNavigate()
  const location = useLocation()
  const vers = (location.state as { depuis?: string } | null)?.depuis ?? '/dashboard'

  // L'indicateur `codes_secours_a_regenerer` vient du serveur, et un profil
  // conserve en memoire peut lui etre anterieur : pose par une migration, ou
  // repasse a false par une regeneration ouverte dans un autre onglet. Cette
  // page est la premiere apres une connexion — elle impose la requete fraiche
  // qui decide d'afficher ou non la banniere.
  useEffect(() => {
    chargerProfil().catch(() => undefined)
  }, [chargerProfil])

  if (!token) return <Navigate to={vers} replace />

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto pb-12 pt-6"/>
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Connexion établie</CardTitle>
          <p className="text-sm text-muted-foreground">
            Session ouverte pour <strong>{profil?.email ?? 'votre compte'}</strong>, second
            facteur actif. L'accès au backoffice est opérationnel.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">

          {profil?.codes_secours_a_regenerer && (
            <div role="status" className="space-y-2 rounded-xl border border-amber-500/50 bg-amber-500/10 p-4 text-sm">
              <p className="font-medium">Codes de secours à régénérer</p>
              <p className="text-muted-foreground">
                Ce compte a le second facteur actif mais <strong>plus aucun code de
                secours utilisable</strong>. Sans eux, un téléphone perdu laisse ce
                compte sans voie de recours : régénérez-les avec un code de votre
                application.
              </p>
              <Button className="w-full" onClick={() => navigate('/codes-secours')}>
                Régénérer mes codes de secours
              </Button>
            </div>
          )}

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
    </AppShell>
  )
}
