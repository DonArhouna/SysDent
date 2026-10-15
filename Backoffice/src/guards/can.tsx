import { type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore, possedePermission } from '@/stores/auth-store'

/**
 * Vrai si le profil courant porte la permission demandée. Sans profil, aucun
 * droit : toute navigation conditionnée doit attendre `/auth/me`.
 */
export function usePermission(permission?: string): boolean {
  const profil = useAuthStore((s) => s.profil)
  if (!profil || !permission) return false
  return possedePermission(profil, permission)
}

interface CanProps {
  permission?: string
  role?: string | string[]
  fallback?: ReactNode
  children: ReactNode
}

/**
 * Garde d'affichage conditionnel basé sur le RBAC.
 * Exemple:
 * <Can permission="PATIENTS:CREATE">
 *   <Button>Nouveau Patient</Button>
 * </Can>
 */
export function Can({ permission, role, fallback = null, children }: CanProps) {
  const profil = useAuthStore((s) => s.profil)

  if (!profil) return <>{fallback}</>

  // Vérification de rôle
  if (role) {
    const rolesAcceptes = Array.isArray(role) ? role : [role]
    const roles = profil.roles ?? (profil.role ? [profil.role] : [])
    const roleAutorise = roles.some((r) => rolesAcceptes.includes(r))
    if (!roleAutorise) return <>{fallback}</>
  }

  // Vérification de permission
  if (permission && !possedePermission(profil, permission)) {
    return <>{fallback}</>
  }

  return <>{children}</>
}

/**
 * Guard pour les routes protégées par permission RBAC.
 * Redirige vers /403 si l'utilisateur n'a pas les droits requis.
 */
export function ProtectedRoute({
  permission,
  role,
  children,
}: {
  permission?: string
  role?: string | string[]
  children: ReactNode
}) {
  const profil = useAuthStore((s) => s.profil)

  if (!profil) return null

  if (role) {
    const rolesAcceptes = Array.isArray(role) ? role : [role]
    const roles = profil.roles ?? (profil.role ? [profil.role] : [])
    const roleAutorise = roles.some((r) => rolesAcceptes.includes(r))
    if (!roleAutorise) return <Navigate to="/403" replace />
  }

  if (permission && !possedePermission(profil, permission)) {
    return <Navigate to="/403" replace />
  }

  return <>{children}</>
}
