export interface AuditLog {
  id: string
  timestamp: string
  user_id?: string | null
  user_email?: string | null
  action: string
  resource_type: string
  resource_id: string
  changes?: Record<string, any> | null
  ip_address?: string | null
  user_agent?: string | null
}
