import { useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToastStore } from '@/stores/toast-store'
import { rbacApi } from '../services/rbac-api'
import type { Role } from '../types'

interface RoleModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (role: Role) => void
}

export function RoleModal({ isOpen, onClose, onSuccess }: RoleModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [niveau, setNiveau] = useState(3)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nom.trim()) {
      addToast({ type: 'warning', message: 'Le nom du rôle est obligatoire.' })
      return
    }

    try {
      setSubmitting(true)
      const res = await rbacApi.creerRole({
        nom: nom.trim().toUpperCase(),
        description: description.trim() || undefined,
        niveau_hierarchie: Number(niveau),
      })
      addToast({ type: 'success', message: `Rôle ${res.data.nom} créé avec succès.` })
      onSuccess(res.data)
      onClose()
    } catch {
      // toast géré par l'intercepteur API
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Créer un nouveau rôle métier" size="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Nom du rôle (identifiant technique) *"
          placeholder="Ex: ASSISTANT_CHIRURGICAL, SECRETAIRE_ACCUEIL"
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          required
          helperText="Sera normalisé en lettres majuscules."
        />

        <Input
          label="Description du rôle"
          placeholder="Ex: Accès en lecture seule aux dossiers et gestion des RDV"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        <Input
          label="Niveau hiérarchique (1 = ADMIN_CABINET, 10 = subalterne)"
          type="number"
          min={1}
          max={10}
          value={niveau}
          onChange={(e) => setNiveau(parseInt(e.target.value) || 3)}
          required
        />

        <div className="p-3 bg-card rounded-lg border border-border text-xs text-muted-foreground">
          Note de sécurité : Les rôles sont créés sans aucune permission initiale. Vous lui
          attribuerez ses permissions via la matrice de droits après création.
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Création...' : 'Créer le rôle'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
