import { FileQuestion, Home } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center p-6 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-muted text-muted-foreground shadow-inner">
        <FileQuestion className="h-10 w-10" />
      </div>

      <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
        404 - Page Introuvable
      </h1>

      <p className="mt-3 max-w-md text-sm text-muted-foreground leading-relaxed">
        La page ou le dossier que vous cherchez n'existe pas ou a été déplacé.
      </p>

      <div className="mt-8 flex items-center justify-center">
        <Link to="/dashboard">
          <Button variant="primary">
            <Home className="h-4 w-4" />
            Retour au tableau de bord
          </Button>
        </Link>
      </div>
    </div>
  )
}
