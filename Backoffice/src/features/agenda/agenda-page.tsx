import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { CalendarDays, ChevronLeft, ChevronRight, List, Plus } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TableEmpty, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { usePermission } from '@/guards/can'
import { api, type PageReponse } from '@/lib/api'
import { date, heure, messageErreur, statutRendezVous, typeRendezVous, TYPES_RENDEZ_VOUS } from '@/lib/libelles'
import { PERMISSIONS, type RendezVous } from '@/lib/plateforme'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'
import { Cible, DetailRendezVous } from './detail-rendez-vous'
import { RendezVousDrawer } from './rendez-vous-drawer'

const JOURS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

function lundi(d: Date): Date {
  const r = new Date(d)
  r.setHours(0, 0, 0, 0)
  r.setDate(r.getDate() - ((r.getDay() + 6) % 7))
  return r
}

function ajouterJours(d: Date, n: number): Date {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

function cleJour(d: Date): string {
  const deux = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`
}

/**
 * Agenda de l'équipe éditrice : rendez-vous avec les cabinets et les prospects.
 *
 * **Aucun rendez-vous de patient ici** : ceux-là appartiennent au cabinet et
 * restent dans sa base. Vue semaine par défaut, vue liste pour les recherches.
 */
export function AgendaPage() {
  const moi = useAuthStore((e) => e.profil)
  const peutEcrire = usePermission(PERMISSIONS.agendaEcrire)
  const [params, setParams] = useSearchParams()

  const [vue, setVue] = useState<'semaine' | 'liste'>('semaine')
  const [debutSemaine, setDebutSemaine] = useState(() => lundi(new Date()))
  const [mesRdv, setMesRdv] = useState(false)
  const [type, setType] = useState('')
  const [annules, setAnnules] = useState(false)
  const [selection, setSelection] = useState<RendezVous | null>(null)
  const [edition, setEdition] = useState<{ rdv?: RendezVous; date?: string } | null>(
    // La palette de commandes ouvre directement le formulaire (`?nouveau=1`).
    params.get('nouveau') ? {} : null,
  )

  const finSemaine = ajouterJours(debutSemaine, 7)
  const periode =
    vue === 'semaine'
      ? { du: debutSemaine.toISOString(), au: finSemaine.toISOString() }
      : { du: lundi(new Date()).toISOString() }

  const requete = useQuery({
    queryKey: ['agenda', vue, periode, mesRdv, type],
    queryFn: () =>
      api.get<PageReponse<RendezVous>>('/platform/rendez-vous', {
        params: { ...periode, agent_id: mesRdv ? moi?.id : undefined, type_rdv: type, limit: 100 },
      }),
  })

  const rdvs = (requete.data?.items ?? []).filter((r) => annules || r.statut !== 'ANNULE')
  const parJour = useMemo(() => {
    const m = new Map<string, RendezVous[]>()
    for (const r of rdvs) {
      const k = cleJour(new Date(r.debut))
      m.set(k, [...(m.get(k) ?? []), r])
    }
    return m
  }, [rdvs])

  const fermerEdition = () => {
    setEdition(null)
    if (params.get('nouveau')) setParams({}, { replace: true })
  }

  const aujourdhui = cleJour(new Date())
  const libellePeriode = `${date(debutSemaine.toISOString())} – ${date(ajouterJours(debutSemaine, 6).toISOString())}`

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader titre="Agenda" sousTitre="Rendez-vous de l'équipe avec les cabinets et les prospects." onRefresh={() => void requete.refetch()}>
          {peutEcrire && (
            <Button onClick={() => setEdition({})}>
              <Plus aria-hidden />
              Nouveau rendez-vous
            </Button>
          )}
        </PageHeader>

        <Card className="flex flex-wrap items-center gap-3 p-3">
          <div role="tablist" aria-label="Affichage" className="inline-flex rounded-xl bg-muted p-1">
            {([['semaine', CalendarDays, 'Semaine'], ['liste', List, 'À venir']] as const).map(([v, Icone, libelle]) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={vue === v}
                onClick={() => setVue(v)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                  vue === v ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Icone className="h-4 w-4" aria-hidden />
                {libelle}
              </button>
            ))}
          </div>

          {vue === 'semaine' && (
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" aria-label="Semaine précédente" onClick={() => setDebutSemaine((d) => ajouterJours(d, -7))}>
                <ChevronLeft aria-hidden />
              </Button>
              <Button variant="outline" size="sm" onClick={() => setDebutSemaine(lundi(new Date()))}>
                Aujourd'hui
              </Button>
              <Button variant="ghost" size="icon" aria-label="Semaine suivante" onClick={() => setDebutSemaine((d) => ajouterJours(d, 7))}>
                <ChevronRight aria-hidden />
              </Button>
              <span className="ml-2 text-sm font-medium">{libellePeriode}</span>
            </div>
          )}

          <div className="ml-auto flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={mesRdv} onChange={(e) => setMesRdv(e.target.checked)} />
              Mes rendez-vous
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={annules} onChange={(e) => setAnnules(e.target.checked)} />
              Afficher les annulés
            </label>
            <div className="w-44">
              <Select aria-label="Filtrer par type" value={type} onChange={(e) => setType(e.target.value)} options={[{ value: '', label: 'Tous les types' }, ...TYPES_RENDEZ_VOUS]} />
            </div>
          </div>
        </Card>

        {requete.isError ? (
          <Card className="space-y-3 p-6">
            <p role="alert" className="text-sm text-danger">{messageErreur(requete.error)}</p>
            <Button variant="outline" size="sm" onClick={() => void requete.refetch()}>Réessayer</Button>
          </Card>
        ) : requete.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : vue === 'semaine' ? (
          <div className="grid gap-3 md:grid-cols-7">
            {JOURS.map((nom, i) => {
              const jour = ajouterJours(debutSemaine, i)
              const k = cleJour(jour)
              const liste = parJour.get(k) ?? []
              return (
                <Card key={k} className={cn('flex min-h-40 flex-col p-2', k === aujourdhui && 'ring-2 ring-primary/40')}>
                  <div className="mb-2 flex items-center justify-between px-1">
                    <span className={cn('text-xs font-semibold uppercase tracking-wide', k === aujourdhui ? 'text-primary' : 'text-muted-foreground')}>
                      {nom} {jour.getDate()}
                    </span>
                    {peutEcrire && (
                      <button
                        type="button"
                        aria-label={`Nouveau rendez-vous le ${date(jour.toISOString())}`}
                        onClick={() => setEdition({ date: k })}
                        className="rounded-md p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <Plus className="h-3.5 w-3.5" aria-hidden />
                      </button>
                    )}
                  </div>
                  <ul className="flex-1 space-y-1.5">
                    {liste.map((r) => {
                      const t = typeRendezVous(r.type_rdv)
                      return (
                        <li key={r.id}>
                          <button
                            type="button"
                            onClick={() => setSelection(r)}
                            className={cn(
                              'w-full rounded-lg border border-border bg-background/60 p-2 text-left text-xs transition-colors hover:border-primary/40 hover:bg-primary/5',
                              r.statut === 'ANNULE' && 'opacity-50 line-through',
                            )}
                          >
                            <span className="block font-semibold">{heure(r.debut)} · {r.titre}</span>
                            <span className="block truncate text-muted-foreground">{r.tenant_nom ?? r.prospect_nom}</span>
                            <span className="mt-1 flex flex-wrap gap-1">
                              <StatusBadge tone={t.ton}>{t.texte}</StatusBadge>
                            </span>
                          </button>
                        </li>
                      )
                    })}
                    {liste.length === 0 && <li className="px-1 text-xs text-muted-foreground/60">—</li>}
                  </ul>
                </Card>
              )
            })}
          </div>
        ) : (
          <Card className="overflow-hidden p-0">
            <Table>
              <THead>
                <TRow>
                  <TH>Date</TH>
                  <TH>Objet</TH>
                  <TH>Avec</TH>
                  <TH>Type</TH>
                  <TH>Agent</TH>
                  <TH>Statut</TH>
                </TRow>
              </THead>
              <TBody>
                {rdvs.length === 0 ? (
                  <TRow>
                    <TD colSpan={6}><TableEmpty>Aucun rendez-vous à venir.</TableEmpty></TD>
                  </TRow>
                ) : (
                  rdvs.map((r) => (
                    <TRow key={r.id} className="cursor-pointer" onClick={() => setSelection(r)}>
                      <TD className="whitespace-nowrap">{date(r.debut)} · {heure(r.debut)}</TD>
                      <TD className="font-medium">{r.titre}</TD>
                      <TD onClick={(e) => e.stopPropagation()}><Cible rdv={r} /></TD>
                      <TD><StatusBadge tone={typeRendezVous(r.type_rdv).ton}>{typeRendezVous(r.type_rdv).texte}</StatusBadge></TD>
                      <TD className="text-muted-foreground">{r.agent_nom ?? '—'}</TD>
                      <TD><StatusBadge tone={statutRendezVous(r.statut).ton}>{statutRendezVous(r.statut).texte}</StatusBadge></TD>
                    </TRow>
                  ))
                )}
              </TBody>
            </Table>
          </Card>
        )}
      </div>

      {selection && (
        <DetailRendezVous
          rdv={selection}
          onClose={() => setSelection(null)}
          onModifier={() => {
            setEdition({ rdv: selection })
            setSelection(null)
          }}
        />
      )}
      {edition && <RendezVousDrawer rdv={edition.rdv} initial={{ date: edition.date }} onClose={fermerEdition} />}
    </AppShell>
  )
}
