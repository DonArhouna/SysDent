import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Stethoscope,
  Clock,
  Building2,
  Plus,
  Trash2,
  RefreshCw,
  Mail,
  Phone,
  ShieldCheck,
  Calendar,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Modal } from '@/components/ui/modal'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Can } from '@/components/auth/can'
import { toast } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { praticiensApi } from '../services/praticiens-api'
import type { Disponibilite } from '../types'

const JOURS_SEMAINE = [
  { index: 0, nom: 'Lundi' },
  { index: 1, nom: 'Mardi' },
  { index: 2, nom: 'Mercredi' },
  { index: 3, nom: 'Jeudi' },
  { index: 4, nom: 'Vendredi' },
  { index: 5, nom: 'Samedi' },
  { index: 6, nom: 'Dimanche' },
]

export function PraticiensPage() {
  const queryClient = useQueryClient()
  const cabinetActifId = useCabinetStore((s) => s.cabinetActifId)
  const cabinets = useCabinetStore((s) => s.cabinets)

  const [praticienSelectionneId, setPraticienSelectionneId] = useState<string | null>(null)

  // Modale Plage de travail
  const [modalPlageOpen, setModalPlageOpen] = useState(false)
  const [typePlage, setTypePlage] = useState<'CONSULTATION' | 'URGENCE' | 'BLOCKING'>('CONSULTATION')
  const [modeRecurrence, setModeRecurrence] = useState<'hebdo' | 'date'>('hebdo')
  const [jourSemaine, setJourSemaine] = useState('0')
  const [dateSpecifique, setDateSpecifique] = useState('')
  const [heureDebut, setHeureDebut] = useState('08:30')
  const [heureFin, setHeureFin] = useState('17:00')
  const [cabinetPlageId, setCabinetPlageId] = useState<string>('')
  const [motifBlocage, setMotifBlocage] = useState('')
  const [loadingPlage, setLoadingPlage] = useState(false)

  // Date de test créneaux
  const [dateTestCreneaux, setDateTestCreneaux] = useState(
    () => new Date().toISOString().slice(0, 10),
  )

  // Requête des praticiens
  const { data: resPraticiens, isLoading, refetch } = useQuery({
    queryKey: ['praticiens-list', cabinetActifId],
    queryFn: () => praticiensApi.lister(cabinetActifId),
  })

  const praticiens = resPraticiens?.data ?? []
  const praticienActif =
    praticiens.find((p) => p.id === praticienSelectionneId) ?? praticiens[0] ?? null

  // Disponibilités du praticien actif
  const { data: resDispos, isLoading: loadingDispos } = useQuery({
    queryKey: ['praticien-disponibilites', praticienActif?.id],
    queryFn: () => praticiensApi.listerDisponibilites(praticienActif!.id),
    enabled: Boolean(praticienActif?.id),
  })

  // Créneaux calculés pour la date test
  const { data: resCreneaux, isLoading: loadingCreneaux } = useQuery({
    queryKey: ['praticien-creneaux', praticienActif?.id, dateTestCreneaux],
    queryFn: () => praticiensApi.calculerCreneaux(praticienActif!.id, dateTestCreneaux),
    enabled: Boolean(praticienActif?.id && dateTestCreneaux),
  })

  const disponibilites = resDispos?.data ?? []
  const creneauxData = resCreneaux?.data

  const handleAjouterPlage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!praticienActif) return
    try {
      setLoadingPlage(true)
      await praticiensApi.creerDisponibilite(praticienActif.id, {
        cabinet_id: cabinetPlageId || null,
        jour_semaine: modeRecurrence === 'hebdo' ? parseInt(jourSemaine, 10) : null,
        date_specifique: modeRecurrence === 'date' ? dateSpecifique : null,
        heure_debut: heureDebut,
        heure_fin: heureFin,
        type: typePlage,
        motif_blocage: typePlage === 'BLOCKING' ? motifBlocage : undefined,
      })
      toast.success('Plage horaire enregistrée.')
      setModalPlageOpen(false)
      void queryClient.invalidateQueries({
        queryKey: ['praticien-disponibilites', praticienActif.id],
      })
      void queryClient.invalidateQueries({
        queryKey: ['praticien-creneaux', praticienActif.id],
      })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingPlage(false)
    }
  }

  const handleSupprimerPlage = async (dispo: Disponibilite) => {
    try {
      await praticiensApi.supprimerDisponibilite(dispo.id)
      toast.success('Plage horaire supprimée.')
      void queryClient.invalidateQueries({
        queryKey: ['praticien-disponibilites', praticienActif?.id],
      })
      void queryClient.invalidateQueries({
        queryKey: ['praticien-creneaux', praticienActif?.id],
      })
    } catch {
      // Géré par le toast global
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            Praticiens & Disponibilités
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Chirurgiens-dentistes, spécialités, numéros d'ordre et plages horaires de consultation
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          <RefreshCw className="h-4 w-4" />
          Actualiser
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="h-64 w-full rounded-2xl" />
          <Skeleton className="h-64 md:col-span-2 w-full rounded-2xl" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Colonne gauche : Liste des praticiens */}
          <div className="lg:col-span-4 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Praticiens ({praticiens.length})
            </h3>

            <div className="space-y-3">
              {praticiens.map((praticien) => {
                const estSelectionne = praticienActif?.id === praticien.id
                return (
                  <div
                    key={praticien.id}
                    onClick={() => setPraticienSelectionneId(praticien.id)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      estSelectionne
                        ? 'border-primary bg-primary/5 shadow-sm'
                        : 'border-border bg-card hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Stethoscope className="h-4 w-4 text-primary" />
                          <h4 className="font-bold text-sm text-foreground">
                            {praticien.titre ? `${praticien.titre} ` : 'Dr '}
                            {praticien.nom_complet}
                          </h4>
                        </div>
                        <p className="text-xs text-muted-foreground font-medium">
                          {praticien.specialite ?? 'Chirurgien-Dentiste'}
                        </p>
                        {praticien.numero_ordre && (
                          <p className="text-[11px] text-muted-foreground font-mono">
                            N° Ordre : {praticien.numero_ordre}
                          </p>
                        )}
                      </div>
                      <Badge variant={praticien.actif ? 'success' : 'neutral'}>
                        {praticien.actif ? 'Actif' : 'Inactif'}
                      </Badge>
                    </div>

                    {praticien.cabinets_rattaches.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1 border-t border-border pt-2">
                        {praticien.cabinets_rattaches.map((r) => (
                          <Badge key={r.cabinet_id} variant="neutral" className="text-[10px]">
                            <Building2 className="h-2.5 w-2.5 mr-1" />
                            {r.nom}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Colonne droite : Fiche du praticien & Gestion de ses disponibilités */}
          <div className="lg:col-span-8 space-y-6">
            {praticienActif && (
              <>
                {/* Profil Praticien */}
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-3">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Stethoscope className="h-5 w-5 text-primary" />
                        {praticienActif.titre ? `${praticienActif.titre} ` : 'Dr '}
                        {praticienActif.nom_complet}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {praticienActif.specialite ?? 'Omnipratique & Chirurgie dentaire'}
                      </p>
                    </div>

                    <Can permission="DISPONIBILITES:CREATE">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          if (cabinets.length > 0) setCabinetPlageId(cabinets[0].id)
                          setModalPlageOpen(true)
                        }}
                      >
                        <Plus className="h-4 w-4" />
                        Déclarer une plage
                      </Button>
                    </Can>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Mail className="h-3.5 w-3.5 text-primary" />
                        <span className="truncate">{praticienActif.email}</span>
                      </div>
                      {praticienActif.telephone && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Phone className="h-3.5 w-3.5 text-primary" />
                          <span>{praticienActif.telephone}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 text-muted-foreground font-mono">
                        <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                        <span>N° {praticienActif.numero_ordre ?? 'Ordre non renseigné'}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Plages déclarées */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-primary" />
                        Plages de Travail & Horaires de Consultation
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {loadingDispos ? (
                      <Skeleton className="h-24 w-full rounded-xl" />
                    ) : disponibilites.length === 0 ? (
                      <div className="text-center py-6 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                        Aucune plage horaire déclarée. Le praticien ne sera pas proposé lors de la prise de rendez-vous.
                      </div>
                    ) : (
                      <div className="divide-y divide-border">
                        {disponibilites.map((d) => {
                          const estHebdo = d.jour_semaine !== null && d.jour_semaine !== undefined
                          const jourNom = estHebdo
                            ? JOURS_SEMAINE[d.jour_semaine!]?.nom
                            : d.date_specifique
                          const estBlocking = d.type === 'BLOCKING'

                          return (
                            <div
                              key={d.id}
                              className="py-3 flex flex-wrap items-center justify-between gap-3 text-xs"
                            >
                              <div className="space-y-0.5">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-foreground text-sm">
                                    {jourNom}
                                  </span>
                                  <Badge
                                    variant={
                                      estBlocking
                                        ? 'danger'
                                        : d.type === 'URGENCE'
                                          ? 'warning'
                                          : 'success'
                                    }
                                  >
                                    {estBlocking
                                      ? 'Indisponible / Bloqué'
                                      : d.type === 'URGENCE'
                                        ? 'Créneaux Urgences'
                                        : 'Consultations'}
                                  </Badge>
                                </div>
                                <p className="text-muted-foreground font-mono">
                                  {d.heure_debut} - {d.heure_fin}
                                  {d.cabinet_nom ? ` • Site ${d.cabinet_nom}` : ' • Tous les sites'}
                                  {d.motif_blocage ? ` • Motif: ${d.motif_blocage}` : ''}
                                </p>
                              </div>

                              <Can permission="DISPONIBILITES:DELETE">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => void handleSupprimerPlage(d)}
                                  title="Supprimer la plage"
                                >
                                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-danger" />
                                </Button>
                              </Can>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Simulateur de Créneaux Proposables */}
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-3">
                    <div>
                      <CardTitle className="text-base flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-primary" />
                        Simulation des Créneaux Disponibles
                      </CardTitle>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Test en direct du moteur de calcul des créneaux (D2A / D2B)
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Label htmlFor="date-simu" className="text-xs hidden sm:inline">
                        Date visée :
                      </Label>
                      <input
                        id="date-simu"
                        type="date"
                        value={dateTestCreneaux}
                        onChange={(e) => setDateTestCreneaux(e.target.value)}
                        className="rounded-lg border border-input bg-card px-2.5 py-1 text-xs text-foreground"
                      />
                    </div>
                  </CardHeader>

                  <CardContent>
                    {loadingCreneaux ? (
                      <Skeleton className="h-16 w-full rounded-xl" />
                    ) : creneauxData?.creneaux && creneauxData.creneaux.length > 0 ? (
                      <div className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                          {creneauxData.creneaux.map((c, i) => (
                            <div
                              key={i}
                              className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-mono font-semibold text-foreground shadow-2xs hover:border-primary transition-colors"
                            >
                              {c.heure_debut} - {c.heure_fin}
                            </div>
                          ))}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {creneauxData.creneaux.length} créneau(x) calculé(s) selon les plages de travail du praticien.
                        </p>
                      </div>
                    ) : (
                      <div className="text-center py-6 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                        {creneauxData?.avertissement ??
                          'Aucun créneau disponible pour cette date (vérifiez les plages déclarées).'}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </div>
      )}

      {/* Modale Déclaration Plage */}
      <Modal
        open={modalPlageOpen}
        onClose={() => setModalPlageOpen(false)}
        title="Déclarer une plage de travail"
        maxWidth="md"
      >
        <form onSubmit={handleAjouterPlage} className="space-y-4 pt-2">
          <div>
            <Label htmlFor="type-plage" required>
              Nature de la plage
            </Label>
            <Select
              id="type-plage"
              value={typePlage}
              onChange={(e) => setTypePlage(e.target.value as any)}
            >
              <option value="CONSULTATION">Consultations normales (crée des créneaux)</option>
              <option value="URGENCE">Plage réservée aux urgences dentaires</option>
              <option value="BLOCKING">Indisponibilité / Blocage (congé, formation, absence)</option>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setModeRecurrence('hebdo')}
              className={`p-2.5 rounded-lg border text-xs font-semibold transition-all ${
                modeRecurrence === 'hebdo'
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground'
              }`}
            >
              Récurrence hebdomadaire
            </button>
            <button
              type="button"
              onClick={() => setModeRecurrence('date')}
              className={`p-2.5 rounded-lg border text-xs font-semibold transition-all ${
                modeRecurrence === 'date'
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground'
              }`}
            >
              Date spécifique (exception)
            </button>
          </div>

          {modeRecurrence === 'hebdo' ? (
            <div>
              <Label htmlFor="jour-semaine" required>
                Jour de la semaine
              </Label>
              <Select
                id="jour-semaine"
                value={jourSemaine}
                onChange={(e) => setJourSemaine(e.target.value)}
              >
                {JOURS_SEMAINE.map((j) => (
                  <option key={j.index} value={j.index}>
                    {j.nom}
                  </option>
                ))}
              </Select>
            </div>
          ) : (
            <div>
              <Label htmlFor="date-specifique" required>
                Date visée
              </Label>
              <Input
                id="date-specifique"
                type="date"
                value={dateSpecifique}
                onChange={(e) => setDateSpecifique(e.target.value)}
                required
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="h-debut" required>
                Heure début
              </Label>
              <Input
                id="h-debut"
                type="time"
                value={heureDebut}
                onChange={(e) => setHeureDebut(e.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="h-fin" required>
                Heure fin
              </Label>
              <Input
                id="h-fin"
                type="time"
                value={heureFin}
                onChange={(e) => setHeureFin(e.target.value)}
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="cab-plage">Site du cabinet (facultatif)</Label>
            <Select
              id="cab-plage"
              value={cabinetPlageId}
              onChange={(e) => setCabinetPlageId(e.target.value)}
            >
              <option value="">Tous les sites du cabinet</option>
              {cabinets.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nom} {c.ville ? `(${c.ville})` : ''}
                </option>
              ))}
            </Select>
          </div>

          {typePlage === 'BLOCKING' && (
            <div>
              <Label htmlFor="motif-bloc">Motif de l'indisponibilité</Label>
              <Input
                id="motif-bloc"
                value={motifBlocage}
                onChange={(e) => setMotifBlocage(e.target.value)}
                placeholder="Ex: Congrès ADF, Formation Implanto, Congé..."
              />
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalPlageOpen(false)}
              disabled={loadingPlage}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" loading={loadingPlage}>
              Enregistrer la plage
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
