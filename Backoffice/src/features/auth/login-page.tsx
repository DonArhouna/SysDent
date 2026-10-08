import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Connexion plateforme — mot de passe puis code TOTP.
 *
 * **Confidentialité.** Un compte plateforme ouvre la porte à tous les cabinets.
 * Deux règles en découlent, et elles sont dans le code plutôt que dans une note :
 *
 * - le message d'erreur est **identique** que le motifRefusé soit un compte
 *   inconnu, un mot de passe faux ou un compte désactivé. Distinguer les cas
 *   offre un oracle d'énumération de comptes ;
 * - aucun detail de motif n'est journalisé côté client. La limitation de débit
 *   et le verrouillage sont faits par le backend, qui est le seul à voir l'IP.
 *
 * **2FA obligatoire.** Un compte sans secret confirmé ne reçoit pas de session :
 * le backend renvoie un jeton d'étape, et l'écran passe au code TOTP. C'est ce
 * qui rend impossible d'ouvrir une session plateforme en knowing only le mot de
 * passe.
 */
export function LoginPage() {
  const token = useAuthStore((etat) => etat.token)
  const challenge2fa = useAuthStore((etat) => etat.challenge2fa)
  const connexion = useAuthStore((etat) => etat.connexion)
  const valider2fa = useAuthStore((etat) => etat.valider2fa)
  const annuler2fa = useAuthStore((etat) => etat.annuler2fa)

  const location = useLocation()
  const depuis = (location.state as { depuis?: string } | null)?.depuis ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [erreur, setErreur] = useState('')
  const [soumission, setSoumission] = useState(false)

  if (token) return <Navigate to={depuis} replace />

  const enCours = async (action: () => Promise<unknown>) => {
    setErreur('')
    setSoumission(true)
    try {
      await action()
    } catch (e) {
      // Un seul message, quel que soit le motif : voir l'en-tête du fichier.
      setErreur(e instanceof Error ? e.message : 'Connexion impossible.')
    } finally {
      setSoumission(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-4">
        {/* La différenciation avec l'application client est obligatoire : un accès
            support donne accès à tous les cabinets. Confondre les deux interfaces
            doit être visible immédiatement. */}
        <div className="flex items-center justify-center gap-2">
          <Badge className="bg-plateforme text-plateforme-foreground">Plateforme</Badge>
          <span className="text-lg font-semibold text-foreground">SysDent Pro – Backoffice</span>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>
              {challenge2fa ? 'Vérification en deux étapes' : 'Connexion'}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {challenge2fa
                ? 'Saisissez le code à 6 chiffres de votre application d’authentification.'
                : 'Accès réservé aux comptes de la plateforme.'}
            </p>
          </CardHeader>

          <CardContent>
            {challenge2fa ? (
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault()
                  void enCours(() => valider2fa(code.trim()))
                }}
              >
                <div className="space-y-1.5">
                  <label htmlFor="code">Code de vérification</label>
                  <Input
                    id="code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    autoFocus
                  />
                </div>

                {erreur && (
                  <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
                    {erreur}
                  </p>
                )}

                <div className="flex justify-between gap-2">
                  <Button type="button" variant="outline" onClick={annuler2fa} disabled={soumission}>
                    Retour
                  </Button>
                  <Button type="submit" disabled={soumission || code.trim().length < 6}>
                    {soumission ? 'Vérification…' : 'Valider'}
                  </Button>
                </div>
              </form>
            ) : (
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault()
                  void enCours(() => connexion(email.trim(), password))
                }}
              >
                <div className="space-y-1.5">
                  <label htmlFor="email">Adresse e-mail</label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="password">Mot de passe</label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>

                {erreur && (
                  <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
                    {erreur}
                  </p>
                )}

                <Button type="submit" className="w-full" disabled={soumission}>
                  {soumission ? 'Connexion…' : 'Se connecter'}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}