import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Modal } from '@/components/ui/modal'
import { Select } from '@/components/ui/select'
import { useToastStore } from '@/stores/toast-store'

import type { OrganismeAssurance, OrganismeCreate } from '../types'
import { tarificationApi } from '../services/tarification-api'

/**
 * Creation et edition d'un organisme payeur.
 *
 * Les deux natures d'organisme viennent d'une liste **ecrite ici**, et c'est
 * delibere : `ASSURANCE` et `MUTUELLE` sont les deux seules valeurs qu'accepte
 * le serveur, elles sont un choix de forme et non une donnee du cabinet. Tout
 * ce qui est du cabinet - les organismes eux-memes, les taux, les numeros de
 * police - vient de l'API. Un cabinet qui traite la Songu ne doit pas avoir a
 * la saisir.
 *
 * Le code n'est pas modifiable apres creation : il sert de clef stable dans
 * les imports et les references, et le changer laisserait deux codes pour le
 * meme payeur.
 */
export function OrganismeModal({
  isOpen,
  onClose,
  organisme,
  onSuccess,
}: {
  isOpen: boolean
  onClose: () => void
  /** `null` = creation. */
  organisme: OrganismeAssurance | null
  onSuccess?: () => void
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const creation = organisme === null

  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [type, setType] = useState('ASSURANCE')
  const [actif, setActif] = useState(true)
  const [erreurs, setErreurs] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!isOpen) return
    setErreurs({})
    setCode(organisme?.code ?? '')
    setNom(organisme?.nom ?? '')
    setType(organisme?.type_organisme ?? 'ASSURANCE')
    setActif(organisme?.actif ?? true)
  }, [isOpen, organisme])

  const enregistrer = useMutation({
    mutationFn: () => {
      if (creation) {
        const corps: OrganismeCreate = {
          code: code.trim().toLowerCase(),
          nom: nom.trim(),
          type_organisme: type,
          actif,
        }
        return tarificationApi.creerOrganisme(corps)
      }
      return tarificationApi.modifierOrganisme(organisme.id, {
        nom: nom.trim(),
        type_organisme: type,
        actif,
      })
    },
    onSuccess: () => {
      addToast({
        type: 'success',
        message: creation ? 'Organisme ajoute.' : 'Organisme mis a jour.',
      })
      void client.invalidateQueries({ queryKey: ['tarification', 'organismes'] })
      onSuccess?.()
      onClose()
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "L'enregistrement a échoué.",
      }),
  })

  function soumettre() {
    const trouvees: Record<string, string> = {}
    if (nom.trim().length < 2) trouvees.nom = 'Le nom est obligatoire.'
    if (creation && !/^[A-Za-z0-9_-]{2,50}$/.test(code.trim())) {
      trouvees.code = 'Le code ne peut contenir que des lettres, chiffres, - et _.'
    }
    setErreurs(trouvees)
    if (Object.keys(trouvees).length > 0) return
    enregistrer.mutate()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={creation ? 'Nouvel organisme' : `Modifier ${organisme?.code ?? ''}`}
      description={
        creation
          ? "Un organisme payeur est propre au cabinet : ce que le cabinet ne traite pas n'a pas a etre saisi."
          : 'Le code reste stable : il sert de reference dans les ecritures.'
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Code *"
            placeholder="sona"
            value={code}
            disabled={!creation}
            error={erreurs.code}
            onChange={(e) => setCode(e.target.value)}
          />
          <Select
            label="Nature *"
            value={type}
            onChange={(e) => setType(e.target.value)}
            disabled={!creation}
            options={[
              { value: 'ASSURANCE', label: 'Assurance (regime obligatoire)' },
              { value: 'MUTUELLE', label: 'Mutuelle complementaire' },
            ]}
          />
        </div>

        <Input
          label="Nom *"
          placeholder="Mutuelle des employes"
          value={nom}
          error={erreurs.nom}
          onChange={(e) => setNom(e.target.value)}
        />

        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={actif}
            onChange={(e) => setActif(e.target.checked)}
          />
          Organisme actif
        </label>
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>
          Annuler
        </Button>
        <Button onClick={soumettre} disabled={enregistrer.isPending}>
          {enregistrer.isPending ? 'Enregistrement...' : creation ? 'Creer' : 'Enregistrer'}
        </Button>
      </div>
    </Modal>
  )
}