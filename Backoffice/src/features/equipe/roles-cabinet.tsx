import { Fragment, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Check, Lock, Minus, ShieldAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { messageErreur } from '@/lib/libelles'
import { PERMISSIONS, type MatriceCabinet, type PermissionCabinet, type RoleCabinet } from '@/lib/plateforme'
import { cn } from '@/lib/utils'
import { toast } from '@/stores/toast-store'
import { useNomsCabinets } from '@/features/offres/noms-cabinets'

const ROLES: Record<string, string> = {
  ADMIN_CABINET: 'Administrateur',
  PRATICIEN: 'Praticien',
  SECRETAIRE: 'Secrétaire',
  ASSISTANT: 'Assistant',
  COMPTABLE: 'Comptable',
  SUPER_ADMIN: 'Super Admin',
}

const MODULES: Record<string, string> = {
  PATIENTS: 'Patients',
  CONSULTATIONS: 'Consultations',
  ODONTOGRAMME: 'Odontogramme',
  ORDONNANCES: 'Ordonnances',
  CABINETS: 'Cabinet',
  PRATICIENS: 'Praticiens',
  DISPONIBILITES: 'Disponibilités',
  AGENDA: 'Agenda',
  FACTURATION: 'Facturation',
  STOCK: 'Stock',
  AUDIT: 'Audit',
  ADMIN: 'Administration',
  TARIFS: 'Tarifs',
  ASSURANCE: 'Assurance',
}

interface Changement {
  role: RoleCabinet
  permission: PermissionCabinet
  accorder: boolean
}

/**
 * Rôles et permissions À L'INTÉRIEUR d'un cabinet.
 *
 * Chaque case accorde ou retire une permission à un rôle, **après un motif**,
 * inscrit au journal de la console ET à celui du cabinet. Administrateur et
 * Super Admin ont tous les droits par construction : leurs colonnes sont
 * verrouillées.
 *
 * Un changement s'applique aux utilisateurs du cabinet à leur prochaine
 * connexion ou au renouvellement de leur session (15 minutes au plus).
 */
export function RolesCabinet({ cabinetInitial }: { cabinetInitial?: string }) {
  const client = useQueryClient()
  const peutModifier = usePermission(PERMISSIONS.cabinetsRbac)
  const { cabinets } = useNomsCabinets()
  const [cabinet, setCabinet] = useState(cabinetInitial ?? '')
  const [changement, setChangement] = useState<Changement | null>(null)

  const matrice = useQuery({
    queryKey: ['cabinet', cabinet, 'rbac'],
    queryFn: () => api.get<ApiReponse<MatriceCabinet>>(`/platform/tenants/${cabinet}/rbac`),
    enabled: cabinet !== '',
  })

  const modifier = useMutation({
    mutationFn: ({ role, permission, accorder, motif }: Changement & { motif: string }) =>
      api.post(
        `/platform/tenants/${cabinet}/rbac/roles/${role.id}/permissions${accorder ? '' : '/retrait'}`,
        { permission: permission.code, motif },
      ),
    onSuccess: (_r, { accorder, permission, role }) => {
      void client.invalidateQueries({ queryKey: ['cabinet', cabinet, 'rbac'] })
      toast.success(`${permission.code} ${accorder ? 'accordée à' : 'retirée à'} ${ROLES[role.nom] ?? role.nom}.`)
    },
  })

  const roles = matrice.data?.data.roles ?? []
  const groupes = useMemo(() => {
    const parModule = new Map<string, PermissionCabinet[]>()
    for (const p of matrice.data?.data.catalogue ?? []) {
      parModule.set(p.module, [...(parModule.get(p.module) ?? []), p])
    }
    return [...parModule.entries()]
  }, [matrice.data])

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-end gap-4 p-4">
        <div className="w-80 max-w-full">
          <Select
            label="Cabinet"
            value={cabinet}
            onChange={(e) => setCabinet(e.target.value)}
            options={[{ value: '', label: 'Choisir un cabinet' }, ...cabinets.map((c) => ({ value: c.tenant_id, label: c.nom }))]}
          />
        </div>
        <p className="flex max-w-xl items-start gap-2 text-xs text-muted-foreground">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
          {peutModifier
            ? "Chaque modification est tracée dans le journal de la console et dans celui du cabinet, avec son motif. Elle s'applique aux utilisateurs à leur prochaine connexion."
            : 'Lecture seule : modifier les rôles d’un cabinet demande la permission « platform.tenants.rbac ».'}
        </p>
      </Card>

      {cabinet === '' ? (
        <EmptyState icon={Building2} titre="Choisissez un cabinet" description="Sa matrice des rôles s'affichera ici." />
      ) : matrice.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : matrice.isError ? (
        <Card className="space-y-3 p-6">
          <p role="alert" className="text-sm text-danger">{messageErreur(matrice.error)}</p>
          <Button variant="outline" size="sm" onClick={() => void matrice.refetch()}>Réessayer</Button>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
            {roles.map((r) => (
              <Card key={r.id}>
                <CardContent className="space-y-1 p-4 text-sm">
                  <p className="flex items-center gap-1.5 font-semibold">
                    {ROLES[r.nom] ?? r.nom}
                    {!r.modifiable && <Lock className="h-3.5 w-3.5 text-muted-foreground" aria-label="Tous les droits, non modifiable" />}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {r.modifiable ? `${r.permissions.length} permission(s)` : 'Tous les droits'} · {r.nb_utilisateurs} utilisateur(s)
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
                  {roles.map((r) => (
                    <TH key={r.id} className="text-center">{ROLES[r.nom] ?? r.nom}</TH>
                  ))}
                </TRow>
              </THead>
              <TBody>
                {groupes.map(([module, perms]) => (
                  <Fragment key={module}>
                    <TRow className="bg-muted/40 hover:bg-muted/40">
                      <TD colSpan={roles.length + 1} className="py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {MODULES[module] ?? module}
                      </TD>
                    </TRow>
                    {perms.map((p) => (
                      <TRow key={p.code}>
                        <TD>
                          <span className="block text-sm">{p.description ?? p.code}</span>
                          <span className="font-mono text-[11px] text-muted-foreground">{p.code}</span>
                          {!p.disponible && <span className="ml-2 text-[11px] text-warning">absente de la base de ce cabinet</span>}
                        </TD>
                        {roles.map((r) => {
                          const accordee = !r.modifiable || r.permissions.includes(p.code)
                          const cliquable = peutModifier && r.modifiable && p.disponible
                          const libelle = `${p.code} pour ${ROLES[r.nom] ?? r.nom} : ${accordee ? 'accordée' : 'non accordée'}`
                          return (
                            <TD key={r.id} className="text-center">
                              {cliquable ? (
                                <button
                                  type="button"
                                  onClick={() => setChangement({ role: r, permission: p, accorder: !accordee })}
                                  aria-label={`${libelle}. Cliquer pour ${accordee ? 'retirer' : 'accorder'}.`}
                                  className={cn(
                                    'focus-ring mx-auto flex h-7 w-7 items-center justify-center rounded-lg border transition-colors',
                                    accordee
                                      ? 'border-success/40 bg-success/10 text-success hover:bg-success/20'
                                      : 'border-border text-muted-foreground/40 hover:border-primary/40 hover:bg-primary/5 hover:text-primary',
                                  )}
                                >
                                  {accordee ? <Check className="h-4 w-4" aria-hidden /> : <Minus className="h-4 w-4" aria-hidden />}
                                </button>
                              ) : accordee ? (
                                <Check className={cn('mx-auto h-4 w-4', r.modifiable ? 'text-success' : 'text-muted-foreground')} aria-label={libelle} />
                              ) : (
                                <Minus className="mx-auto h-4 w-4 text-muted-foreground/40" aria-label={libelle} />
                              )}
                            </TD>
                          )
                        })}
                      </TRow>
                    ))}
                  </Fragment>
                ))}
              </TBody>
            </Table>
          </Card>
        </>
      )}

      {changement && (
        <MotifDialog
          open
          onClose={() => setChangement(null)}
          titre={`${changement.accorder ? 'Accorder' : 'Retirer'} ${changement.permission.code}`}
          description={`Rôle ${ROLES[changement.role.nom] ?? changement.role.nom} (${changement.role.nb_utilisateurs} utilisateur(s)) du cabinet ${cabinets.find((c) => c.tenant_id === cabinet)?.nom ?? ''}. ${changement.permission.description ?? ''}`}
          libelleConfirmer={changement.accorder ? 'Accorder' : 'Retirer'}
          variante={changement.accorder ? 'primary' : 'danger'}
          onConfirm={(motif) => modifier.mutateAsync({ ...changement, motif })}
        />
      )}
    </div>
  )
}
