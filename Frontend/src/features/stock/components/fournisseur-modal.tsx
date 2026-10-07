import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Modal } from '@/components/ui/modal'
import { useToastStore } from '@/stores/toast-store'
import { stockApi } from '../services/stock-api'
import type { Fournisseur } from '../types'

/**
 * Création et modification d'un fournisseur.
 *
 * Un fournisseur n'est pas une donnée figée : un cabinet en ajoute, en change,
 * cesse de commander chez un grossiste. Les tenir en dur dans l'interface oblige
 * à redéployer pour un changement de fournisseur — et une liste rentrée à la main
 * finit toujours par diverger de la réalité, sans qu'aucune erreur ne le signale.
 *
 * Le même formulaire sert depuis la gestion des fournisseurs et depuis la saisie
 * d'une commande : découvrir sur le bon de commande qu'un fournisseur manque est
 * le moment naturel pour le créer, pas celui d'abandonner la commande.
 */
export function FournisseurModal({
  isOpen,
  fournisseur,
  onClose,
  onCree,
}: {
  isOpen: boolean
  fournisseur?: Fournisseur | null
  onClose: () => void
  /** Rappelé à la création : la saisie de commande sélectionne le nouveau. */
  onCree?: (fournisseur: Fournisseur) => void
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const edition = Boolean(fournisseur)

  const [nom, setNom] = useState('')
  const [contact, setContact] = useState('')
  const [telephone, setTelephone] = useState('')
  const [email, setEmail] = useState('')
  const [adresse, setAdresse] = useState('')
  const [notes, setNotes] = useState('')
  const [erreur, setErreur] = useState('')

  const enregistrer = useMutation({
    mutationFn: () => {
      const payload = {
        nom: nom.trim(),
        contact: contact.trim() || null,
        telephone: telephone.trim() || null,
        email: email.trim() || null,
        adresse: adresse.trim() || null,
        notes: notes.trim() || null,
      }
      return fournisseur
        ? stockApi.modifierFournisseur(fournisseur.id, payload)
        : stockApi.creerFournisseur(payload)
    },
    onSuccess: (resultat) => {
      addToast({
        type: 'success',
        message: edition
          ? `Fournisseur ${resultat.nom} mis à jour.`
          : `Fournisseur ${resultat.nom} créé.`,
      })
      void client.invalidateQueries({ queryKey: ['stock', 'fournisseurs'] })
      void client.invalidateQueries({ queryKey: ['stock', 'commandes'] })
      if (!edition) onCree?.(resultat)
      onClose()
    },
    onError: (e) => setErreur(e instanceof Error ? e.message : 'Enregistrement impossible.'),
  })

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={edition ? `Modifier ${fournisseur?.nom ?? ''}` : 'Nouveau fournisseur'}
      description={
        edition ? undefined : 'Le nom suffit : le reste pourra être complété plus tard.'
      }
      maxWidth="lg"
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          setErreur('')
          if (!nom.trim()) {
            setErreur('La raison sociale est obligatoire.')
            return
          }
          enregistrer.mutate()
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="f-nom" required>
            Raison sociale
          </Label>
          <Input id="f-nom" value={nom} onChange={(e) => setNom(e.target.value)} required autoFocus />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="f-contact">Personne à contacter</Label>
            <Input id="f-contact" value={contact} onChange={(e) => setContact(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-tel">Téléphone</Label>
            <Input id="f-tel" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="f-email">Email</Label>
          <Input id="f-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="f-adresse">Adresse</Label>
          <Input id="f-adresse" value={adresse} onChange={(e) => setAdresse(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="f-notes">Notes</Label>
          <Textarea
            id="f-notes"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Délais de livraison, conditions de paiement…"
          />
        </div>

        {erreur && (
          <p
            role="alert"
            className="rounded-xl2 border border-danger/30 bg-danger/10 px-3 py-2 text-sm"
          >
            {erreur}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" disabled={enregistrer.isPending}>
            {edition ? 'Enregistrer' : 'Créer le fournisseur'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
