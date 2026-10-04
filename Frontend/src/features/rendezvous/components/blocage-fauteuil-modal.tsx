import { useState, useEffect, type FormEvent } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { toast } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { cabinetsApi } from '@/features/cabinets/services/cabinets-api'
import { rendezvousApi } from '../services/rendezvous-api'
import type { Fauteuil } from '@/features/cabinets/types'
import type { MotifBlocageFauteuil } from '../types'

interface BlocageFauteuilModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  initialDate?: string
}

const MOTIFS_BLOCAGE: Array<{ value: MotifBlocageFauteuil; label: string }> = [
  { value: 'PANNE', label: 'Panne technique / Matériel hors service' },
  { value: 'MAINTENANCE', label: 'Maintenance préventive / Révision' },
  { value: 'DESINFECTION', label: 'Désinfection approfondie & Stérilisation' },
  { value: 'RESERVATION_INTERNE', label: 'Réservation interne / Bloc chirurgical' },
  { value: 'AUTRE', label: 'Autre motif' },
]

export function BlocageFauteuilModal({
  open,
  onClose,
  onSuccess,
  initialDate,
}: BlocageFauteuilModalProps) {
  const cabinetActifId = useCabinetStore((s) => s.cabinetActifId)
  const cabinets = useCabinetStore((s) => s.cabinets)

  const [fauteuils, setFauteuils] = useState<Fauteuil[]>([])
  const [fauteuilId, setFauteuilId] = useState('')
  const [date, setDate] = useState(() => initialDate ?? new Date().toISOString().slice(0, 10))
  const [heureDebut, setHeureDebut] = useState('12:00')
  const [heureFin, setHeureFin] = useState('14:00')
  const [motif, setMotif] = useState<MotifBlocageFauteuil>('PANNE')
  const [motifDetail, setMotifDetail] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open) {
      const cabCible = cabinetActifId || cabinets[0]?.id
      if (cabCible) {
        void cabinetsApi.listerFauteuils(cabCible, false).then((res) => {
          const liste = res.data ?? []
          setFauteuils(liste)
          if (liste.length > 0 && !fauteuilId) {
            setFauteuilId(liste[0].id)
          }
        })
      }
    }
  }, [open, cabinetActifId, cabinets, fauteuilId])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!fauteuilId) {
      toast.error('Veuillez sélectionner un fauteuil.')
      return
    }

    try {
      setLoading(true)
      await rendezvousApi.bloquerFauteuil({
        fauteuil_id: fauteuilId,
        debut: `${date}T${heureDebut}:00`,
        fin: `${date}T${heureFin}:00`,
        motif,
        motif_detail: motifDetail.trim() || undefined,
      })
      toast.success('Fauteuil immobilisé avec succès.')
      onSuccess()
      onClose()
    } catch {
      // Géré par le toast global
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Immobiliser un fauteuil dentaire"
      description="Déclare une indisponibilité (panne, maintenance) interdisant la prise de rendez-vous sur ce fauteuil"
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 pt-2">
        <div>
          <Label htmlFor="bloc-fauteuil" required>
            Fauteuil concerné
          </Label>
          <Select
            id="bloc-fauteuil"
            value={fauteuilId}
            onChange={(e) => setFauteuilId(e.target.value)}
            required
          >
            {fauteuils.map((f) => (
              <option key={f.id} value={f.id}>
                {f.numero} ({f.nom_salle ?? 'Salle'})
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label htmlFor="bloc-motif" required>
            Motif d'indisponibilité
          </Label>
          <Select
            id="bloc-motif"
            value={motif}
            onChange={(e) => setMotif(e.target.value as MotifBlocageFauteuil)}
            required
          >
            {MOTIFS_BLOCAGE.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label htmlFor="bloc-date" required>
            Date
          </Label>
          <Input
            id="bloc-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="bloc-h-debut" required>
              Heure début
            </Label>
            <Input
              id="bloc-h-debut"
              type="time"
              value={heureDebut}
              onChange={(e) => setHeureDebut(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="bloc-h-fin" required>
              Heure fin
            </Label>
            <Input
              id="bloc-h-fin"
              type="time"
              value={heureFin}
              onChange={(e) => setHeureFin(e.target.value)}
              required
            />
          </div>
        </div>

        <div>
          <Label htmlFor="bloc-detail">Précision / Détail technique</Label>
          <Input
            id="bloc-detail"
            value={motifDetail}
            onChange={(e) => setMotifDetail(e.target.value)}
            placeholder="Ex: Compresseur en panne, remplacement pièce..."
          />
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Annuler
          </Button>
          <Button type="submit" variant="danger" loading={loading}>
            Confirmer l'immobilisation
          </Button>
        </div>
      </form>
    </Modal>
  )
}
