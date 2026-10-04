import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useToastStore } from '@/stores/toast-store'
import { ordonnancesApi } from '../services/ordonnances-api'
import { patientsApi } from '@/features/patients/services/patients-api'
import type { Patient } from '@/features/patients/types'
import type {
  ControleContreIndicationResponse,
  LignePrescriptionCreate,
  Medicament,
  OrdonnanceResponse,
} from '../types'
import { AlertTriangle, CheckCircle2, Plus, ShieldAlert, Trash2 } from 'lucide-react'

interface OrdonnanceModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (ordonnance: OrdonnanceResponse) => void
  initialPatientId?: string
  initialConsultationId?: string
}

export function OrdonnanceModal({
  isOpen,
  onClose,
  onSuccess,
  initialPatientId,
  initialConsultationId,
}: OrdonnanceModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  // Patient
  const [patientId, setPatientId] = useState(initialPatientId || '')
  const [patients, setPatients] = useState<Patient[]>([])
  const [consultationId, setConsultationId] = useState(initialConsultationId || '')

  // Référentiel
  const [medicaments, setMedicaments] = useState<Medicament[]>([])
  const [rechercheMedicament, setRechercheMedicament] = useState('')

  // Ligne en cours de saisie
  const [selectedMedicament, setSelectedMedicament] = useState<Medicament | null>(null)
  const [medicamentTexte, setMedicamentTexte] = useState('')
  const [posologie, setPosologie] = useState('')
  const [duree, setDuree] = useState('7 jours')
  const [instructions, setInstructions] = useState('')
  const [quantite, setQuantite] = useState(1)
  const [justification, setJustification] = useState('')

  // Contrôle à blanc en temps réel (UC8)
  const [controleResult, setControleResult] = useState<ControleContreIndicationResponse | null>(null)
  const [verifiantControle, setVerifiantControle] = useState(false)

  // Liste des lignes de l'ordonnance
  const [lignes, setLignes] = useState<LignePrescriptionCreate[]>([])
  const [notesGenerales, setNotesGenerales] = useState('')

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
    ordonnancesApi.listerMedicaments({ q: rechercheMedicament }).then((res) => {
      setMedicaments(res.data)
    })
  }, [rechercheMedicament])

  // Déclencher le contrôle à blanc dès qu'un médicament est sélectionné pour le patient
  useEffect(() => {
    if (!patientId || (!selectedMedicament && !medicamentTexte.trim())) {
      setControleResult(null)
      return
    }

    const timer = setTimeout(async () => {
      try {
        setVerifiantControle(true)
        const ligneTest: LignePrescriptionCreate = {
          medicament_id: selectedMedicament?.id || null,
          medicament_texte: selectedMedicament ? null : medicamentTexte,
          posologie: posologie || '1 comprimé par jour',
          duree: duree || '7 jours',
          quantite: quantite || 1,
        }
        const res = await ordonnancesApi.controlerPrescription(patientId, ligneTest)
        setControleResult(res.data)
      } catch {
        // En cas d'erreur de contrôle silencieux
      } finally {
        setVerifiantControle(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [patientId, selectedMedicament, medicamentTexte, posologie, duree, quantite])

  const handleSelectMedicament = (m: Medicament) => {
    setSelectedMedicament(m)
    setMedicamentTexte('')
    if (m.posologie_adulte) {
      setPosologie(m.posologie_adulte)
    }
    if (m.precautions) {
      setInstructions(m.precautions)
    }
  }

  const handleAddLigne = () => {
    if (!selectedMedicament && !medicamentTexte.trim()) {
      addToast({ type: 'warning', message: 'Veuillez choisir un médicament ou saisir un libellé.' })
      return
    }
    if (!posologie.trim()) {
      addToast({ type: 'warning', message: 'La posologie est obligatoire.' })
      return
    }

    if (controleResult && !controleResult.prescription_possible) {
      addToast({
        type: 'error',
        message: 'Prescription interdite en raison de contre-indications absolues.',
      })
      return
    }

    if (controleResult?.justification_requise && !justification.trim()) {
      addToast({
        type: 'warning',
        message: 'Une justification médicale écrite est obligatoire pour valider cette précaution.',
      })
      return
    }

    const nouvelleLigne: LignePrescriptionCreate = {
      medicament_id: selectedMedicament ? selectedMedicament.id : null,
      medicament_texte: selectedMedicament
        ? `${selectedMedicament.nom_commercial} (${selectedMedicament.dci})`
        : medicamentTexte.trim(),
      posologie: posologie.trim(),
      duree: duree.trim() || undefined,
      instructions: instructions.trim() || undefined,
      quantite,
      justification_precaution: justification.trim() || undefined,
    }

    setLignes((prev) => [...prev, nouvelleLigne])

    // Reset du formulaire de ligne
    setSelectedMedicament(null)
    setMedicamentTexte('')
    setPosologie('')
    setDuree('7 jours')
    setInstructions('')
    setQuantite(1)
    setJustification('')
    setControleResult(null)
  }

  const handleRemoveLigne = (idx: number) => {
    setLignes((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!patientId) {
      addToast({ type: 'warning', message: 'Veuillez sélectionner un patient.' })
      return
    }
    if (lignes.length === 0) {
      addToast({ type: 'warning', message: 'Ajoutez au moins une ligne de prescription.' })
      return
    }

    // Si consultationId n'est pas fourni, le backend exige une consultationId UUID valide
    // Si ouverte depuis une consultation, elle est pré-remplie
    if (!consultationId) {
      addToast({
        type: 'error',
        message: 'Une consultation associée est requise pour émettre une ordonnance légale.',
      })
      return
    }

    try {
      setSubmitting(true)
      const res = await ordonnancesApi.creer({
        patient_id: patientId,
        consultation_id: consultationId,
        lignes,
        notes_generales: notesGenerales.trim() || undefined,
      })
      addToast({ type: 'success', message: `Ordonnance ${res.data.numero} émise avec succès.` })
      onSuccess(res.data)
      onClose()
    } catch {
      // toast géré par l'intercepteur
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Rédiger une ordonnance" size="xl">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* En-tête : Patient & Consultation */}
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
            label="ID Consultation associée *"
            placeholder="UUID de la consultation"
            value={consultationId}
            onChange={(e) => setConsultationId(e.target.value)}
            required
            helperText="Une ordonnance doit être rattachée à une consultation médicale."
          />
        </div>

        {/* Section Médicament & Contrôle */}
        <div className="border border-primary/40 rounded-xl p-4 bg-primary/15 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-primary flex items-center gap-2">
              <Plus className="w-4 h-4" /> Ajouter un médicament
            </h4>
            {verifiantControle && (
              <span className="text-xs text-primary animate-pulse">
                Contrôle des contre-indications en cours...
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-card-foreground mb-1 block">
                Sélectionner dans le référentiel du cabinet
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Rechercher nom commercial, DCI..."
                  value={rechercheMedicament}
                  onChange={(e) => setRechercheMedicament(e.target.value)}
                  className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-sm text-foreground focus:outline-none focus:border-primary/40"
                />
                {medicaments.length > 0 && rechercheMedicament && (
                  <div className="absolute z-20 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-card border border-border rounded-lg shadow-xl divide-y divide-border">
                    {medicaments.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => {
                          handleSelectMedicament(m)
                          setRechercheMedicament('')
                        }}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-muted flex items-center justify-between"
                      >
                        <div>
                          <span className="font-semibold text-foreground">{m.nom_commercial}</span>{' '}
                          <span className="text-muted-foreground">({m.dci})</span>
                          {m.dosage && <span className="ml-2 text-primary font-mono">{m.dosage}</span>}
                        </div>
                        <span className="text-[10px] uppercase px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                          {m.forme}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div>
              <Input
                label="Ou saisie libre (hors référentiel)"
                placeholder="Ex: Formule magistrale..."
                value={medicamentTexte}
                onChange={(e) => {
                  setMedicamentTexte(e.target.value)
                  setSelectedMedicament(null)
                }}
              />
            </div>
          </div>

          {selectedMedicament && (
            <div className="p-2.5 rounded-lg bg-primary/15 border border-primary/40 text-xs text-primary flex items-center justify-between">
              <div>
                <span className="font-bold text-white">{selectedMedicament.nom_commercial}</span>
                <span className="mx-1.5">•</span>
                <span>{selectedMedicament.dci}</span>
                <span className="mx-1.5">•</span>
                <span className="uppercase text-primary">{selectedMedicament.forme}</span>
                {selectedMedicament.dosage && <span> - {selectedMedicament.dosage}</span>}
              </div>
              <button
                type="button"
                onClick={() => setSelectedMedicament(null)}
                className="text-xs text-primary hover:text-primary underline"
              >
                Changer
              </button>
            </div>
          )}

          {/* Feedback du contrôle automatique (RG07 & RG08) */}
          {controleResult && (
            <div className="space-y-2">
              {!controleResult.prescription_possible ? (
                <div className="p-3 rounded-lg bg-danger/15 border border-danger/40 text-danger text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-danger">
                    <ShieldAlert className="w-4 h-4 text-danger" />
                    PRESCRIPTION BLOQUÉE (Contre-indication absolue)
                  </div>
                  {controleResult.alertes.map((a, i) => (
                    <div key={i} className="pl-6 text-danger">
                      • {a.message} {a.condition && `[${a.condition}]`}
                    </div>
                  ))}
                </div>
              ) : controleResult.justification_requise ? (
                <div className="p-3 rounded-lg bg-warning/15 border border-warning/40 text-warning text-xs space-y-2">
                  <div className="flex items-center gap-2 font-bold text-warning">
                    <AlertTriangle className="w-4 h-4 text-warning" />
                    PRÉCAUTION D'EMPLOI REQUISE
                  </div>
                  {controleResult.alertes.map((a, i) => (
                    <div key={i} className="pl-6 text-warning">
                      • {a.message} {a.condition && `[${a.condition}]`}
                    </div>
                  ))}
                  <div>
                    <label className="font-semibold text-warning block mb-1">
                      Justification médicale obligatoire (conservée au dossier) :
                    </label>
                    <input
                      type="text"
                      className="w-full h-8 px-2.5 rounded bg-card border border-warning/40 text-xs text-white"
                      placeholder="Ex: Bénéfice supérieur au risque après avis du médecin traitant..."
                      value={justification}
                      onChange={(e) => setJustification(e.target.value)}
                    />
                  </div>
                </div>
              ) : (
                <div className="p-2 rounded bg-success/15 border border-success/40 text-success text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-success" />
                  Aucune contre-indication détectée pour ce patient.
                </div>
              )}
            </div>
          )}

          {/* Posologie, Durée, Quantité */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div className="md:col-span-2">
              <Input
                label="Posologie *"
                placeholder="Ex: 1 comprimé matin et soir"
                value={posologie}
                onChange={(e) => setPosologie(e.target.value)}
              />
            </div>
            <div>
              <Input
                label="Durée"
                placeholder="Ex: 6 jours"
                value={duree}
                onChange={(e) => setDuree(e.target.value)}
              />
            </div>
            <div>
              <Input
                label="Quantité (boîtes)"
                type="number"
                min={1}
                max={50}
                value={quantite}
                onChange={(e) => setQuantite(parseInt(e.target.value) || 1)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
            <div className="md:col-span-10">
              <Input
                label="Instructions spécifiques (optionnel)"
                placeholder="Ex: À prendre au milieu des repas avec un grand verre d'eau"
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </div>
            <div className="md:col-span-2">
              <Button
                type="button"
                variant="primary"
                onClick={handleAddLigne}
                disabled={
                  (!selectedMedicament && !medicamentTexte.trim()) ||
                  (controleResult !== null && !controleResult.prescription_possible)
                }
                className="w-full h-10 flex items-center justify-center gap-1.5"
              >
                <Plus className="w-4 h-4" /> Ajouter
              </Button>
            </div>
          </div>
        </div>

        {/* Lignes ajoutées */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-card-foreground uppercase tracking-wider block">
            Lignes prescrites ({lignes.length})
          </label>
          {lignes.length === 0 ? (
            <div className="p-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl bg-card">
              Aucun médicament ajouté à l'ordonnance pour le moment.
            </div>
          ) : (
            <div className="border border-border rounded-xl overflow-hidden divide-y divide-border bg-card">
              {lignes.map((l, idx) => (
                <div key={idx} className="p-3.5 flex items-center justify-between text-xs">
                  <div className="space-y-1">
                    <div className="font-bold text-foreground flex items-center gap-2">
                      <span>{idx + 1}.</span>
                      <span>{l.medicament_texte}</span>
                      <span className="px-2 py-0.5 rounded bg-muted border border-border text-muted-foreground text-[10px]">
                        Qté: {l.quantite}
                      </span>
                    </div>
                    <div className="text-card-foreground pl-4">
                      <span className="text-primary font-medium">{l.posologie}</span>
                      {l.duree && <span> pendant {l.duree}</span>}
                    </div>
                    {l.instructions && (
                      <div className="text-muted-foreground text-[11px] pl-4 italic">
                        Note: {l.instructions}
                      </div>
                    )}
                    {l.justification_precaution && (
                      <div className="text-warning text-[11px] pl-4">
                        Justification: {l.justification_precaution}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveLigne(idx)}
                    className="p-1.5 text-muted-foreground hover:text-danger rounded-lg hover:bg-muted transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Consignes générales */}
        <Textarea
          label="Consignes générales / Recommandations"
          placeholder="Ex: Maintenir une hygiène bucco-dentaire rigoureuse, bain de bouche 2h après le brossage..."
          value={notesGenerales}
          onChange={(e) => setNotesGenerales(e.target.value)}
          rows={3}
        />

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting || lignes.length === 0}>
            {submitting ? 'Émission...' : "Émettre l'ordonnance"}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
