import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { messageErreur } from '@/lib/libelles'
import type { CabinetDetail, CabinetModification } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'

const CHAMPS: Array<{ cle: keyof CabinetModification; libelle: string; type?: string }> = [
  { cle: 'nom', libelle: 'Nom du cabinet' },
  { cle: 'email', libelle: 'E-mail', type: 'email' },
  { cle: 'telephone', libelle: 'Téléphone' },
  { cle: 'ninea', libelle: 'NINEA' },
  { cle: 'ville', libelle: 'Ville' },
  { cle: 'pays', libelle: 'Pays' },
  { cle: 'adresse_siege', libelle: 'Adresse du siège' },
  { cle: 'site_web', libelle: 'Site web', type: 'url' },
]

/**
 * Modification des informations d'un cabinet.
 *
 * **N'envoie que ce qui a changé.** Un PATCH portant tous les champs écraserait
 * une modification faite entre-temps par un collègue, et le journal d'audit
 * montrerait des changements qui n'en sont pas.
 */
export function ModifierCabinetDrawer({
  cabinet,
  onClose,
  onModifie,
}: {
  cabinet: CabinetDetail
  onClose: () => void
  onModifie: () => void
}) {
  const initial = Object.fromEntries(CHAMPS.map(({ cle }) => [cle, (cabinet[cle as keyof CabinetDetail] as string | null) ?? '']))
  const [valeurs, setValeurs] = useState<Record<string, string>>(initial)
  const [motif, setMotif] = useState('')

  const modifs = Object.fromEntries(
    Object.entries(valeurs)
      .filter(([cle, v]) => v.trim() !== (initial[cle] ?? '').trim())
      .map(([cle, v]) => [cle, v.trim() === '' ? null : v.trim()]),
  ) as CabinetModification

  const enregistrement = useMutation({
    mutationFn: () => api.patch(`/platform/tenants/${cabinet.tenant_id}`, { ...modifs, motif: motif.trim() || null }),
    onSuccess: () => {
      onModifie()
      toast.success('Cabinet modifié.')
      onClose()
    },
  })

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    enregistrement.mutate()
  }

  const rien = Object.keys(modifs).length === 0

  return (
    <Drawer open onClose={enregistrement.isPending ? () => undefined : onClose} title={`Modifier ${cabinet.nom}`} width="lg">
      <form className="space-y-4" onSubmit={soumettre}>
        <div className="grid gap-3 sm:grid-cols-2">
          {CHAMPS.map(({ cle, libelle, type }) => (
            <Input
              key={cle}
              label={libelle}
              type={type}
              value={valeurs[cle] ?? ''}
              onChange={(e) => setValeurs((v) => ({ ...v, [cle]: e.target.value }))}
              required={cle === 'nom'}
            />
          ))}
        </div>
        <Textarea label="Motif" helperText="Facultatif, inscrit au journal d'audit." rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} />

        {enregistrement.isError && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {messageErreur(enregistrement.error)}
          </p>
        )}

        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
          {/* Un bouton grisé sans explication se lit comme un formulaire bloqué. */}
          <p className="mr-auto text-xs text-muted-foreground" role="status">
            {rien
              ? 'Modifiez au moins un champ pour pouvoir enregistrer.'
              : `${Object.keys(modifs).length} champ(s) modifié(s).`}
          </p>
          <Button type="button" variant="outline" onClick={onClose} disabled={enregistrement.isPending}>
            Annuler
          </Button>
          <Button type="submit" disabled={rien || enregistrement.isPending}>
            {enregistrement.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </Drawer>
  )
}
