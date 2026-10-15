import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, XCircle } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { api, type ApiReponse } from '@/lib/api'
import { dateHeure, messageErreur } from '@/lib/libelles'
import type { ControleSante, RapportSante } from '@/lib/plateforme'
import { cn } from '@/lib/utils'

const NOMS: Record<string, { titre: string; description: string }> = {
  base_plateforme: { titre: 'Base plateforme', description: 'Comptes, abonnements, journal de la console.' },
  base_master: { titre: 'Base master', description: 'Registre des cabinets et routage des connexions.' },
  files_clients: { titre: 'Bases des cabinets', description: 'Répartition des cabinets par état technique.' },
  bases_absentes: { titre: 'Bases manquantes', description: 'Cabinets inscrits au registre dont la base n’existe plus.' },
  schemas_tenants: { titre: 'Schémas des cabinets', description: 'Version de schéma de chaque base cliente.' },
  migrations_par_tenant: { titre: 'Migrations', description: 'Bases restées en retard sur la dernière migration.' },
  catalogue: { titre: 'Catalogue des offres', description: 'Présence d’un plan par défaut.' },
  jobs_planifies: { titre: 'Tâches planifiées', description: 'Exécution des tâches de fond.' },
}

const CLES_TECHNIQUES = new Set(['composant', 'ok', 'detail'])

/** Valeur d'un champ de contrôle, lisible sans connaître sa forme exacte. */
function Valeur({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <>—</>
  if (typeof v === 'boolean') return <>{v ? 'oui' : 'non'}</>
  if (typeof v === 'number' || typeof v === 'string') return <>{String(v)}</>
  if (Array.isArray(v) && v.length === 0) return <>aucun</>
  if (typeof v === 'object' && !Array.isArray(v) && Object.values(v).every((x) => typeof x !== 'object')) {
    return (
      <span className="flex flex-wrap gap-1">
        {Object.entries(v as Record<string, unknown>).map(([k, x]) => (
          <StatusBadge key={k} tone="neutral">{`${k} : ${String(x)}`}</StatusBadge>
        ))}
      </span>
    )
  }
  return <pre className="max-h-40 overflow-auto rounded bg-muted/60 p-2 text-[11px]">{JSON.stringify(v, null, 2)}</pre>
}

function CarteControle({ c }: { c: ControleSante }) {
  const nom = NOMS[c.composant] ?? { titre: c.composant, description: '' }
  const extras = Object.entries(c).filter(([k]) => !CLES_TECHNIQUES.has(k))
  return (
    <Card className={cn('border-l-4', c.ok ? 'border-l-success' : 'border-l-danger')}>
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-2">
        <div>
          <CardTitle className="text-base">{nom.titre}</CardTitle>
          {nom.description && <p className="mt-0.5 text-xs text-muted-foreground">{nom.description}</p>}
        </div>
        {c.ok ? (
          <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-label="Opérationnel" />
        ) : (
          <XCircle className="h-5 w-5 shrink-0 text-danger" aria-label="En panne" />
        )}
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {c.detail && <p className="rounded-lg bg-danger/10 p-2 text-xs text-danger">{c.detail}</p>}
        {extras.length > 0 && (
          <dl className="space-y-1.5">
            {extras.map(([k, v]) => (
              <div key={k} className="flex flex-wrap items-start justify-between gap-2">
                <dt className="text-xs text-muted-foreground">{k.replace(/_/g, ' ')}</dt>
                <dd className="text-xs font-medium">
                  <Valeur v={v} />
                </dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * État de santé de la plateforme.
 *
 * Chaque contrôle s'affiche **avec son détail** : un voyant vert global qui
 * masquerait une base de cabinet manquante est exactement le défaut que cette
 * page doit révéler.
 */
export function SantePage() {
  const requete = useQuery({
    queryKey: ['sante'],
    queryFn: () => api.get<ApiReponse<RapportSante>>('/platform/sante'),
    refetchInterval: 60_000,
  })
  const rapport = requete.data?.data

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          titre="Santé du système"
          sousTitre={rapport ? `Vérifié le ${dateHeure(rapport.verifie_le)} · actualisation automatique chaque minute` : 'Contrôles des bases et des services.'}
          onRefresh={() => void requete.refetch()}
        />

        {requete.isPending ? (
          <Skeleton className="h-64 w-full" />
        ) : requete.isError ? (
          <Card className="space-y-3 p-6">
            <p role="alert" className="text-sm text-danger">{messageErreur(requete.error)}</p>
            <Button variant="outline" size="sm" onClick={() => void requete.refetch()}>
              Réessayer
            </Button>
          </Card>
        ) : rapport ? (
          <>
            <Card
              className={cn(
                'flex items-center gap-4 p-5',
                rapport.statut === 'ok' ? 'bg-success/5' : 'bg-danger/5',
              )}
            >
              {rapport.statut === 'ok' ? (
                <CheckCircle2 className="h-8 w-8 text-success" aria-hidden />
              ) : (
                <XCircle className="h-8 w-8 text-danger" aria-hidden />
              )}
              <div>
                <p className="text-lg font-semibold">
                  {rapport.statut === 'ok' ? 'Tous les systèmes sont opérationnels' : 'Fonctionnement dégradé'}
                </p>
                <p className="text-sm text-muted-foreground">
                  {rapport.controles.filter((c) => c.ok).length} / {rapport.controles.length} contrôles au vert
                  {rapport.en_panne.length > 0 && ` · en panne : ${rapport.en_panne.map((n) => NOMS[n]?.titre ?? n).join(', ')}`}
                </p>
              </div>
            </Card>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {[...rapport.controles].sort((a, b) => Number(a.ok) - Number(b.ok)).map((c) => (
                <CarteControle key={c.composant} c={c} />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  )
}
