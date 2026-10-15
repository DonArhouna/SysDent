import { useEffect, useState, type FormEvent } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Mail, QrCode } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { EnvoiCode, PreparationTotp } from '@/stores/auth-store'
import { messageErreur, reglesManquantes } from './regles'

/** Choix d'un nouveau mot de passe, avec confirmation et règles en direct. */
export function NouveauMotDePasse({
  email,
  libelleBouton,
  onValider,
}: {
  email?: string
  libelleBouton: string
  onValider: (mdp: string) => Promise<unknown>
}) {
  const [mdp, setMdp] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const manquantes = mdp ? reglesManquantes(mdp, email) : []
  const pret = mdp !== '' && manquantes.length === 0 && confirmation === mdp

  const soumettre = async (e: FormEvent) => {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      await onValider(mdp)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <form className="space-y-3" onSubmit={soumettre}>
      {/* Rattache le nouveau mot de passe au bon compte dans les gestionnaires de mots de passe. */}
      {email && <input type="text" name="username" autoComplete="username" value={email} readOnly hidden />}
      <Input
        id="nouveau-mdp"
        label="Nouveau mot de passe"
        type="password"
        autoComplete="new-password"
        required
        autoFocus
        value={mdp}
        onChange={(e) => setMdp(e.target.value)}
        error={manquantes.length ? `Il manque : ${manquantes.join(', ')}.` : undefined}
        helperText="12 caractères minimum, avec majuscule, minuscule, chiffre et caractère spécial."
      />
      <Input
        id="confirmation-mdp"
        label="Confirmer le mot de passe"
        type="password"
        autoComplete="new-password"
        required
        value={confirmation}
        onChange={(e) => setConfirmation(e.target.value)}
        error={confirmation && confirmation !== mdp ? 'Les deux saisies ne correspondent pas.' : undefined}
      />
      {erreur && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          {erreur}
        </p>
      )}
      <Button type="submit" className="w-full" disabled={!pret} loading={enCours}>
        {libelleBouton}
      </Button>
    </form>
  )
}

/** Bouton d'envoi du code par e-mail, avec adresse masquée et délai de renvoi. */
export function EnvoiCodeEmail({ envoyer }: { envoyer: () => Promise<EnvoiCode> }) {
  const [envoi, setEnvoi] = useState<EnvoiCode | null>(null)
  const [attente, setAttente] = useState(0)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    if (attente <= 0) return
    const t = setTimeout(() => setAttente((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [attente])

  const cliquer = async () => {
    setErreur('')
    setEnCours(true)
    try {
      setEnvoi(await envoyer())
      setAttente(30)
    } catch (e) {
      setErreur(messageErreur(e))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="space-y-2">
      {envoi && (
        <p role="status" className="rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
          Code envoyé à <strong className="text-foreground">{envoi.destinataire}</strong>, valable{' '}
          {Math.round(envoi.expiration_secondes / 60)} minutes.
        </p>
      )}
      <Button type="button" variant={envoi ? 'link' : 'outline'} className={envoi ? 'h-auto px-0' : 'w-full'} onClick={cliquer} disabled={attente > 0} loading={enCours}>
        {!envoi && <Mail aria-hidden />}
        {envoi ? (attente > 0 ? `Renvoyer le code (${attente} s)` : 'Renvoyer le code') : 'Envoyer le code par e-mail'}
      </Button>
      {erreur && (
        <p role="alert" className="text-xs text-danger">
          {erreur}
        </p>
      )}
    </div>
  )
}

/** Champ du code à 6 chiffres (ou code de secours si `secours`). */
export function ChampCode({
  value,
  onChange,
  secours = false,
}: {
  value: string
  onChange: (v: string) => void
  secours?: boolean
}) {
  return (
    <Input
      id="code-verification"
      label={secours ? 'Code de vérification ou code de secours' : 'Code de vérification'}
      inputMode={secours ? 'text' : 'numeric'}
      autoComplete="one-time-code"
      maxLength={secours ? 8 : 6}
      placeholder="000000"
      required
      value={value}
      onChange={(e) => onChange(secours ? e.target.value.trim().toUpperCase() : e.target.value.replace(/\D/g, ''))}
    />
  )
}

/**
 * Configuration de la double authentification : QR code (application) ou
 * code reçu par e-mail. Sert à la connexion (rôle obligatoire) et à « Mon compte ».
 */
export function ConfigurationDeuxFacteurs({
  preparer,
  envoyerCode,
  activer,
  onAnnuler,
}: {
  preparer: () => Promise<PreparationTotp>
  envoyerCode: () => Promise<EnvoiCode>
  /** Rend les codes de secours, que l'appelant affiche une fois. */
  activer: (methode: 'totp' | 'email', code: string) => Promise<unknown>
  onAnnuler?: () => void
}) {
  const [methode, setMethode] = useState<'totp' | 'email' | null>(null)
  const [preparation, setPreparation] = useState<PreparationTotp | null>(null)
  const [code, setCode] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const choisirTotp = async () => {
    setErreur('')
    setEnCours(true)
    try {
      setPreparation(await preparer())
      setMethode('totp')
    } catch (e) {
      setErreur(messageErreur(e))
    } finally {
      setEnCours(false)
    }
  }

  const soumettre = async (e: FormEvent) => {
    e.preventDefault()
    if (!methode) return
    setErreur('')
    setEnCours(true)
    try {
      await activer(methode, code)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  if (!methode) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Choisissez comment vous recevrez votre code de vérification à chaque connexion.
        </p>
        <Button className="w-full" onClick={choisirTotp} loading={enCours}>
          <QrCode aria-hidden />
          Scanner un QR code (application)
        </Button>
        <Button variant="outline" className="w-full" onClick={() => setMethode('email')}>
          <Mail aria-hidden />
          Recevoir un code par e-mail
        </Button>
        {erreur && <p role="alert" className="text-xs text-danger">{erreur}</p>}
        {onAnnuler && (
          <Button variant="ghost" className="w-full" onClick={onAnnuler}>
            Annuler
          </Button>
        )}
      </div>
    )
  }

  return (
    <form className="space-y-4" onSubmit={soumettre}>
      {methode === 'totp' && preparation ? (
        <>
          <p className="text-sm text-muted-foreground">
            Scannez ce QR code avec une application d'authentification (Google Authenticator,
            Microsoft Authenticator, Aegis…), puis saisissez le code affiché.
          </p>
          <div className="flex justify-center rounded-xl border bg-white p-4">
            <QRCodeSVG value={preparation.uri} size={180} role="img" aria-label="QR code de la double authentification" />
          </div>
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground">Saisir la clé à la main</summary>
            <p className="mt-2 break-all rounded-lg border bg-muted/40 p-2 font-mono">{preparation.secret}</p>
          </details>
        </>
      ) : (
        <EnvoiCodeEmail envoyer={envoyerCode} />
      )}
      <ChampCode value={code} onChange={setCode} />
      {erreur && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          {erreur}
        </p>
      )}
      <div className="flex justify-between gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setMethode(null)
            setCode('')
            setErreur('')
          }}
        >
          Retour
        </Button>
        <Button type="submit" disabled={code.length < 6} loading={enCours}>
          Activer
        </Button>
      </div>
    </form>
  )
}

/** Codes de secours : affichés UNE fois, validation après confirmation de copie. */
export function CodesSecours({ codes, onTerminer }: { codes: string[]; onTerminer: () => void }) {
  const [copies, setCopies] = useState(false)
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Ces codes remplacent votre code de vérification si vous perdez votre téléphone ou votre
        accès e-mail. <strong className="text-foreground">Chacun ne sert qu'une fois</strong> et ils
        ne seront plus jamais affichés : copiez-les dans un endroit sûr.
      </p>
      <ul className="grid grid-cols-2 gap-2 rounded-xl border bg-muted/40 p-4 font-mono text-sm">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={copies} onChange={(e) => setCopies(e.target.checked)} />
        J'ai copié ces codes dans un endroit sûr.
      </label>
      <Button className="w-full" disabled={!copies} onClick={onTerminer}>
        Terminer
      </Button>
    </div>
  )
}
