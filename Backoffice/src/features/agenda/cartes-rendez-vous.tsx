import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CalendarDays, Plus } from 'lucide-react'

import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { usePermission } from '@/guards/can'
import { api, type PageReponse } from '@/lib/api'
import { date, heure, messageErreur, statutRendezVous, typeRendezVous } from '@/lib/libelles'
import { PERMISSIONS, type RendezVous } from '@/lib/plateforme'
import { useAuthStore } from '@/stores/auth-store'
import { DetailRendezVous } from './detail-rendez-vous'
import { RendezVousDrawer } from './rendez-vous-drawer'

function ListeCompacte({ rdvs, onChoisir, avecCible }: { rdvs: RendezVous[]; onChoisir: (r: RendezVous) => void; avecCible: boolean }) {
  return (
    <ul className="divide-y divide-border">
      {rdvs.map((r) => (
        <li key={r.id}>
          <button type="button" onClick={() => onChoisir(r)} className="flex w-full items-center justify-between gap-3 py-2 text-left hover:text-primary">
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{r.titre}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {date(r.debut)} à {heure(r.debut)}
                {avecCible && ` · ${r.tenant_nom ?? r.prospect_nom}`}
                {r.agent_nom && ` · ${r.agent_nom}`}
              </span>
            </span>
            <span className="flex shrink-0 gap-1">
              <StatusBadge tone={typeRendezVous(r.type_rdv).ton}>{typeRendezVous(r.type_rdv).texte}</StatusBadge>
              {r.statut !== 'PLANIFIE' && (
                <StatusBadge tone={statutRendezVous(r.statut).ton}>{statutRendezVous(r.statut).texte}</StatusBadge>
              )}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

function useDetail() {
  const [selection, setSelection] = useState<RendezVous | null>(null)
  const [edition, setEdition] = useState<RendezVous | null>(null)
  const rendu = (
    <>
      {selection && (
        <DetailRendezVous
          rdv={selection}
          onClose={() => setSelection(null)}
          onModifier={() => {
            setEdition(selection)
            setSelection(null)
          }}
        />
      )}
      {edition && <RendezVousDrawer rdv={edition} onClose={() => setEdition(null)} />}
    </>
  )
  return { setSelection, rendu }
}

/** Rendez-vous de l'équipe avec CE cabinet (fiche du cabinet). */
export function RendezVousCabinet({ tenantId }: { tenantId: string }) {
  const peutLire = usePermission(PERMISSIONS.agendaLire)
  const peutEcrire = usePermission(PERMISSIONS.agendaEcrire)
  const [creation, setCreation] = useState(false)
  const { setSelection, rendu } = useDetail()

  const requete = useQuery({
    queryKey: ['agenda', 'cabinet', tenantId],
    queryFn: () => api.get<PageReponse<RendezVous>>('/platform/rendez-vous', { params: { tenant_id: tenantId, limit: 100 } }),
    enabled: peutLire,
  })
  if (!peutLire) return null

  const tous = requete.data?.items ?? []
  const maintenant = Date.now()
  const aVenir = tous.filter((r) => new Date(r.fin).getTime() >= maintenant && r.statut !== 'ANNULE')
  const passes = tous.filter((r) => !aVenir.includes(r)).reverse().slice(0, 5)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarDays className="h-4 w-4 text-muted-foreground" aria-hidden />
          Rendez-vous avec ce cabinet
        </CardTitle>
        {peutEcrire && (
          <Button size="sm" variant="outline" onClick={() => setCreation(true)}>
            <Plus aria-hidden />
            Planifier
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {requete.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : requete.isError ? (
          <p className="text-sm text-danger">{messageErreur(requete.error)}</p>
        ) : tous.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun rendez-vous avec ce cabinet.</p>
        ) : (
          <>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">À venir</p>
              {aVenir.length ? <ListeCompacte rdvs={aVenir} onChoisir={setSelection} avecCible={false} /> : <p className="text-sm text-muted-foreground">Aucun.</p>}
            </div>
            {passes.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Historique</p>
                <ListeCompacte rdvs={passes} onChoisir={setSelection} avecCible={false} />
              </div>
            )}
          </>
        )}
      </CardContent>
      {creation && <RendezVousDrawer initial={{ tenant_id: tenantId }} onClose={() => setCreation(false)} />}
      {rendu}
    </Card>
  )
}

/** Prochains rendez-vous de l'agent connecté (tableau de bord). */
export function ProchainsRendezVous() {
  const peutLire = usePermission(PERMISSIONS.agendaLire)
  const moi = useAuthStore((e) => e.profil?.id)
  const { setSelection, rendu } = useDetail()
  const [maintenant] = useState(() => new Date().toISOString())

  const requete = useQuery({
    queryKey: ['agenda', 'prochains', moi],
    queryFn: () =>
      api.get<PageReponse<RendezVous>>('/platform/rendez-vous', { params: { du: maintenant, agent_id: moi, limit: 20 } }),
    enabled: peutLire && Boolean(moi),
  })
  if (!peutLire) return null

  const prochains = (requete.data?.items ?? []).filter((r) => r.statut !== 'ANNULE').slice(0, 5)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarDays className="h-4 w-4 text-muted-foreground" aria-hidden />
          Mes prochains rendez-vous
        </CardTitle>
        <Link to="/agenda" className={buttonVariants({ variant: 'link', size: 'sm' })}>
          Voir l'agenda →
        </Link>
      </CardHeader>
      <CardContent>
        {requete.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : requete.isError ? (
          <p className="text-sm text-danger">{messageErreur(requete.error)}</p>
        ) : prochains.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun rendez-vous prévu.</p>
        ) : (
          <ListeCompacte rdvs={prochains} onChoisir={setSelection} avecCible />
        )}
      </CardContent>
      {rendu}
    </Card>
  )
}
