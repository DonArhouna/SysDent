import { useEffect, useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Modal } from '@/components/ui/modal'
import { Textarea } from '@/components/ui/textarea'
import { messageErreur } from '@/lib/libelles'

/**
 * Confirmation d'une action sensible, **avec motif obligatoire**.
 *
 * Le backend exige un motif sur chaque action qui change l'état d'un cabinet ou
 * d'un compte, et l'inscrit au journal d'audit : une action sans motif est
 * injugeable après coup. L'écran ne laisse donc pas valider tant qu'il est vide.
 *
 * L'erreur du serveur reste affichée **dans** la fenêtre : la fermer ferait
 * perdre le motif saisi, et croire que l'action a réussi.
 */
export function MotifDialog({
  open,
  onClose,
  onConfirm,
  titre,
  description,
  libelleConfirmer = 'Confirmer',
  variante = 'primary',
  motifRequis = true,
  children,
}: {
  open: boolean
  onClose: () => void
  /** Reçoit le motif saisi. Une promesse rejetée garde la fenêtre ouverte. */
  onConfirm: (motif: string) => Promise<unknown>
  titre: ReactNode
  description?: ReactNode
  libelleConfirmer?: string
  variante?: 'primary' | 'danger'
  motifRequis?: boolean
  /** Champs supplémentaires (sélecteur de plan, confirmation…). */
  children?: ReactNode
}) {
  const [motif, setMotif] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    if (open) {
      setMotif('')
      setErreur('')
    }
  }, [open])

  const valider = async () => {
    setErreur('')
    setEnCours(true)
    try {
      await onConfirm(motif.trim())
      onClose()
    } catch (e) {
      setErreur(messageErreur(e))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal open={open} onClose={enCours ? () => undefined : onClose} maxWidth="md" title={titre} description={description}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          void valider()
        }}
      >
        {children}
        <Textarea
          label={motifRequis ? 'Motif (obligatoire)' : 'Motif'}
          helperText="5 caractères minimum. Inscrit au journal d'audit."
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          rows={3}
          maxLength={500}
          required={motifRequis}
          autoFocus
        />
        {erreur && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {erreur}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={enCours}>
            Annuler
          </Button>
          <Button
            type="submit"
            variant={variante}
            disabled={enCours || (motifRequis && motif.trim().length < 5)}
          >
            {enCours ? 'Traitement…' : libelleConfirmer}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
