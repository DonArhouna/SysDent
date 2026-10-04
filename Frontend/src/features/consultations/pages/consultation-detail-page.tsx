import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Stethoscope,
  CheckCircle2,
  FileQuestion,
  RefreshCw,
  WifiOff,
  AlertTriangle,
  Plus,
  Trash2,
  FileText,
  Pill,
  Receipt,
  Save,
  ClipboardList,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { StatusBadge } from '@/components/ui/status-badge'
import { EmptyState } from '@/components/ui/empty-state'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { Modal } from '@/components/ui/modal'
import { Skeleton } from '@/components/ui/skeleton'
import { Can } from '@/components/auth/can'
import { formatFcfa, formatDateTimeFr } from '@/lib/format'
import { toast } from '@/stores/toast-store'
import { consultationsApi } from '../services/consultations-api'
import type { ActeNomenclature } from '../types'

export function ConsultationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Formulaire examen et diagnostic
  const [anamnese, setAnamnese] = useState('')
  const [examenExo, setExamenExo] = useState('')
  const [examenEndo, setExamenEndo] = useState('')
  const [diagnosticPrincipal, setDiagnosticPrincipal] = useState('')
  const [codesCim10, setCodesCim10] = useState('')
  const [planTraitement, setPlanTraitement] = useState('')
  const [recommandations, setRecommandations] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)

  // Modale Ajout d'Acte
  const [modalActeOpen, setModalActeOpen] = useState(false)
  const [nomenclature, setNomenclature] = useState<ActeNomenclature[]>([])
  const [acteSelectionneId, setActeSelectionneId] = useState('')
  const [dentNumero, setDentNumero] = useState('')
  const [quantite, setQuantite] = useState(1)
  const [notesActe, setNotesActe] = useState('')
  const [loadingActe, setLoadingActe] = useState(false)

  // Modale Clôture
  const [modalTerminerOpen, setModalTerminerOpen] = useState(false)
  const [loadingTerminer, setLoadingTerminer] = useState(false)

  const { data: resDetail, isLoading, isError, refetch } = useQuery({
    queryKey: ['consultation-detail', id],
    queryFn: () => consultationsApi.obtenirDetail(id!),
    enabled: Boolean(id),
  })

  const consultation = resDetail?.data

  useEffect(() => {
    if (consultation) {
      setAnamnese(consultation.anamnese ?? '')
      setExamenExo(consultation.examen_exobuccal ?? '')
      setExamenEndo(consultation.examen_endobuccal ?? '')
      setDiagnosticPrincipal(consultation.diagnostic_principal ?? '')
      setCodesCim10(consultation.codes_cim10?.join(', ') ?? '')
      setPlanTraitement(consultation.plan_traitement ?? '')
      setRecommandations(consultation.recommandations ?? '')
    }
  }, [consultation])

  const ouvrirModalActe = () => {
    void consultationsApi.listerNomenclature().then((res) => {
      const liste = res.items ?? []
      setNomenclature(liste)
      if (liste.length > 0 && !acteSelectionneId) {
        setActeSelectionneId(liste[0].id)
      }
    })
    setModalActeOpen(true)
  }

  const handleSaveNotes = async () => {
    if (!id) return
    try {
      setSavingNotes(true)
      await consultationsApi.mettreAJour(id, {
        anamnese: anamnese.trim() || undefined,
        examen_exobuccal: examenExo.trim() || undefined,
        examen_endobuccal: examenEndo.trim() || undefined,
        diagnostic_principal: diagnosticPrincipal.trim() || undefined,
        codes_cim10: codesCim10
          ? codesCim10.split(',').map((s) => s.trim()).filter(Boolean)
          : undefined,
        plan_traitement: planTraitement.trim() || undefined,
        recommandations: recommandations.trim() || undefined,
      })
      toast.success('Examen clinique et diagnostic sauvegardés.')
      void queryClient.invalidateQueries({ queryKey: ['consultation-detail', id] })
    } catch {
      // Géré par le toast global
    } finally {
      setSavingNotes(false)
    }
  }

  const handleAjouterActe = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id || !acteSelectionneId) return
    try {
      setLoadingActe(true)
      await consultationsApi.ajouterActe(id, {
        acte_id: acteSelectionneId,
        dent_numero: dentNumero ? parseInt(dentNumero, 10) : undefined,
        quantite,
        notes: notesActe.trim() || undefined,
      })
      toast.success('Acte enregistré sur la consultation.')
      setModalActeOpen(false)
      setDentNumero('')
      setNotesActe('')
      void queryClient.invalidateQueries({ queryKey: ['consultation-detail', id] })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingActe(false)
    }
  }

  const handleDeleteActe = async (acteId: string) => {
    try {
      await consultationsApi.supprimerActe(acteId, 'Supprimé par le praticien')
      toast.info('Acte supprimé de la consultation.')
      void queryClient.invalidateQueries({ queryKey: ['consultation-detail', id] })
    } catch {
      // Géré par le toast global
    }
  }

  const handleTerminerConsultation = async () => {
    if (!id) return
    if (!diagnosticPrincipal.trim()) {
      toast.error('Un diagnostic principal est obligatoire pour clôturer la consultation (RG06).')
      return
    }

    try {
      setLoadingTerminer(true)
      await consultationsApi.terminer(id, {
        diagnostic_principal: diagnosticPrincipal.trim(),
        plan_traitement: planTraitement.trim() || undefined,
        recommandations: recommandations.trim() || undefined,
      })
      toast.success('Consultation terminée. Total facturable figé.')
      setModalTerminerOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['consultation-detail', id] })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingTerminer(false)
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    )
  }

  // Un échec réseau n'est pas une consultation absente : distinguer les deux,
  // sinon l'utilisateur croit à une suppression alors que c'est un incident.
  if (isError || !consultation) {
    return (
      <div className="mx-auto max-w-lg rounded-xl2 border border-border bg-card shadow-float">
        <EmptyState
          icon={isError ? WifiOff : FileQuestion}
          titre={isError ? 'Consultation indisponible' : 'Consultation introuvable'}
          description={
            isError
              ? "La consultation n'a pas pu être chargée. Vérifiez que le backend est démarré puis réessayez."
              : "Cette consultation n'existe plus ou n'a jamais existé."
          }
        >
          {isError ? (
            <Button variant="outline" onClick={() => void refetch()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          ) : (
            <Button variant="outline" onClick={() => navigate('/consultations')}>
              Retour à la liste
            </Button>
          )}
        </EmptyState>
      </div>
    )
  }

  const estTerminee = consultation.statut === 'TERMINEE'
  const estAnnulee = consultation.statut === 'ANNULEE'

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête */}
      <PageHeader
        titre={
          <span className="flex flex-wrap items-center gap-2">
            Consultation Clinique
            <StatusBadge
              tone={estTerminee ? 'success' : estAnnulee ? 'danger' : 'purple'}
            >
              {consultation.statut}
            </StatusBadge>
          </span>
        }
        sousTitre={
          <>
            Motif :{' '}
            <strong className="text-foreground">{consultation.motif}</strong> • Date :{' '}
            {formatDateTimeFr(consultation.date_consultation)}
          </>
        }
        retour={{ to: '/consultations', label: 'Retour à la liste' }}
      >
        {/* Actions principales */}
        <>
          {consultation.patient_id && (
            <Link to={`/odontogramme?patient_id=${consultation.patient_id}`}>
              <Button variant="outline" size="sm">
                <ClipboardList className="h-4 w-4" />
                Odontogramme
              </Button>
            </Link>
          )}

          {consultation.patient_id && (
            <Link
              to={`/ordonnances?consultation_id=${consultation.id}&patient_id=${consultation.patient_id}`}
            >
              <Button variant="outline" size="sm">
                <Pill className="h-4 w-4" />
                Prescrire
              </Button>
            </Link>
          )}

          {estTerminee && (
            <Can permission="FACTURATION:CREATE">
              <Link to={`/factures?consultation_id=${consultation.id}&creer=true`}>
                <Button variant="primary" size="sm" className="bg-success hover:bg-success/90">
                  <Receipt className="h-4 w-4" />
                  Facturer la consultation
                </Button>
              </Link>
            </Can>
          )}

          {!estTerminee && !estAnnulee && (
            <Can permission="CONSULTATIONS:UPDATE">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setModalTerminerOpen(true)}
              >
                <CheckCircle2 className="h-4 w-4" />
                Clôturer la séance
              </Button>
            </Can>
          )}
        </>
      </PageHeader>

      {/* Rappel RG02 si l'état général doit être vérifié */}
      {consultation.etat_general_a_verifier && (
        <div className="flex items-center justify-between p-3.5 rounded-xl border border-warning/40 bg-warning/10 text-xs text-warning-foreground">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-warning shrink-0" />
            <span>
              <strong>Vigilance RG02 :</strong> L'état général du patient n'a pas été contrôlé récemment. Vérifiez les allergies et antécédents avant d'anesthésier.
            </span>
          </div>
          {consultation.patient_id && (
            <Link to={`/patients/${consultation.patient_id}`}>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                Vérifier le dossier
              </Button>
            </Link>
          )}
        </div>
      )}

      {/* Contenu en 2 colonnes */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Colonne gauche : Examen Clinique & Diagnostic */}
        <div className="lg:col-span-7 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Stethoscope className="h-4 w-4 text-primary" />
                Examen & Diagnostic Médical
              </CardTitle>
              {!estTerminee && !estAnnulee && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSaveNotes}
                  loading={savingNotes}
                >
                  <Save className="h-3.5 w-3.5" />
                  Sauvegarder notes
                </Button>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="anamnese">Anamnèse & Motif détaillé</Label>
                <Textarea
                  id="anamnese"
                  value={anamnese}
                  onChange={(e) => setAnamnese(e.target.value)}
                  placeholder="Histoire de la maladie, évolution des douleurs, prise d'antalgiques..."
                  rows={2}
                  disabled={estTerminee}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="examen-exo">Examen Exobuccal</Label>
                  <Textarea
                    id="examen-exo"
                    value={examenExo}
                    onChange={(e) => setExamenExo(e.target.value)}
                    placeholder="Palpation ganglionnaire, ATM, asymétrie faciale..."
                    rows={2}
                    disabled={estTerminee}
                  />
                </div>
                <div>
                  <Label htmlFor="examen-endo">Examen Endobuccal</Label>
                  <Textarea
                    id="examen-endo"
                    value={examenEndo}
                    onChange={(e) => setExamenEndo(e.target.value)}
                    placeholder="Muqueuses, hygiène buccale, tartre, occlusion..."
                    rows={2}
                    disabled={estTerminee}
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-border">
                <Label htmlFor="diag-principal" required>
                  Diagnostic Principal (Obligatoire pour clôturer)
                </Label>
                <Input
                  id="diag-principal"
                  value={diagnosticPrincipal}
                  onChange={(e) => setDiagnosticPrincipal(e.target.value)}
                  placeholder="Ex: Pulpite aiguë sur dent 36, Carie dentinaire profonde..."
                  disabled={estTerminee}
                  required
                />
              </div>

              <div>
                <Label htmlFor="cim-10">Codes CIM-10 (séparés par virgules)</Label>
                <Input
                  id="cim-10"
                  value={codesCim10}
                  onChange={(e) => setCodesCim10(e.target.value)}
                  placeholder="Ex: K02.1 (Carie dentinaire), K04.0 (Pulpite)"
                  disabled={estTerminee}
                />
              </div>

              <div className="pt-2 border-t border-border">
                <Label htmlFor="plan-t">Plan de Traitement Proposé</Label>
                <Textarea
                  id="plan-t"
                  value={planTraitement}
                  onChange={(e) => setPlanTraitement(e.target.value)}
                  placeholder="Étapes thérapeutiques futures, devis à établir..."
                  rows={2}
                  disabled={estTerminee}
                />
              </div>

              <div>
                <Label htmlFor="recommandations">Recommandations & Consignes Patient</Label>
                <Textarea
                  id="recommandations"
                  value={recommandations}
                  onChange={(e) => setRecommandations(e.target.value)}
                  placeholder="Bains de bouche, alimentation tiède, rappel post-opératoire..."
                  rows={2}
                  disabled={estTerminee}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Colonne droite : Actes Réalisés & Total facturable */}
        <div className="lg:col-span-5 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  Actes Réalisés ({consultation.actes?.length ?? 0})
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Tarification automatique selon nomenclature cabinet
                </p>
              </div>

              {!estTerminee && !estAnnulee && (
                <Can permission="CONSULTATIONS:UPDATE">
                  <Button variant="primary" size="sm" onClick={ouvrirModalActe}>
                    <Plus className="h-3.5 w-3.5" />
                    Saisir un acte
                  </Button>
                </Can>
              )}
            </CardHeader>

            <CardContent className="space-y-4">
              {consultation.actes?.length === 0 ? (
                <div className="text-center py-8 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                  Aucun acte dentaire saisi sur cette consultation.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <THead>
                      <TRow>
                        <TH>Acte</TH>
                        <TH>Dent</TH>
                        <TH className="text-right">Montant</TH>
                        {!estTerminee && <TH className="w-8"></TH>}
                      </TRow>
                    </THead>
                    <TBody>
                      {consultation.actes?.map((acte) => (
                        <TRow key={acte.id}>
                          <TD className="text-xs">
                            <span className="font-semibold text-foreground block">
                              {acte.libelle_acte}
                            </span>
                            <span className="font-mono text-[10px] text-muted-foreground">
                              {acte.code_acte} • Qte: {acte.quantite}
                            </span>
                          </TD>
                          <TD className="text-xs font-mono">
                            {acte.dent_numero ? `Dent ${acte.dent_numero}` : '—'}
                          </TD>
                          <TD className="text-right text-xs font-bold tabular-nums">
                            {formatFcfa(Number(acte.montant))}
                          </TD>
                          {!estTerminee && (
                            <TD className="text-right">
                              <Can permission="CONSULTATIONS:UPDATE">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => void handleDeleteActe(acte.id)}
                                  title="Supprimer l'acte"
                                >
                                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-danger" />
                                </Button>
                              </Can>
                            </TD>
                          )}
                        </TRow>
                      ))}
                    </TBody>
                  </Table>
                </div>
              )}

              {/* Bloc Total Facturable */}
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Total Facturable
                  </span>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Importé automatiquement lors de la facturation (RG07)
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-xl font-black text-primary tabular-nums">
                    {formatFcfa(Number(consultation.total_actes))}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Modale Saisie d'Acte */}
      <Modal
        open={modalActeOpen}
        onClose={() => setModalActeOpen(false)}
        title="Ajouter un acte réalisé"
        maxWidth="md"
      >
        <form onSubmit={handleAjouterActe} className="space-y-4 pt-2">
          <div>
            <Label htmlFor="nomenclature-select" required>
              Acte de la nomenclature
            </Label>
            <Select
              id="nomenclature-select"
              value={acteSelectionneId}
              onChange={(e) => setActeSelectionneId(e.target.value)}
              required
            >
              {nomenclature.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.code} - {n.libelle} ({formatFcfa(Number(n.tarif_base))})
                </option>
              ))}
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="dent-num">Numéro de dent (FDI)</Label>
              <Input
                id="dent-num"
                type="number"
                value={dentNumero}
                onChange={(e) => setDentNumero(e.target.value)}
                placeholder="Ex: 11, 26, 47..."
              />
            </div>

            <div>
              <Label htmlFor="acte-qte" required>
                Quantité
              </Label>
              <Input
                id="acte-qte"
                type="number"
                min="1"
                max="32"
                value={quantite}
                onChange={(e) => setQuantite(parseInt(e.target.value, 10) || 1)}
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="acte-notes">Notes / Précisions</Label>
            <Input
              id="acte-notes"
              value={notesActe}
              onChange={(e) => setNotesActe(e.target.value)}
              placeholder="Matériau utilisé, anesthésie..."
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalActeOpen(false)}
              disabled={loadingActe}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" loading={loadingActe}>
              Enregistrer l'acte
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modale Clôture de Consultation */}
      <Modal
        open={modalTerminerOpen}
        onClose={() => setModalTerminerOpen(false)}
        title="Clôturer la consultation"
        maxWidth="md"
      >
        <div className="space-y-4 pt-2">
          <p className="text-xs sm:text-sm text-muted-foreground">
            La clôture verrouille les actes réalisés et fige le total facturable. Le diagnostic
            principal doit être validé.
          </p>

          <div>
            <Label htmlFor="diag-cloture" required>
              Confirmer le Diagnostic Principal
            </Label>
            <Input
              id="diag-cloture"
              value={diagnosticPrincipal}
              onChange={(e) => setDiagnosticPrincipal(e.target.value)}
              placeholder="Diagnostic final..."
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalTerminerOpen(false)}
              disabled={loadingTerminer}
            >
              Annuler
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleTerminerConsultation}
              loading={loadingTerminer}
            >
              Confirmer la clôture
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
