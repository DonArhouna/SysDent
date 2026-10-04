import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ClipboardList,
  User,
  Plus,
  RefreshCw,
  WifiOff,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { Input, Label } from '@/components/ui/input'
import { Modal } from '@/components/ui/modal'
import { toast } from '@/stores/toast-store'
import { patientsApi } from '@/features/patients/services/patients-api'
import { odontogrammeApi } from '../services/odontogramme-api'
import { OdontogrammeSvg } from '../components/odontogramme-svg'
import { DentDrawer } from '../components/dent-drawer'
import type { DentOdontogramme, TypeOdontogramme } from '../types'
import type { Patient } from '@/features/patients/types'

export function OdontogrammePage() {
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const patientIdParam = searchParams.get('patient_id')
  const [patientSelectionne, setPatientSelectionne] = useState<Patient | null>(null)
  const [recherchePatient, setRecherchePatient] = useState('')
  const [patientsTrouves, setPatientsTrouves] = useState<Patient[]>([])

  const [typeOdontogramme, setTypeOdontogramme] = useState<TypeOdontogramme>('ADULTE')
  const [dentSelectionnee, setDentSelectionnee] = useState<DentOdontogramme | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Charting parodontal
  const [modalChartingOpen, setModalChartingOpen] = useState(false)
  const [dentCharting, setDentCharting] = useState('11')
  const [sondageMV, setSondageMV] = useState('2')
  const [sondageV, setSondageV] = useState('2')
  const [sondageDV, setSondageDV] = useState('2')
  const [sondageML, setSondageML] = useState('2')
  const [sondageL, setSondageL] = useState('2')
  const [sondageDL, setSondageDL] = useState('2')
  const [saignement, setSaignement] = useState(false)
  const [recession, setRecession] = useState('0')
  const [loadingCharting, setLoadingCharting] = useState(false)

  // 1. Référentiel des couleurs et états officiels
  const { data: resRef } = useQuery({
    queryKey: ['odontogramme-referentiel'],
    queryFn: () => odontogrammeApi.obtenirReferentiel(),
  })
  const referentiel = resRef?.data?.etats ?? []

  // 2. Préchargement du patient si paramètre URL
  useEffect(() => {
    if (patientIdParam) {
      void patientsApi.obtenir(patientIdParam).then((res) => {
        setPatientSelectionne(res.data)
      })
    }
  }, [patientIdParam])

  // Recherche patient dynamique
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

  // 3. Odontogramme du patient actif
  const {
    data: resOdonto,
    isLoading: loadingOdonto,
    isError: erreurOdonto,
    refetch,
  } = useQuery({
    queryKey: ['odontogramme-patient', patientSelectionne?.id],
    queryFn: () => odontogrammeApi.obtenir(patientSelectionne!.id),
    enabled: Boolean(patientSelectionne?.id),
  })

  // 4. Chartings parodontaux
  const { data: resChartings } = useQuery({
    queryKey: ['chartings-patient', patientSelectionne?.id],
    queryFn: () => odontogrammeApi.listerChartings(patientSelectionne!.id),
    enabled: Boolean(patientSelectionne?.id),
  })

  const odontogramme = resOdonto?.data
  const dents = odontogramme?.dents ?? []
  const chartings = resChartings?.data ?? []

  const handleEnregistrerCharting = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!patientSelectionne) return
    try {
      setLoadingCharting(true)
      await odontogrammeApi.enregistrerCharting(patientSelectionne.id, {
        numero_fdi: parseInt(dentCharting, 10),
        sondage_mesio_vestibulaire: parseInt(sondageMV, 10),
        sondage_vestibulaire: parseInt(sondageV, 10),
        sondage_disto_vestibulaire: parseInt(sondageDV, 10),
        sondage_mesio_lingual: parseInt(sondageML, 10),
        sondage_lingual: parseInt(sondageL, 10),
        sondage_disto_lingual: parseInt(sondageDL, 10),
        recession_gingivale: parseInt(recession, 10),
        saignement_sondage: saignement,
      })
      toast.success('Relevé parodontal enregistré.')
      setModalChartingOpen(false)
      void queryClient.invalidateQueries({
        queryKey: ['chartings-patient', patientSelectionne.id],
      })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingCharting(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête */}
      <PageHeader
        titre={
          <span className="flex items-center gap-2">
            <ClipboardList className="h-7 w-7 text-primary" aria-hidden />
            Odontogramme &amp; Charting Parodontal
          </span>
        }
        sousTitre={
          patientSelectionne
            ? `${patientSelectionne.prenom} ${patientSelectionne.nom} — cartographie dentaire vectorielle FDI interactive (32 dents adultes & 20 temporaires)`
            : 'Cartographie dentaire vectorielle FDI interactive (32 dents adultes & 20 temporaires)'
        }
        retour={
          patientSelectionne
            ? { to: `/patients/${patientSelectionne.id}`, label: 'Retour au dossier patient' }
            : undefined
        }
        onRefresh={patientSelectionne ? () => void refetch() : undefined}
        libelleRefresh="Actualiser le schéma"
      />

      {/* Sélecteur de patient si non défini */}
      {!patientSelectionne ? (
        <Card className="p-8 text-center space-y-4 max-w-xl mx-auto">
          <User className="h-12 w-12 text-primary/60 mx-auto" />
          <h3 className="font-bold text-lg text-foreground">Sélectionnez un patient</h3>
          <p className="text-xs text-muted-foreground">
            Veuillez choisir un patient pour ouvrir son schéma dentaire ou explorer l'historique de ses soins.
          </p>

          <div className="relative text-left">
            <Input
              placeholder="Rechercher par nom, prénom ou N° de dossier..."
              value={recherchePatient}
              onChange={(e) => setRecherchePatient(e.target.value)}
            />
            {patientsTrouves.length > 0 && (
              <div className="absolute top-full left-0 right-0 z-30 mt-1 max-h-48 overflow-y-auto rounded-xl border border-border bg-card p-1 shadow-xl">
                {patientsTrouves.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setPatientSelectionne(p)
                      setRecherchePatient('')
                      setPatientsTrouves([])
                    }}
                    className="flex w-full items-center justify-between p-2.5 rounded-lg text-left text-xs hover:bg-muted transition-colors"
                  >
                    <span className="font-semibold text-foreground">
                      {p.prenom} {p.nom}
                    </span>
                    <span className="font-mono text-muted-foreground">{p.numero_dossier}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Bandeau d'identité patient + Bascule Adulte/Enfant */}
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl border border-border bg-card shadow-xs">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary font-bold">
                {patientSelectionne.prenom[0]}
                {patientSelectionne.nom[0]}
              </div>
              <div>
                <h3 className="font-bold text-base text-foreground">
                  {patientSelectionne.prenom} {patientSelectionne.nom}
                </h3>
                <p className="text-xs text-muted-foreground font-mono">
                  Dossier : {patientSelectionne.numero_dossier}
                </p>
              </div>
            </div>

            {/* Bascule Adulte / Enfant */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-muted-foreground">Denture :</span>
              <div className="inline-flex rounded-xl border border-border bg-muted/40 p-1">
                <button
                  type="button"
                  onClick={() => setTypeOdontogramme('ADULTE')}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    typeOdontogramme === 'ADULTE'
                      ? 'bg-card text-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Adulte (32 dents)
                </button>
                <button
                  type="button"
                  onClick={() => setTypeOdontogramme('ENFANT')}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    typeOdontogramme === 'ENFANT'
                      ? 'bg-card text-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Enfant (20 dents)
                </button>
              </div>
            </div>
          </div>

          {/* Synthèse des dents */}
          {odontogramme && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              <div className="p-3 rounded-xl border border-border bg-card shadow-2xs">
                <span className="text-xs text-muted-foreground">Dents soignées</span>
                <p className="text-lg font-bold text-primary">{odontogramme.nb_dents_soignees}</p>
              </div>
              <div className="p-3 rounded-xl border border-border bg-card shadow-2xs">
                <span className="text-xs text-muted-foreground">À traiter / Caries</span>
                <p className="text-lg font-bold text-danger">{odontogramme.nb_dents_a_traiter}</p>
              </div>
              <div className="p-3 rounded-xl border border-border bg-card shadow-2xs">
                <span className="text-xs text-muted-foreground">Dents absentes</span>
                <p className="text-lg font-bold text-muted-foreground">
                  {odontogramme.nb_dents_absentes}
                </p>
              </div>
              <div className="p-3 rounded-xl border border-border bg-card shadow-2xs">
                <span className="text-xs text-muted-foreground">Total examinées</span>
                <p className="text-lg font-bold text-foreground">{odontogramme.nb_dents}</p>
              </div>
            </div>
          )}

          {/* Onglets : Schéma SVG vs Charting Parodontal */}
          <Tabs defaultValue="schema">
            <TabsList>
              <TabsTrigger value="schema">Schéma SVG Interactif</TabsTrigger>
              <TabsTrigger value="parodontal" badge={chartings.length || undefined}>
                Charting Parodontal (6 points)
              </TabsTrigger>
            </TabsList>

            <TabsContent value="schema" className="space-y-4">
              {/* Légende officielle du référentiel */}
              <div className="flex flex-wrap items-center gap-3 p-3 rounded-xl border border-border bg-muted/20 text-xs">
                <span className="font-bold text-foreground">Légende :</span>
                {referentiel.map((etat) => (
                  <div key={etat.code} className="flex items-center gap-1.5">
                    <span
                      className="h-3 w-3 rounded-full shrink-0 border border-black/10"
                      style={{ backgroundColor: etat.couleur }}
                    />
                    <span className="text-muted-foreground">{etat.libelle}</span>
                  </div>
                ))}
              </div>

              {/* Composant SVG */}
              {loadingOdonto ? (
                <div className="space-y-4">
                  <Skeleton className="h-44 w-full rounded-2xl" />
                  <Skeleton className="h-44 w-full rounded-2xl" />
                </div>
              ) : erreurOdonto ? (
                /* Ne pas dessiner un schéma vide : cela laisserait croire à un
                   patient sans dentition alors que le chargement a échoué. */
                <EmptyState
                  icon={WifiOff}
                  titre="Schéma indisponible"
                  description="L'odontogramme n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
                >
                  <Button variant="outline" onClick={() => void refetch()}>
                    <RefreshCw className="h-4 w-4" /> Réessayer
                  </Button>
                </EmptyState>
              ) : (
                <OdontogrammeSvg
                  dents={dents}
                  referentielEtats={referentiel}
                  dentSelectionneeFdi={dentSelectionnee?.numero_fdi}
                  onSelectDent={(d) => {
                    setDentSelectionnee(d)
                    setDrawerOpen(true)
                  }}
                  typeOdontogramme={typeOdontogramme}
                />
              )}
            </TabsContent>

            {/* Charting Parodontal */}
            <TabsContent value="parodontal" className="space-y-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Relevés Parodontaux (Sondage 6 points & Mobilité)</CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Mesures de la profondeur des poches (MV, V, DV, ML, L, DL) et récession gingivale
                    </p>
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setModalChartingOpen(true)}
                  >
                    <Plus className="h-4 w-4" />
                    Nouveau relevé
                  </Button>
                </CardHeader>
                <CardContent>
                  {chartings.length === 0 ? (
                    <div className="p-8 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                      Aucun relevé parodontal enregistré pour ce patient.
                    </div>
                  ) : (
                    <div className="divide-y divide-border text-xs">
                      {chartings.map((c) => (
                        <div key={c.id} className="py-3 flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <span className="font-bold text-foreground text-sm">
                              Dent {c.numero_fdi ?? 'Globale'}
                            </span>
                            <span className="text-muted-foreground ml-2">
                              Poches Vestibulaires : {c.sondage_mesio_vestibulaire ?? '-'} /{' '}
                              {c.sondage_vestibulaire ?? '-'} / {c.sondage_disto_vestibulaire ?? '-'} mm
                            </span>
                            <span className="text-muted-foreground block text-[11px]">
                              Poches Linguales : {c.sondage_mesio_lingual ?? '-'} /{' '}
                              {c.sondage_lingual ?? '-'} / {c.sondage_disto_lingual ?? '-'} mm
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            {c.saignement_sondage && (
                              <Badge variant="danger">BOP / Saignement</Badge>
                            )}
                            {c.recession_gingivale ? (
                              <Badge variant="warning">Récession {c.recession_gingivale}mm</Badge>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {/* Drawer latéral d'édition de dent */}
          <DentDrawer
            patientId={patientSelectionne.id}
            dent={dentSelectionnee}
            open={drawerOpen}
            onClose={() => {
              setDrawerOpen(false)
              setDentSelectionnee(null)
            }}
            referentielEtats={referentiel}
            onSuccess={() => {
              void queryClient.invalidateQueries({
                queryKey: ['odontogramme-patient', patientSelectionne.id],
              })
            }}
          />

          {/* Modale Charting */}
          <Modal
            open={modalChartingOpen}
            onClose={() => setModalChartingOpen(false)}
            title="Nouveau sondage parodontal 6 points"
            maxWidth="md"
          >
            <form onSubmit={handleEnregistrerCharting} className="space-y-4 pt-2">
              <div>
                <Label htmlFor="chart-dent" required>
                  Numéro FDI de la dent
                </Label>
                <Input
                  id="chart-dent"
                  type="number"
                  value={dentCharting}
                  onChange={(e) => setDentCharting(e.target.value)}
                  placeholder="Ex: 11, 21, 36..."
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>Sondage Vestibulaire (mm) : Mésial / Médian / Distal</Label>
                <div className="grid grid-cols-3 gap-2">
                  <Input
                    type="number"
                    value={sondageMV}
                    onChange={(e) => setSondageMV(e.target.value)}
                    placeholder="MV"
                    min="0"
                    max="15"
                  />
                  <Input
                    type="number"
                    value={sondageV}
                    onChange={(e) => setSondageV(e.target.value)}
                    placeholder="V"
                    min="0"
                    max="15"
                  />
                  <Input
                    type="number"
                    value={sondageDV}
                    onChange={(e) => setSondageDV(e.target.value)}
                    placeholder="DV"
                    min="0"
                    max="15"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Sondage Palatin / Lingual (mm) : Mésial / Médian / Distal</Label>
                <div className="grid grid-cols-3 gap-2">
                  <Input
                    type="number"
                    value={sondageML}
                    onChange={(e) => setSondageML(e.target.value)}
                    placeholder="ML"
                    min="0"
                    max="15"
                  />
                  <Input
                    type="number"
                    value={sondageL}
                    onChange={(e) => setSondageL(e.target.value)}
                    placeholder="L"
                    min="0"
                    max="15"
                  />
                  <Input
                    type="number"
                    value={sondageDL}
                    onChange={(e) => setSondageDL(e.target.value)}
                    placeholder="DL"
                    min="0"
                    max="15"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="chart-rec">Récession gingivale (mm)</Label>
                  <Input
                    id="chart-rec"
                    type="number"
                    value={recession}
                    onChange={(e) => setRecession(e.target.value)}
                    min="0"
                    max="15"
                  />
                </div>

                <div className="flex items-center pt-5">
                  <label className="flex items-center gap-2 text-xs font-semibold text-foreground cursor-pointer">
                    <input
                      type="checkbox"
                      checked={saignement}
                      onChange={(e) => setSaignement(e.target.checked)}
                      className="rounded border-border text-danger focus:ring-danger"
                    />
                    <span>Saignement au sondage (BOP)</span>
                  </label>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-border">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setModalChartingOpen(false)}
                  disabled={loadingCharting}
                >
                  Annuler
                </Button>
                <Button type="submit" variant="primary" loading={loadingCharting}>
                  Enregistrer relevé
                </Button>
              </div>
            </form>
          </Modal>
        </div>
      )}
    </div>
  )
}
