import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Regeneration des codes de secours d'un compte deja enrole.
 *
 * **Le probleme qu'il resout.** Un compte dont la 2FA est active mais dont les
 * codes de secours manquent — un compte anterieur a cette correction, ou une
 * liste epuisee — n'a aucune voie de recours si le telephone disparait : le TOTP
 * est sur le perdu, et les codes aussi. Avant, la seule issue etait une reinite
 * cote operateur (et le serveur l'ecrivait noir sur blanc). Ce n'est plus le
 * cas : le compte regenere lui-meme son lot, sous preuve de sa session ET d'un
 * TOTP valide sur le secret actif.
 *
 * **Un TOTP de plus, pas seulement la session.** Ouvrir la porte ne suffit pas :
 * c'est la regle du backend, portee par `regenerer_codes_secours`, et un ecran
 * qui l'oublierait offrirait a un voleur de session la destruction silencieuse
 * de la seule voie de secours du compte.
 *
 * **Le motif est consigne au journal.** Une regeneration invalide d'un coup
 * dix sauvegardes legumeres laisse une trace explicite de qui l'a faite et
 * pourquoi — c'est un evenement de securite, pas un clic de confort.
 *
 * **Les dix nouveaux codes s'affichent une seule fois**, comme a l'activation.
 * L'ancien lot est desactive dans la meme transaction : il n'y a jamais deux
 * lots valides a la fois.
 */
export function CodesSecoursPage() {
  const token = useAuthStore((e) => e.token)
  const regenerer = useAuthStore((e) => e.regenererCodesSecours)

  const navigate = useNavigate()

  const [code, setCode] = useState('')
  const [motif, setMotif] = useState('')
  const [erreur, setErreur] = useState('')
  const [soumission, setSoumission] = useState(false)
  const [codes, setCodes] = useState<string[] | null>(null)
  const [copies, setCopies] = useState(false)

  // Meme garde que la RouteGuard, en tete : un etat purgle pendant le rendu ne
  // doit pas laisser un ecran de securite afficher un formulaire sans session.
  if (!token) return <Navigate to="/dashboard" replace />

  // ── Nouveaux codes : seul ecran ou ils apparaissent ────────────────────────
  // **Avant** la garde ci-dessus serait absurde ici : le token ne disparait pas
  // a la regeneration, seule la session ouverte compte, et elle le reste.
  if (codes) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Vos nouveaux codes de secours</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Ces dix codes remplacent les précédents, désormais invalides.
              <strong> Chacun ne sert qu'une seule fois.</strong> Copiez-les
              maintenant : ils ne seront plus jamais affichés, et les retrouver
              exigera de repasser par un opérateur.
            </p>
            <ul className="grid grid-cols-2 gap-2 rounded-xl border bg-muted/40 p-4 font-mono text-sm">
              {codes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={copies}
                onChange={(e) => setCopies(e.target.checked)}
              />
              <span>J'ai copié ces nouveaux codes dans un endroit sûr.</span>
            </label>
            <Button
              className="w-full"
              disabled={!copies}
              onClick={() => {
                // Les codes quittent la memoire de l'onglet des la validation :
                // personne ne doit pouvoir les relire en revenant en arriere.
                setCodes(null)
                navigate('/dashboard', { replace: true })
              }}
            >
              Terminer
            </Button>
            {!copies && (
              <p className="text-xs text-muted-foreground">
                Le bouton s'active une fois les codes copiés.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Régénérer les codes de secours</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            L'ancien lot est invalidé dès la régénération. Confirmez-la avec un
            code de votre application, et précisez pourquoi.
          </p>

          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              setErreur('')
              setSoumission(true)
              regenerer(code.trim(), motif.trim())
                .then(setCodes)
                .catch((e: Error) => setErreur(e.message))
                .finally(() => setSoumission(false))
            }}
          >
            <div className="space-y-1.5">
              <label htmlFor="code-regeneration">Code à 6 chiffres</label>
              <Input
                id="code-regeneration"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                required
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="motif-regeneration">Motif (consigné au journal)</label>
              <Input
                id="motif-regeneration"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                placeholder="Ex. : téléphone perdu, codes égarés"
                minLength={3}
                maxLength={200}
                required
              />
            </div>

            {erreur && (
              <p role="alert" className="text-sm text-danger">
                {erreur}
              </p>
            )}

            <div className="flex justify-between gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/dashboard', { replace: true })}
              >
                Annuler
              </Button>
              <Button type="submit" disabled={soumission || code.trim().length < 6}>
                {soumission ? 'Vérification…' : 'Régénérer'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
