import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, ShieldCheck, ShieldOff, Users } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Avatar, initiales } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TableEmpty, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { usePermission } from '@/guards/can'
import { api, type PageReponse } from '@/lib/api'
import { dateHeure, libelleRole, messageErreur, statutCompte } from '@/lib/libelles'
import { PERMISSIONS, type Utilisateur } from '@/lib/plateforme'
import { CreerUtilisateurDrawer } from './creer-utilisateur-drawer'
import { UtilisateurDrawer } from './utilisateur-drawer'

const LIMITE = 20

/**
 * Comptes de la console (l'équipe de l'éditeur, jamais les utilisateurs des cabinets).
 *
 * La colonne 2FA est mise en avant : un compte qui ouvre tous les cabinets sans
 * second facteur configuré est le premier risque à voir.
 */
export function EquipePage() {
  const peutCreer = usePermission(PERMISSIONS.equipeCreer)
  const [q, setQ] = useState('')
  const [statut, setStatut] = useState('')
  const [page, setPage] = useState(1)
  const [creation, setCreation] = useState(false)
  const [selection, setSelection] = useState<string | null>(null)

  const requete = useQuery({
    queryKey: ['equipe', { q, statut, page }],
    queryFn: ({ signal }) =>
      api.get<PageReponse<Utilisateur>>('/platform/users', {
        params: { q: q.trim(), statut, page, limit: LIMITE },
        signal,
      }),
    placeholderData: (precedent) => precedent,
  })
  const comptes = requete.data?.items ?? []

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          titre="Équipe"
          sousTitre="Comptes ayant accès à la console plateforme."
          onRefresh={() => void requete.refetch()}
        >
          {peutCreer && (
            <Button onClick={() => setCreation(true)}>
              <Plus aria-hidden />
              Nouveau compte
            </Button>
          )}
        </PageHeader>

        <Card className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="relative min-w-[220px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                aria-label="Rechercher un compte"
                placeholder="Nom ou e-mail…"
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
                value={statut}
                onChange={(e) => {
                  setStatut(e.target.value)
                  setPage(1)
                }}
                options={[
                  { value: '', label: 'Tous les statuts' },
                  { value: 'ACTIF', label: 'Actif' },
                  { value: 'VERROUILLE', label: 'Verrouillé' },
                  { value: 'DESACTIF', label: 'Désactivé' },
                ]}
              />
            </div>
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
                  <TH>Compte</TH>
                  <TH>Rôles</TH>
                  <TH>Statut</TH>
                  <TH>2FA</TH>
                  <TH>Dernière connexion</TH>
                </TRow>
              </THead>
              <TBody>
                {requete.isPending ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <TRow key={i}>
                      <TD colSpan={5}>
                        <Skeleton className="h-5 w-full" />
                      </TD>
                    </TRow>
                  ))
                ) : comptes.length === 0 ? (
                  <TRow>
                    <TD colSpan={5}>
                      <TableEmpty>
                        <span className="inline-flex items-center gap-2">
                          <Users className="h-4 w-4" aria-hidden />
                          Aucun compte ne correspond.
                        </span>
                      </TableEmpty>
                    </TD>
                  </TRow>
                ) : (
                  comptes.map((u) => {
                    const s = statutCompte(u.statut)
                    return (
                      <TRow key={u.id} className="cursor-pointer" onClick={() => setSelection(u.id)}>
                        <TD>
                          <span className="flex items-center gap-3">
                            <Avatar initials={initiales(u.prenom, u.nom)} />
                            <span className="min-w-0">
                              <span className="block truncate font-medium">{`${u.prenom} ${u.nom}`}</span>
                              <span className="block truncate text-xs text-muted-foreground">{u.email}</span>
                            </span>
                          </span>
                        </TD>
                        <TD>
                          <span className="flex flex-wrap gap-1">
                            {u.roles.map((r) => (
                              <StatusBadge key={r} tone="purple">{libelleRole(r)}</StatusBadge>
                            ))}
                          </span>
                        </TD>
                        <TD>
                          <StatusBadge tone={s.ton}>{s.texte}</StatusBadge>
                        </TD>
                        <TD>
                          {u.deux_facteurs_actif ? (
                            <span className="inline-flex items-center gap-1 text-sm text-success">
                              <ShieldCheck className="h-4 w-4" aria-hidden /> Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-sm text-warning">
                              <ShieldOff className="h-4 w-4" aria-hidden /> À configurer
                            </span>
                          )}
                        </TD>
                        <TD className="text-muted-foreground">{dateHeure(u.dernier_login)}</TD>
                      </TRow>
                    )
                  })
                )}
              </TBody>
            </Table>
          )}
        </Card>

        <Pagination meta={requete.data?.meta} page={page} limit={LIMITE} onPageChange={setPage} libelle="comptes" onPageHorsBornes={() => setPage(1)} />
      </div>

      <CreerUtilisateurDrawer open={creation} onClose={() => setCreation(false)} />
      {selection && <UtilisateurDrawer id={selection} onClose={() => setSelection(null)} />}
    </AppShell>
  )
}
