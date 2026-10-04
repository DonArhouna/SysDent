import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useToastStore } from '@/stores/toast-store'
import { facturationApi } from '../services/facturation-api'
import { patientsApi } from '@/features/patients/services/patients-api'
import { consultationsApi } from '@/features/consultations/services/consultations-api'
import { formatFcfa } from '@/lib/format'
import type { Patient } from '@/features/patients/types'
import type { ActeNomenclature } from '@/features/consultations/types'
import type { DevisCreate, DevisResponse, LigneDevisEntree } from '../types'
import { Plus, Trash2 } from 'lucide-react'

interface DevisModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (devis: DevisResponse) => void
  initialPatientId?: string
}

export function DevisModal({
  isOpen,
  onClose,
  onSuccess,
  initialPatientId,
}: DevisModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const [patientId, setPatientId] = useState(initialPatientId || '')
  const [patients, setPatients] = useState<Patient[]>([])
  const [nomenclature, setNomenclature] = useState<ActeNomenclature[]>([])

  const defaultValidite = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0]
  const [dateValidite, setDateValidite] = useState(defaultValidite)
  const [notes, setNotes] = useState('')

  // Saisie de ligne
  const [selectedActeId, setSelectedActeId] = useState('')
  const [designation, setDesignation] = useState('')
  const [dentNumero, setDentNumero] = useState<string>('')
  const [quantite, setQuantite] = useState(1)
  const [prixUnitaire, setPrixUnitaire] = useState<number>(0)

  // Lignes ajoutées
  const [lignes, setLignes] = useState<LigneDevisEntree[]>([])

  useEffect(() => {
    if (!initialPatientId) {
      patientsApi.lister({ limit: 50 }).then((res) => {
        setPatients(res.items)
        if (res.items.length > 0 && !patientId) {
          setPatientId(res.items[0].id)
        }
      })
    }
  }, [initialPatientId, patientId])

  useEffect(() => {
    consultationsApi.listerNomenclature().then((res) => {
      setNomenclature(res.items)
    })
  }, [])

  const handleSelectActe = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const acteId = e.target.value
    setSelectedActeId(acteId)
    const acte = nomenclature.find((a) => a.id === acteId)
    if (acte) {
      setDesignation(acte.libelle)
      setPrixUnitaire(Number(acte.tarif_base))
    }
  }

  const handleAddLigne = () => {
    if (!designation.trim()) {
      addToast({ type: 'warning', message: 'Veuillez saisir un libellé de prestation.' })
      return
    }
    if (prixUnitaire < 0) {
      addToast({ type: 'warning', message: 'Le prix unitaire doit être positif.' })
      return
    }

    const dentNum = dentNumero ? parseInt(dentNumero) : null

    setLignes((prev) => [
      ...prev,
      {
        acte_id: selectedActeId || null,
        designation: designation.trim(),
        dent_numero: dentNum,
        quantite,
        prix_unitaire: prixUnitaire,
      },
    ])

    // Reset ligne
    setSelectedActeId('')
    setDesignation('')
    setDentNumero('')
    setQuantite(1)
    setPrixUnitaire(0)
  }

  const handleRemoveLigne = (idx: number) => {
    setLignes((prev) => prev.filter((_, i) => i !== idx))
  }

  const totalDevis = lignes.reduce((acc, l) => acc + l.quantite * l.prix_unitaire, 0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!patientId) {
      addToast({ type: 'warning', message: 'Veuillez sélectionner un patient.' })
      return
    }
    if (lignes.length === 0) {
      addToast({ type: 'warning', message: 'Ajoutez au moins une ligne au devis.' })
      return
    }

    try {
      setSubmitting(true)
      const payload: DevisCreate = {
        patient_id: patientId,
        date_validite: dateValidite,
        notes: notes.trim() || undefined,
        lignes,
      }
      const res = await facturationApi.creerDevis(payload)
      addToast({ type: 'success', message: `Devis ${res.data.numero} créé.` })
      onSuccess(res.data)
      onClose()
    } catch {
      // toast géré par l'intercepteur API
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Créer un devis de soins" size="xl">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-card p-4 rounded-xl border border-border">
          <div>
            <label className="text-xs font-semibold text-card-foreground mb-1 block">Patient *</label>
            {initialPatientId ? (
              <div className="h-10 px-3 flex items-center bg-muted border border-border rounded-lg text-sm text-foreground">
                Patient sélectionné ({initialPatientId})
              </div>
            ) : (
              <select
                className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-sm text-foreground"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                required
              >
                <option value="">Sélectionner un patient...</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nom.toUpperCase()} {p.prenom} ({p.numero_dossier})
                  </option>
                ))}
              </select>
            )}
          </div>

          <Input
            label="Date de validité du devis *"
            type="date"
            value={dateValidite}
            onChange={(e) => setDateValidite(e.target.value)}
            required
            helperText="30 jours par défaut conformément aux usages du cabinet."
          />
        </div>

        {/* Ajout de prestations / actes */}
        <div className="border border-border rounded-xl p-4 bg-card space-y-4">
          <h4 className="text-xs font-semibold text-card-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5 text-primary" />
            Ajouter une ligne au devis
          </h4>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-card-foreground mb-1 block">
                Nomenclature d'actes (optionnel)
              </label>
              <select
                className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-xs text-foreground"
                value={selectedActeId}
                onChange={handleSelectActe}
              >
                <option value="">Sélectionner un acte du catalogue...</option>
                {nomenclature.map((a) => (
                  <option key={a.id} value={a.id}>
                    [{a.code}] {a.libelle} ({formatFcfa(a.tarif_base)})
                  </option>
                ))}
              </select>
            </div>

            <Input
              label="Désignation de la prestation *"
              placeholder="Ex: Pose couronne céramique sur molaire"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <Input
                label="Dent FDI (ex: 16, 21...)"
                type="number"
                min="11"
                max="85"
                placeholder="N° Dent"
                value={dentNumero}
                onChange={(e) => setDentNumero(e.target.value)}
              />
            </div>
            <div>
              <Input
                label="Quantité"
                type="number"
                min="1"
                max="99"
                value={quantite}
                onChange={(e) => setQuantite(parseInt(e.target.value) || 1)}
              />
            </div>
            <div>
              <Input
                label="Prix unitaire (FCFA) *"
                type="number"
                min="0"
                value={prixUnitaire}
                onChange={(e) => setPrixUnitaire(parseFloat(e.target.value) || 0)}
              />
            </div>
            <div>
              <Button
                type="button"
                variant="primary"
                onClick={handleAddLigne}
                disabled={!designation.trim()}
                className="w-full h-10 flex items-center justify-center gap-1.5"
              >
                <Plus className="w-4 h-4" /> Ajouter
              </Button>
            </div>
          </div>
        </div>

        {/* Lignes du devis */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-card-foreground uppercase tracking-wider">
              Lignes chiffrées ({lignes.length})
            </span>
            <span className="text-sm font-bold text-primary">
              Total : {formatFcfa(totalDevis)}
            </span>
          </div>

          {lignes.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl bg-card">
              Aucune prestation ajoutée au devis.
            </div>
          ) : (
            <div className="border border-border rounded-xl overflow-hidden divide-y divide-border bg-card">
              {lignes.map((l, idx) => (
                <div key={idx} className="p-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-muted-foreground">{idx + 1}.</span>
                    <div>
                      <div className="font-semibold text-foreground flex items-center gap-2">
                        <span>{l.designation}</span>
                        {l.dent_numero && (
                          <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary border border-primary/40 text-[10px] font-mono">
                            Dent {l.dent_numero}
                          </span>
                        )}
                      </div>
                      <div className="text-muted-foreground text-[11px] mt-0.5">
                        {l.quantite} x {formatFcfa(l.prix_unitaire)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="font-mono font-bold text-foreground">
                      {formatFcfa(l.quantite * l.prix_unitaire)}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveLigne(idx)}
                      className="text-muted-foreground hover:text-danger p-1 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <Textarea
          label="Observations / Conditions du plan de traitement"
          placeholder="Ex: Soins prothétiques sous réserve d'assainissement parodontal préalable..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting || lignes.length === 0}>
            {submitting ? 'Création...' : `Émettre le devis (${formatFcfa(totalDevis)})`}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
