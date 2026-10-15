import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Power, PowerOff, Trash2, UserCog } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { dateHeure, libelleRole, messageErreur, statutCompte } from '@/lib/libelles'
import { PERMISSIONS, type Role, type UtilisateurDetail } from '@/lib/plateforme'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from '@/stores/toast-store'

type Action = 'roles' | 'desactivation' | 'reactivation' | 'reinitialisation' | 'suppression'

/**
 * Fiche d'un compte de la console et ses actions.
 *
 * Le backend protège le **dernier Super Admin actif** (ni désactivable, ni
 * supprimable, ni privé de son rôle) : l'écran affiche son refus tel quel,
 * plutôt que de deviner la règle.
 */
export function UtilisateurDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const client = useQueryClient()
  const moi = useAuthStore((e) => e.profil?.id)
  const [action, setAction] = useState<Action | null>(null)
  const [rolesChoisis, setRolesChoisis] = useState<string[]>([])
  const [confirmation, setConfirmation] = useState('')

  const peut = {
    modifier: usePermission(PERMISSIONS.equipeModifier),
    desactiver: usePermission(PERMISSIONS.equipeDesactiver),
    reinitialiser: usePermission(PERMISSIONS.equipeReinitialiser),
    supprimer: usePermission(PERMISSIONS.equipeSupprimer),
  }

  const fiche = useQuery({
    queryKey: ['equipe', 'detail', id],
    queryFn: () => api.get<ApiReponse<UtilisateurDetail>>(`/platform/users/${id}`),
  })
  const roles = useQuery({
    queryKey: ['roles'],
    queryFn: () => api.get<ApiReponse<Role[]>>('/platform/roles'),
    enabled: action === 'roles',
  })

  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: ['equipe'] })
    void client.invalidateQueries({ queryKey: ['roles'] })
  }

  const executer = useMutation({
    mutationFn: async ({ type, motif }: { type: Action; motif: string }) => {
      switch (type) {
        case 'roles':
          return api.patch(`/platform/users/${id}`, { roles: rolesChoisis, motif })
        case 'desactivation':
          return api.post(`/platform/users/${id}/desactivation`, { motif })
        case 'reactivation':
          return api.post(`/platform/users/${id}/reactivation`)
        case 'reinitialisation':
          // Le serveur renvoie un secret prepare, volontairement IGNORE : a la
          // connexion suivante, l'enrolement en prepare un nouveau (QR ou
          // e-mail au choix), qui remplace celui-ci. L'afficher ferait scanner
          // un secret deja condamne.
          return api.post(`/platform/users/${id}/reinitialisation-acces`, { motif })
        case 'suppression':
          return api.delete(`/platform/users/${id}`, { body: { motif, confirmation } })
      }
    },
    onSuccess: (_r, { type }) => {
      rafraichir()
      toast.success('Action enregistrée.')
      if (type === 'suppression') onClose()
    },
  })

  const u = fiche.data?.data.utilisateur
  const s = statutCompte(u?.statut)
  const estMoi = u?.id === moi

  return (
    <>
      <Drawer open onClose={onClose} title={u ? `${u.prenom} ${u.nom}` : 'Compte'} description={u?.email} width="lg">
        {fiche.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : fiche.isError ? (
          <p role="alert" className="text-sm text-danger">{messageErreur(fiche.error)}</p>
        ) : u ? (
          <div className="space-y-6">
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone={s.ton}>{s.texte}</StatusBadge>
              <StatusBadge tone={u.deux_facteurs_actif ? 'success' : 'warning'}>
                {u.deux_facteurs_actif ? '2FA active' : '2FA à configurer'}
              </StatusBadge>
              {estMoi && <StatusBadge tone="info">Vous</StatusBadge>}
            </div>

            <dl className="grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">Rôles</dt>
                <dd className="mt-1 flex flex-wrap gap-1">
                  {u.roles.map((r) => (
                    <StatusBadge key={r} tone="purple">{libelleRole(r)}</StatusBadge>
                  ))}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Sessions actives</dt>
                <dd className="mt-1 text-sm font-medium">{fiche.data.data.sessions_actives}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Dernière connexion</dt>
                <dd className="mt-1 text-sm font-medium">{dateHeure(u.dernier_login)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Créé le</dt>
                <dd className="mt-1 text-sm font-medium">{dateHeure(u.cree_le)}</dd>
              </div>
              {u.telephone && (
                <div>
                  <dt className="text-xs text-muted-foreground">Téléphone</dt>
                  <dd className="mt-1 text-sm font-medium">{u.telephone}</dd>
                </div>
              )}
              {u.motif_desactivation && (
                <div className="sm:col-span-2">
                  <dt className="text-xs text-muted-foreground">Motif de désactivation</dt>
                  <dd className="mt-1 text-sm">{u.motif_desactivation}</dd>
                </div>
              )}
            </dl>

            <details className="rounded-xl border border-border p-3 text-sm">
              <summary className="cursor-pointer font-medium">
                {fiche.data.data.permissions.length} permission(s) effective(s)
              </summary>
              <ul className="mt-2 grid gap-1 font-mono text-xs text-muted-foreground sm:grid-cols-2">
                {fiche.data.data.permissions.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </details>

            <div className="grid gap-2 border-t border-border pt-4 sm:grid-cols-2">
              {peut.modifier && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setRolesChoisis(u.roles)
                    setAction('roles')
                  }}
                >
                  <UserCog aria-hidden />
                  Modifier les rôles
                </Button>
              )}
              {peut.reinitialiser && !estMoi && (
                <Button variant="outline" onClick={() => setAction('reinitialisation')}>
                  <KeyRound aria-hidden />
                  Réinitialiser l'accès
                </Button>
              )}
              {peut.desactiver && !estMoi && u.statut !== 'DESACTIF' && (
                <Button variant="outline" onClick={() => setAction('desactivation')}>
                  <PowerOff aria-hidden />
                  Désactiver
                </Button>
              )}
              {peut.desactiver && u.statut === 'DESACTIF' && (
                <Button variant="outline" onClick={() => executer.mutate({ type: 'reactivation', motif: '' })} disabled={executer.isPending}>
                  <Power aria-hidden />
                  Réactiver
                </Button>
              )}
              {peut.supprimer && !estMoi && (
                <Button
                  variant="danger"
                  onClick={() => {
                    setConfirmation('')
                    setAction('suppression')
                  }}
                >
                  <Trash2 aria-hidden />
                  Supprimer
                </Button>
              )}
            </div>
            {executer.isError && !action && (
              <p role="alert" className="text-sm text-danger">{messageErreur(executer.error)}</p>
            )}
          </div>
        ) : null}
      </Drawer>

      {action && action !== 'reactivation' && u && (
        <MotifDialog
          open
          onClose={() => setAction(null)}
          titre={
            {
              roles: 'Modifier les rôles',
              desactivation: `Désactiver ${u.prenom} ${u.nom}`,
              reinitialisation: `Réinitialiser l'accès de ${u.prenom} ${u.nom}`,
              suppression: `Supprimer définitivement ${u.email}`,
            }[action]
          }
          description={
            {
              roles: 'Les sessions du compte reflètent le changement à la requête suivante.',
              desactivation: 'Toutes ses sessions sont révoquées ; le compte ne peut plus se connecter.',
              reinitialisation: 'Second facteur remis à zéro et sessions révoquées. La personne reconfigure sa 2FA à la prochaine connexion.',
              suppression: 'Irréversible. Préférez la désactivation pour garder la trace du compte.',
            }[action]
          }
          libelleConfirmer={{ roles: 'Enregistrer', desactivation: 'Désactiver', reinitialisation: 'Réinitialiser', suppression: 'Supprimer' }[action]}
          variante={action === 'suppression' || action === 'desactivation' ? 'danger' : 'primary'}
          onConfirm={(motif) => {
            if (action === 'roles' && rolesChoisis.length === 0) return Promise.reject(new Error('Au moins un rôle est requis.'))
            if (action === 'suppression' && confirmation !== 'SUPPRIMER') return Promise.reject(new Error('Tapez SUPPRIMER pour confirmer.'))
            return executer.mutateAsync({ type: action, motif })
          }}
        >
          {action === 'roles' && (
            <fieldset className="space-y-2">
              {(roles.data?.data ?? []).map((r) => (
                <label key={r.code} className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={rolesChoisis.includes(r.code)}
                    onChange={(e) => setRolesChoisis((rs) => (e.target.checked ? [...rs, r.code] : rs.filter((x) => x !== r.code)))}
                  />
                  {r.libelle}
                </label>
              ))}
            </fieldset>
          )}
          {action === 'suppression' && (
            <Input label="Tapez SUPPRIMER pour confirmer" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />
          )}
        </MotifDialog>
      )}

    </>
  )
}
