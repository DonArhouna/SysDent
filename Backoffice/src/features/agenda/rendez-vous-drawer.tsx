import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import { messageErreur, TYPES_RENDEZ_VOUS } from '@/lib/libelles'
import { PERMISSIONS, type RendezVous, type RendezVousCreation, type Utilisateur } from '@/lib/plateforme'
import { useNomsCabinets } from '@/features/offres/noms-cabinets'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from '@/stores/toast-store'

const DUREES = [15, 30, 45, 60, 90, 120, 180, 240].map((m) => ({
  value: String(m),
  label: m < 60 ? `${m} min` : `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60}` : ''}`,
}))

/** `AAAA-MM-JJ` et `HH:MM` en heure LOCALE, depuis une date ISO. */
function enLocal(iso: string): { date: string; heure: string } {
  const d = new Date(iso)
  const deux = (n: number) => String(n).padStart(2, '0')
  return {
    date: `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`,
    heure: `${deux(d.getHours())}:${deux(d.getMinutes())}`,
  }
}

/**
 * Création ou modification d'un rendez-vous de l'équipe.
 *
 * Les heures se saisissent en heure locale et partent en ISO (UTC) : le
 * serveur stocke l'instant, chaque agent le voit dans son fuseau.
 */
export function RendezVousDrawer({
  rdv,
  initial,
  onClose,
}: {
  /** Rendez-vous à modifier ; absent pour une création. */
  rdv?: RendezVous | null
  /** Pré-remplissage d'une création (cabinet, date). */
  initial?: { tenant_id?: string; date?: string }
  onClose: () => void
}) {
  const client = useQueryClient()
  const moi = useAuthStore((e) => e.profil)
  const voitEquipe = usePermission(PERMISSIONS.equipeLire)
  const { cabinets } = useNomsCabinets()
  const local = rdv ? enLocal(rdv.debut) : { date: initial?.date ?? '', heure: '09:00' }

  const [f, setF] = useState({
    titre: rdv?.titre ?? '',
    type_rdv: rdv?.type_rdv ?? 'DEMO',
    date: local.date,
    heure: local.heure,
    duree: String(rdv?.duree_minutes ?? 60),
    cible: rdv ? (rdv.tenant_id ? 'cabinet' : 'prospect') : 'cabinet',
    tenant_id: rdv?.tenant_id ?? initial?.tenant_id ?? '',
    prospect_nom: rdv?.prospect_nom ?? '',
    contact_nom: rdv?.contact_nom ?? '',
    contact_email: rdv?.contact_email ?? '',
    contact_telephone: rdv?.contact_telephone ?? '',
    lieu: rdv?.lieu ?? '',
    lien_visio: rdv?.lien_visio ?? '',
    agent_id: rdv ? (rdv.agent_id ?? '') : (moi?.id ?? ''),
    notes: rdv?.notes ?? '',
  })
  const [notifier, setNotifier] = useState(true)

  // La liste de l'équipe demande la lecture des comptes ; sans elle, on se
  // limite à soi-même plutôt que d'afficher une liste vide.
  const equipe = useQuery({
    queryKey: ['equipe', 'agents'],
    queryFn: () => api.get<PageReponse<Utilisateur>>('/platform/users', { params: { statut: 'ACTIF', limit: 100 } }),
    enabled: voitEquipe,
  })
  const agents = voitEquipe
    ? (equipe.data?.items ?? []).map((u) => ({ value: u.id, label: `${u.prenom} ${u.nom}` }))
    : moi
      ? [{ value: moi.id, label: `${moi.prenom} ${moi.nom} (moi)` }]
      : []

  const enregistrement = useMutation({
    mutationFn: () => {
      const debut = new Date(`${f.date}T${f.heure}`)
      if (Number.isNaN(debut.getTime())) throw new Error('Date ou heure invalide.')
      const corps: RendezVousCreation = {
        titre: f.titre.trim(),
        type_rdv: f.type_rdv,
        debut: debut.toISOString(),
        duree_minutes: Number(f.duree),
        tenant_id: f.cible === 'cabinet' ? f.tenant_id || null : null,
        prospect_nom: f.cible === 'prospect' ? f.prospect_nom.trim() || null : null,
        contact_nom: f.contact_nom.trim() || null,
        contact_email: f.contact_email.trim() || null,
        contact_telephone: f.contact_telephone.trim() || null,
        lieu: f.lieu.trim() || null,
        lien_visio: f.lien_visio.trim() || null,
        agent_id: f.agent_id || null,
        notes: f.notes.trim() || null,
        notifier_contact: notifier,
      }
      return rdv
        ? api.patch<ApiReponse<RendezVous>>(`/platform/rendez-vous/${rdv.id}`, corps)
        : api.post<ApiReponse<RendezVous>>('/platform/rendez-vous', corps)
    },
    onSuccess: (r) => {
      void client.invalidateQueries({ queryKey: ['agenda'] })
      toast.success(
        `${rdv ? 'Rendez-vous modifié' : 'Rendez-vous planifié'}${r.data.contact_prevenu ? ' — contact prévenu par e-mail' : ''}.`,
      )
      onClose()
    },
  })

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    enregistrement.mutate()
  }

  const maj = (cle: keyof typeof f, valeur: string) => setF((x) => ({ ...x, [cle]: valeur }))

  return (
    <Drawer open onClose={enregistrement.isPending ? () => undefined : onClose} title={rdv ? 'Modifier le rendez-vous' : 'Nouveau rendez-vous'} width="lg">
      <form className="space-y-5" onSubmit={soumettre}>
        <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
          <Input label="Objet" required minLength={2} maxLength={150} value={f.titre} onChange={(e) => maj('titre', e.target.value)} autoFocus placeholder="Installation du logiciel" />
          <Select label="Type" value={f.type_rdv} onChange={(e) => maj('type_rdv', e.target.value)} options={TYPES_RENDEZ_VOUS} />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Input label="Date" type="date" required value={f.date} onChange={(e) => maj('date', e.target.value)} />
          <Input label="Heure" type="time" required value={f.heure} onChange={(e) => maj('heure', e.target.value)} />
          <Select label="Durée" value={f.duree} onChange={(e) => maj('duree', e.target.value)} options={DUREES} />
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Avec</legend>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" name="cible" checked={f.cible === 'cabinet'} onChange={() => maj('cible', 'cabinet')} />
              Un cabinet client
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="cible" checked={f.cible === 'prospect'} onChange={() => maj('cible', 'prospect')} />
              Un prospect
            </label>
          </div>
          {f.cible === 'cabinet' ? (
            <Select
              aria-label="Cabinet"
              required
              value={f.tenant_id}
              onChange={(e) => maj('tenant_id', e.target.value)}
              options={[{ value: '', label: 'Choisir un cabinet' }, ...cabinets.map((c) => ({ value: c.tenant_id, label: c.nom }))]}
            />
          ) : (
            <Input aria-label="Nom du prospect" required placeholder="Clinique dentaire Les Almadies" value={f.prospect_nom} onChange={(e) => maj('prospect_nom', e.target.value)} />
          )}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Contact</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="Nom" value={f.contact_nom} onChange={(e) => maj('contact_nom', e.target.value)} />
            <Input label="E-mail" type="email" value={f.contact_email} onChange={(e) => maj('contact_email', e.target.value)} />
            <Input label="Téléphone" value={f.contact_telephone} onChange={(e) => maj('contact_telephone', e.target.value)} />
          </div>
        </fieldset>

        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Lieu" placeholder="Adresse, ou « Visioconférence »" value={f.lieu} onChange={(e) => maj('lieu', e.target.value)} />
          <Input label="Lien de visioconférence" type="url" placeholder="https://meet…" value={f.lien_visio} onChange={(e) => maj('lien_visio', e.target.value)} />
        </div>

        <Select
          label="Agent"
          value={f.agent_id}
          onChange={(e) => maj('agent_id', e.target.value)}
          options={[{ value: '', label: 'Non assigné' }, ...agents]}
          helperText="Un agent ne peut pas avoir deux rendez-vous sur le même créneau."
        />
        <Textarea label="Notes internes" rows={3} value={f.notes} onChange={(e) => maj('notes', e.target.value)} helperText="Visibles de l'équipe seulement, jamais envoyées au contact." />

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={notifier} onChange={(e) => setNotifier(e.target.checked)} disabled={!f.contact_email.trim()} />
          Prévenir le contact par e-mail
          {!f.contact_email.trim() && <span className="text-xs text-muted-foreground">(renseignez son e-mail)</span>}
        </label>

        {enregistrement.isError && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {messageErreur(enregistrement.error)}
          </p>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={enregistrement.isPending}>
            Annuler
          </Button>
          <Button type="submit" disabled={enregistrement.isPending}>
            {enregistrement.isPending ? 'Enregistrement…' : rdv ? 'Enregistrer' : 'Planifier'}
          </Button>
        </div>
      </form>
    </Drawer>
  )
}
