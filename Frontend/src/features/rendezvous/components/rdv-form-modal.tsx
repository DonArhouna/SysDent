import { useState, useEffect, type FormEvent } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { patientsApi } from '@/features/patients/services/patients-api'
import { praticiensApi } from '@/features/praticiens/services/praticiens-api'
import { cabinetsApi } from '@/features/cabinets/services/cabinets-api'
import { rendezvousApi } from '../services/rendezvous-api'
import type { CreneauLibre, RdvCreateInput, RendezVous } from '../types'
import type { Patient } from '@/features/patients/types'
import { nomComplet, type Praticien } from '@/features/praticiens/types'
import type { Fauteuil } from '@/features/cabinets/types'
import { ApiError } from '@/lib/api'
import { AlertCircle, Clock, Check } from 'lucide-react'

interface RdvFormModalProps {
  open: boolean
  onClose: () => void
  onSuccess: (rdv: RendezVous) => void
  initialDate?: string
  initialPraticienId?: string
  initialPatientId?: string
}

const MOTIFS_USUELS = [
  'Consultation initiale & Bilan',
  'Urgence / Douleur aiguë',
  'Détartrage & Prophylaxie',
  'Soin conservateur (Carie)',
  'Endodontie / Dévitalisation',
  'Extraction dentaire',
  'Pose de prothèse / Couronne',
  'Contrôle post-opératoire',
  'Orthodontie',
]

export function RdvFormModal({
  open,
  onClose,
  onSuccess,
  initialDate,
  initialPraticienId,
  initialPatientId,
}: RdvFormModalProps) {
  const cabinetActifId = useCabinetStore((s) => s.cabinetActifId)
  const cabinets = useCabinetStore((s) => s.cabinets)

  // Champs du formulaire
  const [patientId, setPatientId] = useState(initialPatientId ?? '')
  const [praticienId, setPraticienId] = useState(initialPraticienId ?? '')
  const [cabinetId, setCabinetId] = useState(cabinetActifId ?? '')
  const [fauteuilId, setFauteuilId] = useState('')
  const [date, setDate] = useState(() => initialDate ?? new Date().toISOString().slice(0, 10))
  const [heureDebut, setHeureDebut] = useState('09:00')
  const [dureeMinutes, setDureeMinutes] = useState(30)
  const [motif, setMotif] = useState(MOTIFS_USUELS[0])
  const [notes, setNotes] = useState('')

  // Recherche patient
  const [recherchePatient, setRecherchePatient] = useState('')
  const [patientsTrouves, setPatientsTrouves] = useState<Patient[]>([])
  const [patientSelectionne, setPatientSelectionne] = useState<Patient | null>(null)

  // Données chargées
  const [praticiens, setPraticiens] = useState<Praticien[]>([])
  const [fauteuils, setFauteuils] = useState<Fauteuil[]>([])
  const [creneauxLibres, setCreneauxLibres] = useState<CreneauLibre[]>([])
  const [loadingCreneaux, setLoadingCreneaux] = useState(false)

  const [loading, setLoading] = useState(false)
  const [erreurConflit, setErreurConflit] = useState<string | null>(null)

  // Charger la liste des praticiens
  useEffect(() => {
    if (open) {
      void praticiensApi.lister().then((res) => {
        const liste = res.data ?? []
        setPraticiens(liste)
        if (!praticienId && liste.length > 0) {
          setPraticienId(liste[0].id)
        }
      })
    }
  }, [open, praticienId])

  // Charger les fauteuils du cabinet sélectionné
  useEffect(() => {
    const cabId = cabinetId || cabinetActifId || (cabinets[0]?.id ?? '')
    if (cabId) {
      void cabinetsApi.listerFauteuils(cabId, false).then((res) => {
        setFauteuils(res.data ?? [])
      })
    }
  }, [cabinetId, cabinetActifId, cabinets])

  // Charger les créneaux libres en direct dès que praticien/date/durée changent
  useEffect(() => {
    if (praticienId && date) {
      setLoadingCreneaux(true)
      void rendezvousApi
        .creneauxLibres(praticienId, date, dureeMinutes, cabinetId || undefined)
        .then((res) => {
          setCreneauxLibres(res.data ?? [])
        })
        .finally(() => setLoadingCreneaux(false))
    }
  }, [praticienId, date, dureeMinutes, cabinetId])

  // Recherche dynamique des patients
  useEffect(() => {
    if (recherchePatient.trim().length >= 2) {
      const timer = setTimeout(() => {
        void patientsApi.lister({ q: recherchePatient.trim(), limit: 5 }).then((res) => {
          setPatientsTrouves(res.items ?? [])
        })
      }, 250)
      return () => clearTimeout(timer)
    } else {
      setPatientsTrouves([])
    }
  }, [recherchePatient])

  // Pré-remplissage si initialPatientId
  useEffect(() => {
    if (initialPatientId && open) {
      void patientsApi.obtenir(initialPatientId).then((res) => {
        setPatientSelectionne(res.data)
        setPatientId(res.data.id)
      })
    }
  }, [initialPatientId, open])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErreurConflit(null)

    if (!patientId) {
      toast.error('Veuillez sélectionner un patient.')
      return
    }
    if (!praticienId) {
      toast.error('Veuillez sélectionner un praticien.')
      return
    }

    try {
      setLoading(true)
      const debutIso = `${date}T${heureDebut}:00`
      const cabCible = cabinetId || cabinetActifId || (cabinets[0]?.id ?? '')

      const payload: RdvCreateInput = {
        patient_id: patientId,
        praticien_id: praticienId,
        cabinet_id: cabCible,
        fauteuil_id: fauteuilId || null,
        debut: debutIso,
        duree_minutes: dureeMinutes,
        motif,
        notes: notes.trim() || undefined,
      }

      const res = await rendezvousApi.creer(payload)
      toast.success(res.message ?? 'Rendez-vous planifié avec succès.')
      onSuccess(res.data)
      onClose()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'CRENEAU_DEJA_OCCUPE') {
        const details = err.details as { conflits?: Array<{ ressource: string; motif?: string }> } | undefined
        const msg = details?.conflits
          ? `Le créneau est déjà occupé : ${details.conflits.map((c) => `${c.ressource} (${c.motif ?? 'occupé'})`).join(', ')}`
          : err.message
        setErreurConflit(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Planifier un Rendez-vous"
      description="Prise de RDV au planning avec vérification d'absence de conflit praticien et fauteuil"
      maxWidth="3xl"
    >
      <form onSubmit={handleSubmit} className="space-y-5 pt-2">
        {erreurConflit && (
          <div className="flex items-start gap-2.5 rounded-xl border border-danger/40 bg-danger/10 p-3.5 text-danger text-xs sm:text-sm">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Conflit d'agenda détecté</p>
              <p className="mt-0.5">{erreurConflit}</p>
              <p className="mt-1 text-[11px] opacity-80">
                Veuillez choisir un autre créneau ci-dessous parmi les plages disponibles.
              </p>
            </div>
          </div>
        )}

        {/* 1. Patient */}
        <div className="space-y-2">
          <Label required>Patient</Label>
          {patientSelectionne ? (
            <div className="flex items-center justify-between p-3 rounded-xl border border-primary/30 bg-primary/5">
              <div>
                <p className="font-bold text-sm text-foreground">
                  {patientSelectionne.prenom} {patientSelectionne.nom}
                </p>
                <p className="text-xs text-muted-foreground font-mono">
                  {patientSelectionne.numero_dossier} • Tél: {patientSelectionne.telephone_1}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setPatientSelectionne(null)
                  setPatientId('')
                }}
              >
                Changer
              </Button>
            </div>
          ) : (
            <div className="relative">
              <Input
                placeholder="Rechercher patient par nom, prénom ou téléphone..."
                value={recherchePatient}
                onChange={(e) => setRecherchePatient(e.target.value)}
              />
              {patientsTrouves.length > 0 && (
                <div className="absolute top-full left-0 right-0 z-30 mt-1 max-h-48 overflow-y-auto rounded-xl border border-border bg-card p-1 shadow-lg">
                  {patientsTrouves.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        setPatientSelectionne(p)
                        setPatientId(p.id)
                        setRecherchePatient('')
                        setPatientsTrouves([])
                      }}
                      className="flex w-full items-center justify-between p-2 rounded-lg text-left text-xs hover:bg-muted transition-colors"
                    >
                      <span className="font-semibold text-foreground">
                        {p.prenom} {p.nom}
                      </span>
                      <span className="font-mono text-muted-foreground">{p.telephone_1}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 2. Praticien et Site */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <Label htmlFor="rdv-praticien" required>
              Praticien
            </Label>
            <Select
              id="rdv-praticien"
              value={praticienId}
              onChange={(e) => setPraticienId(e.target.value)}
              required
            >
              {praticiens.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.titre ? `${p.titre} ` : 'Dr '}
                  {nomComplet(p)} ({p.specialite ?? 'Généraliste'})
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="rdv-cabinet">Cabinet / Site</Label>
            <Select
              id="rdv-cabinet"
              value={cabinetId}
              onChange={(e) => setCabinetId(e.target.value)}
            >
              {cabinets.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nom} {c.ville ? `(${c.ville})` : ''}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {/* 3. Date, Heure et Durée */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <Label htmlFor="rdv-date" required>
              Date
            </Label>
            <Input
              id="rdv-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="rdv-heure" required>
              Heure de début
            </Label>
            <Input
              id="rdv-heure"
              type="time"
              value={heureDebut}
              onChange={(e) => setHeureDebut(e.target.value)}
              required
            />
          </div>

          <div>
            <Label htmlFor="rdv-duree" required>
              Durée
            </Label>
            <Select
              id="rdv-duree"
              value={dureeMinutes}
              onChange={(e) => setDureeMinutes(parseInt(e.target.value, 10))}
            >
              <option value={15}>15 minutes</option>
              <option value={30}>30 minutes</option>
              <option value={45}>45 minutes</option>
              <option value={60}>1 heure</option>
              <option value={90}>1h 30min (Chirurgie)</option>
            </Select>
          </div>
        </div>

        {/* Suggestion des créneaux libres en temps réel */}
        <div className="rounded-xl border border-border bg-muted/20 p-3 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-primary" />
              Créneaux libres calculés pour le {date} :
            </span>
            {loadingCreneaux && <span className="text-muted-foreground text-[11px]">Calcul…</span>}
          </div>

          {creneauxLibres.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              {creneauxLibres.map((c, i) => {
                const estChoisi = c.debut === `${date}T${heureDebut}:00`
                const heureAffichée = c.debut.slice(11, 16)
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setHeureDebut(heureAffichée)
                      if (c.fauteuils_libres.length > 0) {
                        setFauteuilId(c.fauteuils_libres[0].id)
                      }
                    }}
                    className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium transition-all ${
                      estChoisi
                        ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                        : 'border border-border bg-card text-foreground hover:border-primary/50'
                    }`}
                  >
                    {heureAffichée}
                    {estChoisi && <Check className="h-3 w-3 inline ml-1" />}
                  </button>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground italic">
              {loadingCreneaux ? 'Recherche des disponibilités...' : 'Aucun créneau libre automatique détecté (la saisie manuelle reste permise).'}
            </p>
          )}
        </div>

        {/* 4. Fauteuil & Motif */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <Label htmlFor="rdv-fauteuil">Fauteuil d'examen</Label>
            <Select
              id="rdv-fauteuil"
              value={fauteuilId}
              onChange={(e) => setFauteuilId(e.target.value)}
            >
              <option value="">Attribution automatique au passage</option>
              {fauteuils.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.numero} ({f.nom_salle ?? 'Salle'})
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="rdv-motif" required>
              Motif du rendez-vous
            </Label>
            <Select
              id="rdv-motif"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
            >
              {MOTIFS_USUELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div>
          <Label htmlFor="rdv-notes">Consignes & Notes pour l'accueil</Label>
          <Textarea
            id="rdv-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Détails complémentaires, dossier à préparer..."
            rows={2}
          />
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            Confirmer le rendez-vous
          </Button>
        </div>
      </form>
    </Modal>
  )
}
