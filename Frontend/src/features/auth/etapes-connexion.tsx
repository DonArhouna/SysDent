import { useState, type FormEvent } from 'react'
import { KeyRound, ShieldCheck } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'
import {
  ChampCode,
  ConfigurationDeuxFacteurs,
  EnvoiCodeEmail,
  NouveauMotDePasse,
} from './securite-ui'
import { messageErreur } from './regles'

/**
 * Étapes qui suivent un mot de passe correct, avant toute session :
 * changement du mot de passe temporaire, code de vérification, ou
 * configuration de la double authentification (obligatoire pour certains rôles).
 *
 * `onConnecte` est appelé une fois la session ouverte. Les codes de secours
 * passent par le store (`codesSecoursAAfficher`) : la page les affiche avant
 * de quitter l'écran.
 */
export function EtapesConnexion({ email, onConnecte }: { email: string; onConnecte: () => void }) {
  const etape = useAuthStore((e) => e.etapeConnexion)
  const changer = useAuthStore((e) => e.changerMotDePasseInitial)
  const envoyerCode = useAuthStore((e) => e.envoyerCodeEtape)
  const valider = useAuthStore((e) => e.validerCodeEtape)
  const preparer = useAuthStore((e) => e.preparerTotpEtape)
  const activer = useAuthStore((e) => e.activer2faEtape)
  const annuler = useAuthStore((e) => e.annulerEtape)

  const suite = (issue: string) => {
    if (issue === 'session') onConnecte()
  }

  if (!etape) return null

  if (etape.etape === 'changement_mot_de_passe') {
    return (
      <Cadre titre="Choisissez un nouveau mot de passe" icone={<KeyRound className="h-5 w-5 text-primary" />} onAnnuler={annuler}>
        <p className="text-sm text-muted-foreground">
          Votre mot de passe actuel est temporaire. Choisissez-en un que vous seul connaîtrez.
        </p>
        <NouveauMotDePasse email={email} libelleBouton="Enregistrer et continuer" onValider={async (mdp) => suite(await changer(mdp))} />
      </Cadre>
    )
  }

  if (etape.etape === 'enrolement_2fa') {
    return (
      <Cadre titre="Sécurisez votre compte" icone={<ShieldCheck className="h-5 w-5 text-primary" />} onAnnuler={annuler}>
        <p className="rounded-lg bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
          Votre rôle donne accès à tout le cabinet : la double authentification est obligatoire.
        </p>
        <ConfigurationDeuxFacteurs
          preparer={preparer}
          envoyerCode={envoyerCode}
          activer={(methode, code) => activer(methode, code)}
        />
      </Cadre>
    )
  }

  return (
    <Cadre titre="Vérification en deux étapes" icone={<ShieldCheck className="h-5 w-5 text-primary" />} onAnnuler={annuler}>
      <SaisieCode methodes={etape.methodes} envoyerCode={envoyerCode} valider={async (code) => suite(await valider(code))} />
    </Cadre>
  )
}

function SaisieCode({
  methodes,
  envoyerCode,
  valider,
}: {
  methodes: string[]
  envoyerCode: () => ReturnType<ReturnType<typeof useAuthStore.getState>['envoyerCodeEtape']>
  valider: (code: string) => Promise<void>
}) {
  const deux = methodes.includes('totp') && methodes.includes('email')
  const [methode, setMethode] = useState<'totp' | 'email'>(methodes.includes('totp') ? 'totp' : 'email')
  const [secours, setSecours] = useState(false)
  const [code, setCode] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const soumettre = async (e: FormEvent) => {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      await valider(code)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <form className="space-y-4" onSubmit={soumettre}>
      {deux && !secours && (
        <div role="tablist" aria-label="Méthode de vérification" className="grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
          {(['totp', 'email'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={methode === m}
              onClick={() => setMethode(m)}
              className={
                'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ' +
                (methode === m ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')
              }
            >
              {m === 'totp' ? 'Application' : 'E-mail'}
            </button>
          ))}
        </div>
      )}
      {!secours && (
        <p className="text-sm text-muted-foreground">
          {methode === 'totp'
            ? "Saisissez le code à 6 chiffres affiché par votre application d'authentification."
            : 'Recevez un code à 6 chiffres sur votre adresse e-mail.'}
        </p>
      )}
      {!secours && methode === 'email' && <EnvoiCodeEmail envoyer={envoyerCode} />}
      <ChampCode value={code} onChange={setCode} secours={secours} />
      {erreur && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          {erreur}
        </p>
      )}
      <Button type="submit" className="w-full" disabled={code.length < 6} loading={enCours}>
        Valider
      </Button>
      <button
        type="button"
        className="w-full text-center text-xs text-muted-foreground underline-offset-4 hover:underline"
        onClick={() => {
          setSecours((v) => !v)
          setCode('')
        }}
      >
        {secours ? 'Utiliser un code de vérification' : "Je n'ai pas accès à mon téléphone ni à mes e-mails"}
      </button>
    </form>
  )
}

export function Cadre({
  titre,
  icone,
  onAnnuler,
  children,
}: {
  titre: string
  icone: React.ReactNode
  onAnnuler?: () => void
  children: React.ReactNode
}) {
  return (
    <div className="space-y-4 rounded-card border border-border bg-card p-6 shadow-sm">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        {icone}
        {titre}
      </h2>
      {children}
      {onAnnuler && (
        <Button variant="ghost" className="w-full" onClick={onAnnuler}>
          Revenir à la connexion
        </Button>
      )}
    </div>
  )
}
