import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { rbacApi } from '../services/rbac-api'
import type { PermissionCatalogueItem, Role } from '../types'
import { RoleModal } from '../components/role-modal'
import { PermissionMatrix } from '../components/permission-matrix'
import { Plus, RefreshCw, Shield, Users, ShieldAlert, WifiOff } from 'lucide-react'

export function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [catalogue, setCatalogue] = useState<PermissionCatalogueItem[]>([])
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [loading, setLoading] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)
  /** Un chargement échoué ne doit pas s'afficher comme un cabinet sans rôle. */
  const [erreurChargement, setErreurChargement] = useState(false)

  const chargerDonnees = async () => {
    try {
      setLoading(true)
      setErreurChargement(false)
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
      // Erreurs déjà signalées par le toast global de l'API client.
      setErreurChargement(true)
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
      {/* En-tête */}
      <PageHeader
        titre={
          <span className="flex items-center gap-2.5">
            <Shield className="h-6 w-6 text-primary" aria-hidden />
            Gestion des Rôles &amp; Habilitations (RBAC)
          </span>
        }
        sousTitre="Configuration granulaire des permissions d'accès aux modules pour chaque profil métier."
        onRefresh={() => void chargerDonnees()}
      >
        <Button
          variant="primary"
          className="flex items-center gap-1.5 text-xs"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus className="w-4 h-4" /> Créer un rôle
        </Button>
      </PageHeader>

      {loading ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-2.5 lg:col-span-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-[5.5rem] rounded-xl2" />
            ))}
          </div>
          <Skeleton className="h-80 rounded-xl2 lg:col-span-8" />
        </div>
      ) : erreurChargement ? (
        /* Un échec de chargement n'est pas un cabinet sans rôle : le dire. */
        <div className="rounded-xl2 border border-border bg-card shadow-float">
          <EmptyState
            icon={WifiOff}
            titre="Rôles indisponibles"
            description="Les rôles et habilitations n'ont pas pu être chargés. Vérifiez que le backend est démarré puis réessayez."
          >
            <Button variant="outline" onClick={() => void chargerDonnees()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          </EmptyState>
        </div>
      ) : roles.length === 0 ? (
        <div className="rounded-xl2 border border-border bg-card shadow-float">
          <EmptyState
            icon={ShieldAlert}
            titre="Aucun rôle configuré"
            description="Créez un premier rôle pour attribuer des permissions aux profils de votre cabinet."
          >
            <Button variant="primary" onClick={() => setIsModalOpen(true)}>
              <Plus className="w-4 h-4" /> Créer un rôle
            </Button>
          </EmptyState>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Liste des rôles */}
          <div className="space-y-2.5 lg:col-span-4">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Rôles du cabinet ({roles.length})
            </span>

            {roles.map((r) => {
              const isSelected = selectedRole?.id === r.id
              const estAdmin = r.nom === 'ADMIN_CABINET'

              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedRole(r)}
                  className={`focus-ring cursor-pointer rounded-xl2 border p-3.5 transition-colors duration-150 ${
                    isSelected
                      ? 'border-primary/40 bg-primary/10 shadow-float'
                      : 'border-border bg-card hover:bg-surface-hover'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sm text-foreground">{r.nom}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                      Niv. {r.niveau_hierarchie}
                    </span>
                  </div>

                  {r.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{r.description}</p>
                  )}

                  <div className="mt-2.5 flex items-center justify-between border-t border-border pt-2 text-[11px] text-muted-foreground">
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
          <div className="rounded-xl2 border border-border bg-card p-6 shadow-float lg:col-span-8">
            {selectedRole ? (
              <PermissionMatrix
                role={selectedRole}
                catalogue={catalogue}
                onRoleUpdated={handleRoleUpdated}
              />
            ) : (
              <EmptyState
                icon={Users}
                titre="Sélectionnez un rôle"
                description="Choisissez un rôle dans la liste pour configurer ses permissions."
              />
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
