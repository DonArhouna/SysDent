import { useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Archive, AlertTriangle } from 'lucide-react'
import { toast } from '@/stores/toast-store'
import { patientsApi } from '../services/patients-api'
import type { Patient } from '../types'

interface ArchiveDialogProps {
  patient: Patient | null
  open: boolean
  onClose: () => void
  onSuccess: (patient: Patient) => void
}

export function ArchiveDialog({ patient, open, onClose, onSuccess }: ArchiveDialogProps) {
  const [motif, setMotif] = useState('')
  const [loading, setLoading] = useState(false)

  if (!patient) return null

  const handleArchive = async () => {
    try {
      setLoading(true)
      const res = await patientsApi.archiver(patient.id, motif.trim() || undefined)
      toast.success(`Le dossier ${patient.numero_dossier} a été archivé.`)
      onSuccess(res.data)
      onClose()
    } catch {
      // Erreur déjà affichée par le toast global
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} maxWidth="md">
      <div className="flex flex-col items-center text-center p-2">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-warning/10 text-warning shadow-inner">
          <Archive className="h-7 w-7" />
        </div>

        <h3 className="text-lg font-bold text-foreground">
          Archiver le dossier {patient.numero_dossier}
        </h3>

        <p className="mt-1 text-xs sm:text-sm text-muted-foreground max-w-sm">
          Patient : <strong className="text-foreground">{patient.prenom} {patient.nom}</strong>
        </p>

        <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-left text-xs text-muted-foreground">
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning mt-0.5" />
          <span>
            Le dossier ne sera pas supprimé (obligation médico-légale de conservation). Il sera
            masqué des recherches courantes et pourra être réactivé à tout moment.
          </span>
        </div>

        <div className="mt-4 w-full text-left">
          <label htmlFor="motif-archivage" className="block text-xs font-semibold text-foreground mb-1">
            Motif de l'archivage (conservé dans l'audit)
          </label>
          <Textarea
            id="motif-archivage"
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Ex: Déménagement, demande expresse du patient, inactif depuis 5 ans..."
            rows={3}
          />
        </div>

        <div className="mt-6 flex w-full gap-3">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading} className="flex-1">
            Annuler
          </Button>
          <Button type="button" variant="danger" onClick={handleArchive} loading={loading} className="flex-1">
            Confirmer l'archivage
          </Button>
        </div>
      </div>
    </Modal>
  )
}
