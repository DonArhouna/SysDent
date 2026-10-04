import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  CalendarDays,
  Plus,
  ChevronLeft,
  ChevronRight,
  Clock,
  Armchair,
  Stethoscope,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Play,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Can } from '@/components/auth/can'
import { formatDateFr } from '@/lib/format'
import { toast } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { praticiensApi } from '@/features/praticiens/services/praticiens-api'
import { rendezvousApi } from '../services/rendezvous-api'
import { RdvFormModal } from '../components/rdv-form-modal'
import { BlocageFauteuilModal } from '../components/blocage-fauteuil-modal'
import type { RendezVous, StatutRdv } from '../types'

const STATUT_STYLES: Record<
  StatutRdv,
  { label: string; badge: 'info' | 'success' | 'warning' | 'purple' | 'danger' | 'neutral'; border: string }
> = {
  PLANIFIE: { label: 'Planifié', badge: 'info', border: 'border-l-sky-500' },
  CONFIRME: { label: 'Confirmé', badge: 'success', border: 'border-l-success' },
  EN_ATTENTE: { label: 'En salle d’attente', badge: 'warning', border: 'border-l-warning' },
  EN_CONSULTATION: { label: 'En consultation', badge: 'purple', border: 'border-l-purple-500' },
  TERMINEE: { label: 'Soins terminés', badge: 'neutral', border: 'border-l-muted-foreground' },
  ANNULE: { label: 'Annulé', badge: 'danger', border: 'border-l-danger' },
  ABSENT: { label: 'Patient absent', badge: 'danger', border: 'border-l-danger' },
}

export function AgendaPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const cabinetActifId = useCabinetStore((s) => s.cabinetActifId)

  const [dateSelectionnee, setDateSelectionnee] = useState(
    () => new Date().toISOString().slice(0, 10),
  )
  const [praticienFiltreId, setPraticienFiltreId] = useState<string>('')

  // Modales
  const [modalRdvOpen, setModalRdvOpen] = useState(false)
  const [modalBlocageOpen, setModalBlocageOpen] = useState(false)

  // Praticiens
  const { data: resPraticiens } = useQuery({
    queryKey: ['praticiens-agenda', cabinetActifId],
    queryFn: () => praticiensApi.lister(cabinetActifId),
  })
  const praticiens = resPraticiens?.data ?? []

  // Données de l'agenda
  const { data: resAgenda, isLoading, refetch } = useQuery({
    queryKey: ['agenda-jour', dateSelectionnee, cabinetActifId, praticienFiltreId],
    queryFn: () =>
      rendezvousApi.obtenirAgenda(
        dateSelectionnee,
        cabinetActifId,
        praticienFiltreId || undefined,
      ),
  })

  const agenda = resAgenda?.data
  const rendezVous = agenda?.rendez_vous ?? []
  const indisponibilites = agenda?.indisponibilites_fauteuil ?? []

  const changerJour = (delta: number) => {
    const cur = new Date(dateSelectionnee)
    cur.setDate(cur.getDate() + delta)
    setDateSelectionnee(cur.toISOString().slice(0, 10))
  }

  const handleChangerStatut = async (rdvId: string, statut: StatutRdv) => {
    try {
      await rendezvousApi.changerStatut(rdvId, statut)
      toast.success(`Statut mis à jour : ${STATUT_STYLES[statut].label}`)
      void queryClient.invalidateQueries({ queryKey: ['agenda-jour'] })
    } catch {
      // Géré par le toast global
    }
  }

  const handleDemarrerConsultation = async (rdv: RendezVous) => {
    try {
      const res = await rendezvousApi.demarrerConsultation(rdv.id)
      toast.success('Consultation ouverte depuis le rendez-vous.')
      void queryClient.invalidateQueries({ queryKey: ['agenda-jour'] })
      if (res.data?.id) {
        navigate(`/consultations/${res.data.id}`)
      }
    } catch {
      // Géré par le toast global
    }
  }

  const handleDebloquerFauteuil = async (creneauId: string) => {
    try {
      await rendezvousApi.debloquerFauteuil(creneauId)
      toast.success('Fauteuil remis en service.')
      void queryClient.invalidateQueries({ queryKey: ['agenda-jour'] })
    } catch {
      // Géré par le toast global
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête de l'Agenda */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            Agenda & Planning des Soins
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gestion du flux de rendez-vous, occupation des fauteuils et appels en salle d'attente
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>

          <Can permission="AGENDA:UPDATE">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setModalBlocageOpen(true)}
              className="text-warning dark:text-warning"
            >
              <AlertTriangle className="h-4 w-4" />
              Bloquer fauteuil
            </Button>
          </Can>

          <Can permission="AGENDA:CREATE">
            <Button variant="primary" size="sm" onClick={() => setModalRdvOpen(true)}>
              <Plus className="h-4 w-4" />
              Nouveau RDV
            </Button>
          </Can>
        </div>
      </div>

      {/* Barre de navigation temporelle et filtres */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl border border-border bg-card p-4 shadow-xs">
        <div className="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-start">
          <Button variant="outline" size="icon" onClick={() => changerJour(-1)} title="Jour précédent">
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setDateSelectionnee(new Date().toISOString().slice(0, 10))}
          >
            Aujourd'hui
          </Button>

          <Button variant="outline" size="icon" onClick={() => changerJour(1)} title="Jour suivant">
            <ChevronRight className="h-4 w-4" />
          </Button>

          <div className="flex items-center gap-2 ml-2">
            <CalendarDays className="h-4 w-4 text-primary shrink-0" />
            <span className="font-bold text-sm sm:text-base text-foreground capitalize">
              {new Date(dateSelectionnee).toLocaleDateString('fr-FR', {
                weekday: 'long',
                day: 'numeric',
                month: 'long',
                year: 'numeric',
              })}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <input
            type="date"
            value={dateSelectionnee}
            onChange={(e) => setDateSelectionnee(e.target.value)}
            className="rounded-lg border border-input bg-card px-3 py-1.5 text-xs text-foreground"
          />

          <Select
            value={praticienFiltreId}
            onChange={(e) => setPraticienFiltreId(e.target.value)}
            className="h-9 text-xs min-w-[180px]"
          >
            <option value="">Tous les praticiens</option>
            {praticiens.map((p) => (
              <option key={p.id} value={p.id}>
                {p.titre ? `${p.titre} ` : 'Dr '}
                {p.nom_complet}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Zone du planning */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full rounded-2xl" />
          <Skeleton className="h-28 w-full rounded-2xl" />
          <Skeleton className="h-28 w-full rounded-2xl" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Section Fauteuils indisponibles si présents */}
          {indisponibilites.length > 0 && (
            <div className="rounded-xl border border-warning/30 bg-warning/5 p-4 space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-warning dark:text-warning flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4" />
                Fauteuils en maintenance ou indisponibles sur cette journée ({indisponibilites.length})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {indisponibilites.map((indispo) => (
                  <div
                    key={indispo.id}
                    className="flex items-center justify-between p-2.5 rounded-lg border border-warning/30 bg-card text-xs"
                  >
                    <div>
                      <span className="font-bold text-foreground">
                        {indispo.fauteuil_numero ?? 'Fauteuil'}
                      </span>
                      <span className="text-muted-foreground block font-mono text-[11px]">
                        {indispo.debut.slice(11, 16)} - {indispo.fin.slice(11, 16)} • {indispo.motif}
                      </span>
                    </div>
                    <Can permission="AGENDA:UPDATE">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleDebloquerFauteuil(indispo.id)}
                        className="text-xs text-warning hover:text-warning"
                      >
                        Libérer
                      </Button>
                    </Can>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Liste des rendez-vous de la journée */}
          {rendezVous.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border bg-card p-12 text-center space-y-3">
              <CalendarDays className="h-12 w-12 text-muted-foreground/40 mx-auto" />
              <h3 className="font-bold text-base text-foreground">Aucun rendez-vous sur cette journée</h3>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Le planning est libre pour le {formatDateFr(dateSelectionnee)}.
              </p>
              <Can permission="AGENDA:CREATE">
                <Button variant="primary" size="sm" onClick={() => setModalRdvOpen(true)}>
                  <Plus className="h-4 w-4" />
                  Prendre un rendez-vous
                </Button>
              </Can>
            </div>
          ) : (
            <div className="space-y-3">
              {rendezVous.map((rdv) => {
                const conf = STATUT_STYLES[rdv.statut]
                const heureDebut = rdv.debut.slice(11, 16)
                const heureFin = rdv.fin.slice(11, 16)

                return (
                  <div
                    key={rdv.id}
                    className={`rounded-xl border border-border bg-card p-4 shadow-2xs hover:shadow-xs transition-all border-l-4 ${conf.border}`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      {/* Horaires et Patient */}
                      <div className="flex items-start gap-4">
                        <div className="flex flex-col items-center justify-center rounded-xl bg-muted/60 px-3 py-2 text-center shrink-0 min-w-[75px]">
                          <span className="font-mono text-sm font-bold text-foreground">
                            {heureDebut}
                          </span>
                          <span className="text-[10px] text-muted-foreground font-mono">
                            {heureFin}
                          </span>
                          <span className="text-[9px] text-primary font-semibold mt-0.5">
                            {rdv.duree_minutes} min
                          </span>
                        </div>

                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h4 className="font-bold text-base text-foreground">
                              {rdv.patient_nom ?? 'Patient'}
                            </h4>
                            <Badge variant={conf.badge}>{conf.label}</Badge>
                            {rdv.hors_disponibilites && (
                              <Badge variant="warning" className="text-[10px]">
                                Hors plages
                              </Badge>
                            )}
                          </div>

                          <p className="text-xs font-medium text-foreground">{rdv.motif}</p>

                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground pt-0.5">
                            <span className="flex items-center gap-1">
                              <Stethoscope className="h-3.5 w-3.5 text-primary" />
                              {rdv.praticien_nom ?? 'Praticien'}
                            </span>
                            {rdv.fauteuil_nom && (
                              <span className="flex items-center gap-1 font-mono">
                                <Armchair className="h-3.5 w-3.5 text-primary" />
                                {rdv.fauteuil_nom}
                              </span>
                            )}
                            {rdv.notes && (
                              <span className="italic truncate max-w-xs">• {rdv.notes}</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Actions du cycle de vie */}
                      <div className="flex flex-wrap items-center gap-1.5 self-end md:self-center">
                        {rdv.statut === 'PLANIFIE' && (
                          <Can permission="AGENDA:UPDATE">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void handleChangerStatut(rdv.id, 'CONFIRME')}
                            >
                              <CheckCircle className="h-3.5 w-3.5 text-success" />
                              Confirmer
                            </Button>
                          </Can>
                        )}

                        {(rdv.statut === 'PLANIFIE' || rdv.statut === 'CONFIRME') && (
                          <Can permission="AGENDA:UPDATE">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void handleChangerStatut(rdv.id, 'EN_ATTENTE')}
                              className="text-warning dark:text-warning"
                            >
                              <Clock className="h-3.5 w-3.5" />
                              Salle d'attente
                            </Button>
                          </Can>
                        )}

                        {rdv.statut === 'EN_ATTENTE' && (
                          <Can permission="CONSULTATIONS:CREATE">
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => void handleDemarrerConsultation(rdv)}
                            >
                              <Play className="h-3.5 w-3.5" />
                              Ouvrir consultation
                            </Button>
                          </Can>
                        )}

                        {rdv.statut !== 'TERMINEE' && rdv.statut !== 'ANNULE' && rdv.statut !== 'ABSENT' && (
                          <Can permission="AGENDA:UPDATE">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleChangerStatut(rdv.id, 'ABSENT')}
                              className="text-xs text-muted-foreground hover:text-danger"
                            >
                              Absent
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleChangerStatut(rdv.id, 'ANNULE')}
                              className="text-xs text-muted-foreground hover:text-danger"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                            </Button>
                          </Can>
                        )}

                        {rdv.consultation_id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/consultations/${rdv.consultation_id}`)}
                          >
                            Voir consultation
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Modale Prise de RDV */}
      <RdvFormModal
        open={modalRdvOpen}
        onClose={() => setModalRdvOpen(false)}
        initialDate={dateSelectionnee}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['agenda-jour'] })
        }}
      />

      {/* Modale Blocage Fauteuil */}
      <BlocageFauteuilModal
        open={modalBlocageOpen}
        onClose={() => setModalBlocageOpen(false)}
        initialDate={dateSelectionnee}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['agenda-jour'] })
        }}
      />
    </div>
  )
}
