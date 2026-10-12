import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Modal } from '@/components/ui/modal'
import { useToastStore } from '@/stores/toast-store'

import type { ActeCreate, ActeNomenclature } from '../types'
import { tarificationApi } from '../services/tarification-api'
import { normaliserMontant, validerMontant } from './validation'

/**
 * Creation et edition d'un acte de nomenclature.
 *
 * **Le tarif de base ne se saisit pas dans ce formulaire d'edition.** Le
 * serveur ne l'accepte pas sur un `PATCH` : le changer passerait par un tarif
 * de categorie, et c'est volontaire - un PATCH general qui le permettrait
 * changerait le prix sous les factures deja emises. Le formulaire d'edition ne
 * propose donc que ce que `PATCH` accepte, et le tarif se change dans le
 * panneau de tarifs, cote.
 *
 * A la creation, en revanche, le tarif de base est demande : un acte cree sans
 * prix n'a aucun sens, et le serveur l'exige.
 */

type Etat = {
  code: string
  libelle: string
  categorie: string
  tarifBase: string
  duree: string
  unitaire: boolean
}

const VIDE: Etat = {
  code: '',
  libelle: '',
  categorie: '',
  tarifBase: '',
  duree: '30',
  unitaire: false,
}

export function ActeModal({
  isOpen,
  onClose,
  acte,
  onSuccess,
}: {
  isOpen: boolean
  onClose: () => void
  /** `null` = creation. */
  acte: ActeNomenclature | null
  onSuccess?: () => void
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const creation = acte === null

  const [etat, setEtat] = useState<Etat>(VIDE)
  const [erreurs, setErreurs] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!isOpen) return
    setErreurs({})
    setEtat(
      acte
        ? {
            code: acte.code,
            libelle: acte.libelle,
            categorie: acte.categorie,
            tarifBase: acte.tarif_base,
            duree: String(acte.duree_estimee_min),
            unitaire: acte.unitaire,
          }
        : VIDE,
    )
  }, [isOpen, acte])

  const enregistrer = useMutation({
    mutationFn: async () => {
      const commun = {
        libelle: etat.libelle.trim(),
        categorie: etat.categorie.trim().toUpperCase(),
        duree_estimee_min: Number(etat.duree) || 30,
        unitaire: etat.unitaire,
      }
      if (creation) {
        const corps: ActeCreate = {
          code: etat.code.trim().toUpperCase(),
          ...commun,
          tarif_base: normaliserMontant(etat.tarifBase),
        }
        return tarificationApi.creerActe(corps)
      }
      return tarificationApi.modifierActe(acte.id, commun)
    },
    onSuccess: () => {
      addToast({
        type: 'success',
        message: creation ? 'Acte ajoute a la nomenclature.' : 'Acte mis a jour.',
      })
      void client.invalidateQueries({ queryKey: ['tarification', 'actes'] })
      onSuccess?.()
      onClose()
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "L'enregistrement a échoué.",
      }),
  })

  function valider(): boolean {
    const trouvees: Record<string, string> = {}
    if (etat.libelle.trim().length < 2) trouvees.libelle = 'Le libelle est obligatoire.'
    if (etat.categorie.trim().length < 2)
      trouvees.categorie = 'La categorie est obligatoire (SOINS, PROTHESE...).'
    if (etat.duree && (Number(etat.duree) < 1 || Number(etat.duree) > 480))
      trouvees.duree = 'La duree doit etre comprise entre 1 et 480 minutes.'
    if (creation) {
      if (etat.code.trim().length < 2) trouvees.code = 'Le code est obligatoire.'
      const montant = validerMontant(etat.tarifBase)
      if (!montant.valide) trouvees.tarifBase = montant.message
    }
    setErreurs(trouvees)
    return Object.keys(trouvees).length === 0
  }

  function soumettre() {
    if (!valider()) return
    enregistrer.mutate()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={creation ? 'Nouvel acte' : `Modifier ${acte?.code ?? ''}`}
      description={
        creation
          ? "Le tarif de base est repris dans la categorie standard et sert de reference a toute facture."
          : "Le tarif ne se change pas ici : il se modifie par categorie de patient, dans le panneau des tarifs."
      }
      size="lg"
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Code *"
            placeholder="DT01"
            value={etat.code}
            disabled={!creation}
            error={erreurs.code}
            onChange={(e) => setEtat({ ...etat, code: e.target.value })}
            helperText={creation ? undefined : "Le code identifie l'acte : il n'est plus modifiable."}
          />
          <Input
            label="Categorie *"
            placeholder="SOINS"
            value={etat.categorie}
            error={erreurs.categorie}
            onChange={(e) => setEtat({ ...etat, categorie: e.target.value })}
          />
        </div>

        <Input
          label="Libelle *"
          placeholder="Denture partielle"
          value={etat.libelle}
          error={erreurs.libelle}
          onChange={(e) => setEtat({ ...etat, libelle: e.target.value })}
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {creation && (
            <Input
              label="Tarif de base * (FCFA)"
              inputMode="decimal"
              placeholder="15000"
              value={etat.tarifBase}
              error={erreurs.tarifBase}
              onChange={(e) => setEtat({ ...etat, tarifBase: e.target.value })}
              helperText="Reference du cabinet, copiee dans la categorie standard."
            />
          )}
          <Input
            label="Duree estimee (min)"
            inputMode="numeric"
            value={etat.duree}
            error={erreurs.duree}
            onChange={(e) => setEtat({ ...etat, duree: e.target.value })}
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={etat.unitaire}
            onChange={(e) => setEtat({ ...etat, unitaire: e.target.checked })}
          />
          Soin unitaire (porte sur une dent, le numero FDI sera obligatoire)
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