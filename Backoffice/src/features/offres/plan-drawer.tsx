import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { messageErreur } from '@/lib/libelles'
import type { Plan, PlanCreation, PlanModification } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'

const GO = 1024 ** 3

/** Quotas connus du backend. Champ vide = illimité (clé absente du plan). */
export const QUOTAS: Array<{ cle: string; libelle: string; enGo?: boolean }> = [
  { cle: 'utilisateurs', libelle: 'Utilisateurs' },
  { cle: 'sites', libelle: 'Sites' },
  { cle: 'praticiens', libelle: 'Praticiens' },
  { cle: 'stockage_octets', libelle: 'Stockage (Go)', enGo: true },
  { cle: 'sms_par_mois', libelle: 'SMS par mois' },
]

export const FONCTIONNALITES: Array<{ cle: string; libelle: string }> = [
  { cle: 'stock', libelle: 'Gestion de stock' },
  { cle: 'sms', libelle: 'Envoi de SMS' },
  { cle: 'rapports', libelle: 'Rapports' },
  { cle: 'export_patients', libelle: 'Export des patients' },
  { cle: 'api', libelle: 'Accès API' },
]

function quotasVersSaisie(quotas: Record<string, unknown> | undefined): Record<string, string> {
  return Object.fromEntries(
    QUOTAS.map(({ cle, enGo }) => {
      const v = quotas?.[cle]
      if (typeof v !== 'number') return [cle, '']
      return [cle, String(enGo ? Math.round((v / GO) * 10) / 10 : v)]
    }),
  )
}

function saisieVersQuotas(saisie: Record<string, string>): Record<string, number> {
  const sortie: Record<string, number> = {}
  for (const { cle, enGo } of QUOTAS) {
    const brut = saisie[cle]?.trim()
    if (!brut) continue
    const n = Number(brut)
    if (Number.isFinite(n) && n >= 0) sortie[cle] = Math.round(enGo ? n * GO : n)
  }
  return sortie
}

/**
 * Création ou modification d'un plan.
 *
 * **Modifier crée une nouvelle version.** Les abonnements existants gardent le
 * plan figé au moment de leur souscription : changer un prix ici ne change pas
 * la facture d'un client déjà abonné. Un motif est donc demandé à la modification.
 */
export function PlanDrawer({ plan, onClose }: { plan: Plan | null; onClose: () => void }) {
  const client = useQueryClient()
  const creation = plan === null
  const [f, setF] = useState({
    code: plan?.code ?? '',
    nom: plan?.nom ?? '',
    description: plan?.description ?? '',
    prix: plan ? String(Number(plan.prix)) : '0',
    devise: plan?.devise ?? 'XOF',
    periodicite: plan?.periodicite ?? 'MENSUEL',
    jours_essai: String(plan?.jours_essai ?? 14),
  })
  const [quotas, setQuotas] = useState(quotasVersSaisie(plan?.quotas as Record<string, unknown> | undefined))
  const [features, setFeatures] = useState<Record<string, boolean>>(
    Object.fromEntries(FONCTIONNALITES.map(({ cle }) => [cle, Boolean((plan?.features as Record<string, unknown> | undefined)?.[cle])])),
  )
  const [motif, setMotif] = useState('')

  const enregistrement = useMutation({
    mutationFn: () => {
      const commun = {
        nom: f.nom.trim(),
        description: f.description.trim() || null,
        prix: Number(f.prix),
        devise: f.devise.trim().toUpperCase(),
        periodicite: f.periodicite,
        jours_essai: Number(f.jours_essai),
        quotas: saisieVersQuotas(quotas),
        features,
      }
      if (creation) {
        const corps: PlanCreation = { ...commun, code: f.code.trim().toUpperCase(), plan_defaut: false }
        return api.post('/platform/plans', corps)
      }
      const corps: PlanModification = { ...commun, motif: motif.trim() || null }
      return api.patch(`/platform/plans/${plan.id}`, corps)
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['plans'] })
      toast.success(creation ? 'Plan créé.' : 'Nouvelle version du plan enregistrée.')
      onClose()
    },
  })

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    enregistrement.mutate()
  }

  return (
    <Drawer
      open
      onClose={enregistrement.isPending ? () => undefined : onClose}
      title={creation ? 'Nouveau plan' : `Modifier ${plan.nom}`}
      description={creation ? undefined : `Version actuelle : ${plan.version}. L'enregistrement crée la version ${plan.version + 1}.`}
      width="lg"
    >
      <form className="space-y-5" onSubmit={soumettre}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Code"
            required
            disabled={!creation}
            value={f.code}
            onChange={(e) => setF({ ...f, code: e.target.value })}
            helperText={creation ? 'Majuscules, ex. PRO. Non modifiable ensuite.' : undefined}
          />
          <Input label="Nom" required value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} />
        </div>
        <Textarea label="Description" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <div className="grid gap-3 sm:grid-cols-4">
          <Input label="Prix" type="number" min={0} step="any" required value={f.prix} onChange={(e) => setF({ ...f, prix: e.target.value })} />
          <Input label="Devise" maxLength={3} required value={f.devise} onChange={(e) => setF({ ...f, devise: e.target.value })} />
          <Select
            label="Périodicité"
            value={f.periodicite}
            onChange={(e) => setF({ ...f, periodicite: e.target.value })}
            options={[
              { value: 'MENSUEL', label: 'Mensuel' },
              { value: 'ANNUEL', label: 'Annuel' },
              { value: 'GRATUIT', label: 'Gratuit' },
            ]}
          />
          <Input label="Jours d'essai" type="number" min={0} max={365} value={f.jours_essai} onChange={(e) => setF({ ...f, jours_essai: e.target.value })} />
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Quotas</legend>
          <p className="text-xs text-muted-foreground">Laisser vide pour « illimité ».</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {QUOTAS.map(({ cle, libelle }) => (
              <Input
                key={cle}
                label={libelle}
                type="number"
                min={0}
                step="any"
                placeholder="Illimité"
                value={quotas[cle] ?? ''}
                onChange={(e) => setQuotas((q) => ({ ...q, [cle]: e.target.value }))}
              />
            ))}
          </div>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Fonctionnalités</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {FONCTIONNALITES.map(({ cle, libelle }) => (
              <label key={cle} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={features[cle] ?? false} onChange={(e) => setFeatures((x) => ({ ...x, [cle]: e.target.checked }))} />
                {libelle}
              </label>
            ))}
          </div>
        </fieldset>

        {!creation && (
          <Textarea label="Motif du changement" helperText="Conservé dans l'historique des versions." rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} />
        )}

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
            {enregistrement.isPending ? 'Enregistrement…' : creation ? 'Créer le plan' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </Drawer>
  )
}
