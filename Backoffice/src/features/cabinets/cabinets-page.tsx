import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Building2, PauseCircle, PlayCircle, Plus, Search } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TableEmpty, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { usePermission } from '@/guards/can'
import { api, type PageReponse } from '@/lib/api'
import { date, messageErreur, statutCabinet } from '@/lib/libelles'
import { PERMISSIONS, type Cabinet } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'
import { CreerCabinetDrawer } from './creer-cabinet-drawer'
import { ApercuLogo } from './logo-cabinet'

const LIMITE = 20

const FILTRES_STATUT = [
  { value: '', label: 'Tous les statuts' },
  { value: 'ESSAI', label: 'Essai' },
  { value: 'ACTIF', label: 'Actif' },
  { value: 'SUSPENDU', label: 'Désactivé' },
  { value: 'RESILIE', label: 'Résilié' },
]

/**
 * Registre des cabinets : recherche, filtre de statut, pagination serveur.
 *
 * Les archivés sont exclus par défaut (comportement du backend) ; une case les
 * affiche seuls, pour qu'un cabinet archivé ne se confonde jamais avec un actif.
 */
export function CabinetsPage() {
  const client = useQueryClient()
  const peutCreer = usePermission(PERMISSIONS.cabinetsCreer)
  const peutDesactiver = usePermission(PERMISSIONS.cabinetsSuspendre)
  const peutReactiver = usePermission(PERMISSIONS.cabinetsActiver)
  const [bascule, setBascule] = useState<{ cabinet: Cabinet; desactiver: boolean } | null>(null)

  const basculer = useMutation({
    mutationFn: ({ cabinet, desactiver, motif }: { cabinet: Cabinet; desactiver: boolean; motif: string }) =>
      api.post(`/platform/tenants/${cabinet.tenant_id}/${desactiver ? 'suspension' : 'reactivation'}`, { motif }),
    onSuccess: (_r, { cabinet, desactiver }) => {
      void client.invalidateQueries({ queryKey: ['cabinets'] })
      void client.invalidateQueries({ queryKey: ['cabinet', cabinet.tenant_id] })
      toast.success(`${cabinet.nom} ${desactiver ? 'désactivé' : 'réactivé'}.`)
    },
  })
  const [q, setQ] = useState('')
  const [statut, setStatut] = useState('')
  const [archives, setArchives] = useState(false)
  const [page, setPage] = useState(1)
  const [creation, setCreation] = useState(false)

  const requete = useQuery({
    queryKey: ['cabinets', { q, statut, archives, page }],
    queryFn: ({ signal }) =>
      api.get<PageReponse<Cabinet>>('/platform/tenants', {
        params: { q: q.trim(), statut, archive: archives ? true : undefined, page, limit: LIMITE },
        signal,
      }),
    placeholderData: (precedent) => precedent,
  })

  const cabinets = requete.data?.items ?? []

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          titre="Cabinets"
          sousTitre="Registre de tous les cabinets clients de la plateforme."
          onRefresh={() => void requete.refetch()}
        >
          {peutCreer && (
            <Button onClick={() => setCreation(true)}>
              <Plus aria-hidden />
              Nouveau cabinet
            </Button>
          )}
        </PageHeader>

        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="relative min-w-[220px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                aria-label="Rechercher un cabinet"
                placeholder="Nom, e-mail, NINEA…"
                className="pl-9"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value)
                  setPage(1)
                }}
              />
            </div>
            <div className="w-48">
              <Select
                aria-label="Filtrer par statut"
                options={FILTRES_STATUT}
                value={statut}
                onChange={(e) => {
                  setStatut(e.target.value)
                  setPage(1)
                }}
              />
            </div>
            <label className="flex h-9 items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={archives}
                onChange={(e) => {
                  setArchives(e.target.checked)
                  setPage(1)
                }}
              />
              Archivés uniquement
            </label>
          </div>
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
                  <TH>Cabinet</TH>
                  <TH>Contact</TH>
                  <TH>Ville</TH>
                  <TH>Statut</TH>
                  <TH>Fin d'essai</TH>
                  <TH>Créé le</TH>
                  {(peutDesactiver || peutReactiver) && <TH className="text-right">Accès</TH>}
                </TRow>
              </THead>
              <TBody>
                {requete.isPending ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TRow key={i}>
                      <TD colSpan={7}>
                        <Skeleton className="h-5 w-full" />
                      </TD>
                    </TRow>
                  ))
                ) : cabinets.length === 0 ? (
                  <TRow>
                    <TD colSpan={7}>
                      <TableEmpty>
                        <span className="inline-flex items-center gap-2">
                          <Building2 className="h-4 w-4" aria-hidden />
                          Aucun cabinet ne correspond à ces critères.
                        </span>
                      </TableEmpty>
                    </TD>
                  </TRow>
                ) : (
                  cabinets.map((c) => {
                    const s = statutCabinet(c.statut)
                    return (
                      <TRow key={c.tenant_id}>
                        <TD>
                          <span className="flex items-center gap-3">
                            <ApercuLogo url={c.logo_url} nom={c.nom} taille="sm" />
                            <Link
                              to={`/cabinets/${c.tenant_id}`}
                              className="font-medium text-foreground hover:text-primary hover:underline"
                            >
                              {c.nom}
                            </Link>
                          </span>
                        </TD>
                        <TD className="text-muted-foreground">{c.email ?? c.telephone ?? '—'}</TD>
                        <TD className="text-muted-foreground">{[c.ville, c.pays].filter(Boolean).join(', ') || '—'}</TD>
                        <TD>
                          <StatusBadge tone={s.ton}>{s.texte}</StatusBadge>
                        </TD>
                        <TD className="text-muted-foreground">{c.statut === 'ESSAI' ? date(c.date_fin_essai) : '—'}</TD>
                        <TD className="text-muted-foreground">{date(c.date_creation)}</TD>
                        {(peutDesactiver || peutReactiver) && (
                          <TD className="text-right">
                            {/* Uniquement les transitions que le serveur autorise. */}
                            {peutDesactiver && (c.transitions_possibles ?? []).includes('SUSPENDU') ? (
                              <Button size="sm" variant="ghost" onClick={() => setBascule({ cabinet: c, desactiver: true })}>
                                <PauseCircle aria-hidden />
                                Désactiver
                              </Button>
                            ) : peutReactiver && c.statut === 'SUSPENDU' && (c.transitions_possibles ?? []).includes('ACTIF') ? (
                              <Button size="sm" variant="ghost" onClick={() => setBascule({ cabinet: c, desactiver: false })}>
                                <PlayCircle aria-hidden />
                                Réactiver
                              </Button>
                            ) : null}
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

        <Pagination
          meta={requete.data?.meta}
          page={page}
          limit={LIMITE}
          onPageChange={setPage}
          libelle="cabinets"
          onPageHorsBornes={() => setPage(1)}
        />
      </div>

      <CreerCabinetDrawer open={creation} onClose={() => setCreation(false)} />

      {bascule && (
        <MotifDialog
          open
          onClose={() => setBascule(null)}
          titre={`${bascule.desactiver ? 'Désactiver' : 'Réactiver'} ${bascule.cabinet.nom}`}
          description={
            bascule.desactiver
              ? "Plus personne du cabinet ne peut se connecter, dès maintenant. Les données sont conservées et le cabinet peut être réactivé à tout moment."
              : 'Le cabinet retrouve un accès complet.'
          }
          libelleConfirmer={bascule.desactiver ? 'Désactiver' : 'Réactiver'}
          variante={bascule.desactiver ? 'danger' : 'primary'}
          onConfirm={(motif) => basculer.mutateAsync({ ...bascule, motif })}
        />
      )}
    </AppShell>
  )
}
