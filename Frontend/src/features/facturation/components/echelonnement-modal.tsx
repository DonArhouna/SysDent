import { useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useToastStore } from '@/stores/toast-store'
import { facturationApi } from '../services/facturation-api'
import { formatFcfa } from '@/lib/format'
import type { FactureResponse, FrequenceEchelonnement, PlanEchelonnementResponse } from '../types'
import { Layers } from 'lucide-react'

interface EchelonnementModalProps {
  isOpen: boolean
  onClose: () => void
  facture: FactureResponse | null
  onSuccess: (plan: PlanEchelonnementResponse) => void
}

const FREQUENCES = [
  { value: 'MENSUEL', label: 'Mensuelle (chaque mois)' },
  { value: 'HEBDOMADAIRE', label: 'Hebdomadaire (chaque semaine)' },
]

export function EchelonnementModal({
  isOpen,
  onClose,
  facture,
  onSuccess,
}: EchelonnementModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const resteAPayer = Number(facture?.montant_restant || 0)
  const [nombreEcheances, setNombreEcheances] = useState(3)
  const [frequence, setFrequence] = useState<FrequenceEchelonnement>('MENSUEL')
  const [dateDebut, setDateDebut] = useState(
    new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  )
  const [notes, setNotes] = useState('')

  if (!facture) return null

  // Calcul prévisionnel des échéances
  const montantParEcheance = Math.floor(resteAPayer / nombreEcheances)
  const reliquatDerniere = resteAPayer - montantParEcheance * (nombreEcheances - 1)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (nombreEcheances < 2 || nombreEcheances > 36) {
      addToast({ type: 'warning', message: "Le nombre d'échéances doit être entre 2 et 36." })
      return
    }

    try {
      setSubmitting(true)
      const res = await facturationApi.creerEchelonnement(facture.id, {
        nombre_echeances: nombreEcheances,
        date_debut: dateDebut,
        frequence,
        notes: notes.trim() || undefined,
      })
      addToast({
        type: 'success',
        message: `Plan d'échelonnement créé : ${res.data.nombre_echeances} échéances.`,
      })
      onSuccess(res.data)
      onClose()
    } catch {
      // toast géré par l'intercepteur API
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Plan d'échelonnement - Facture ${facture.numero}`}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="p-4 rounded-xl bg-card border border-border flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground">Montant total à échelonner</span>
            <p className="text-lg font-bold text-primary">{formatFcfa(resteAPayer)}</p>
          </div>
          <div className="text-right">
            <span className="text-xs text-muted-foreground">Mensualité estimée</span>
            <p className="text-lg font-bold text-foreground">
              ~ {formatFcfa(montantParEcheance)} / mois
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="Nombre d'échéances (2 - 36) *"
            type="number"
            min={2}
            max={36}
            value={nombreEcheances}
            onChange={(e) => setNombreEcheances(parseInt(e.target.value) || 2)}
            required
          />

          <Select
            label="Périodicité *"
            options={FREQUENCES}
            value={frequence}
            onChange={(e) => setFrequence(e.target.value as FrequenceEchelonnement)}
          />

          <Input
            label="Date de la 1ère échéance *"
            type="date"
            value={dateDebut}
            onChange={(e) => setDateDebut(e.target.value)}
            required
          />
        </div>

        {/* Aperçu du plan calculé */}
        <div className="border border-border rounded-xl p-4 bg-card space-y-3">
          <h4 className="text-xs font-semibold text-card-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-primary" />
            Échéancier prévisionnel ({nombreEcheances} versements)
          </h4>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            {Array.from({ length: nombreEcheances }).map((_, idx) => {
              const montantVerse =
                idx === nombreEcheances - 1 ? reliquatDerniere : montantParEcheance
              return (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-muted border border-border text-center"
                >
                  <span className="text-[10px] text-muted-foreground block font-medium">
                    Échéance #{idx + 1}
                  </span>
                  <span className="font-bold text-foreground">{formatFcfa(montantVerse)}</span>
                </div>
              )
            })}
          </div>
        </div>

        <Textarea
          label="Conditions particulières / Notes accordées au patient"
          placeholder="Ex: Échelonnement accordé avec accord du directeur de clinique. Paiements attendus le 5 de chaque mois par Wave..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Création...' : "Confirmer le plan d'échelonnement"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
