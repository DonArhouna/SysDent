import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Users,
  UserPlus,
  Search,
  Filter,
  Archive,
  RotateCcw,
  Pencil,
  Phone,
  FileText,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Pagination } from '@/components/ui/pagination'
import { Input } from '@/components/ui/input'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { StatusBadge } from '@/components/ui/status-badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Can } from '@/components/auth/can'
import { formatDateFr, calculerAge } from '@/lib/format'
import { toast } from '@/stores/toast-store'
import { patientsApi } from '../services/patients-api'
import { PatientFormModal } from '../components/patient-form-modal'
import { ArchiveDialog } from '../components/archive-dialog'
import type { Patient } from '../types'

export function PatientsListPage() {
  const queryClient = useQueryClient()

  // Paramètres de filtres et recherche
  const [recherche, setRecherche] = useState('')
  const [page, setPage] = useState(1)
  const [includeArchives, setIncludeArchives] = useState(false)
  const [filtreAvance, setFiltreAvance] = useState(false)
  const [nomFiltre, setNomFiltre] = useState('')
  const [telFiltre, setTelFiltre] = useState('')
  const [numFiltre, setNumFiltre] = useState('')

  // Modales
  const [modalFormOpen, setModalFormOpen] = useState(false)
  const [patientToEdit, setPatientToEdit] = useState<Patient | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<Patient | null>(null)

  const limit = 15

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [
      'patients',
      page,
      recherche,
      includeArchives,
      nomFiltre,
      telFiltre,
      numFiltre,
    ],
    queryFn: () =>
      patientsApi.lister({
        q: recherche.trim() || undefined,
        nom: nomFiltre.trim() || undefined,
        telephone: telFiltre.trim() || undefined,
        numero_dossier: numFiltre.trim() || undefined,
        include_archives: includeArchives,
        page,
        limit,
      }),
  })

  const patients = data?.items ?? []
  const meta = data?.meta

  const handleReactiver = async (patient: Patient) => {
    try {
      await patientsApi.reactiver(patient.id)
      toast.success(`Le dossier ${patient.numero_dossier} a été réactivé.`)
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
    } catch {
      // Géré par le toast global
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête */}
      <PageHeader
        titre="Dossiers Patients"
        sousTitre={
          meta
            ? `Gestion du fichier patient, consultations médicales, antécédents et coordonnées — ${meta.total_records} dossier${meta.total_records > 1 ? 's' : ''}`
            : 'Gestion du fichier patient, consultations médicales, antécédents et coordonnées'
        }
        onRefresh={() => void refetch()}
      >
        <Can permission="PATIENTS:CREATE">
          <Button
            variant="primary"
            onClick={() => {
              setPatientToEdit(null)
              setModalFormOpen(true)
            }}
          >
            <UserPlus className="h-4 w-4" />
            Nouveau patient
          </Button>
        </Can>
      </PageHeader>

      {/* Barre de recherche et filtres */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="search"
              placeholder="Rechercher par nom, prénom, N° dossier ou téléphone..."
              value={recherche}
              onChange={(e) => {
                setRecherche(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-lg border border-input bg-background pl-9 pr-4 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary transition-all placeholder:text-muted-foreground"
            />
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant={filtreAvance ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setFiltreAvance(!filtreAvance)}
            >
              <Filter className="h-4 w-4" />
              Filtres {filtreAvance && 'actifs'}
            </Button>

            <label className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs font-medium text-foreground cursor-pointer hover:bg-muted select-none">
              <input
                type="checkbox"
                checked={includeArchives}
                onChange={(e) => {
                  setIncludeArchives(e.target.checked)
                  setPage(1)
                }}
                className="rounded border-border text-primary focus:ring-primary"
              />
              <span>Inclure archivés</span>
            </label>
          </div>
        </div>

        {/* Filtres avancés dépliables */}
        {filtreAvance && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-border animate-in fade-in-50">
            <div>
              <Input
                placeholder="Filtrer par nom de famille"
                value={nomFiltre}
                onChange={(e) => {
                  setNomFiltre(e.target.value)
                  setPage(1)
                }}
                className="h-9 text-xs"
              />
            </div>
            <div>
              <Input
                placeholder="Filtrer par téléphone"
                value={telFiltre}
                onChange={(e) => {
                  setTelFiltre(e.target.value)
                  setPage(1)
                }}
                className="h-9 text-xs"
              />
            </div>
            <div>
              <Input
                placeholder="N° dossier exact (SYS-AAAAMMJJ-NNNN)"
                value={numFiltre}
                onChange={(e) => {
                  setNumFiltre(e.target.value)
                  setPage(1)
                }}
                className="h-9 text-xs"
              />
            </div>
          </div>
        )}
      </div>

      {/* Tableau des patients */}
      <div className="rounded-xl border border-border bg-card shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-sm text-danger">
            Impossible de charger la liste des patients. Veuillez vérifier la connexion au serveur.
          </div>
        ) : patients.length === 0 ? (
          <EmptyState
            icon={Users}
            titre="Aucun patient trouvé"
            description={
              recherche || nomFiltre || telFiltre
                ? 'Aucun résultat ne correspond à vos critères de recherche.'
                : 'Commencez par enregistrer un premier patient pour démarrer les dossiers cliniques.'
            }
          >
            <Can permission="PATIENTS:CREATE">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setPatientToEdit(null)
                  setModalFormOpen(true)
                }}
              >
                <UserPlus className="h-4 w-4" />
                Créer un dossier
              </Button>
            </Can>
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TRow>
                  <TH>N° Dossier</TH>
                  <TH>Patient</TH>
                  <TH>Âge / Sexe</TH>
                  <TH>Téléphone</TH>
                  <TH>Localisation</TH>
                  <TH>Statut</TH>
                  <TH className="text-right">Actions</TH>
                </TRow>
              </THead>
              <TBody>
                {patients.map((patient) => (
                  <TRow key={patient.id} className={patient.archive ? 'opacity-60 bg-muted/20' : ''}>
                    <TD className="whitespace-nowrap font-mono text-xs font-semibold text-primary">
                      <Link
                        to={`/patients/${patient.id}`}
                        className="hover:underline flex items-center gap-1.5"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        {patient.numero_dossier}
                      </Link>
                    </TD>
                    <TD>
                      <Link
                        to={`/patients/${patient.id}`}
                        className="font-semibold text-foreground hover:text-primary transition-colors block"
                      >
                        {patient.prenom} {patient.nom}
                      </Link>
                      {patient.profession && (
                        <span className="text-[11px] text-muted-foreground block truncate max-w-[180px]">
                          {patient.profession}
                        </span>
                      )}
                    </TD>
                    <TD className="text-xs">
                      <span className="font-medium text-foreground">
                        {calculerAge(patient.date_naissance)}
                      </span>
                      <span className="text-muted-foreground ml-1">
                        ({patient.sexe === 'F' ? 'Féminin' : 'Masculin'})
                      </span>
                      <span className="text-[11px] text-muted-foreground block">
                        Né(e) le {formatDateFr(patient.date_naissance)}
                      </span>
                    </TD>
                    <TD className="text-xs tabular-nums">
                      <div className="flex items-center gap-1.5 text-foreground font-medium">
                        <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                        {patient.telephone_1}
                      </div>
                      {patient.telephone_2 && (
                        <span className="text-[11px] text-muted-foreground block pl-5">
                          {patient.telephone_2}
                        </span>
                      )}
                    </TD>
                    <TD className="text-xs text-muted-foreground">
                      {patient.ville ?? '—'}
                    </TD>
                    <TD>
                      {patient.archive ? (
                        <StatusBadge tone="warning">Archivé</StatusBadge>
                      ) : (
                        <StatusBadge tone="success">Actif</StatusBadge>
                      )}
                    </TD>
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Link to={`/patients/${patient.id}`}>
                          <Button variant="ghost" size="sm" title="Ouvrir le dossier médical">
                            Consulter
                          </Button>
                        </Link>

                        <Can permission="PATIENTS:UPDATE">
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Modifier l'état civil"
                            onClick={() => {
                              setPatientToEdit(patient)
                              setModalFormOpen(true)
                            }}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>

                          {patient.archive ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Réactiver le dossier"
                              onClick={() => void handleReactiver(patient)}
                            >
                              <RotateCcw className="h-3.5 w-3.5 text-success" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Archiver le dossier"
                              onClick={() => setArchiveTarget(patient)}
                            >
                              <Archive className="h-3.5 w-3.5 text-muted-foreground hover:text-danger" />
                            </Button>
                          )}
                        </Can>
                      </div>
                    </TD>
                  </TRow>
                ))}
              </TBody>
            </Table>
          </div>
        )}

        <Pagination
          meta={meta}
          page={page}
          limit={limit}
          onPageChange={setPage}
          libelle="dossiers"
        />
      </div>

      {/* Modale de création / modification */}
      <PatientFormModal
        open={modalFormOpen}
        onClose={() => setModalFormOpen(false)}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['patients'] })
        }}
        patientToEdit={patientToEdit}
      />

      {/* Dialogue d'archivage */}
      <ArchiveDialog
        patient={archiveTarget}
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['patients'] })
        }}
      />
    </div>
  )
}
