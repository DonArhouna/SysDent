import { Link } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * Page 403.
 *
 * L'écran n'a pas à dire *quelle* permission manque : la révéler guide
 * l'utilisateur vers la contourner. Le message reste générique et propose la
 * sortie.
 */
export function ForbiddenPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Accès refusé</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Vous n'avez pas les droits nécessaires pour consulter cette page. Si vous
            pensez qu'il s'agit d'une erreur, contactez un administrateur plateforme.
          </p>
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            Retour à l'accueil
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
