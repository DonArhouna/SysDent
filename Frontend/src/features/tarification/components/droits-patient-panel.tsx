import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, ShieldCheck, Trash2, WifiOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Modal } from '@/components/ui/modal'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { possedePermission, useAuthStore } from '@/stores/auth-store'
import { useToastStore } from '@/stores/toast-store'

import { tarificationApi } from '../services/tarification-api'
import {
  PERM_ASSURANCE_READ,
  PERM_ASSURANCE_WRITE,
  type DroitPriseEnCharge,
} from '../types'
import { normaliserTaux, validerPriorite, validerTaux } from './validation'

/**
 * Onglet « Prise en charge » de la fiche patient.
 *
 * **Un patient peut avoir plusieurs droits** - une assurance obligatoire et
 * une mutuelle complementaire. La priorite dit lequel s'applique en premier
 * quand les deux se recouvrent ; c'est une decision du cabinet, et aucun code
 * ne peut la deduire.
 *
 * **Lecture seule sans `ASSURANCE:WRITE`.** Le praticien voit qui couvre quoi
 * avant de soin - c'est une information clinique - mais ne declare pas le
 * droit. Aucun bouton n'est rendu dans ce cas : un bouton qui repond 403
 * apprend au praticien qu'il a echoue, alors que son profil n'a jamais eu ce
 * droit.
 */
export function DroitsPatientPanel({ patientId }: { patientId: string }) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const profil = useAuthStore((e) => e.profil)

  const peutLire = possedePermission(profil, PERM_ASSURANCE_READ)
  const peutEcrire = possedePermission(profil, PERM_ASSURANCE_WRITE)

  const [ajoutOuvert, setAjoutOuvert] = useState(false)

  const droits = useQuery({
    queryKey: ['tarification', 'droits', patientId],
    queryFn: () => tarificationApi.listerDroitsPatient(patientId),
    enabled: peutLire && Boolean(patientId),
  })

  const organismes = useQuery({
    queryKey: ['tarification', 'organismes', 'choix', peutEcrire],
    queryFn: () => tarificationApi.listerOrganismes({ limit: 100, actif: true }),
    enabled: peutEcrire,
  })

  const supprimer = useMutation({
    mutationFn: (droit: DroitPriseEnCharge) => tarificationApi.supprimerDroit(droit.id),
    onSuccess: () => {
      addToast({ type: 'success', message: 'Droit de prise en charge retire.' })
      void client.invalidateQueries({ queryKey: ['tarification', 'droits', patientId] })
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "Le droit n'a pas pu etre retire.",
      }),
  })

  const lignes = droits.data?.items ?? []

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Prise en charge</CardTitle>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Assurance et mutuelle du patient. Le taux est applique lors de la facturation.
          </p>
        </div>
        {peutEcrire && (
          <Button size="sm" onClick={() => setAjoutOuvert(true)}>
            <Plus className="h-3.5 w-3.5" /> Ajouter un droit
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {!peutLire ? (
          <EmptyState
            icon={WifiOff}
            titre="Acces non autorise"
            description="Votre profil ne peut pas consulter la prise en charge."
          />
        ) : droits.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : droits.isError ? (
          <EmptyState
            icon={WifiOff}
            titre="Prise en charge indisponible"
            description="Les droits n'ont pas pu etre charges."
          >
            <Button variant="outline" onClick={() => void droits.refetch()}>
              <RefreshCw className="h-4 w-4" /> Reessayer
            </Button>
          </EmptyState>
        ) : lignes.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            titre="Aucune prise en charge declaree"
            description={
              peutEcrire
                ? "Ajoutez l'assurance ou la mutuelle du patient : sans elle, la facture ne pourra pas etre ventilee."
                : "Aucun organisme ne couvre ce patient a ce jour."
            }
          />
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>Organisme</TH>
                <TH>Numero de police</TH>
                <TH className="text-right">Taux</TH>
                <TH className="text-center">Priorite</TH>
                <TH>Etat</TH>
                {peutEcrire && <TH className="text-right">Actions</TH>}
              </TRow>
            </THead>
            <TBody>
              {lignes.map((droit) => (
                <TRow key={droit.id}>
                  <TD>
                    <span className="font-medium text-foreground">
                      {droit.organisme_nom ?? droit.organisme_id}
                    </span>
                    {droit.organisme_code && (
                      <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                        {droit.organisme_code}
                      </span>
                    )}
                  </TD>
                  <TD className="font-mono text-xs">{droit.numero_police ?? '-'}</TD>
                  <TD className="text-right font-mono tabular-nums">
                    {droit.taux_prise_en_charge} %
                  </TD>
                  <TD className="text-center tabular-nums">{droit.priorite}</TD>
                  <TD>
                    <StatusBadge tone={droit.actif ? 'success' : 'warning'}>
                      {droit.actif ? 'actif' : 'suspendu'}
                    </StatusBadge>
                  </TD>
                  {peutEcrire && (
                    <TD className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={supprimer.isPending}
                        onClick={() => supprimer.mutate(droit)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        <span className="sr-only">
                          Retirer {droit.organisme_nom ?? 'ce droit'}
                        </span>
                      </Button>
                    </TD>
                  )}
                </TRow>
              ))}
            </TBody>
          </Table>
        )}
      </CardContent>

      {peutEcrire && (
        <DroitModal
          isOpen={ajoutOuvert}
          patientId={patientId}
            organismes={(organismes.data?.items ?? []).map((o) => ({
              value: o.id,
              label: `${o.nom} (${o.code})`,
            }))}
          onClose={() => setAjoutOuvert(false)}
        />
      )}
    </Card>
  )
}

/**
 * Ajout d'un droit. La validation du taux est **ici et pas seulement dans le
 * `min`** : le navigateur autorise un nombre hors bornes, et le serveur
 * refuserait avec un 422 que l'utilisateur ne comprendrait pas.
 */
function DroitModal({
  isOpen,
  patientId,
  organismes,
  onClose,
}: {
  isOpen: boolean
  patientId: string
  organismes: Array<{ value: string; label: string }>
  onClose: () => void
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const [organismeId, setOrganismeId] = useState('')
  const [police, setPolice] = useState('')
  const [taux, setTaux] = useState('')
  const [priorite, setPriorite] = useState('1')
  const [erreurs, setErreurs] = useState<Record<string, string>>({})

  const creer = useMutation({
    mutationFn: () =>
      tarificationApi.creerDroit(patientId, {
        organisme_id: organismeId,
        numero_police: police.trim() || null,
        taux_prise_en_charge: normaliserTaux(taux),
        priorite: Number(priorite) || 1,
        actif: true,
      }),
    onSuccess: () => {
      addToast({ type: 'success', message: 'Droit de prise en charge enregistre.' })
      void client.invalidateQueries({ queryKey: ['tarification', 'droits', patientId] })
      setOrganismeId('')
      setPolice('')
      setTaux('')
      setPriorite('1')
      onClose()
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "Le droit n'a pas pu etre enregistre.",
      }),
  })

  function soumettre() {
    const trouvees: Record<string, string> = {}
    if (!organismeId) trouvees.organismeId = 'Choisissez un organisme.'
    const controleTaux = validerTaux(taux)
    if (!controleTaux.valide) trouvees.taux = controleTaux.message
    const controlePriorite = validerPriorite(priorite)
    if (!controlePriorite.valide) trouvees.priorite = controlePriorite.message
    setErreurs(trouvees)
    if (Object.keys(trouvees).length > 0) return
    creer.mutate()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Ajouter un droit de prise en charge"
      description="Le taux est un pourcentage de 0 a 100 : la part remboursee. Le reste reste a la charge du patient."
    >
      <div className="space-y-4">
        <Select
          label="Organisme *"
          value={organismeId}
          error={erreurs.organismeId}
          onChange={(e) => setOrganismeId(e.target.value)}
          options={[{ value: '', label: 'Choisir un organisme...' }, ...organismes]}
        />
        <Input
          label="Numero de police"
          placeholder="2024-001234"
          value={police}
          onChange={(e) => setPolice(e.target.value)}
          helperText="Facultatif : certains organismes dispensent."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Taux de prise en charge * (%)"
            inputMode="decimal"
            placeholder="70"
            value={taux}
            error={erreurs.taux}
            onChange={(e) => setTaux(e.target.value)}
          />
          <Input
            label="Priorite"
            inputMode="numeric"
            value={priorite}
            error={erreurs.priorite}
            onChange={(e) => setPriorite(e.target.value)}
            helperText="1 = principal."
          />
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>
          Annuler
        </Button>
        <Button onClick={soumettre} disabled={creer.isPending}>
          {creer.isPending ? 'Enregistrement...' : 'Enregistrer'}
        </Button>
      </div>
    </Modal>
  )
}