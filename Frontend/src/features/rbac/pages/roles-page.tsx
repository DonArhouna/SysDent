import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { rbacApi } from '../services/rbac-api'
import type { PermissionCatalogueItem, Role } from '../types'
import { RoleModal } from '../components/role-modal'
import { PermissionMatrix } from '../components/permission-matrix'
import { Plus, Shield, Users } from 'lucide-react'

export function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [catalogue, setCatalogue] = useState<PermissionCatalogueItem[]>([])
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [loading, setLoading] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const chargerDonnees = async () => {
    try {
      setLoading(true)
      const [resRoles, resCatalogue] = await Promise.all([
        rbacApi.listerRoles(),
        rbacApi.listerCataloguePermissions(),
      ])
      setRoles(resRoles.data)
      setCatalogue(resCatalogue.data)
      if (resRoles.data.length > 0 && !selectedRole) {
        setSelectedRole(resRoles.data[0])
      }
    } catch {
      //
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerDonnees()
  }, [])

  const handleRoleCreated = (nouveauRole: Role) => {
    setRoles((prev) => [...prev, nouveauRole])
    setSelectedRole(nouveauRole)
  }

  const handleRoleUpdated = (updatedRole: Role) => {
    setRoles((prev) => prev.map((r) => (r.id === updatedRole.id ? updatedRole : r)))
    setSelectedRole(updatedRole)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2.5">
            <Shield className="w-6 h-6 text-primary" />
            Gestion des Rôles & Habilitations (RBAC)
          </h1>
          <p className="text-sm text-muted-foreground">
            Configuration granulaire des permissions d'accès aux modules pour chaque profil métier.
          </p>
        </div>

        <Button
          variant="primary"
          className="flex items-center gap-1.5 text-xs"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus className="w-4 h-4" /> Créer un rôle
        </Button>
      </div>

      {loading ? (
        <div className="p-12 text-center text-sm text-muted-foreground">
          Chargement des rôles et autorisations...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Liste des rôles */}
          <div className="lg:col-span-4 space-y-2.5">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
              Rôles du cabinet ({roles.length})
            </span>

            {roles.map((r) => {
              const isSelected = selectedRole?.id === r.id
              const estAdmin = r.nom === 'ADMIN_CABINET'

              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedRole(r)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-primary/15 border-primary/40 shadow-sm'
                      : 'bg-card border-border hover:border-border'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sm text-foreground">{r.nom}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-mono">
                      Niv. {r.niveau_hierarchie}
                    </span>
                  </div>

                  {r.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{r.description}</p>
                  )}

                  <div className="flex items-center justify-between text-[11px] text-muted-foreground mt-2.5 pt-2 border-t border-border">
                    <span className="flex items-center gap-1">
                      <Users className="w-3.5 h-3.5" /> {r.nb_utilisateurs} utilisateur(s)
                    </span>
                    <span className="text-primary font-medium">
                      {estAdmin ? 'Toutes (Illimitées)' : `${r.permissions.length} droit(s)`}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Matrice des droits du rôle sélectionné */}
          <div className="lg:col-span-8 bg-card p-6 rounded-xl border border-border">
            {selectedRole ? (
              <PermissionMatrix
                role={selectedRole}
                catalogue={catalogue}
                onRoleUpdated={handleRoleUpdated}
              />
            ) : (
              <div className="p-8 text-center text-sm text-muted-foreground">
                Sélectionnez un rôle pour configurer ses permissions.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modale Nouveau Rôle */}
      <RoleModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleRoleCreated}
      />
    </div>
  )
}
