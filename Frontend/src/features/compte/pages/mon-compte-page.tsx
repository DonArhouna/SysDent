import { useQuery } from '@tanstack/react-query'
import { AtSign, BadgeCheck, Building2, KeyRound, ShieldCheck, UserRound } from 'lucide-react'
import { api, type ApiReponse } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { StatusBadge } from '@/components/ui/status-badge'
import { Avatar, initiales } from '@/components/ui/avatar'
import { formatDateFr } from '@/lib/format'

/**
 * « Mon compte » — profil de l'utilisateur connecté.
 *
 * Alimentation réelle : `/auth/me` pour l'identité et les permissions,
 * `/cabinets` pour le site rattaché. Aucun champ n'est saisi ni simulé : une
 * modification d'identité passe par la console d'administration, pas par
 * l'écran de consultation — un praticien ne réécrit pas son propre rôle.
 */

interface Profil {
  id: string
  email: string
  prenom: string
  nom: string
  role: string
  permissions: string[]
  telephone?: string | null
  tenant_id?: string | null
  /** Nom du cabinet et site de rattachement : exposes par `/auth/me`. */
  cabinet_nom?: string | null
  cabinet_id?: string | null
}

interface Cabinet {
  id: string
  nom: string
  ville: string | null
  actif: boolean
}

const LIBELLES_ROLES: Record<string, string> = {
  ADMIN_CABINET: 'Administrateur de cabinet',
  SUPER_ADMIN: 'Super Administrateur',
  PRATICIEN: 'Praticien',
  ASSISTANT: 'Assistant Dentaire',
  SECRETAIRE: 'Secrétariat',
  COMPTABLE: 'Comptable',
  GESTIONNAIRE_STOCK: 'Gestionnaire de Stock',
}

export function MonComptePage() {
  const profil = useAuthStore((etat) => etat.profil)

  const { data: profilApi, isError } = useQuery({
    queryKey: ['compte', 'profil'],
    queryFn: () => api.get<ApiReponse<Profil>>('/auth/me'),
  })

  const { data: cabinets } = useQuery({
    queryKey: ['compte', 'cabinets'],
    queryFn: () => api.get<ApiReponse<Cabinet[]>>('/cabinets'),
  })

  // Le store est la source affichée immédiatement (pas de rechargement) ; la
  // requête confirme en arrière-plan et rafraîchit si nécessaire.
  const p = profilApi?.data ?? profil
  const nomComplet = p ? `${p.prenom} ${p.nom}`.trim() : '—'
  const role = p?.role ?? '—'
  const permissions = p?.permissions ?? []
  // `tenant_id` identifie le tenant, pas un site : s'en servir pour retrouver un
  // cabinet pouvait afficher le mauvais nom. On part du site de rattachement,
  // avec le nom du cabinet déjà fourni par `/auth/me` en repli.
  const cabinet = cabinets?.data?.find((c) => c.id === p?.cabinet_id) ?? cabinets?.data?.[0]

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        titre="Mon compte"
        sousTitre="Votre identité, votre rôle et ce à quoi vous avez accès dans ce cabinet"
      />

      <Card>
        <CardContent className="flex flex-col gap-4 pt-6 sm:flex-row sm:items-center">
          <Avatar initials={initiales(p?.prenom, p?.nom)} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xl font-bold">{nomComplet}</p>
            <p className="truncate text-sm text-muted-foreground">{p?.email ?? '—'}</p>
          </div>
          <StatusBadge tone="info">{LIBELLES_ROLES[role] ?? role}</StatusBadge>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Identité</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Ligne icone={UserRound} label="Nom complet" valeur={nomComplet} />
            <Ligne icone={AtSign} label="Adresse e-mail" valeur={p?.email ?? '—'} />
            <Ligne icone={KeyRound} label="Téléphone" valeur={p?.telephone ?? 'Non renseigné'} />
            <Ligne
              icone={BadgeCheck}
              label="Rôle"
              valeur={LIBELLES_ROLES[role] ?? role}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Rattachement</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Ligne
              icone={Building2}
              label="Cabinet"
              valeur={cabinet?.nom ?? p?.cabinet_nom ?? '-'}
            />
            <Ligne icone={Building2} label="Ville" valeur={cabinet?.ville ?? '—'} />
            <Ligne
              icone={ShieldCheck}
              label="Session ouverte le"
              valeur={formatDateFr(new Date())}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mes permissions</CardTitle>
        </CardHeader>
        <CardContent>
          {isError ? (
            <p className="text-sm text-muted-foreground">
              Impossible de charger vos permissions. Vérifiez la connexion au backend.
            </p>
          ) : permissions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune permission individuelle : votre rôle couvre l'accès.
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {permissions.map((permission) => (
                <li
                  key={permission}
                  className="rounded-full border border-surface-border bg-muted/50 px-3 py-1 font-mono text-[11px] text-muted-foreground"
                >
                  {permission}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">
            L'attribution des permissions se fait depuis « Rôles &amp; Permissions ». Le
            backend fait foi : un accès refusé par le serveur ne peut pas être contourné
            depuis l'interface.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function Ligne({
  icone: Icone,
  label,
  valeur,
}: {
  icone: typeof UserRound
  label: string
  valeur: string
}) {
  return (
    <div className="flex items-start gap-3">
      <Icone className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="truncate">{valeur}</p>
      </div>
    </div>
  )
}