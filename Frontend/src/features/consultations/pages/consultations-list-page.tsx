import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Stethoscope,
  Plus,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatusBadge, type StatusTone } from '@/components/ui/status-badge'
import { EmptyState } from '@/components/ui/empty-state'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Modal } from '@/components/ui/modal'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Can } from '@/components/auth/can'
import { formatDateFr, formatTimeFr } from '@/lib/format'
import { toast } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { patientsApi } from '@/features/patients/services/patients-api'
import { praticiensApi } from '@/features/praticiens/services/praticiens-api'
import { consultationsApi } from '../services/consultations-api'
import type { StatutConsultation } from '../types'
import type { Patient } from '@/features/patients/types'
import { nomComplet, type Praticien } from '@/features/praticiens/types'

const STATUT_BADGES: Record<StatutConsultation, { label: string; tone: StatusTone }> = {
  PLANIFIEE: { label: 'Planifiée', tone: 'info' },
  EN_ATTENTE: { label: 'En attente', tone: 'warning' },
  EN_COURS: { label: 'En cours', tone: 'purple' },
  TERMINEE: { label: 'Terminée', tone: 'success' },
  ANNULEE: { label: 'Annulée', tone: 'danger' },
}

export function ConsultationsListPage() {
  const [searchParams] = useSearchParams()
  const cabinetActifId = useCabinetStore((s) => s.cabinetActifId)
  const cabinets = useCabinetStore((s) => s.cabinets)

  const patientIdParam = searchParams.get('patient_id')
  const nouveauParam = searchParams.get('nouveau') === 'true'

  const [page] = useState(1)
  const [statutFiltre, setStatutFiltre] = useState<string>('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')

  // Modale Démarrer consultation
  const [modalDemarrerOpen, setModalDemarrerOpen] = useState(nouveauParam)
  const [patientId, setPatientId] = useState(patientIdParam ?? '')
  const [praticienId, setPraticienId] = useState('')
  const [cabinetId] = useState(cabinetActifId ?? '')
  const [motif, setMotif] = useState('Consultation de contrôle')
  const [loadingDemarrage, setLoadingDemarrage] = useState(false)

  // Patients et Praticiens
  const [patients, setPatients] = useState<Patient[]>([])
  const [praticiens, setPraticiens] = useState<Praticien[]>([])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['consultations', page, statutFiltre, patientIdParam, dateDebut, dateFin],
    queryFn: () =>
      consultationsApi.lister({
        patient_id: patientIdParam || undefined,
        statut: statutFiltre || undefined,
        date_debut: dateDebut || undefined,
        date_fin: dateFin || undefined,
        page,
        limit: 15,
      }),
  })

  const consultations = data?.items ?? []

  const ouvrirDemarrage = () => {
    void patientsApi.lister({ limit: 50 }).then((res) => setPatients(res.items ?? []))
    void praticiensApi.lister().then((res) => {
      // On ne présélectionne plus le premier praticien de la liste : cela
      // attribuait la consultation à quelqu'un d'autre que l'utilisateur
      // connecté, sans le dire. Le choix est désormais explicite, ou absent.
      setPraticiens(res.data ?? [])
    })
    setModalDemarrerOpen(true)
  }

  const handleDemarrer = async (e: React.FormEvent) => {
    e.preventDefault()
    // Le praticien n'est plus obligatoire : l'auteur de la consultation est le
    // compte connecté. Choisir un praticien, c'est attribuer la séance à un
    // profil inscrit à l'Ordre — utile quand une secrétaire ouvre la séance
    // pour le praticien qui va la prendre.
    if (!patientId) {
      toast.error('Veuillez sélectionner un patient.')
      return
    }

    try {
      setLoadingDemarrage(true)
      const cabCible = cabinetId || cabinetActifId || (cabinets[0]?.id ?? '')
      const res = await consultationsApi.demarrer({
        patient_id: patientId,
        // Chaîne vide = aucun profil attribué. L'envoyer telle quelle ferait
        // échouer la validation UUID côté serveur.
        praticien_id: praticienId || undefined,
        cabinet_id: cabCible,
        motif,
      })
      toast.success('Consultation démarrée avec succès.')
      setModalDemarrerOpen(false)
      window.location.href = `/consultations/${res.data.id}`
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingDemarrage(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête */}
      <PageHeader
        titre={
          <span className="flex items-center gap-2">
            <Stethoscope className="h-7 w-7 text-primary" aria-hidden />
            Consultations Médicales &amp; Actes
          </span>
        }
        sousTitre="Examens cliniques, diagnostics CIM-10, soins dentaires et total facturable"
        onRefresh={() => void refetch()}
      >
        <Can permission="CONSULTATIONS:CREATE">
          <Button variant="primary" size="sm" onClick={ouvrirDemarrage}>
            <Plus className="h-4 w-4" />
            Nouvelle consultation
          </Button>
        </Can>
      </PageHeader>

      {/* Filtres */}
      <div className="rounded-xl2 border border-border bg-card p-4 shadow-float flex flex-wrap items-center gap-3">
        <Select
          value={statutFiltre}
          onChange={(e) => setStatutFiltre(e.target.value)}
          className="h-9 text-xs w-44"
        >
          <option value="">Tous les statuts</option>
          <option value="EN_COURS">En cours</option>
          <option value="TERMINEE">Terminée</option>
          <option value="PLANIFIEE">Planifiée</option>
          <option value="ANNULEE">Annulée</option>
        </Select>

        <div className="flex items-center gap-2 text-xs">
          <Label htmlFor="date-deb" className="text-muted-foreground">
            Du :
          </Label>
          <input
            id="date-deb"
            type="date"
            value={dateDebut}
            onChange={(e) => setDateDebut(e.target.value)}
            className="rounded-lg border border-input bg-card px-2.5 py-1 text-xs text-foreground"
          />
        </div>

        <div className="flex items-center gap-2 text-xs">
          <Label htmlFor="date-f" className="text-muted-foreground">
            Au :
          </Label>
          <input
            id="date-f"
            type="date"
            value={dateFin}
            onChange={(e) => setDateFin(e.target.value)}
            className="rounded-lg border border-input bg-card px-2.5 py-1 text-xs text-foreground"
          />
        </div>
      </div>

      {/* Tableau des consultations */}
      <div className="rounded-xl2 border border-border bg-card shadow-float overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : isError ? (
          <EmptyState
            icon={Stethoscope}
            titre="Consultations indisponibles"
            description="Impossible de charger les consultations. Vérifiez votre session puis réessayez via « Actualiser »."
          />
        ) : consultations.length === 0 ? (
          <EmptyState
            icon={Stethoscope}
            titre="Aucune consultation trouvée"
            description="Démarrez une consultation pour alimenter l'historique du patient."
          >
            <Can permission="CONSULTATIONS:CREATE">
              <Button variant="outline" size="sm" onClick={ouvrirDemarrage}>
                Démarrer une consultation
              </Button>
            </Can>
          </EmptyState>
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>Date & Heure</TH>
                <TH>Patient</TH>
                <TH>Auteur</TH>
                <TH>Motif de consultation</TH>
                <TH>Diagnostic principal</TH>
                <TH>Statut</TH>
                <TH className="text-right">Action</TH>
              </TRow>
            </THead>
            <TBody>
              {consultations.map((c) => {
                const conf = STATUT_BADGES[c.statut] ?? { label: c.statut, tone: 'neutral' as StatusTone }
                return (
                  <TRow key={c.id}>
                    <TD className="text-xs font-mono">
                      <span className="font-semibold text-foreground block">
                        {formatDateFr(c.date_consultation)}
                      </span>
                      <span className="text-muted-foreground">{formatTimeFr(c.date_consultation)}</span>
                    </TD>
                    <TD>
                      <Link
                        to={`/patients/${c.patient_id}`}
                        className="font-semibold text-foreground hover:text-primary transition-colors text-xs"
                      >
                        {c.patient_numero_dossier ?? 'Dossier'}
                      </Link>
                    </TD>
                    <TD className="text-xs font-medium text-foreground max-w-xs truncate">
                      {c.motif}
                    </TD>
                    <TD className="text-xs text-muted-foreground max-w-xs truncate">
                      {c.diagnostic_principal ?? '—'}
                    </TD>
                    <TD className="text-xs">
                      {/* L'auteur est le compte qui a fait l'acte ; le profil
                          praticien est l'attribution reglementaire, facultative. */}
                      <span className="block truncate">{c.auteur_email ?? '—'}</span>
                      {!c.praticien_id && (
                        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                          sans profil Order
                        </span>
                      )}
                    </TD>
                    <TD>
                      <StatusBadge tone={conf.tone}>{conf.label}</StatusBadge>
                    </TD>
                    <TD className="text-right">
                      <Link to={`/consultations/${c.id}`}>
                        <Button variant="ghost" size="sm">
                          Ouvrir soin
                        </Button>
                      </Link>
                    </TD>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        )}
      </div>

      {/* Modale Démarrage */}
      <Modal
        open={modalDemarrerOpen}
        onClose={() => setModalDemarrerOpen(false)}
        title="Démarrer une consultation dentaire"
        maxWidth="md"
      >
        <form onSubmit={handleDemarrer} className="space-y-4 pt-2">
          <div>
            <Label htmlFor="cons-patient" required>
              Patient
            </Label>
            {patientIdParam ? (
              <p className="text-xs font-semibold p-2.5 rounded-lg border border-border bg-muted/40">
                Patient lié au dossier actif
              </p>
            ) : (
              <Select
                id="cons-patient"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                required
              >
                <option value="">Sélectionner un patient</option>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.prenom} {p.nom} ({p.numero_dossier})
                  </option>
                ))}
              </Select>
            )}
          </div>

          <div>
            <Label htmlFor="cons-prat">Praticien (facultatif)</Label>
            <Select
              id="cons-prat"
              value={praticienId}
              onChange={(e) => setPraticienId(e.target.value)}
            >
              <option value="">Aucun praticien attribué</option>
              {praticiens.map((pr) => (
                <option key={pr.id} value={pr.id}>
                  {pr.titre ? `${pr.titre} ` : 'Dr '}
                  {nomComplet(pr)}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="cons-motif" required>
              Motif de consultation
            </Label>
            <Input
              id="cons-motif"
              value={motif}
              onChange={(e) => setMotif(e.target.value)}
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalDemarrerOpen(false)}
              disabled={loadingDemarrage}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" loading={loadingDemarrage}>
              Ouvrir le dossier de soin
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
