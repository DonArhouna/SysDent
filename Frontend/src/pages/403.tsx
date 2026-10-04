import { ShieldAlert, ArrowLeft, Home } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function ForbiddenPage() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center p-6 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-danger/10 text-danger shadow-inner">
        <ShieldAlert className="h-10 w-10" />
      </div>

      <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
        403 - Accès Non Autorisé
      </h1>

      <p className="mt-3 max-w-md text-sm text-muted-foreground leading-relaxed">
        Vous ne disposez pas des permissions requises par votre rôle pour accéder à cette
        ressource ou effectuer cette action clinique/administrative.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
          Page précédente
        </Button>
        <Link to="/dashboard">
          <Button variant="primary">
            <Home className="h-4 w-4" />
            Tableau de bord
          </Button>
        </Link>
      </div>
    </div>
  )
}
