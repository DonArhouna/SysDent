import { Fragment, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronRight, Download, FileCheck } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge, type StatusTone } from '@/components/ui/status-badge'
import { Table, TableEmpty, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { usePermission } from '@/guards/can'
import { api, telecharger, type PageReponse } from '@/lib/api'
import { dateHeure, messageErreur } from '@/lib/libelles'
import { PERMISSIONS, type EntreeAudit } from '@/lib/plateforme'
import { cn } from '@/lib/utils'
import { toast } from '@/stores/toast-store'

const LIMITE = 50

/** Ton d'une action d'après son nom : les échecs et refus ressortent. */
function tonAction(action: string): StatusTone {
  if (/ECHOU|ECHEC|REFUS|BLOQUE|VERROUILL/.test(action)) return 'danger'
  if (/SUPPRIM|RESILI|DESACTIV|SUSPEN|REVOQ|REINITIALIS/.test(action)) return 'warning'
  if (/CREE|CREATION|ACTIV|LOGIN/.test(action)) return 'success'
  return 'neutral'
}

function Json({ titre, valeur }: { titre: string; valeur: unknown }) {
  if (valeur === null || valeur === undefined) return null
  return (
    <div className="min-w-0 flex-1">
      <p className="mb-1 text-xs font-semibold text-muted-foreground">{titre}</p>
      <pre className="max-h-64 overflow-auto rounded-lg bg-muted/60 p-3 text-xs">{JSON.stringify(valeur, null, 2)}</pre>
    </div>
  )
}

/**
 * Journal d'audit de la plateforme : qui a fait quoi, quand, d'où, et pourquoi.
 *
 * Le journal est **immuable** côté base (ni UPDATE, ni TRUNCATE) : cet écran ne
 * propose donc aucune action, seulement la lecture et l'export.
 */
export function AuditPage() {
  const peutExporter = usePermission(PERMISSIONS.auditExporter)
  const [filtres, setFiltres] = useState({ acteur_email: '', action: '', type_cible: '', tenant_id: '', debut: '', fin: '' })
  const [page, setPage] = useState(1)
  const [ouverte, setOuverte] = useState<string | null>(null)

  const params = Object.fromEntries(Object.entries(filtres).map(([k, v]) => [k, v.trim()]))

  const requete = useQuery({
    queryKey: ['audit', params, page],
    queryFn: ({ signal }) =>
      api.get<PageReponse<EntreeAudit>>('/platform/audit', { params: { ...params, page, limit: LIMITE }, signal }),
    placeholderData: (precedent) => precedent,
  })

  const exporter = useMutation({
    mutationFn: () => {
      const { type_cible: _ignore, ...paramsExport } = params
      return telecharger('/platform/audit/export', `audit-plateforme-${new Date().toISOString().slice(0, 10)}.csv`, paramsExport)
    },
    onError: (e) => toast.error(messageErreur(e)),
  })

  const changer = (cle: keyof typeof filtres, valeur: string) => {
    setFiltres((f) => ({ ...f, [cle]: valeur }))
    setPage(1)
  }

  const entrees = requete.data?.items ?? []

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader titre="Journal d'audit" sousTitre="Toutes les actions effectuées sur la plateforme." onRefresh={() => void requete.refetch()}>
          {peutExporter && (
            <Button variant="outline" onClick={() => exporter.mutate()} disabled={exporter.isPending}>
              <Download aria-hidden />
              {exporter.isPending ? 'Export…' : 'Exporter en CSV'}
            </Button>
          )}
        </PageHeader>

        <Card className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6">
          <Input label="Acteur (e-mail)" value={filtres.acteur_email} onChange={(e) => changer('acteur_email', e.target.value)} />
          <Input label="Action" placeholder="ex. PLATFORM_LOGIN" value={filtres.action} onChange={(e) => changer('action', e.target.value)} />
          <Input label="Type de cible" placeholder="ex. AUTH" value={filtres.type_cible} onChange={(e) => changer('type_cible', e.target.value)} />
          <Input label="Cabinet (ID)" value={filtres.tenant_id} onChange={(e) => changer('tenant_id', e.target.value)} />
          <Input label="Du" type="date" value={filtres.debut} onChange={(e) => changer('debut', e.target.value)} />
          <Input label="Au" type="date" value={filtres.fin} onChange={(e) => changer('fin', e.target.value)} />
        </Card>

        <Card className="overflow-hidden p-0">
          {requete.isError ? (
            <div className="space-y-3 p-6 text-sm">
              <p role="alert" className="text-danger">{messageErreur(requete.error)}</p>
              <Button variant="outline" size="sm" onClick={() => void requete.refetch()}>
                Réessayer
              </Button>
            </div>
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH className="w-8" />
                  <TH>Date</TH>
                  <TH>Action</TH>
                  <TH>Acteur</TH>
                  <TH>Cible</TH>
                  <TH>Motif</TH>
                </TRow>
              </THead>
              <TBody>
                {requete.isPending ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <TRow key={i}>
                      <TD colSpan={6}>
                        <Skeleton className="h-5 w-full" />
                      </TD>
                    </TRow>
                  ))
                ) : entrees.length === 0 ? (
                  <TRow>
                    <TD colSpan={6}>
                      <TableEmpty>
                        <span className="inline-flex items-center gap-2">
                          <FileCheck className="h-4 w-4" aria-hidden />
                          Aucune entrée pour ces filtres.
                        </span>
                      </TableEmpty>
                    </TD>
                  </TRow>
                ) : (
                  entrees.map((e) => {
                    const deplie = ouverte === e.id
                    return (
                      <Fragment key={e.id}>
                        <TRow className="cursor-pointer" onClick={() => setOuverte(deplie ? null : e.id)} aria-expanded={deplie}>
                          <TD>
                            <ChevronRight className={cn('h-4 w-4 text-muted-foreground transition-transform', deplie && 'rotate-90')} aria-hidden />
                          </TD>
                          <TD className="whitespace-nowrap text-muted-foreground">{dateHeure(e.horodatage)}</TD>
                          <TD>
                            <StatusBadge tone={tonAction(e.action)}>{e.action}</StatusBadge>
                          </TD>
                          <TD className="max-w-[220px] truncate">{e.acteur_email ?? '—'}</TD>
                          <TD className="text-muted-foreground">{e.type_cible ?? '—'}</TD>
                          <TD className="max-w-[260px] truncate text-muted-foreground">{e.motif ?? '—'}</TD>
                        </TRow>
                        {deplie && (
                          <TRow className="bg-muted/20 hover:bg-muted/20">
                            <TD />
                            <TD colSpan={5}>
                              <div className="space-y-3 py-2">
                                <dl className="grid gap-2 text-xs sm:grid-cols-3">
                                  <div><dt className="text-muted-foreground">Adresse IP</dt><dd className="font-mono">{e.ip_address ?? '—'}</dd></div>
                                  <div><dt className="text-muted-foreground">Cible</dt><dd className="font-mono break-all">{e.cible_id ?? '—'}</dd></div>
                                  <div><dt className="text-muted-foreground">Cabinet</dt><dd className="font-mono break-all">{e.tenant_id ?? '—'}</dd></div>
                                  <div className="sm:col-span-3"><dt className="text-muted-foreground">Navigateur</dt><dd className="break-all">{e.user_agent ?? '—'}</dd></div>
                                </dl>
                                {e.motif && <p className="text-sm"><span className="text-muted-foreground">Motif : </span>{e.motif}</p>}
                                <div className="flex flex-col gap-3 lg:flex-row">
                                  <Json titre="Avant" valeur={e.avant} />
                                  <Json titre="Après" valeur={e.apres} />
                                </div>
                              </div>
                            </TD>
                          </TRow>
                        )}
                      </Fragment>
                    )
                  })
                )}
              </TBody>
            </Table>
          )}
        </Card>

        <Pagination meta={requete.data?.meta} page={page} limit={LIMITE} onPageChange={setPage} libelle="entrées" onPageHorsBornes={() => setPage(1)} />
      </div>
    </AppShell>
  )
}
