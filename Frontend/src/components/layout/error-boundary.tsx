import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { LifeBuoy, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  /** Libellé de la zone, pour que le message dise *où* ça a cassé. */
  zone?: string
}

interface State {
  erreur: Error | null
}

/**
 * Garde-fou d'erreur.
 *
 * Sans lui, une seule exception dans un panneau — un symbole importé manquant,
 * une donnée inattendue — replaces toute la page par un écran blanc. L'utilisateur
 * ne distingue plus « l'application est cassée » de « j'ai fait une bêtise », et le
 * message ne dit rien de ce qui a échoué.
 *
 * Ici, l'erreur est contenue, nommée, et deux sorties sont proposées :
 * réessayer le rendu, ou revenir au tableau de bord.
 *
 * `getDerivedStateFromError` est en lecture : le composant est en train de se
 * démonter, il n'a pas le droit de déclencher d'écriture.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { erreur: null }

  static getDerivedStateFromError(erreur: Error): State {
    return { erreur }
  }

  componentDidCatch(erreur: Error, info: ErrorInfo) {
    // On journalise l'erreur et la pile : c'est ce qui permet de la retrouver.
    // Jamais de donnée de santé ici — un identifiant de composant ne l'est pas.
    console.error('Erreur dans un panneau de l interface', erreur, info.componentStack)
  }

  render() {
    const { erreur } = this.state
    if (!erreur) return this.props.children

    return (
      <div className="mx-auto max-w-lg rounded-xl2 border border-danger/30 bg-danger/5 p-6 text-center">
        <LifeBuoy className="mx-auto h-8 w-8 text-danger" aria-hidden />
        <h2 className="mt-3 text-base font-semibold">
          {this.props.zone ? `« ${this.props.zone} » n'a pas pu s'afficher` : "Cet écran n'a pas pu s'afficher"}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Le reste de l'application reste utilisable. Vous pouvez réessayer — si l'erreur
          persiste, elle est réelle et doit être signalée.
        </p>
        <p className="mt-3 rounded-lg bg-card px-3 py-2 font-mono text-xs text-muted-foreground">
          {erreur.message}
        </p>
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="outline" onClick={() => this.setState({ erreur: null })}>
            <RefreshCw className="h-4 w-4" /> Réessayer
          </Button>
          <Button onClick={() => window.location.assign('/dashboard')}>
            Retour au tableau de bord
          </Button>
        </div>
      </div>
    )
  }
}
