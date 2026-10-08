import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Enrôlement du second facteur — le premier écran de tout compte plateforme.
 *
 * **Aucun code n'est envoyé par e-mail.** Le second facteur est un TOTP : un code
 * à six chiffres affiché par une application d'authentification. Le serveur
 * renvoie un secret base32 et une URI `otpauth://`, à scanner.
 *
 * **Les codes de secours s'affichent une seule fois.** Ni la base ni le journal
 * ne les conservent en clair : perdus, ils imposent de repasser par un
 * opérateur. L'écran ne peut donc pas se contenter de les montrer, il faut que
 * l'opérateur confirme les avoir copiés - d'où la case obligatoire.
 *
 * **Rien de secret dans le stockage.** Le secret et le jeton d'enrôlement vivent
 * dans le store non persiste, et disparaissent à la fermeture de l'onglet.
 */
export function EnrolementPage() {
  const preparation = useAuthStore((e) => e.preparation2fa)
  const preparer = useAuthStore((e) => e.preparerEnrolement)
  const activer = useAuthStore((e) => e.activerEnrolement)
  const annuler = useAuthStore((e) => e.annulerEnrolement)
  const jetonEnrolement = useAuthStore((e) => e.jetonEnrolement)

  const navigate = useNavigate()

  const [code, setCode] = useState('')
  const [erreur, setErreur] = useState('')
  const [soumission, setSoumission] = useState(false)
  const [codes, setCodes] = useState<string[] | null>(null)
  const [copies, setCopies] = useState(false)

  // Sans jeton d'enrolement, cet écran n'a rien a faire : on ne l'atteint que
  // depuis un login reussi, et le jeton est consomme a l'activation.
  // **Ordre imperatif.** L'ecran des codes vient **avant** la garde « pas de
  // jeton » : le store consomme le jeton d'enrolement a l'activation, donc des
  // la reussite il vaut null. Avec la garde en tete, l'ecran basculait sur
  // « session expiree » et les codes de secours - qui ne s'affichent qu'une
  // seule fois, jamais plus - n'etaient jamais vus.
  // ── Codes de secours : seul écran ou ils apparaissent ───────────────────────
  if (codes) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Vos codes de secours</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Ces dix codes remplacent le code de votre application quand le
              téléphone n'est pas sous la main. <strong>Chacun ne sert qu'une
              seule fois.</strong> Copiez-les maintenant : ils ne seront plus
              jamais affichés, et les retrouver exigera de passer par un opérateur.
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
              <span>J'ai copié ces codes dans un endroit sûr.</span>
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

  if (!jetonEnrolement) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Session d'enrôlement expirée</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Le jeton d'enrôlement a été consommé ou a expiré. Reprenez
              l'identification pour obtenir un nouveau jeton.
            </p>
            <Button className="w-full" onClick={() => navigate('/login', { replace: true })}>
              Revenir à la connexion
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ── Preparation : QR + secret saisi a la main ────────────────────────────────
  if (!preparation) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Second facteur à configurer</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Vos identifiants sont corrects. Ce compte n'a pas encore de secret
              TOTP.
            </p>
            <Button
              className="w-full"
              disabled={soumission}
              onClick={() => {
                setErreur('')
                setSoumission(true)
                preparer().catch((e: Error) => setErreur(e.message)).finally(() => setSoumission(false))
              }}
            >
              {soumission ? 'Préparation…' : 'Afficher le QR code'}
            </Button>
            {erreur && (
              <p role="alert" className="text-sm text-danger">
                {erreur}
              </p>
            )}
            <Button variant="outline" className="w-full" onClick={() => navigate('/login')}>
              Revenir à la connexion
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Scanner le QR code</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{preparation.instruction}</p>

          <div className="flex justify-center rounded-xl border bg-white p-4">
            {/* `role` et `aria-label` explicites : sans eux ce SVG n'a aucun nom
                accessible, et un lecteur d'ecran passe dessus sans rien dire.
                Lisible ne veut pas dire Audible - le secret reste saisi ou scanne,
                jamais prononce. */}
            <QRCodeSVG
              value={preparation.uri}
              size={208}
              role="img"
              aria-label="QR code du secret TOTP de ce compte"
            />
          </div>

          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">
              Saisir le secret à la main
            </summary>
            <p className="mt-2 break-all rounded-lg border bg-muted/40 p-3 font-mono text-xs">
              {preparation.secret}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Transcrire 32 caractères à la main est une source d'erreur. Le QR
              code est préférable.
            </p>
          </details>

          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              setErreur('')
              setSoumission(true)
              activer(code.trim())
                .then(setCodes)
                .catch((e: Error) => setErreur(e.message))
                .finally(() => setSoumission(false))
            }}
          >
            <div className="space-y-1.5">
              <label htmlFor="code">Code à 6 chiffres</label>
              <Input
                id="code"
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

            {erreur && (
              <p role="alert" className="text-sm text-danger">
                {erreur}
              </p>
            )}

            <div className="flex justify-between gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  annuler()
                  navigate('/login', { replace: true })
                }}
              >
                Annuler
              </Button>
              <Button type="submit" disabled={soumission || code.trim().length < 6}>
                {soumission ? 'Vérification…' : 'Activer'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}