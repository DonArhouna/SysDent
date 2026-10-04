import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  DoorOpen,
  Armchair,
  Plus,
  Pencil,
  Trash2,
  RefreshCw,
  Phone,
  Mail,
  MapPin,
  Clock,
  CheckCircle2,
  XCircle,
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
import { cabinetsApi } from '../services/cabinets-api'
import type { Cabinet, Fauteuil, Salle } from '../types'

export function CabinetsPage() {
  const queryClient = useQueryClient()
  const [cabinetSelectionneId, setCabinetSelectionneId] = useState<string | null>(null)

  // Modales
  const [modalCabinetOpen, setModalCabinetOpen] = useState(false)
  const [cabinetToEdit, setCabinetToEdit] = useState<Cabinet | null>(null)
  const [nomCabinet, setNomCabinet] = useState('')
  const [adresseCabinet, setAdresseCabinet] = useState('')
  const [villeCabinet, setVilleCabinet] = useState('')
  const [telCabinet, setTelCabinet] = useState('')
  const [emailCabinet, setEmailCabinet] = useState('')

  // Modale Salle
  const [modalSalleOpen, setModalSalleOpen] = useState(false)
  const [nomSalle, setNomSalle] = useState('')
  const [etageSalle, setEtageSalle] = useState('0')

  // Modale Fauteuil
  const [modalFauteuilOpen, setModalFauteuilOpen] = useState(false)
  const [salleCibleId, setSalleCibleId] = useState('')
  const [numeroFauteuil, setNumeroFauteuil] = useState('')

  const [loadingAction, setLoadingAction] = useState(false)

  // Liste des cabinets
  const { data: resCabinets, isLoading, refetch } = useQuery({
    queryKey: ['cabinets-list'],
    queryFn: () => cabinetsApi.lister(true),
  })

  const cabinets = resCabinets?.data ?? []
  const cabinetActif =
    cabinets.find((c) => c.id === cabinetSelectionneId) ?? cabinets[0] ?? null

  // Salles et Fauteuils du cabinet actif
  const { data: resSalles, isLoading: loadingSalles } = useQuery({
    queryKey: ['cabinet-salles', cabinetActif?.id],
    queryFn: () => cabinetsApi.listerSalles(cabinetActif!.id),
    enabled: Boolean(cabinetActif?.id),
  })

  const { data: resFauteuils, isLoading: loadingFauteuils } = useQuery({
    queryKey: ['cabinet-fauteuils', cabinetActif?.id],
    queryFn: () => cabinetsApi.listerFauteuils(cabinetActif!.id, true),
    enabled: Boolean(cabinetActif?.id),
  })

  const salles = resSalles?.data ?? []
  const fauteuils = resFauteuils?.data ?? []

  const ouvrirEditionCabinet = (cab: Cabinet) => {
    setCabinetToEdit(cab)
    setNomCabinet(cab.nom)
    setAdresseCabinet(cab.adresse ?? '')
    setVilleCabinet(cab.ville ?? '')
    setTelCabinet(cab.telephone ?? '')
    setEmailCabinet(cab.email ?? '')
    setModalCabinetOpen(true)
  }

  const handleSaveCabinet = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!cabinetToEdit) return
    try {
      setLoadingAction(true)
      await cabinetsApi.modifier(cabinetToEdit.id, {
        nom: nomCabinet.trim(),
        adresse: adresseCabinet.trim() || undefined,
        ville: villeCabinet.trim() || undefined,
        telephone: telCabinet.trim() || undefined,
        email: emailCabinet.trim() || undefined,
      })
      toast.success('Informations du site mises à jour.')
      setModalCabinetOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['cabinets-list'] })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingAction(false)
    }
  }

  const handleCreateSalle = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!cabinetActif || !nomSalle.trim()) return
    try {
      setLoadingAction(true)
      await cabinetsApi.creerSalle(cabinetActif.id, {
        nom: nomSalle.trim(),
        etage: etageSalle ? parseInt(etageSalle, 10) : 0,
      })
      toast.success(`Salle « ${nomSalle} » créée.`)
      setModalSalleOpen(false)
      setNomSalle('')
      setEtageSalle('0')
      void queryClient.invalidateQueries({ queryKey: ['cabinet-salles', cabinetActif.id] })
      void queryClient.invalidateQueries({ queryKey: ['cabinets-list'] })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingAction(false)
    }
  }

  const handleDeleteSalle = async (salle: Salle) => {
    if (!cabinetActif) return
    if ((salle.nb_fauteuils ?? 0) > 0) {
      toast.error('Une salle contenant des fauteuils ne peut pas être supprimée.')
      return
    }
    try {
      await cabinetsApi.supprimerSalle(cabinetActif.id, salle.id)
      toast.success(`Salle « ${salle.nom} » supprimée.`)
      void queryClient.invalidateQueries({ queryKey: ['cabinet-salles', cabinetActif.id] })
      void queryClient.invalidateQueries({ queryKey: ['cabinets-list'] })
    } catch {
      // Géré par le toast global
    }
  }

  const handleCreateFauteuil = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!salleCibleId || !numeroFauteuil.trim()) return
    try {
      setLoadingAction(true)
      await cabinetsApi.creerFauteuil(salleCibleId, {
        numero: numeroFauteuil.trim(),
      })
      toast.success(`Fauteuil « ${numeroFauteuil} » ajouté.`)
      setModalFauteuilOpen(false)
      setNumeroFauteuil('')
      void queryClient.invalidateQueries({ queryKey: ['cabinet-fauteuils', cabinetActif?.id] })
      void queryClient.invalidateQueries({ queryKey: ['cabinet-salles', cabinetActif?.id] })
      void queryClient.invalidateQueries({ queryKey: ['cabinets-list'] })
    } catch {
      // Géré par le toast global
    } finally {
      setLoadingAction(false)
    }
  }

  const handleToggleFauteuil = async (f: Fauteuil) => {
    try {
      if (f.actif) {
        await cabinetsApi.modifierFauteuil(f.id, { actif: false })
        toast.info(`Fauteuil ${f.numero} désactivé (hors service).`)
      } else {
        await cabinetsApi.reactiverFauteuil(f.id)
        toast.success(`Fauteuil ${f.numero} remis en service.`)
      }
      void queryClient.invalidateQueries({ queryKey: ['cabinet-fauteuils', cabinetActif?.id] })
      void queryClient.invalidateQueries({ queryKey: ['cabinets-list'] })
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
            Cabinets & Ressources Matérielles
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Configuration des sites, des salles de soins et du parc de fauteuils dentaires
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
          {/* Colonne gauche : Liste des cabinets */}
          <div className="lg:col-span-4 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Sites & Cabinets ({cabinets.length})
            </h3>

            <div className="space-y-3">
              {cabinets.map((cab) => {
                const estSelectionne = cabinetActif?.id === cab.id
                return (
                  <div
                    key={cab.id}
                    onClick={() => setCabinetSelectionneId(cab.id)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      estSelectionne
                        ? 'border-primary bg-primary/5 shadow-sm'
                        : 'border-border bg-card hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-primary" />
                          <h4 className="font-bold text-sm text-foreground">{cab.nom}</h4>
                        </div>
                        {cab.ville && (
                          <p className="text-xs text-muted-foreground flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            {cab.ville} {cab.adresse ? `• ${cab.adresse}` : ''}
                          </p>
                        )}
                      </div>
                      <Badge variant={cab.actif ? 'success' : 'neutral'}>
                        {cab.actif ? 'Actif' : 'Inactif'}
                      </Badge>
                    </div>

                    <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center text-xs">
                      <div>
                        <span className="block font-bold text-foreground">{cab.nb_salles}</span>
                        <span className="text-[10px] text-muted-foreground">Salles</span>
                      </div>
                      <div>
                        <span className="block font-bold text-foreground">
                          {cab.nb_fauteuils_actifs}
                        </span>
                        <span className="text-[10px] text-muted-foreground">Fauteuils</span>
                      </div>
                      <div>
                        <span className="block font-bold text-foreground">
                          {cab.nb_praticiens_actifs}
                        </span>
                        <span className="text-[10px] text-muted-foreground">Praticiens</span>
                      </div>
                    </div>

                    <div className="mt-3 flex justify-end gap-1">
                      <Can permission="CABINETS:UPDATE">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            ouvrirEditionCabinet(cab)
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Paramètres
                        </Button>
                      </Can>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Colonne droite : Salles et Fauteuils du cabinet sélectionné */}
          <div className="lg:col-span-8 space-y-6">
            {cabinetActif && (
              <>
                {/* Carte d'information du site actif */}
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-3">
                    <div>
                      <CardTitle>{cabinetActif.nom}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Ressources physiques et aménagement du site
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <Can permission="CABINETS:CREATE">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setModalSalleOpen(true)}
                        >
                          <DoorOpen className="h-4 w-4" />
                          Nouvelle salle
                        </Button>

                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            if (salles.length > 0) {
                              setSalleCibleId(salles[0].id)
                            }
                            setModalFauteuilOpen(true)
                          }}
                          disabled={salles.length === 0}
                        >
                          <Plus className="h-4 w-4" />
                          Nouveau fauteuil
                        </Button>
                      </Can>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                      {cabinetActif.telephone && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Phone className="h-3.5 w-3.5 text-primary" />
                          <span>{cabinetActif.telephone}</span>
                        </div>
                      )}
                      {cabinetActif.email && (
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <Mail className="h-3.5 w-3.5 text-primary" />
                          <span>{cabinetActif.email}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="h-3.5 w-3.5 text-primary" />
                        <span>Horaires configurés</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Parc des Fauteuils */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Armchair className="h-4 w-4 text-primary" />
                        Fauteuils Dentaires ({fauteuils.length})
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {loadingFauteuils ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <Skeleton className="h-20 w-full rounded-xl" />
                        <Skeleton className="h-20 w-full rounded-xl" />
                      </div>
                    ) : fauteuils.length === 0 ? (
                      <div className="text-center py-8 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                        Aucun fauteuil installé. Créez d'abord une salle puis ajoutez un fauteuil.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                        {fauteuils.map((f) => (
                          <div
                            key={f.id}
                            className={`p-3.5 rounded-xl border transition-all ${
                              f.actif
                                ? 'border-border bg-card shadow-2xs'
                                : 'border-border bg-muted/30 opacity-70'
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h5 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                                  <Armchair className="h-4 w-4 text-primary" />
                                  {f.numero}
                                </h5>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                  {f.nom_salle ?? 'Salle non assignée'}
                                </p>
                              </div>
                              <Badge variant={f.actif ? 'success' : 'neutral'}>
                                {f.actif ? 'En service' : 'Hors service'}
                              </Badge>
                            </div>

                            <div className="mt-3 flex items-center justify-between border-t border-border pt-2">
                              <Can permission="CABINETS:UPDATE">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 text-xs"
                                  onClick={() => void handleToggleFauteuil(f)}
                                >
                                  {f.actif ? (
                                    <>
                                      <XCircle className="h-3.5 w-3.5 text-danger" />
                                      Désactiver
                                    </>
                                  ) : (
                                    <>
                                      <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                                      Réactiver
                                    </>
                                  )}
                                </Button>
                              </Can>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Salles du cabinet */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <DoorOpen className="h-4 w-4 text-primary" />
                      Salles de Soins ({salles.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {loadingSalles ? (
                      <Skeleton className="h-16 w-full rounded-xl" />
                    ) : salles.length === 0 ? (
                      <div className="text-center py-6 text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                        Aucune salle déclarée pour ce site.
                      </div>
                    ) : (
                      <div className="divide-y divide-border">
                        {salles.map((salle) => (
                          <div
                            key={salle.id}
                            className="py-3 flex items-center justify-between text-xs"
                          >
                            <div>
                              <span className="font-semibold text-foreground text-sm">
                                {salle.nom}
                              </span>
                              <span className="text-muted-foreground ml-2">
                                (Étage {salle.etage ?? 0}) • {salle.nb_fauteuils ?? 0} fauteuil(s)
                              </span>
                            </div>

                            <Can permission="CABINETS:DELETE">
                              {(salle.nb_fauteuils ?? 0) === 0 && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => void handleDeleteSalle(salle)}
                                  title="Supprimer la salle vide"
                                >
                                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-danger" />
                                </Button>
                              )}
                            </Can>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </div>
      )}

      {/* Modale d'édition du site */}
      <Modal
        open={modalCabinetOpen}
        onClose={() => setModalCabinetOpen(false)}
        title="Paramètres du Site"
      >
        <form onSubmit={handleSaveCabinet} className="space-y-4 pt-2">
          <div>
            <Label htmlFor="nom-cab" required>
              Nom du cabinet
            </Label>
            <Input
              id="nom-cab"
              value={nomCabinet}
              onChange={(e) => setNomCabinet(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ville-cab">Ville</Label>
              <Input
                id="ville-cab"
                value={villeCabinet}
                onChange={(e) => setVilleCabinet(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="tel-cab">Téléphone</Label>
              <Input
                id="tel-cab"
                value={telCabinet}
                onChange={(e) => setTelCabinet(e.target.value)}
              />
            </div>
          </div>

          <div>
            <Label htmlFor="adresse-cab">Adresse</Label>
            <Input
              id="adresse-cab"
              value={adresseCabinet}
              onChange={(e) => setAdresseCabinet(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="email-cab">Email</Label>
            <Input
              id="email-cab"
              type="email"
              value={emailCabinet}
              onChange={(e) => setEmailCabinet(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalCabinetOpen(false)}
              disabled={loadingAction}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" loading={loadingAction}>
              Enregistrer
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modale création Salle */}
      <Modal
        open={modalSalleOpen}
        onClose={() => setModalSalleOpen(false)}
        title="Ajouter une salle de soins"
        maxWidth="sm"
      >
        <form onSubmit={handleCreateSalle} className="space-y-4 pt-2">
          <div>
            <Label htmlFor="nom-salle" required>
              Nom de la salle
            </Label>
            <Input
              id="nom-salle"
              value={nomSalle}
              onChange={(e) => setNomSalle(e.target.value)}
              placeholder="Ex: Salle Chirurgie A, Box 1"
              required
            />
          </div>

          <div>
            <Label htmlFor="etage-salle">Étage</Label>
            <Input
              id="etage-salle"
              type="number"
              value={etageSalle}
              onChange={(e) => setEtageSalle(e.target.value)}
              min="-2"
              max="20"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalSalleOpen(false)}
              disabled={loadingAction}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" loading={loadingAction}>
              Créer la salle
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modale création Fauteuil */}
      <Modal
        open={modalFauteuilOpen}
        onClose={() => setModalFauteuilOpen(false)}
        title="Ajouter un fauteuil dentaire"
        maxWidth="sm"
      >
        <form onSubmit={handleCreateFauteuil} className="space-y-4 pt-2">
          <div>
            <Label htmlFor="salle-cible" required>
              Salle d'affectation
            </Label>
            <Select
              id="salle-cible"
              value={salleCibleId}
              onChange={(e) => setSalleCibleId(e.target.value)}
              required
            >
              {salles.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nom} (Étage {s.etage ?? 0})
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="num-fauteuil" required>
              Numéro / Identifiant du fauteuil
            </Label>
            <Input
              id="num-fauteuil"
              value={numeroFauteuil}
              onChange={(e) => setNumeroFauteuil(e.target.value)}
              placeholder="Ex: Fauteuil 1, F-02..."
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="outline"
              onClick={() => setModalFauteuilOpen(false)}
              disabled={loadingAction}
            >
              Annuler
            </Button>
            <Button type="submit" variant="primary" loading={loadingAction}>
              Ajouter le fauteuil
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
