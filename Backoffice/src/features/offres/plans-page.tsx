import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, History, Minus, Pencil, Plus, Power, PowerOff, Star } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Modal } from '@/components/ui/modal'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { dateHeure, libellePeriodicite, messageErreur, montant } from '@/lib/libelles'
import { PERMISSIONS, type Plan, type RevisionPlan } from '@/lib/plateforme'
import { cn } from '@/lib/utils'
import { toast } from '@/stores/toast-store'
import { FONCTIONNALITES, PlanDrawer, QUOTAS } from './plan-drawer'

function valeurQuota(cle: string, v: unknown): string {
  if (typeof v !== 'number') return 'Illimité'
  if (cle === 'stockage_octets') return `${Math.round((v / 1024 ** 3) * 10) / 10} Go`
  return v.toLocaleString('fr-FR')
}

/**
 * Catalogue des offres.
 *
 * Désactiver un plan le retire des nouvelles souscriptions ; les cabinets déjà
 * abonnés le gardent tel qu'il était à leur souscription.
 */
export function PlansPage() {
  const client = useQueryClient()
  const peutEcrire = usePermission(PERMISSIONS.plansEcrire)
  const [edition, setEdition] = useState<Plan | null | 'nouveau'>(null)
  const [bascule, setBascule] = useState<Plan | null>(null)
  const [historique, setHistorique] = useState<Plan | null>(null)

  const plans = useQuery({ queryKey: ['plans', { tous: true }], queryFn: () => api.get<ApiReponse<Plan[]>>('/platform/plans') })
  const revisions = useQuery({
    queryKey: ['plans', historique?.id, 'revisions'],
    queryFn: () => api.get<ApiReponse<RevisionPlan[]>>(`/platform/plans/${historique?.id}/revisions`),
    enabled: historique !== null,
  })

  const basculer = useMutation({
    mutationFn: ({ plan, motif }: { plan: Plan; motif: string }) => api.patch(`/platform/plans/${plan.id}`, { actif: !plan.actif, motif }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['plans'] })
      toast.success('Plan mis à jour.')
    },
  })

  const liste = [...(plans.data?.data ?? [])].sort((a, b) => Number(b.actif) - Number(a.actif) || Number(a.prix) - Number(b.prix))

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader titre="Plans" sousTitre="Offres proposées aux cabinets." onRefresh={() => void plans.refetch()}>
          {peutEcrire && (
            <Button onClick={() => setEdition('nouveau')}>
              <Plus aria-hidden />
              Nouveau plan
            </Button>
          )}
        </PageHeader>

        {plans.isPending ? (
          <div className="grid gap-4 md:grid-cols-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-80 w-full" />)}
          </div>
        ) : plans.isError ? (
          <Card className="space-y-3 p-6">
            <p role="alert" className="text-sm text-danger">{messageErreur(plans.error)}</p>
            <Button variant="outline" size="sm" onClick={() => void plans.refetch()}>Réessayer</Button>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {liste.map((p) => (
              <Card key={p.id} className={cn('flex flex-col', !p.actif && 'opacity-70')}>
                <CardHeader className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-lg">
                        {p.nom}
                        {p.plan_defaut && <Star className="h-4 w-4 fill-warning text-warning" aria-label="Plan par défaut" />}
                      </CardTitle>
                      <p className="font-mono text-xs text-muted-foreground">{p.code} · v{p.version}</p>
                    </div>
                    <StatusBadge tone={p.actif ? 'success' : 'neutral'}>{p.actif ? 'Actif' : 'Inactif'}</StatusBadge>
                  </div>
                  <p className="text-2xl font-bold">
                    {montant(p.prix, p.devise)}
                    <span className="ml-1 text-sm font-normal text-muted-foreground">/ {libellePeriodicite(p.periodicite).toLowerCase()}</span>
                  </p>
                  {p.description && <p className="text-sm text-muted-foreground">{p.description}</p>}
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-4">
                  <dl className="space-y-1.5 text-sm">
                    {QUOTAS.map(({ cle, libelle }) => (
                      <div key={cle} className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">{libelle.replace(' (Go)', '')}</dt>
                        <dd className="font-medium">{valeurQuota(cle, (p.quotas as Record<string, unknown>)[cle])}</dd>
                      </div>
                    ))}
                  </dl>
                  <ul className="space-y-1 text-sm">
                    {FONCTIONNALITES.map(({ cle, libelle }) => {
                      const oui = Boolean((p.features as Record<string, unknown>)[cle])
                      return (
                        <li key={cle} className={cn('flex items-center gap-2', !oui && 'text-muted-foreground')}>
                          {oui ? <Check className="h-4 w-4 text-success" aria-hidden /> : <Minus className="h-4 w-4" aria-hidden />}
                          {libelle}
                        </li>
                      )
                    })}
                  </ul>
                  <p className="text-xs text-muted-foreground">{p.jours_essai} jours d'essai</p>
                  <div className="mt-auto flex flex-wrap gap-2 border-t border-border pt-3">
                    <Button size="sm" variant="ghost" onClick={() => setHistorique(p)}>
                      <History aria-hidden />
                      Versions
                    </Button>
                    {peutEcrire && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => setEdition(p)}>
                          <Pencil aria-hidden />
                          Modifier
                        </Button>
                        {!p.plan_defaut && (
                          <Button size="sm" variant="ghost" onClick={() => setBascule(p)}>
                            {p.actif ? <PowerOff aria-hidden /> : <Power aria-hidden />}
                            {p.actif ? 'Désactiver' : 'Activer'}
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {edition && <PlanDrawer plan={edition === 'nouveau' ? null : edition} onClose={() => setEdition(null)} />}

      {bascule && (
        <MotifDialog
          open
          onClose={() => setBascule(null)}
          titre={`${bascule.actif ? 'Désactiver' : 'Activer'} le plan ${bascule.nom}`}
          description={bascule.actif ? "Il ne sera plus proposé aux nouveaux cabinets. Les abonnés actuels le conservent." : 'Il sera de nouveau proposé aux cabinets.'}
          libelleConfirmer={bascule.actif ? 'Désactiver' : 'Activer'}
          onConfirm={(motif) => basculer.mutateAsync({ plan: bascule, motif })}
        />
      )}

      <Modal open={historique !== null} onClose={() => setHistorique(null)} title={`Versions de ${historique?.nom ?? ''}`} maxWidth="lg">
        {revisions.isPending ? (
          <Skeleton className="h-32 w-full" />
        ) : revisions.isError ? (
          <p className="text-sm text-danger">{messageErreur(revisions.error)}</p>
        ) : (revisions.data?.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune version antérieure.</p>
        ) : (
          <ol className="max-h-[60vh] space-y-3 overflow-auto">
            {[...(revisions.data?.data ?? [])].sort((a, b) => b.version - a.version).map((r) => (
              <li key={r.version} className="rounded-xl border border-border p-3 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  <StatusBadge tone="info">v{r.version}</StatusBadge>
                  <span className="text-muted-foreground">{dateHeure(r.created_at)} · {r.auteur}</span>
                </p>
                {r.motif && <p className="mt-1">{r.motif}</p>}
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-muted-foreground">Contenu de la version</summary>
                  <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted/60 p-2 text-[11px]">{JSON.stringify(r.instantane, null, 2)}</pre>
                </details>
              </li>
            ))}
          </ol>
        )}
      </Modal>
    </AppShell>
  )
}
