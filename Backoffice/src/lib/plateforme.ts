import type { components } from '@/lib/openapi'

/**
 * Types des ressources de la console, **tirés du schéma OpenAPI**.
 *
 * Écrits à la main, ils dériveraient du backend sans que rien ne le signale ;
 * tirés de `openapi.d.ts`, un champ renommé côté serveur casse la compilation
 * au lieu de s'afficher `undefined` à l'écran.
 */
type S = components['schemas']

export type Cabinet = S['TenantResponse']
export type CabinetDetail = S['TenantDetailResponse']
export type CabinetCreation = S['TenantCreate']
export type CabinetCree = S['TenantCreationResponse']
export type CabinetModification = S['TenantUpdate']
export type EntreeHistorique = S['HistoriqueStatutEntry']
export type ResumeQuotas = S['QuotaResumeResponse']

export type Utilisateur = S['UtilisateurPlateformeResponse']
export type UtilisateurDetail = S['DetailUtilisateurResponse']
export type UtilisateurCreation = S['UtilisateurPlateformeCreate']
export type UtilisateurModification = S['UtilisateurPlateformeUpdate']
export type Role = S['RolePlateformeResponse']
export type Permission = S['PermissionPlateformeResponse']

export type EntreeAudit = S['AuditEntryResponse']

export type MatriceCabinet = S['MatriceCabinetResponse']
export type RoleCabinet = S['RoleCabinetResponse']
export type PermissionCabinet = S['PermissionCabinetResponse']
export type PermissionsRoleCabinet = S['PermissionsRoleCabinetResponse']
export type AdminCabinet = S['AdminCabinetResponse']
export type ActionAccesAdmin = S['ActionAccesAdminResponse']

export type RendezVous = S['RendezVousPlateformeResponse']
export type RendezVousCreation = S['RendezVousPlateformeCreate']
export type RendezVousModification = S['RendezVousPlateformeUpdate']

export type Plan = S['PlanResponse']
export type PlanCreation = S['PlanCreate']
export type PlanModification = S['PlanUpdate']
export type RevisionPlan = S['PlanRevisionResponse']
export type Abonnement = S['AbonnementResponse']
export type Facture = S['FacturePlateformeResponse']

/** Ligne de facture telle que le backend l'attend (`FacturePlateformeCreate.lignes`). */
export interface LigneFacture {
  libelle: string
  quantite: number
  prix_unitaire: number
  montant: number
}

/** Contrôle de `/platform/sante` (réponse non typée côté backend). */
export interface ControleSante {
  composant: string
  ok: boolean
  detail?: string | null
  [cle: string]: unknown
}

export interface RapportSante {
  statut: 'ok' | 'degrade' | string
  verifie_le: string
  controles: ControleSante[]
  en_panne: string[]
}

/** Ressource de `QuotaResumeResponse.ressources` (non typée côté backend). */
export interface RessourceQuota {
  ressource: string
  illimite: boolean
  consommation: number
  limite: number | null
  taux: number | null
  depasse?: boolean
}

/**
 * Permissions de la console, telles que le backend les nomme.
 *
 * Une seule table : la navigation, les gardes de route et les boutons lisent
 * les mêmes codes que `require_platform_permissions` côté serveur.
 */
export const PERMISSIONS = {
  stats: 'platform.stats.read',
  sante: 'platform.health.read',
  cabinetsLire: 'platform.tenants.read',
  cabinetsCreer: 'platform.tenants.create',
  cabinetsModifier: 'platform.tenants.update',
  cabinetsSuspendre: 'platform.tenants.suspend',
  cabinetsActiver: 'platform.tenants.activate',
  cabinetsResilier: 'platform.tenants.terminate',
  cabinetsArchiver: 'platform.tenants.archive',
  /** Rôles et permissions À L'INTÉRIEUR d'un cabinet : droit sensible. */
  cabinetsRbac: 'platform.tenants.rbac',
  /** Dépanner l'accès des administrateurs d'un cabinet : droit sensible. */
  cabinetsAcces: 'platform.tenants.reset_access',
  equipeLire: 'platform.users.read',
  equipeCreer: 'platform.users.create',
  equipeModifier: 'platform.users.update',
  equipeDesactiver: 'platform.users.deactivate',
  equipeReinitialiser: 'platform.users.reset',
  equipeSupprimer: 'platform.users.delete',
  auditLire: 'platform.audit.read',
  auditExporter: 'platform.audit.export',
  plansLire: 'platform.plans.read',
  plansEcrire: 'platform.plans.write',
  abonnementsLire: 'platform.subscriptions.read',
  abonnementsEcrire: 'platform.subscriptions.write',
  facturationLire: 'platform.billing.read',
  facturationEcrire: 'platform.billing.write',
  agendaLire: 'platform.agenda.read',
  agendaEcrire: 'platform.agenda.write',
} as const
