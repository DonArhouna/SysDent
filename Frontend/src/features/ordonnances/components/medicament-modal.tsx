import { useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useToastStore } from '@/stores/toast-store'
import { ordonnancesApi } from '../services/ordonnances-api'
import type { Medicament, RegleContreIndication } from '../types'
import { Plus, Trash2 } from 'lucide-react'

interface MedicamentModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (medicament: Medicament) => void
}

const FORMES = [
  { value: 'COMPRIME', label: 'Comprimé' },
  { value: 'GELULE', label: 'Gélule' },
  { value: 'SIROP', label: 'Sirop / Solution buvable' },
  { value: 'BAIN_BOUCHE', label: 'Bain de bouche' },
  { value: 'GEL_BUCCAL', label: 'Gel buccal' },
  { value: 'INJECTABLE', label: 'Injectable' },
  { value: 'SACHET', label: 'Poudre / Sachet' },
]

const CONDITIONS_COURANTES = [
  { value: 'ALLERGIE_PENICILLINE', label: 'Allergie Pénicilline' },
  { value: 'ALLERGIE_AINS', label: 'Allergie AINS / Aspirine' },
  { value: 'GROSSESSE', label: 'Grossesse' },
  { value: 'ALLAITEMENT', label: 'Allaitement' },
  { value: 'INSUFFISANCE_RENALE', label: 'Insuffisance rénale' },
  { value: 'ULCERE_GASTRIQUE', label: 'Ulcère gastro-duodénal' },
  { value: 'ASTHME', label: 'Asthme' },
  { value: 'HYPERTENSION', label: 'Hypertension artérielle' },
]

export function MedicamentModal({ isOpen, onClose, onSuccess }: MedicamentModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const [nomCommercial, setNomCommercial] = useState('')
  const [dci, setDci] = useState('')
  const [forme, setForme] = useState('COMPRIME')
  const [dosage, setDosage] = useState('')
  const [classe, setClasse] = useState('')
  const [posologieAdulte, setPosologieAdulte] = useState('')
  const [precautions] = useState('')
  const [regles, setRegles] = useState<RegleContreIndication[]>([])

  const [nouvelleCondition, setNouvelleCondition] = useState('ALLERGIE_PENICILLINE')
  const [nouvelleGravite, setNouvelleGravite] = useState<'INTERDIT' | 'PRECAUTION'>('INTERDIT')
  const [nouveauMessage, setNouveauMessage] = useState('')

  const handleAddRegle = () => {
    if (!nouveauMessage.trim()) {
      addToast({ type: 'warning', message: 'Indiquez un message pour cette contre-indication.' })
      return
    }
    setRegles((prev) => [
      ...prev,
      {
        condition: nouvelleCondition,
        gravite: nouvelleGravite,
        message: nouveauMessage.trim(),
      },
    ])
    setNouveauMessage('')
  }

  const handleRemoveRegle = (index: number) => {
    setRegles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nomCommercial.trim() || !dci.trim()) {
      addToast({ type: 'warning', message: 'Nom commercial et DCI sont obligatoires.' })
      return
    }

    try {
      setSubmitting(true)
      const res = await ordonnancesApi.creerMedicament({
        nom_commercial: nomCommercial.trim(),
        dci: dci.trim(),
        forme,
        dosage: dosage.trim() || undefined,
        classe_therapeutique: classe.trim() || undefined,
        posologie_adulte: posologieAdulte.trim() || undefined,
        precautions: precautions.trim() || undefined,
        contre_indications: regles,
      })
      addToast({ type: 'success', message: 'Médicament ajouté au référentiel.' })
      onSuccess(res.data)
      onClose()
    } catch {
      // toast géré par l'intercepteur API
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Ajouter un médicament au référentiel" size="lg">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Nom commercial *"
            placeholder="Ex: Augmentin, Paracétamol..."
            value={nomCommercial}
            onChange={(e) => setNomCommercial(e.target.value)}
            required
          />
          <Input
            label="DCI (Dénomination Commune) *"
            placeholder="Ex: Amoxicilline + Acide clavulanique"
            value={dci}
            onChange={(e) => setDci(e.target.value)}
            required
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Select
            label="Forme galénique"
            options={FORMES}
            value={forme}
            onChange={(e) => setForme(e.target.value)}
          />
          <Input
            label="Dosage"
            placeholder="Ex: 1g, 500mg"
            value={dosage}
            onChange={(e) => setDosage(e.target.value)}
          />
          <Input
            label="Classe thérapeutique"
            placeholder="Ex: Antibiotique, AINS, Antalgique"
            value={classe}
            onChange={(e) => setClasse(e.target.value)}
          />
        </div>

        <Input
          label="Posologie adulte recommandée"
          placeholder="Ex: 1 comprimé matin et soir au milieu des repas"
          value={posologieAdulte}
          onChange={(e) => setPosologieAdulte(e.target.value)}
        />

        {/* Section Contre-indications & Alertes automatiques */}
        <div className="border border-border rounded-xl p-4 bg-card space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-foreground">
                Règles de contre-indications & alertes
              </h4>
              <p className="text-xs text-muted-foreground">
                Déclenchera une alerte automatique lors de la prescription selon les antécédents du patient.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
            <div className="md:col-span-4">
              <label className="text-xs text-card-foreground font-medium mb-1 block">Condition</label>
              <select
                className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-xs text-foreground"
                value={nouvelleCondition}
                onChange={(e) => setNouvelleCondition(e.target.value)}
              >
                {CONDITIONS_COURANTES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-3">
              <label className="text-xs text-card-foreground font-medium mb-1 block">Gravité</label>
              <select
                className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-xs text-foreground"
                value={nouvelleGravite}
                onChange={(e) => setNouvelleGravite(e.target.value as 'INTERDIT' | 'PRECAUTION')}
              >
                <option value="INTERDIT">INTERDIT (Bloquant)</option>
                <option value="PRECAUTION">PRECAUTION (Justification requise)</option>
              </select>
            </div>
            <div className="md:col-span-4">
              <label className="text-xs text-card-foreground font-medium mb-1 block">Message d'alerte</label>
              <input
                className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-xs text-foreground"
                placeholder="Ex: Risque de choc anaphylactique"
                value={nouveauMessage}
                onChange={(e) => setNouveauMessage(e.target.value)}
              />
            </div>
            <div className="md:col-span-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full h-10 flex items-center justify-center"
                onClick={handleAddRegle}
              >
                <Plus className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {regles.length > 0 && (
            <div className="mt-3 space-y-2">
              {regles.map((r, idx) => (
                <div
                  key={idx}
                  className={`flex items-center justify-between p-2.5 rounded-lg border text-xs ${
                    r.gravite === 'INTERDIT'
                      ? 'bg-danger/15 border-danger/40 text-danger'
                      : 'bg-warning/15 border-warning/40 text-warning'
                  }`}
                >
                  <div>
                    <span className="font-bold mr-2 uppercase tracking-wide">
                      [{r.gravite}] {r.condition}
                    </span>
                    <span>: {r.message}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveRegle(idx)}
                    className="text-muted-foreground hover:text-danger p-1"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Enregistrement...' : 'Ajouter au référentiel'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
