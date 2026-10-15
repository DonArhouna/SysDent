import { useEffect, useState } from 'react'
import { Mail } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuthStore, type EnvoiCodeEmail } from '@/stores/auth-store'

/** Délai avant de pouvoir redemander un code : le serveur limite aussi les envois. */
const ATTENTE_RENVOI_SECONDES = 30

/**
 * Envoi du code de connexion par e-mail, pour le défi comme pour l'enrôlement.
 *
 * L'écran n'affiche que l'adresse **masquée** renvoyée par le serveur : il n'a
 * pas à connaître l'adresse complète, et un écran partagé ne doit pas la montrer.
 */
export function EnvoiCodeEmailBouton({ onEnvoye }: { onEnvoye?: () => void }) {
  const envoyerCodeEmail = useAuthStore((e) => e.envoyerCodeEmail)

  const [envoi, setEnvoi] = useState<EnvoiCodeEmail | null>(null)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const [attente, setAttente] = useState(0)

  useEffect(() => {
    if (attente <= 0) return
    const minuteur = setTimeout(() => setAttente((s) => s - 1), 1000)
    return () => clearTimeout(minuteur)
  }, [attente])

  const envoyer = () => {
    setErreur('')
    setEnCours(true)
    envoyerCodeEmail()
      .then((resultat) => {
        setEnvoi(resultat)
        setAttente(ATTENTE_RENVOI_SECONDES)
        onEnvoye?.()
      })
      .catch((e: Error) => setErreur(e.message))
      .finally(() => setEnCours(false))
  }

  return (
    <div className="space-y-2">
      {envoi ? (
        <p role="status" className="rounded-xl border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          Code envoyé à <strong className="text-foreground">{envoi.destinataire}</strong>. Il est
          valable {Math.round(envoi.expiration_secondes / 60)} minutes.
        </p>
      ) : null}
      <Button
        type="button"
        variant={envoi ? 'link' : 'outline'}
        className={envoi ? 'h-auto px-0' : 'w-full'}
        disabled={enCours || attente > 0}
        onClick={envoyer}
      >
        {!envoi && <Mail aria-hidden />}
        {enCours
          ? 'Envoi…'
          : envoi
            ? attente > 0
              ? `Renvoyer le code (${attente} s)`
              : 'Renvoyer le code'
            : 'Envoyer le code par e-mail'}
      </Button>
      {erreur && (
        <p role="alert" className="text-sm text-danger">
          {erreur}
        </p>
      )}
    </div>
  )
}
