import { Fragment, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, Check, Minus } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, type ApiReponse } from '@/lib/api'
import { messageErreur } from '@/lib/libelles'
import type { Permission, Role } from '@/lib/plateforme'
import { RolesCabinet } from './roles-cabinet'

const RESSOURCES: Record<string, string> = {
  tenants: 'Cabinets',
  users: 'Équipe',
  plans: 'Plans',
  subscriptions: 'Abonnements',
  billing: 'Facturation',
  stats: 'Statistiques',
  health: 'Santé',
  audit: 'Audit',
  support: 'Accès support',
  announcements: 'Annonces',
}

/**
 * Deux matrices : celle de la console (lecture seule) et celle de chaque cabinet
 * (modifiable par le Super Admin, onglet « Cabinets »).
 *
 * Console : matrice rôles × permissions, en lecture.
 *
 * Les rôles système sont semés par le backend et ne se modifient pas depuis la
 * console : une matrice modifiable à la souris est la façon la plus rapide de
 * donner trop de droits sans s'en apercevoir. Les permissions **sensibles**
 * sont signalées.
 */
export function RolesPage() {
  // L'onglet et le cabinet vivent dans l'URL : la fiche d'un cabinet y mène
  // directement, et un lien partagé rouvre le même écran.
  const [params, setParams] = useSearchParams()
  const onglet = params.get('onglet') === 'cabinets' ? 'cabinets' : 'console'
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api.get<ApiReponse<Role[]>>('/platform/roles') })
  const permissions = useQuery({
    queryKey: ['permissions'],
    queryFn: () => api.get<ApiReponse<Permission[]>>('/platform/permissions'),
  })

  const groupes = useMemo(() => {
    const parRessource = new Map<string, Permission[]>()
    for (const p of permissions.data?.data ?? []) {
      parRessource.set(p.ressource, [...(parRessource.get(p.ressource) ?? []), p])
    }
    return [...parRessource.entries()]
  }, [permissions.data])

  const listeRoles = [...(roles.data?.data ?? [])].sort((a, b) => b.niveau_hierarchie - a.niveau_hierarchie)
  const erreur = roles.error ?? permissions.error

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          titre="Rôles & permissions"
          sousTitre="Ce que chaque rôle peut faire, dans la console et dans les cabinets."
          onRefresh={() => {
            void roles.refetch()
            void permissions.refetch()
          }}
        />

        <Tabs value={onglet} onValueChange={(v) => setParams(v === 'cabinets' ? { onglet: 'cabinets' } : {})}>
          <TabsList>
            <TabsTrigger value="console">Console</TabsTrigger>
            <TabsTrigger value="cabinets">Cabinets</TabsTrigger>
          </TabsList>
          <TabsContent value="cabinets">
            <RolesCabinet cabinetInitial={params.get('cabinet') ?? undefined} />
          </TabsContent>
          <TabsContent value="console">
        {erreur ? (
          <Card className="space-y-3 p-6">
            <p role="alert" className="text-sm text-danger">{messageErreur(erreur)}</p>
            <Button variant="outline" size="sm" onClick={() => void roles.refetch()}>
              Réessayer
            </Button>
          </Card>
        ) : roles.isPending || permissions.isPending ? (
          <Skeleton className="h-96 w-full" />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              {listeRoles.map((r) => (
                <Card key={r.code}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">{r.libelle}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1 text-sm text-muted-foreground">
                    <p className="line-clamp-3">{r.description ?? '—'}</p>
                    <p className="pt-2 text-xs">
                      <strong className="text-foreground">{r.permissions.length}</strong> permissions ·{' '}
                      <strong className="text-foreground">{r.nb_utilisateurs}</strong> compte(s)
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card className="overflow-x-auto p-0">
              <Table>
                <THead>
                  <TRow>
                    <TH className="min-w-[260px]">Permission</TH>
                    {listeRoles.map((r) => (
                      <TH key={r.code} className="text-center">{r.libelle}</TH>
                    ))}
                  </TRow>
                </THead>
                <TBody>
                  {groupes.map(([ressource, perms]) => (
                    <Fragment key={ressource}>
                      <TRow className="bg-muted/40 hover:bg-muted/40">
                        <TD colSpan={listeRoles.length + 1} className="py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          {RESSOURCES[ressource] ?? ressource}
                        </TD>
                      </TRow>
                      {perms.map((p) => (
                        <TRow key={p.code}>
                          <TD>
                            <span className="flex items-center gap-2">
                              <span className="text-sm">{p.description}</span>
                              {p.sensible && (
                                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning" aria-label="Permission sensible" />
                              )}
                            </span>
                            <span className="font-mono text-[11px] text-muted-foreground">{p.code}</span>
                          </TD>
                          {listeRoles.map((r) => (
                            <TD key={r.code} className="text-center">
                              {r.permissions.includes(p.code) ? (
                                <Check className="mx-auto h-4 w-4 text-success" aria-label="Accordée" />
                              ) : (
                                <Minus className="mx-auto h-4 w-4 text-muted-foreground/40" aria-label="Non accordée" />
                              )}
                            </TD>
                          ))}
                        </TRow>
                      ))}
                    </Fragment>
                  ))}
                </TBody>
              </Table>
            </Card>
          </>
        )}
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
