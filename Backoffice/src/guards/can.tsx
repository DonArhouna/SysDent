import type { ReactNode } from 'react'

import { possedePermission, useAuthStore } from '@/stores/auth-store'

/**
 * Permissions pilotées par l'API, jamais par une table codée en dur.
 *
 * La source est la liste **`permissions` de `/platform/auth/me`** : un bouton
 * visible mais refusé en 403 est le pire des deux mondes — l'utilisateur croit
 * à un bug. Et une permission écrite en dur finit toujours par diverger du
 * backend ; c'est déjà arrivé deux fois sur les permissions de rôle.
 *
 * Ce composant ne remplace **pas** le contrôle serveur : il évite d'afficher ce
 * qui serait refusé, pas d'autoriser ce qui ne l'est pas.
 */
export function usePermission(permission: string): boolean {
  const profil = useAuthStore((etat) => etat.profil)
  return possedePermission(profil, permission)
}

export function Can({
  permission,
  children,
  fallback = null,
}: {
  permission: string
  children: ReactNode
  fallback?: ReactNode
}) {
  return usePermission(permission) ? <>{children}</> : <>{fallback}</>
}
