import { useState } from 'react'
import { useToastStore } from '@/stores/toast-store'
import { rbacApi } from '../services/rbac-api'
import type { PermissionCatalogueItem, Role } from '../types'
import { Check, Lock, ShieldCheck } from 'lucide-react'

interface PermissionMatrixProps {
  role: Role
  catalogue: PermissionCatalogueItem[]
  onRoleUpdated: (updatedRole: Role) => void
}

export function PermissionMatrix({ role, catalogue, onRoleUpdated }: PermissionMatrixProps) {
  const { addToast } = useToastStore()
  const [updatingKey, setUpdatingKey] = useState<string | null>(null)

  const estAdminCabinet = role.nom === 'ADMIN_CABINET'

  // Regrouper le catalogue par module
  const modulesGroupes = catalogue.reduce<Record<string, PermissionCatalogueItem[]>>(
    (acc, item) => {
      if (!acc[item.module]) {
        acc[item.module] = []
      }
      acc[item.module].push(item)
      return acc
    },
    {}
  )

  const handleTogglePermission = async (module: string, action: string, cle: string) => {
    if (estAdminCabinet) {
      addToast({
        type: 'warning',
        message: 'Le rôle ADMIN_CABINET conserve tous les droits pour garantir la sécurité du cabinet.',
      })
      return
    }

    const aPermission = role.permissions.includes(cle)
    try {
      setUpdatingKey(cle)
      if (aPermission) {
        const res = await rbacApi.retirerPermission(role.id, cle)
        addToast({ type: 'info', message: `Permission ${cle} révoquée.` })
        onRoleUpdated(res.data)
      } else {
        const res = await rbacApi.accorderPermission(role.id, module, action)
        addToast({ type: 'success', message: `Permission ${cle} accordée.` })
        onRoleUpdated(res.data)
      }
    } catch {
      // toast géré par l'intercepteur API
    } finally {
      setUpdatingKey(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-border">
        <div>
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-primary" />
            Matrice des permissions - Rôle :{' '}
            <span className="text-primary font-mono">{role.nom}</span>
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {estAdminCabinet
              ? 'Ce rôle est le super-administrateur du cabinet et possède l\'ensemble des privilèges.'
              : `${role.permissions.length} permission(s) accordée(s) sur ce rôle.`}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(modulesGroupes).map(([module, permissions]) => (
          <div
            key={module}
            className="p-4 rounded-xl border border-border bg-card space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-foreground tracking-wider">
                MODULE {module}
              </span>
              <span className="text-[10px] text-muted-foreground uppercase">
                {permissions.length} actions
              </span>
            </div>

            <div className="space-y-2">
              {permissions.map((p) => {
                const checked = estAdminCabinet || role.permissions.includes(p.cle)
                const isUpdating = updatingKey === p.cle

                return (
                  <div
                    key={p.cle}
                    onClick={() => !isUpdating && handleTogglePermission(p.module, p.action, p.cle)}
                    className={`flex items-center justify-between p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                      checked
                        ? 'bg-primary/15 border-primary/40 text-foreground'
                        : 'bg-muted border-border text-muted-foreground hover:border-border'
                    }`}
                  >
                    <div>
                      <span className="font-mono font-bold text-primary block">{p.action}</span>
                      {p.description && (
                        <span className="text-[11px] text-muted-foreground block mt-0.5">
                          {p.description}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center pl-3">
                      {estAdminCabinet ? (
                        <Lock className="w-3.5 h-3.5 text-muted-foreground" />
                      ) : (
                        <div
                          className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${
                            checked
                              ? 'bg-primary border-primary/40 text-white'
                              : 'border-input bg-muted'
                          }`}
                        >
                          {checked && <Check className="w-3.5 h-3.5" />}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
