import { api } from '@/lib/api'
import type { PaginatedResponse } from '@/types/api'
import type { AuditLog } from '../types'

export const auditApi = {
  lister: (params?: {
    resource_type?: string
    resource_id?: string
    page?: number
    limit?: number
  }) => {
    return api.get<PaginatedResponse<AuditLog>>('/audit', { params })
  },
}
