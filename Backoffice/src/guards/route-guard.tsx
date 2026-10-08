import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { usePermission } from './can'
import { useAuthStore } from '@/stores/auth-store'

/**
 * Garde de session et de permission.
 *
 * Sans jeton : redirection vers `/login`, en gardant la page demandée pour y
 * revenir après connexion. La redirection est **une conséquence de l'état**, pas
 * un effet de bord : la purge de session met `token` à `null`, et cette garde
 * réagit. Aucune navigation explicite n'est nécessaire ailleurs.
 */
export function RouteGuard({ children }: { children: ReactNode }) {
  const token = useAuthStore((etat) => etat.token)
  const location = useLocation()
  if (!token) {
    return <Navigate to="/login" replace state={{ depuis: location.pathname }} />
  }
  return <>{children}</>
}

export function PermissionGuard({
  permission,
  children,
}: {
  permission: string
  children: ReactNode
}) {
  const autorise = usePermission(permission)
  if (!autorise) return <Navigate to="/403" replace />
  return <>{children}</>
}
