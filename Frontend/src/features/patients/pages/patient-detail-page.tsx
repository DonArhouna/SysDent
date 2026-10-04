import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Calendar,
  Phone,
  Mail,
  MapPin,
  Pencil,
  Plus,
  RefreshCw,
  Stethoscope,
  WifiOff,
  ClipboardList,
  Pill,
  Receipt,
  Clock,
  HeartPulse,
  Baby,
  Activity,
  Flame,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'
import { StatusBadge } from '@/components/ui/status-badge'
import { EmptyState } from '@/components/ui/empty-state'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { Can } from '@/components/auth/can'
import { formatDateFr, formatDateTimeFr, calculerAge } from '@/lib/format'
import { toast } from '@/stores/toast-store'
import { patientsApi } from '../services/patients-api'
import { AlertesBanner } from '../components/alertes-banner'
import { PatientFormModal } from '../components/patient-form-modal'
import { AntecedentModal } from '../components/antecedent-modal'
import type { AntecedentMedical, EtatGeneral } from '../types'

export function PatientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState('synthese')
  const [modalEditOpen, setModalEditOpen] = useState(false)
  const [antecedentModalOpen, setAntecedentModalOpen] = useState(false)
  const [antecedentToEdit, setAntecedentToEdit] = useState<AntecedentMedical | null>(null)

  // Édition rapide État Général
  const [modeEditionEtat, setModeEditionEtat] = useState(false)
  const [etatForm, setEtatForm] = useState<Partial<EtatGeneral>>({})
  const [allergieSaisie, setAllergieSaisie] = useState('')
  const [allergieSeverite, setAllergieSeverite] = useState<'legere' | 'moderee' | 'grave'>('grave')
  const [loadingEtat, setLoadingEtat] = useState(false)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['patient-dossier', id],
    queryFn: () => patientsApi.obtenirDossierComplet(id!),
    enabled: Boolean(id),
  })

  const patient = data?.data

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    )
  }

  if (isError || !patient) {
    // Un échec réseau n'est pas un dossier supprimé : le dire explicitement,
    // sinon l'utilisateur croit à une perte de données.
    return (
      <div className="mx-auto max-w-lg rounded-xl2 border border-border bg-card shadow-float">
        <EmptyState
          icon={isError ? WifiOff : AlertCircle}
          titre={isError ? 'Dossier patient indisponible' : 'Dossier patient introuvable'}
          description={
            isError
              ? "Le dossier n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
              : "Le dossier demandé n'existe pas ou vous n'avez pas la permission d'y accéder."
          }
        >
          {isError ? (
            <Button variant="outline" onClick={() => void refetch()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          ) : (
            <Button variant="outline" onClick={() => navigate('/patients')}>
              <ArrowLeft className="h-4 w-4" />
              Retour à la liste des patients
            </Button>
          )}
        </EmptyState>
      </div>
    )
  }

  const initierEditionEtat = () => {
    setEtatForm({
      grossesse: patient.etat_general?.grossesse ?? false,
      grossesse_terme: patient.etat_general?.grossesse_terme ?? '',
      allaitement: patient.etat_general?.allaitement ?? false,
      diabete: patient.etat_general?.diabete ?? false,
      diabete_type: patient.etat_general?.diabete_type ?? '',
      hta: patient.etat_general?.hta ?? false,
      tabac: patient.etat_general?.tabac ?? false,
      alcool: patient.etat_general?.alcool ?? false,
      allergies: patient.etat_general?.allergies ? [...patient.etat_general.allergies] : [],
    })
    setModeEditionEtat(true)
  }

  const handleSaveEtatGeneral = async () => {
    try {
      setLoadingEtat(true)
      await patientsApi.enregistrerEtatGeneral(patient.id, etatForm)
      toast.success('État général du patient actualisé.')
      setModeEditionEtat(false)
      void queryClient.invalidateQueries({ queryKey: ['patient-dossier', id] })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingEtat(false)
    }
  }

  const ajouterAllergie = () => {
    if (!allergieSaisie.trim()) return
    const liste = etatForm.allergies ? [...etatForm.allergies] : []
    liste.push({
      substance: allergieSaisie.trim(),
      severite: allergieSeverite,
    })
    setEtatForm({ ...etatForm, allergies: liste })
    setAllergieSaisie('')
  }

  const supprimerAllergie = (index: number) => {
    const liste = etatForm.allergies ? [...etatForm.allergies] : []
    liste.splice(index, 1)
    setEtatForm({ ...etatForm, allergies: liste })
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête : identité du dossier + actions */}
      <PageHeader
        titre={
          <span className="flex flex-wrap items-center gap-2">
            {patient.prenom} {patient.nom}
            <StatusBadge tone={patient.archive ? 'warning' : 'success'}>
              {patient.archive ? 'Archivé' : 'Dossier actif'}
            </StatusBadge>
            {patient.groupe_sanguin && (
              <StatusBadge tone="purple" className="font-mono">
                Groupe {patient.groupe_sanguin}
              </StatusBadge>
            )}
          </span>
        }
        sousTitre={
          <>
            <span className="font-mono font-semibold text-primary">
              {patient.numero_dossier}
            </span>{' '}
            • {calculerAge(patient.date_naissance)} ans (
            {patient.sexe === 'F' ? 'Femme' : 'Homme'}) • Né(e) le{' '}
            {formatDateFr(patient.date_naissance)} •{' '}
            {patient.nb_consultations} consultation
            {patient.nb_consultations > 1 ? 's' : ''}
          </>
        }
        retour={{ to: '/patients', label: 'Retour aux dossiers' }}
        onRefresh={() => void refetch()}
      >
        <>
          <Can permission="PATIENTS:UPDATE">
            <Button variant="outline" size="sm" onClick={() => setModalEditOpen(true)}>
              <Pencil className="h-4 w-4" />
              Modifier identité
            </Button>
          </Can>

          <Can permission="CONSULTATIONS:CREATE">
            <Link to={`/consultations?nouveau=true&patient_id=${patient.id}`}>
              <Button variant="primary" size="sm">
                <Stethoscope className="h-4 w-4" />
                Démarrer consultation
              </Button>
            </Link>
          </Can>
        </>
      </PageHeader>

      {/* Bandeau d'alertes médicales en tête */}
      <AlertesBanner alertes={patient.alertes} />

      {/* Carte d'identité principale du patient */}
      <div className="rounded-xl2 border border-border bg-card p-6 shadow-float">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <span
              aria-hidden
              className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl3 bg-primary/10 text-xl font-black text-primary"
            >
              {patient.prenom[0]}
              {patient.nom[0]}
            </span>

            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Dossier patient
              </p>
              <p className="text-sm text-muted-foreground">
                {patient.ville ?? 'Dakar'}
                {patient.profession ? ` • ${patient.profession}` : ''}
              </p>
            </div>
          </div>

          {/* Coordonnées rapides */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs border-t md:border-t-0 md:border-l border-border pt-4 md:pt-0 md:pl-6">
            <div className="flex items-center gap-2 text-foreground font-medium">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <span>{patient.telephone_1}</span>
            </div>
            {patient.email ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Mail className="h-4 w-4" />
                <span className="truncate max-w-[180px]">{patient.email}</span>
              </div>
            ) : null}
            <div className="flex items-center gap-2 text-muted-foreground">
              <MapPin className="h-4 w-4" />
              <span>{patient.ville ?? 'Dakar'}</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Calendar className="h-4 w-4" />
              <span>
                {patient.nb_consultations} consultation{patient.nb_consultations > 1 ? 's' : ''}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Onglets de la Fiche Patient */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="synthese">Vue d'ensemble</TabsTrigger>
          <TabsTrigger
            value="etat-general"
            badge={patient.alertes.length > 0 ? patient.alertes.length : undefined}
          >
            État Général & Allergies
          </TabsTrigger>
          <TabsTrigger
            value="antecedents"
            badge={patient.antecedents.length > 0 ? patient.antecedents.length : undefined}
          >
            Antécédents Médicaux
          </TabsTrigger>
          <TabsTrigger value="odontogramme">Odontogramme</TabsTrigger>
          <TabsTrigger value="consultations" badge={patient.nb_consultations || undefined}>
            Consultations & Actes
          </TabsTrigger>
          <TabsTrigger value="ordonnances">Ordonnances</TabsTrigger>
          <TabsTrigger value="facturation">Factures & Devis</TabsTrigger>
        </TabsList>

        {/* ================= ONGLET 1 : SYNTHÈSE & IDENTITÉ ================= */}
        <TabsContent value="synthese" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Informations administratives */}
            <Card>
              <CardHeader>
                <CardTitle>Identité & Coordonnées</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs sm:text-sm">
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Nom complet</span>
                  <span className="font-semibold text-foreground">
                    {patient.prenom} {patient.nom}
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Date de naissance</span>
                  <span className="font-medium text-foreground">
                    {formatDateFr(patient.date_naissance)} ({calculerAge(patient.date_naissance)})
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Sexe</span>
                  <span className="font-medium text-foreground">
                    {patient.sexe === 'F' ? 'Féminin' : 'Masculin'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Téléphone principal</span>
                  <span className="font-semibold text-foreground">{patient.telephone_1}</span>
                </div>
                {patient.telephone_2 && (
                  <div className="flex justify-between py-1.5 border-b border-border">
                    <span className="text-muted-foreground">Téléphone secondaire</span>
                    <span className="font-medium text-foreground">{patient.telephone_2}</span>
                  </div>
                )}
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Email</span>
                  <span className="font-medium text-foreground">{patient.email ?? '—'}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Adresse</span>
                  <span className="font-medium text-foreground">
                    {patient.adresse ? `${patient.adresse}, ${patient.ville}` : patient.ville ?? '—'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Pièce d'identité</span>
                  <span className="font-medium text-foreground">
                    {patient.type_piece_identite
                      ? `${patient.type_piece_identite} : ${patient.numero_piece_identite ?? 'N/A'}`
                      : 'Non renseignée'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-muted-foreground">Profession</span>
                  <span className="font-medium text-foreground">
                    {patient.profession ? `${patient.profession} (${patient.employeur ?? '—'})` : '—'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-muted-foreground">Date de création du dossier</span>
                  <span className="font-medium text-foreground">
                    {formatDateFr(patient.created_at)}
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Synthèse Médicale */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Vigilances & Antécédents Actifs</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {patient.alertes.length === 0 ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground p-3 rounded-lg bg-muted/40">
                      <CheckCircle2 className="h-4 w-4 text-success" />
                      <span>Aucune contre-indication ni alerte majeure signalée.</span>
                    </div>
                  ) : (
                    <AlertesBanner alertes={patient.alertes} />
                  )}

                  <div className="pt-2 border-t border-border space-y-2">
                    <p className="text-xs font-semibold text-foreground">État général résumé :</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded-lg border border-border p-2 bg-card">
                        <span className="text-muted-foreground block text-[10px]">GROSSESSE</span>
                        <span className="font-semibold text-foreground">
                          {patient.etat_general?.grossesse ? 'Oui' : 'Non'}
                        </span>
                      </div>
                      <div className="rounded-lg border border-border p-2 bg-card">
                        <span className="text-muted-foreground block text-[10px]">DIABÈTE</span>
                        <span className="font-semibold text-foreground">
                          {patient.etat_general?.diabete ? 'Oui' : 'Non'}
                        </span>
                      </div>
                      <div className="rounded-lg border border-border p-2 bg-card">
                        <span className="text-muted-foreground block text-[10px]">HTA</span>
                        <span className="font-semibold text-foreground">
                          {patient.etat_general?.hta ? 'Oui' : 'Non'}
                        </span>
                      </div>
                      <div className="rounded-lg border border-border p-2 bg-card">
                        <span className="text-muted-foreground block text-[10px]">ALLERGIES</span>
                        <span className="font-semibold text-foreground">
                          {patient.etat_general?.allergies?.length ?? 0} déclarée(s)
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {patient.notes && (
                <Card>
                  <CardHeader>
                    <CardTitle>Notes cliniques & observations</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                      {patient.notes}
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </TabsContent>

        {/* ================= ONGLET 2 : ÉTAT GÉNÉRAL & ALLERGIES ================= */}
        <TabsContent value="etat-general" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>État Général du Patient</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Conformité RG02 : l'état général doit être vérifié à chaque consultation pour
                  sécuriser les anesthésies et ordonnances.
                </p>
              </div>

              {!modeEditionEtat ? (
                <Can permission="PATIENTS:UPDATE">
                  <Button variant="outline" size="sm" onClick={initierEditionEtat}>
                    <Pencil className="h-3.5 w-3.5" />
                    Modifier l'état général
                  </Button>
                </Can>
              ) : (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setModeEditionEtat(false)}
                    disabled={loadingEtat}
                  >
                    Annuler
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSaveEtatGeneral}
                    loading={loadingEtat}
                  >
                    Enregistrer
                  </Button>
                </div>
              )}
            </CardHeader>

            <CardContent className="space-y-6">
              {!modeEditionEtat ? (
                /* Mode Consultation */
                <div className="space-y-6">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="rounded-xl border border-border p-3 bg-muted/20">
                      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                        <Baby className="h-4 w-4 text-primary" />
                        Grossesse
                      </div>
                      <p className="mt-1 text-base font-bold text-foreground">
                        {patient.etat_general?.grossesse ? 'Enceinte' : 'Non'}
                      </p>
                      {patient.etat_general?.grossesse_terme && (
                        <p className="text-xs text-muted-foreground">
                          Terme : {patient.etat_general.grossesse_terme}
                        </p>
                      )}
                    </div>

                    <div className="rounded-xl border border-border p-3 bg-muted/20">
                      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                        <Activity className="h-4 w-4 text-primary" />
                        Diabète
                      </div>
                      <p className="mt-1 text-base font-bold text-foreground">
                        {patient.etat_general?.diabete ? 'Diabétique' : 'Non'}
                      </p>
                      {patient.etat_general?.diabete_type && (
                        <p className="text-xs text-muted-foreground">
                          Type : {patient.etat_general.diabete_type}
                        </p>
                      )}
                    </div>

                    <div className="rounded-xl border border-border p-3 bg-muted/20">
                      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                        <HeartPulse className="h-4 w-4 text-primary" />
                        Hypertension (HTA)
                      </div>
                      <p className="mt-1 text-base font-bold text-foreground">
                        {patient.etat_general?.hta ? 'Oui' : 'Non'}
                      </p>
                    </div>

                    <div className="rounded-xl border border-border p-3 bg-muted/20">
                      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                        <Clock className="h-4 w-4 text-primary" />
                        Dernier contrôle
                      </div>
                      <p className="mt-1 text-xs font-semibold text-foreground">
                        {patient.etat_general?.a_jour_le
                          ? formatDateTimeFr(patient.etat_general.a_jour_le)
                          : 'Non vérifié'}
                      </p>
                    </div>
                  </div>

                  {/* Liste des allergies */}
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                      <Flame className="h-3.5 w-3.5 text-danger" />
                      Allergies Médicamenteuses & Contact
                    </h4>
                    {patient.etat_general?.allergies && patient.etat_general.allergies.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                        {patient.etat_general.allergies.map((all, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between rounded-lg border border-danger/30 bg-danger/5 p-2.5 text-xs text-danger"
                          >
                            <div>
                              <span className="font-bold">{all.substance}</span>
                              {all.reaction && (
                                <span className="block text-[11px] text-muted-foreground">
                                  {all.reaction}
                                </span>
                              )}
                            </div>
                            <Badge variant={all.severite === 'grave' ? 'danger' : 'warning'}>
                              {all.severite}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">
                        Aucune allergie répertoriée dans le dossier.
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                /* Mode Édition */
                <div className="space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <label className="flex items-center gap-2 p-3 rounded-lg border border-border bg-card cursor-pointer">
                      <input
                        type="checkbox"
                        checked={etatForm.grossesse ?? false}
                        onChange={(e) => setEtatForm({ ...etatForm, grossesse: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-semibold text-foreground">Patiente Enceinte</span>
                    </label>

                    <label className="flex items-center gap-2 p-3 rounded-lg border border-border bg-card cursor-pointer">
                      <input
                        type="checkbox"
                        checked={etatForm.allaitement ?? false}
                        onChange={(e) => setEtatForm({ ...etatForm, allaitement: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-semibold text-foreground">Allaitement en cours</span>
                    </label>

                    <label className="flex items-center gap-2 p-3 rounded-lg border border-border bg-card cursor-pointer">
                      <input
                        type="checkbox"
                        checked={etatForm.diabete ?? false}
                        onChange={(e) => setEtatForm({ ...etatForm, diabete: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-semibold text-foreground">Diabète</span>
                    </label>

                    <label className="flex items-center gap-2 p-3 rounded-lg border border-border bg-card cursor-pointer">
                      <input
                        type="checkbox"
                        checked={etatForm.hta ?? false}
                        onChange={(e) => setEtatForm({ ...etatForm, hta: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-semibold text-foreground">Hypertension (HTA)</span>
                    </label>

                    <label className="flex items-center gap-2 p-3 rounded-lg border border-border bg-card cursor-pointer">
                      <input
                        type="checkbox"
                        checked={etatForm.tabac ?? false}
                        onChange={(e) => setEtatForm({ ...etatForm, tabac: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-semibold text-foreground">Tabagisme</span>
                    </label>

                    <label className="flex items-center gap-2 p-3 rounded-lg border border-border bg-card cursor-pointer">
                      <input
                        type="checkbox"
                        checked={etatForm.alcool ?? false}
                        onChange={(e) => setEtatForm({ ...etatForm, alcool: e.target.checked })}
                        className="rounded border-border text-primary focus:ring-primary"
                      />
                      <span className="text-xs font-semibold text-foreground">Consommation d'alcool</span>
                    </label>
                  </div>

                  {etatForm.grossesse && (
                    <div className="max-w-xs">
                      <label className="block text-xs font-semibold text-foreground mb-1">
                        Terme de la grossesse (ex: 28 SA / 6 mois)
                      </label>
                      <input
                        type="text"
                        value={etatForm.grossesse_terme ?? ''}
                        onChange={(e) => setEtatForm({ ...etatForm, grossesse_terme: e.target.value })}
                        className="w-full rounded-lg border border-input bg-card px-3 py-1.5 text-xs text-foreground"
                        placeholder="Ex: 32 SA"
                      />
                    </div>
                  )}

                  {/* Gestion dynamique des allergies */}
                  <div className="space-y-3 pt-3 border-t border-border">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
                      Allergies & Substances à proscrire
                    </h4>

                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="text"
                        placeholder="Substance (ex: Pénicilline, Latex, Iode...)"
                        value={allergieSaisie}
                        onChange={(e) => setAllergieSaisie(e.target.value)}
                        className="flex-1 min-w-[200px] rounded-lg border border-input bg-card px-3 py-1.5 text-xs text-foreground"
                      />
                      <select
                        value={allergieSeverite}
                        onChange={(e) => setAllergieSeverite(e.target.value as any)}
                        className="rounded-lg border border-input bg-card px-3 py-1.5 text-xs text-foreground"
                      >
                        <option value="grave">Grave (choc, œdème)</option>
                        <option value="moderee">Modérée (éruption)</option>
                        <option value="legere">Légère</option>
                      </select>
                      <Button type="button" variant="primary" size="sm" onClick={ajouterAllergie}>
                        <Plus className="h-3.5 w-3.5" />
                        Ajouter allergie
                      </Button>
                    </div>

                    <div className="space-y-1.5 pt-2">
                      {etatForm.allergies?.map((all, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-lg border border-border bg-muted/40 p-2 text-xs"
                        >
                          <span className="font-semibold text-danger">{all.substance}</span>
                          <div className="flex items-center gap-2">
                            <Badge variant={all.severite === 'grave' ? 'danger' : 'warning'}>
                              {all.severite}
                            </Badge>
                            <button
                              type="button"
                              onClick={() => supprimerAllergie(i)}
                              className="text-xs text-danger hover:underline"
                            >
                              Supprimer
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= ONGLET 3 : ANTÉCÉDENTS MÉDICAUX ================= */}
        <TabsContent value="antecedents" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Antécédents Médicaux & Chirurgicaux</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Historique médical opposable pour adapter les gestes et anesthésies (UC7)
                </p>
              </div>

              <Can permission="PATIENTS:UPDATE">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    setAntecedentToEdit(null)
                    setAntecedentModalOpen(true)
                  }}
                >
                  <Plus className="h-4 w-4" />
                  Ajouter un antécédent
                </Button>
              </Can>
            </CardHeader>

            <CardContent>
              {patient.antecedents.length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground">
                  Aucun antécédent médical enregistré sur ce dossier.
                </div>
              ) : (
                <div className="space-y-3">
                  {patient.antecedents.map((ant) => (
                    <div
                      key={ant.id}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 hover:border-primary/40 transition-colors"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-foreground">
                            {ant.description}
                          </span>
                          <Badge variant={ant.en_cours ? 'warning' : 'neutral'}>
                            {ant.en_cours ? 'En cours' : 'Passé / Guéri'}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            {ant.type_antecedent}
                          </Badge>
                        </div>

                        {ant.traitement_associe && (
                          <p className="text-xs text-muted-foreground">
                            Traitement associé : <strong className="text-foreground">{ant.traitement_associe}</strong>
                          </p>
                        )}

                        {ant.notes && (
                          <p className="text-xs text-muted-foreground italic">
                            {ant.notes}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center">
                        {ant.date_survenue && (
                          <span className="text-xs text-muted-foreground">
                            Depuis : {formatDateFr(ant.date_survenue)}
                          </span>
                        )}
                        <Can permission="PATIENTS:UPDATE">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setAntecedentToEdit(ant)
                              setAntecedentModalOpen(true)
                            }}
                          >
                            Modifier
                          </Button>
                        </Can>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= ONGLET 4 : ODONTOGRAMME ================= */}
        <TabsContent value="odontogramme">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Schéma Dentaire & Odontogramme</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Numérotation FDI 32 dents adultes + 20 dents de lait, 5 faces et état par dent
                </p>
              </div>
              <Link to={`/odontogramme?patient_id=${patient.id}`}>
                <Button variant="primary" size="sm">
                  <ClipboardList className="h-4 w-4" />
                  Plein écran Odontogramme
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              <div className="p-8 text-center text-xs text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border">
                <ClipboardList className="h-10 w-10 text-primary mx-auto mb-2 opacity-80" />
                <p className="font-semibold text-foreground text-sm">
                  Accès direct au module Odontogramme interactif
                </p>
                <p className="mt-1 max-w-md mx-auto">
                  Consultez et modifiez les 32 dents, l'historique chronologique et le charting parodontal de{' '}
                  {patient.prenom} {patient.nom}.
                </p>
                <Link to={`/odontogramme?patient_id=${patient.id}`}>
                  <Button variant="outline" size="sm" className="mt-4">
                    Ouvrir l'Odontogramme du patient
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= ONGLET 5 : CONSULTATIONS ================= */}
        <TabsContent value="consultations">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Historique des Consultations & Actes</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Examens cliniques, diagnostics CIM-10 et actes réalisés
                </p>
              </div>
              <Can permission="CONSULTATIONS:CREATE">
                <Link to={`/consultations?nouveau=true&patient_id=${patient.id}`}>
                  <Button variant="primary" size="sm">
                    <Plus className="h-4 w-4" />
                    Nouvelle consultation
                  </Button>
                </Link>
              </Can>
            </CardHeader>
            <CardContent>
              <div className="p-6 text-center text-xs text-muted-foreground">
                <Stethoscope className="h-8 w-8 text-muted-foreground/60 mx-auto mb-2" />
                <p className="font-medium text-foreground">
                  {patient.nb_consultations} consultation(s) enregistrée(s)
                </p>
                <Link to={`/consultations?patient_id=${patient.id}`}>
                  <Button variant="outline" size="sm" className="mt-3">
                    Voir les consultations de ce patient
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= ONGLET 6 : ORDONNANCES ================= */}
        <TabsContent value="ordonnances">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Prescriptions & Ordonnances</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Ordonnances émises, signées et contrôlées contre les interactions
                </p>
              </div>
              <Link to={`/ordonnances?patient_id=${patient.id}`}>
                <Button variant="outline" size="sm">
                  <Pill className="h-4 w-4" />
                  Voir toutes les ordonnances
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              <div className="p-6 text-center text-xs text-muted-foreground">
                <Pill className="h-8 w-8 text-muted-foreground/60 mx-auto mb-2" />
                <p className="font-medium text-foreground">Ordonnances du patient</p>
                <Link to={`/ordonnances?patient_id=${patient.id}`}>
                  <Button variant="outline" size="sm" className="mt-3">
                    Consulter l'historique médicamenteux
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ================= ONGLET 7 : FACTURATION ================= */}
        <TabsContent value="facturation">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Factures, Devis & Règlements</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Historique financier, devis acceptés et encaissements caisse
                </p>
              </div>
              <Link to={`/factures?patient_id=${patient.id}`}>
                <Button variant="outline" size="sm">
                  <Receipt className="h-4 w-4" />
                  Voir les factures
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              <div className="p-6 text-center text-xs text-muted-foreground">
                <Receipt className="h-8 w-8 text-muted-foreground/60 mx-auto mb-2" />
                <p className="font-medium text-foreground">Compte financier du patient</p>
                <div className="flex justify-center gap-2 mt-3">
                  <Link to={`/factures?patient_id=${patient.id}`}>
                    <Button variant="outline" size="sm">
                      Factures
                    </Button>
                  </Link>
                  <Link to={`/devis?patient_id=${patient.id}`}>
                    <Button variant="outline" size="sm">
                      Devis
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Modale d'édition administrative */}
      <PatientFormModal
        open={modalEditOpen}
        onClose={() => setModalEditOpen(false)}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['patient-dossier', id] })
        }}
        patientToEdit={patient}
      />

      {/* Modale d'antécédent */}
      <AntecedentModal
        patientId={patient.id}
        open={antecedentModalOpen}
        onClose={() => {
          setAntecedentModalOpen(false)
          setAntecedentToEdit(null)
        }}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['patient-dossier', id] })
        }}
        antecedentToEdit={antecedentToEdit}
      />
    </div>
  )
}
