import { useState, useEffect, type FormEvent } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/stores/toast-store'
import { patientsApi } from '../services/patients-api'
import type { AntecedentMedical } from '../types'

interface AntecedentModalProps {
  patientId: string
  open: boolean
  onClose: () => void
  onSuccess: () => void
  antecedentToEdit?: AntecedentMedical | null
}

const TYPES_ANTECEDENTS = [
  { value: 'CHIRURGICAL', label: 'Chirurgical' },
  { value: 'CARDIO', label: 'Cardio-vasculaire' },
  { value: 'ALLERGIE', label: 'Allergie' },
  { value: 'DIABETE', label: 'Diabète & Métabolique' },
  { value: 'HTA', label: 'Hypertension artérielle' },
  { value: 'RESPIRATOIRE', label: 'Respiratoire (Asthme...)' },
  { value: 'DENTAIRE', label: 'Dentaire spécifique' },
  { value: 'FAMILIAL', label: 'Antécédent familial' },
  { value: 'AUTRE', label: 'Autre pathologie' },
]

export function AntecedentModal({
  patientId,
  open,
  onClose,
  onSuccess,
  antecedentToEdit,
}: AntecedentModalProps) {
  const isEditing = Boolean(antecedentToEdit)

  const [typeAntecedent, setTypeAntecedent] = useState('CARDIO')
  const [description, setDescription] = useState('')
  const [dateSurvenue, setDateSurvenue] = useState('')
  const [enCours, setEnCours] = useState(true)
  const [traitementAssocie, setTraitementAssocie] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)

  useEffect(() => {
    if (antecedentToEdit) {
      setTypeAntecedent(antecedentToEdit.type_antecedent)
      setDescription(antecedentToEdit.description)
      setDateSurvenue(antecedentToEdit.date_survenue ? antecedentToEdit.date_survenue.slice(0, 10) : '')
      setEnCours(antecedentToEdit.en_cours)
      setTraitementAssocie(antecedentToEdit.traitement_associe ?? '')
      setNotes(antecedentToEdit.notes ?? '')
    } else {
      setTypeAntecedent('CARDIO')
      setDescription('')
      setDateSurvenue('')
      setEnCours(true)
      setTraitementAssocie('')
      setNotes('')
    }
    setErreur(null)
  }, [antecedentToEdit, open])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!description.trim()) {
      setErreur('La description de l’antécédent est obligatoire.')
      return
    }

    try {
      setLoading(true)
      if (isEditing && antecedentToEdit) {
        await patientsApi.modifierAntecedent(antecedentToEdit.id, {
          type_antecedent: typeAntecedent,
          description: description.trim(),
          date_survenue: dateSurvenue || null,
          en_cours: enCours,
          traitement_associe: traitementAssocie.trim() || null,
          notes: notes.trim() || null,
        })
        toast.success('Antécédent mis à jour.')
      } else {
        await patientsApi.ajouterAntecedent(patientId, {
          type_antecedent: typeAntecedent,
          description: description.trim(),
          date_survenue: dateSurvenue || null,
          en_cours: enCours,
          traitement_associe: traitementAssocie.trim() || null,
          notes: notes.trim() || null,
        })
        toast.success('Antécédent enregistré dans le dossier.')
      }
      onSuccess()
      onClose()
    } catch {
      // Erreur gérée par le toast global
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEditing ? "Modifier l'antécédent médical" : "Ajouter un antécédent médical"}
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 pt-2">
        <div>
          <Label htmlFor="type-antecedent" required>
            Type de pathologie / Antécédent
          </Label>
          <Select
            id="type-antecedent"
            value={typeAntecedent}
            onChange={(e) => setTypeAntecedent(e.target.value)}
          >
            {TYPES_ANTECEDENTS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label htmlFor="description" required>
            Description clinique
          </Label>
          <Input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Ex: Infarctus du myocarde en 2021, pose de stent"
            error={erreur ?? undefined}
            required
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <Label htmlFor="date-survenue">Date de survenue / diagnostic</Label>
            <Input
              id="date-survenue"
              type="date"
              value={dateSurvenue}
              onChange={(e) => setDateSurvenue(e.target.value)}
            />
          </div>

          <div className="flex items-center pt-5">
            <label className="flex items-center gap-2 text-sm font-semibold text-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={enCours}
                onChange={(e) => setEnCours(e.target.checked)}
                className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
              />
              <span>Pathologie toujours active / en cours</span>
            </label>
          </div>
        </div>

        <div>
          <Label htmlFor="traitement">Traitement associé (médicaments en cours)</Label>
          <Input
            id="traitement"
            value={traitementAssocie}
            onChange={(e) => setTraitementAssocie(e.target.value)}
            placeholder="Ex: Kardegic 75mg / jour, Plavix..."
          />
        </div>

        <div>
          <Label htmlFor="notes">Notes & Recommandations opératoires</Label>
          <Textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Précautions lors des anesthésies locales ou extractions..."
            rows={2}
          />
        </div>

        <div className="flex justify-end gap-3 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            {isEditing ? 'Enregistrer' : 'Ajouter au dossier'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
