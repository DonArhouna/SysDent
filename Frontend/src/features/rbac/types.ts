export interface Role {
  id: string
  nom: string
  description?: string | null
  niveau_hierarchie: number
  permissions: string[]
  nb_utilisateurs: number
}

export interface RoleCreate {
  nom: string
  description?: string
  niveau_hierarchie: number
}

export interface PermissionCatalogueItem {
  module: string
  action: string
  description?: string | null
  cle: string
}
