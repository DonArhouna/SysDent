import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, CircleCheckBig, Pencil, Video, XCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { StatusBadge } from '@/components/ui/status-badge'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { date, heure, messageErreur, statutRendezVous, typeRendezVous } from '@/lib/libelles'
import { PERMISSIONS, type RendezVous } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'

/** Cabinet (lien vers sa fiche) ou prospect. */
export function Cible({ rdv }: { rdv: RendezVous }) {
  if (rdv.tenant_id) {
    return (
      <Link to={`/cabinets/${rdv.tenant_id}`} className="hover:text-primary hover:underline">
        {rdv.tenant_nom ?? 'Cabinet'}
      </Link>
    )
  }
  return <span>{rdv.prospect_nom} <span className="text-xs text-muted-foreground">(prospect)</span></span>
}

function Ligne({ libelle, children }: { libelle: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2 text-sm">
      <dt className="text-muted-foreground">{libelle}</dt>
      <dd className="min-w-0 break-words">{children || '—'}</dd>
    </div>
  )
}

/**
 * Détail d'un rendez-vous et ses actions : modifier, confirmer, marquer
 * effectué, annuler (avec motif). Un rendez-vous effectué ou annulé est figé.
 */
export function DetailRendezVous({
  rdv,
  onClose,
  onModifier,
}: {
  rdv: RendezVous
  onClose: () => void
  onModifier: () => void
}) {
  const client = useQueryClient()
  const peutEcrire = usePermission(PERMISSIONS.agendaEcrire)
  const [annulation, setAnnulation] = useState(false)
  const t = typeRendezVous(rdv.type_rdv)
  const s = statutRendezVous(rdv.statut)
  const fige = rdv.statut === 'EFFECTUE' || rdv.statut === 'ANNULE'

  const statut = useMutation({
    mutationFn: ({ nouveau, motif }: { nouveau: string; motif?: string }) =>
      api.post<ApiReponse<RendezVous>>(`/platform/rendez-vous/${rdv.id}/statut`, { statut: nouveau, motif: motif ?? null }),
    onSuccess: (r) => {
      void client.invalidateQueries({ queryKey: ['agenda'] })
      toast.success(`Rendez-vous ${statutRendezVous(r.data.statut).texte.toLowerCase()}${r.data.contact_prevenu ? ' — contact prévenu' : ''}.`)
      onClose()
    },
    onError: (e) => toast.error(messageErreur(e)),
  })

  return (
    <Drawer open onClose={onClose} title={rdv.titre} width="md">
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">
          <StatusBadge tone={t.ton}>{t.texte}</StatusBadge>
          <StatusBadge tone={s.ton}>{s.texte}</StatusBadge>
        </div>

        <dl className="space-y-2">
          <Ligne libelle="Quand">{`${date(rdv.debut)}, ${heure(rdv.debut)} – ${heure(rdv.fin)}`}</Ligne>
          <Ligne libelle="Avec"><Cible rdv={rdv} /></Ligne>
          <Ligne libelle="Agent">{rdv.agent_nom ?? 'Non assigné'}</Ligne>
          <Ligne libelle="Contact">
            {[rdv.contact_nom, rdv.contact_email, rdv.contact_telephone].filter(Boolean).join(' · ')}
          </Ligne>
          <Ligne libelle="Lieu">{rdv.lieu}</Ligne>
          {rdv.lien_visio && (
            <Ligne libelle="Visio">
              <a href={rdv.lien_visio} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-primary hover:underline">
                <Video className="h-4 w-4" aria-hidden />
                Rejoindre
              </a>
            </Ligne>
          )}
          {rdv.notes && <Ligne libelle="Notes"><span className="whitespace-pre-line">{rdv.notes}</span></Ligne>}
          {rdv.motif_annulation && <Ligne libelle="Motif d'annulation">{rdv.motif_annulation}</Ligne>}
          <Ligne libelle="Créé par">{rdv.cree_par}</Ligne>
        </dl>

        {peutEcrire && !fige && (
          <div className="grid gap-2 border-t border-border pt-4 sm:grid-cols-2">
            <Button variant="outline" onClick={onModifier}>
              <Pencil aria-hidden />
              Modifier
            </Button>
            {rdv.statut === 'PLANIFIE' && (
              <Button variant="outline" onClick={() => statut.mutate({ nouveau: 'CONFIRME' })} disabled={statut.isPending}>
                <CheckCircle2 aria-hidden />
                Confirmer
              </Button>
            )}
            <Button variant="outline" onClick={() => statut.mutate({ nouveau: 'EFFECTUE' })} disabled={statut.isPending}>
              <CircleCheckBig aria-hidden />
              Marquer effectué
            </Button>
            <Button variant="danger" onClick={() => setAnnulation(true)}>
              <XCircle aria-hidden />
              Annuler
            </Button>
          </div>
        )}
        {fige && <p className="text-xs text-muted-foreground">Un rendez-vous effectué ou annulé ne se modifie plus.</p>}
      </div>

      <MotifDialog
        open={annulation}
        onClose={() => setAnnulation(false)}
        titre={`Annuler « ${rdv.titre} »`}
        description={rdv.contact_email ? `Le contact (${rdv.contact_email}) en sera prévenu par e-mail.` : undefined}
        libelleConfirmer="Annuler le rendez-vous"
        variante="danger"
        onConfirm={(motif) => statut.mutateAsync({ nouveau: 'ANNULE', motif })}
      />
    </Drawer>
  )
}
