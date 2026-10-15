import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, LockKeyhole, ShieldCheck, Sparkles, Mail } from 'lucide-react'
import { ApiError } from '@/lib/api'
import {
  oublierFermetureVolontaire,
  sessionFermeeVolontairementVraiment,
  useAuthStore,
} from '@/stores/auth-store'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { ToastContainer } from '@/components/ui/toast'
import { Cadre, EtapesConnexion } from '@/features/auth/etapes-connexion'
import { CodesSecours } from '@/features/auth/securite-ui'

/**
 * Connexion multi-tenant : le backend résout le cabinet rattaché à l'email
 * (index Master) — aucun champ « cabinet » à saisir côté utilisateur.
 */
export function LoginPage() {
  const token = useAuthStore((etat) => etat.token)
  const connexion = useAuthStore((etat) => etat.connexion)
  const etapeConnexion = useAuthStore((etat) => etat.etapeConnexion)
  const codesSecours = useAuthStore((etat) => etat.codesSecoursAAfficher)
  const oublierCodesSecours = useAuthStore((etat) => etat.oublierCodesSecours)
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [motDePasseVisible, setMotDePasseVisible] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)

  const entrer = () => {
    // Après une déconnexion volontaire, la cible est le tableau de bord. La
    // route quittée n'a pas à être restaurée : c'est le comportement que le
    // propriétaire attend, et ce que la garde de session ne peut pas savoir.
    const depuis = sessionFermeeVolontairementVraiment()
      ? null
      : ((location.state as { depuis?: string } | null)?.depuis ?? null)
    oublierFermetureVolontaire()
    navigate(depuis ?? '/dashboard', { replace: true })
  }

  // Codes de secours AVANT la redirection : la session est déjà ouverte quand
  // ils arrivent, et ils ne seront plus jamais affichés.
  if (codesSecours) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-md">
          <Cadre titre="Vos codes de secours" icone={<ShieldCheck className="h-5 w-5 text-success" />}>
            <CodesSecours
              codes={codesSecours}
              onTerminer={() => {
                oublierCodesSecours()
                entrer()
              }}
            />
          </Cadre>
        </div>
      </div>
    )
  }

  if (token) {
    return <Navigate to="/dashboard" replace />
  }

  if (etapeConnexion) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-md">
          <EtapesConnexion email={email.trim()} onConnecte={entrer} />
        </div>
        <ToastContainer />
      </div>
    )
  }

  const soumettre = async (evenement: FormEvent) => {
    evenement.preventDefault()
    setErreur(null)
    setEnCours(true)
    try {
      // Une étape reste peut-être à franchir (mot de passe temporaire, code,
      // configuration de la 2FA) : l'écran bascule alors sur `EtapesConnexion`.
      if ((await connexion(email.trim(), password)) === 'session') entrer()
    } catch (e) {
      setErreur(
        e instanceof ApiError
          ? e.message
          : 'Connexion impossible — le serveur ne répond pas.',
      )
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6">
        {/* Identité */}
        <div className="flex flex-col items-center text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-xl font-black text-white shadow-lg shadow-primary/30">
            SD
          </span>
          <h1 className="mt-4 text-2xl font-bold">SysDent Pro</h1>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-accent-purple" />
            Gestion multi-cabinet médico-dentaire
          </p>
        </div>

        <form
          onSubmit={soumettre}
          className="space-y-4 rounded-card border border-border bg-card p-6 shadow-sm"
        >
          <div className="space-y-1.5">
            <Label htmlFor="email">Email professionnel</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                placeholder="admin@cabinet.sn"
                className="pl-9"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Mot de passe</Label>
            <div className="relative">
              <LockKeyhole className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="password"
                type={motDePasseVisible ? 'text' : 'password'}
                required
                autoComplete="current-password"
                placeholder="--------"
                className="pl-9 pr-9"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                aria-label={motDePasseVisible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                onClick={() => setMotDePasseVisible((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {motDePasseVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {erreur && (
            <p
              role="alert"
              className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
            >
              {erreur}
            </p>
          )}

          <Button type="submit" className="w-full" loading={enCours}>
            Se connecter
          </Button>

          <p className="text-center text-xs text-muted-foreground">
            Votre cabinet est reconnu automatiquement à partir de votre email.
          </p>
        </form>
      </div>
      <ToastContainer />
    </div>
  )
}
