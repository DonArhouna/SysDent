import { api } from '@/lib/api'
import type { APIResponse } from '@/types/api'
import type { PermissionCatalogueItem, Role, RoleCreate } from '../types'

export const rbacApi = {
  listerRoles: () => {
    return api.get<APIResponse<Role[]>>('/rbac/roles')
  },

  creerRole: (data: RoleCreate) => {
    return api.post<APIResponse<Role>>('/rbac/roles', data)
  },

  accorderPermission: (roleId: string, module: string, action: string) => {
    return api.post<APIResponse<Role>>(`/rbac/roles/${roleId}/permissions`, {
      module,
      action,
    })
  },

  retirerPermission: (roleId: string, permissionCle: string) => {
    return api.delete<APIResponse<Role>>(`/rbac/roles/${roleId}/permissions`, {
      params: { permission: permissionCle },
    })
  },

  listerCataloguePermissions: () => {
    return api.get<APIResponse<PermissionCatalogueItem[]>>('/rbac/permissions')
  },
}
