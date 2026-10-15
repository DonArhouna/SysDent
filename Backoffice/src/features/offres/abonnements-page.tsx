import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Repeat } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TableEmpty, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { date, messageErreur, montant, statutAbonnement } from '@/lib/libelles'
import { PERMISSIONS, type Abonnement, type Plan } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'
import { useNomsCabinets } from './noms-cabinets'

/**
 * Abonnements de tous les cabinets.
 *
 * Le plan affiché est le plan **figé** à la souscription (`plan_fige`) : c'est
 * lui qui fait foi pour la facturation, pas la version courante du catalogue.
 */
export function AbonnementsPage() {
  const client = useQueryClient()
  const peutChanger = usePermission(PERMISSIONS.abonnementsEcrire)
  const { nom } = useNomsCabinets()
  const [statut, setStatut] = useState('')
  const [cible, setCible] = useState<Abonnement | null>(null)
  const [planChoisi, setPlanChoisi] = useState('')

  const requete = useQuery({
    queryKey: ['abonnements', { statut }],
    queryFn: () => api.get<ApiReponse<Abonnement[]>>('/platform/subscriptions', { params: { statut } }),
  })
  const plans = useQuery({
    queryKey: ['plans', { actifs: true }],
    queryFn: () => api.get<ApiReponse<Plan[]>>('/platform/plans', { params: { actif_seulement: true } }),
    enabled: cible !== null,
  })

  const changer = useMutation({
    mutationFn: ({ id, motif }: { id: string; motif: string }) => {
      if (!planChoisi) throw new Error('Choisissez un plan.')
      return api.post(`/platform/subscriptions/${id}/plan`, { plan_code: planChoisi, motif })
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['abonnements'] })
      void client.invalidateQueries({ queryKey: ['cabinet'] })
      toast.success('Plan modifié.')
    },
  })

  const liste = requete.data?.data ?? []

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader titre="Abonnements" sousTitre="Plan souscrit par chaque cabinet." onRefresh={() => void requete.refetch()}>
          <div className="w-48">
            <Select
              aria-label="Filtrer par statut"
              value={statut}
              onChange={(e) => setStatut(e.target.value)}
              options={[
                { value: '', label: 'Tous les statuts' },
                { value: 'ESSAI', label: 'Essai' },
                { value: 'ACTIF', label: 'Actif' },
                { value: 'SUSPENDU', label: 'Suspendu' },
                { value: 'EXPIRE', label: 'Expiré' },
                { value: 'RESILIE', label: 'Résilié' },
              ]}
            />
          </div>
        </PageHeader>

        <Card className="overflow-hidden p-0">
          {requete.isError ? (
            <div className="space-y-3 p-6 text-sm">
              <p role="alert" className="text-danger">{messageErreur(requete.error)}</p>
              <Button variant="outline" size="sm" onClick={() => void requete.refetch()}>Réessayer</Button>
            </div>
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH>Numéro</TH>
                  <TH>Cabinet</TH>
                  <TH>Plan</TH>
                  <TH>Statut</TH>
                  <TH>Début</TH>
                  <TH>Fin d'essai</TH>
                  <TH>Renouvellement</TH>
                  {peutChanger && <TH />}
                </TRow>
              </THead>
              <TBody>
                {requete.isPending ? (
                  <TRow>
                    <TD colSpan={8}><Skeleton className="h-20 w-full" /></TD>
                  </TRow>
                ) : liste.length === 0 ? (
                  <TRow>
                    <TD colSpan={8}><TableEmpty>Aucun abonnement.</TableEmpty></TD>
                  </TRow>
                ) : (
                  liste.map((a) => {
                    const s = statutAbonnement(a.statut)
                    const fige = a.plan_fige as { prix?: string | number; devise?: string }
                    return (
                      <TRow key={a.id}>
                        <TD className="font-mono text-xs">{a.numero}</TD>
                        <TD>
                          <Link to={`/cabinets/${a.tenant_id}`} className="font-medium hover:text-primary hover:underline">
                            {nom(a.tenant_id)}
                          </Link>
                        </TD>
                        <TD>
                          <span className="block">{a.plan_nom ?? a.plan ?? '—'}</span>
                          {fige?.prix !== undefined && (
                            <span className="text-xs text-muted-foreground">{montant(fige.prix, fige.devise)}</span>
                          )}
                        </TD>
                        <TD><StatusBadge tone={s.ton}>{s.texte}</StatusBadge></TD>
                        <TD className="text-muted-foreground">{date(a.date_debut)}</TD>
                        <TD className="text-muted-foreground">{date(a.date_fin_essai)}</TD>
                        <TD className="text-muted-foreground">{a.renouvellement_auto ? 'Automatique' : 'Manuel'}</TD>
                        {peutChanger && (
                          <TD className="text-right">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                setPlanChoisi('')
                                setCible(a)
                              }}
                            >
                              <Repeat aria-hidden />
                              Changer de plan
                            </Button>
                          </TD>
                        )}
                      </TRow>
                    )
                  })
                )}
              </TBody>
            </Table>
          )}
        </Card>
      </div>

      {cible && (
        <MotifDialog
          open
          onClose={() => setCible(null)}
          titre={`Changer le plan de ${nom(cible.tenant_id)}`}
          description={`Plan actuel : ${cible.plan_nom ?? cible.plan ?? '—'}.`}
          libelleConfirmer="Changer de plan"
          onConfirm={(motif) => changer.mutateAsync({ id: cible.id, motif })}
        >
          <Select
            label="Nouveau plan"
            required
            value={planChoisi}
            onChange={(e) => setPlanChoisi(e.target.value)}
            options={[
              { value: '', label: plans.isPending ? 'Chargement…' : 'Choisir un plan' },
              ...(plans.data?.data ?? [])
                .filter((p) => p.code !== cible.plan)
                .map((p) => ({ value: p.code, label: `${p.nom} — ${montant(p.prix, p.devise)}` })),
            ]}
          />
        </MotifDialog>
      )}
    </AppShell>
  )
}
