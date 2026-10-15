import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { Archive, ArchiveRestore, Ban, KeyRound, Pencil, PauseCircle, PlayCircle, Repeat } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { toast } from '@/stores/toast-store'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { date, dateHeure, messageErreur, montant, statutAbonnement, statutCabinet } from '@/lib/libelles'
import {
  PERMISSIONS,
  type CabinetDetail,
  type EntreeHistorique,
  type Plan,
  type ResumeQuotas,
  type RessourceQuota,
} from '@/lib/plateforme'
import { AdminsCabinet } from './admins-cabinet'
import { LogoCabinet } from './logo-cabinet'
import { RendezVousCabinet } from '@/features/agenda/cartes-rendez-vous'
import { ModifierCabinetDrawer } from './modifier-cabinet-drawer'

/** Abonnement résumé dans la fiche (`TenantDetailResponse.abonnement`, non typé côté backend). */
interface AbonnementResume {
  id: string
  numero: string
  statut: string
  plan: string | null
  date_debut: string
  date_fin_essai: string | null
}

type Action = 'suspension' | 'reactivation' | 'resiliation' | 'archiver' | 'desarchiver' | 'plan'

const RESSOURCES: Record<string, string> = {
  utilisateurs: 'Utilisateurs',
  sites: 'Sites',
  praticiens: 'Praticiens',
  stockage: 'Stockage',
  'SMS par mois': 'SMS par mois',
}

/** Le stockage arrive en octets : affiché en Mo / Go, les autres ressources telles quelles. */
function quantite(ressource: string, n: number): string {
  if (ressource !== 'stockage') return n.toLocaleString('fr-FR')
  const mo = n / (1024 * 1024)
  return mo >= 1024 ? `${(mo / 1024).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Go` : `${mo.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} Mo`
}

function Champ({ libelle, children }: { libelle: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{libelle}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium">{children || '—'}</dd>
    </div>
  )
}

function BarreQuota({ r }: { r: RessourceQuota }) {
  const taux = r.illimite || r.taux === null ? 0 : Math.min(r.taux, 100)
  const couleur = r.depasse ? 'bg-danger' : taux >= 80 ? 'bg-warning' : 'bg-primary'
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span>{RESSOURCES[r.ressource] ?? r.ressource}</span>
        <span className="text-muted-foreground">
          {quantite(r.ressource, r.consommation)} / {r.illimite ? '∞' : quantite(r.ressource, r.limite ?? 0)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={taux} aria-valuemin={0} aria-valuemax={100} aria-label={RESSOURCES[r.ressource] ?? r.ressource}>
        <div className={`h-full rounded-full ${couleur}`} style={{ width: `${r.illimite ? 0 : taux}%` }} />
      </div>
    </div>
  )
}

/**
 * Fiche d'un cabinet.
 *
 * **Les actions proposées sont celles du serveur.** Le bouton « Suspendre »
 * n'apparaît que si `transitions_possibles` contient `SUSPENDU` : la machine à
 * états vit côté backend, l'écran ne la recopie pas. Chaque action exige un
 * motif, journalisé.
 */
export function CabinetDetailPage() {
  const { id = '' } = useParams()
  const client = useQueryClient()
  const [action, setAction] = useState<Action | null>(null)
  const [edition, setEdition] = useState(false)
  const [planChoisi, setPlanChoisi] = useState('')

  const peut = {
    suspendre: usePermission(PERMISSIONS.cabinetsSuspendre),
    activer: usePermission(PERMISSIONS.cabinetsActiver),
    resilier: usePermission(PERMISSIONS.cabinetsResilier),
    archiver: usePermission(PERMISSIONS.cabinetsArchiver),
    modifier: usePermission(PERMISSIONS.cabinetsModifier),
    quotas: usePermission(PERMISSIONS.plansLire),
    changerPlan: usePermission(PERMISSIONS.abonnementsEcrire),
    // La page « Rôles & permissions » est gardée par la lecture de l'équipe.
    roles: usePermission(PERMISSIONS.equipeLire),
    agenda: usePermission(PERMISSIONS.agendaLire),
  }

  const fiche = useQuery({
    queryKey: ['cabinet', id],
    queryFn: () => api.get<ApiReponse<CabinetDetail>>(`/platform/tenants/${id}`),
  })
  const historique = useQuery({
    queryKey: ['cabinet', id, 'historique'],
    queryFn: () => api.get<ApiReponse<EntreeHistorique[]>>(`/platform/tenants/${id}/historique`, { params: { limit: 50 } }),
  })
  const quotas = useQuery({
    queryKey: ['cabinet', id, 'quotas'],
    queryFn: () => api.get<ApiReponse<ResumeQuotas>>(`/platform/tenants/${id}/quotas`),
    enabled: peut.quotas,
  })
  const plans = useQuery({
    queryKey: ['plans', { actifs: true }],
    queryFn: () => api.get<ApiReponse<Plan[]>>('/platform/plans', { params: { actif_seulement: true } }),
    enabled: action === 'plan',
  })

  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: ['cabinet', id] })
    void client.invalidateQueries({ queryKey: ['cabinets'] })
    void client.invalidateQueries({ queryKey: ['abonnements'] })
  }

  const executer = useMutation({
    mutationFn: async ({ type, motif }: { type: Action; motif: string }) => {
      const abonnement = fiche.data?.data.abonnement as AbonnementResume | null | undefined
      switch (type) {
        case 'suspension':
        case 'reactivation':
        case 'resiliation':
          return api.post(`/platform/tenants/${id}/${type}`, { motif })
        case 'archiver':
        case 'desarchiver':
          return api.post(`/platform/tenants/${id}/archivage`, { archiver: type === 'archiver', motif })
        case 'plan':
          if (!abonnement) throw new Error("Ce cabinet n'a pas d'abonnement.")
          if (!planChoisi) throw new Error('Choisissez un plan.')
          return api.post(`/platform/subscriptions/${abonnement.id}/plan`, { plan_code: planChoisi, motif })
      }
    },
    onSuccess: () => {
      rafraichir()
      toast.success('Action enregistrée.')
    },
  })

  if (fiche.isPending) {
    return (
      <AppShell>
        <div className="space-y-4">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-48 w-full" />
        </div>
      </AppShell>
    )
  }

  if (fiche.isError) {
    return (
      <AppShell>
        <PageHeader titre="Cabinet" retour={{ to: '/cabinets', label: 'Retour aux cabinets' }} />
        <Card className="mt-6 space-y-3 p-6">
          <p role="alert" className="text-sm text-danger">{messageErreur(fiche.error)}</p>
          <Button variant="outline" size="sm" onClick={() => void fiche.refetch()}>
            Réessayer
          </Button>
        </Card>
      </AppShell>
    )
  }

  const c = fiche.data.data
  const s = statutCabinet(c.statut)
  const transitions = c.transitions_possibles ?? []
  const abonnement = c.abonnement as AbonnementResume | null | undefined
  // `archivable` porte l'état « archivé » (nom historique du backend) : c'est
  // la colonne que le filtre « archive=true » du registre interroge.
  const archive = c.archivable === true

  const DIALOGUES: Record<Action, { titre: string; description: string; libelle: string; danger?: boolean }> = {
    suspension: {
      titre: `Désactiver ${c.nom}`,
      description:
        "Plus personne du cabinet ne peut se connecter, dès maintenant. Les données sont conservées et le cabinet peut être réactivé à tout moment.",
      libelle: 'Désactiver',
      danger: true,
    },
    reactivation: {
      titre: c.statut === 'ESSAI' ? `Passer ${c.nom} en actif` : `Réactiver ${c.nom}`,
      description: 'Le cabinet retrouve un accès complet.',
      libelle: c.statut === 'ESSAI' ? 'Passer en actif' : 'Réactiver',
    },
    resiliation: {
      titre: `Résilier ${c.nom}`,
      description: "État terminal : aucune transition n'est possible ensuite. L'accès est coupé.",
      libelle: 'Résilier définitivement',
      danger: true,
    },
    archiver: {
      titre: `Archiver ${c.nom}`,
      description: "Le cabinet disparaît du registre courant. L'archivage est réversible.",
      libelle: 'Archiver',
    },
    desarchiver: {
      titre: `Désarchiver ${c.nom}`,
      description: 'Le cabinet revient dans le registre courant.',
      libelle: 'Désarchiver',
    },
    plan: {
      titre: 'Changer de plan',
      description: "L'abonnement passe au plan choisi ; l'ancien plan reste dans l'historique.",
      libelle: 'Changer de plan',
    },
  }
  const dialogue = action ? DIALOGUES[action] : null

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          titre={c.nom}
          sousTitre={
            <span className="flex flex-wrap items-center gap-2">
              <StatusBadge tone={s.ton}>{s.texte}</StatusBadge>
              {archive && <StatusBadge tone="neutral">Archivé</StatusBadge>}
              <span className="text-muted-foreground">Créé le {date(c.date_creation)}</span>
            </span>
          }
          retour={{ to: '/cabinets', label: 'Retour aux cabinets' }}
          onRefresh={rafraichir}
        >
          {peut.roles && (
            <Link to={`/roles?onglet=cabinets&cabinet=${c.tenant_id}`} className={buttonVariants({ variant: 'outline' })}>
              <KeyRound aria-hidden />
              Rôles du cabinet
            </Link>
          )}
          {peut.modifier && (
            <Button variant="outline" onClick={() => setEdition(true)}>
              <Pencil aria-hidden />
              Modifier
            </Button>
          )}
          {transitions.includes('ACTIF') && peut.activer && (
            <Button variant="outline" onClick={() => setAction('reactivation')}>
              <PlayCircle aria-hidden />
              {c.statut === 'ESSAI' ? 'Passer en actif' : 'Réactiver'}
            </Button>
          )}
          {transitions.includes('SUSPENDU') && peut.suspendre && (
            <Button variant="outline" onClick={() => setAction('suspension')}>
              <PauseCircle aria-hidden />
              Désactiver
            </Button>
          )}
          {transitions.includes('RESILIE') && peut.resilier && (
            <Button variant="danger" onClick={() => setAction('resiliation')}>
              <Ban aria-hidden />
              Résilier
            </Button>
          )}
          {peut.archiver && (
            <Button variant="ghost" onClick={() => setAction(archive ? 'desarchiver' : 'archiver')}>
              {archive ? <ArchiveRestore aria-hidden /> : <Archive aria-hidden />}
              {archive ? 'Désarchiver' : 'Archiver'}
            </Button>
          )}
        </PageHeader>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle className="text-base">Informations</CardTitle>
              <LogoCabinet tenantId={c.tenant_id} nom={c.nom} url={c.logo_url} modifiable={peut.modifier} />
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Champ libelle="E-mail">{c.email}</Champ>
                <Champ libelle="Téléphone">{c.telephone}</Champ>
                <Champ libelle="NINEA">{c.ninea}</Champ>
                <Champ libelle="Ville">{c.ville}</Champ>
                <Champ libelle="Pays">{c.pays}</Champ>
                <Champ libelle="Adresse du siège">{c.adresse_siege}</Champ>
                <Champ libelle="Site web">{c.site_web}</Champ>
                <Champ libelle="Langue / devise">{`${c.langue ?? '—'} · ${c.devise ?? '—'}`}</Champ>
                <Champ libelle="Fuseau horaire">{c.fuseau_horaire}</Champ>
                <Champ libelle="Base de données">{c.db_name}</Champ>
                <Champ libelle="État technique">{c.statut_technique}</Champ>
                <Champ libelle="Identifiant">
                  <span className="font-mono text-xs">{c.tenant_id}</span>
                </Champ>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-2">
              <CardTitle className="text-base">Abonnement</CardTitle>
              {abonnement && peut.changerPlan && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setPlanChoisi('')
                    setAction('plan')
                  }}
                >
                  <Repeat aria-hidden />
                  Changer
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {abonnement ? (
                <dl className="grid gap-3">
                  <Champ libelle="Numéro">{abonnement.numero}</Champ>
                  <Champ libelle="Plan">{abonnement.plan}</Champ>
                  <div>
                    <dt className="text-xs text-muted-foreground">Statut</dt>
                    <dd className="mt-1">
                      <StatusBadge tone={statutAbonnement(abonnement.statut).ton}>
                        {statutAbonnement(abonnement.statut).texte}
                      </StatusBadge>
                    </dd>
                  </div>
                  <Champ libelle="Début">{date(abonnement.date_debut)}</Champ>
                  {abonnement.date_fin_essai && <Champ libelle="Fin d'essai">{date(abonnement.date_fin_essai)}</Champ>}
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">Aucun abonnement.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <AdminsCabinet tenantId={c.tenant_id} />

        {peut.agenda && <RendezVousCabinet tenantId={c.tenant_id} />}

        <div className="grid gap-6 lg:grid-cols-3">
          {peut.quotas && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Consommation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {quotas.isPending ? (
                  <Skeleton className="h-24 w-full" />
                ) : quotas.isError ? (
                  <p className="text-sm text-danger">{messageErreur(quotas.error)}</p>
                ) : (quotas.data.data.ressources ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {quotas.data.data.illimite ? 'Plan sans limite.' : 'Aucun relevé disponible.'}
                  </p>
                ) : (
                  (quotas.data.data.ressources as unknown as RessourceQuota[]).map((r) => <BarreQuota key={r.ressource} r={r} />)
                )}
                {quotas.data?.data.releve_jour && (
                  <p className="text-xs text-muted-foreground">Relevé du {date(quotas.data.data.releve_jour)}</p>
                )}
              </CardContent>
            </Card>
          )}

          <Card className={peut.quotas ? 'lg:col-span-2' : 'lg:col-span-3'}>
            <CardHeader>
              <CardTitle className="text-base">Historique des statuts</CardTitle>
            </CardHeader>
            <CardContent>
              {historique.isPending ? (
                <Skeleton className="h-24 w-full" />
              ) : historique.isError ? (
                <p className="text-sm text-danger">{messageErreur(historique.error)}</p>
              ) : (historique.data.data ?? []).length === 0 ? (
                <EmptyState titre="Aucun changement de statut" description="Les transitions apparaîtront ici, avec leur motif." />
              ) : (
                <ol className="relative space-y-4 border-l border-border pl-5">
                  {historique.data.data.map((h, i) => (
                    <li key={i} className="relative">
                      <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-card bg-primary" aria-hidden />
                      <p className="flex flex-wrap items-center gap-2 text-sm">
                        <StatusBadge tone={statutCabinet(h.statut_precedent).ton}>{statutCabinet(h.statut_precedent).texte}</StatusBadge>
                        <span aria-hidden>→</span>
                        <StatusBadge tone={statutCabinet(h.statut_nouveau).ton}>{statutCabinet(h.statut_nouveau).texte}</StatusBadge>
                        <span className="text-xs text-muted-foreground">{dateHeure(h.horodatage)}</span>
                      </p>
                      <p className="mt-1 text-sm">{h.motif}</p>
                      <p className="text-xs text-muted-foreground">par {h.auteur_email}</p>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {dialogue && action && (
        <MotifDialog
          open
          onClose={() => setAction(null)}
          titre={dialogue.titre}
          description={dialogue.description}
          libelleConfirmer={dialogue.libelle}
          variante={dialogue.danger ? 'danger' : 'primary'}
          onConfirm={(motif) => executer.mutateAsync({ type: action, motif })}
        >
          {action === 'plan' && (
            <Select
              label="Nouveau plan"
              required
              value={planChoisi}
              onChange={(e) => setPlanChoisi(e.target.value)}
              options={[
                { value: '', label: plans.isPending ? 'Chargement…' : 'Choisir un plan' },
                ...(plans.data?.data ?? [])
                  .filter((p) => p.code !== abonnement?.plan)
                  .map((p) => ({ value: p.code, label: `${p.nom} — ${montant(p.prix, p.devise)}` })),
              ]}
            />
          )}
        </MotifDialog>
      )}

      {edition && <ModifierCabinetDrawer cabinet={c} onClose={() => setEdition(false)} onModifie={rafraichir} />}
    </AppShell>
  )
}
