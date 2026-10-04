import { useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useToastStore } from '@/stores/toast-store'
import { stockApi } from '../services/stock-api'
import type { ArticleStock, MouvementStock, TypeMouvementStock } from '../types'

interface MouvementModalProps {
  isOpen: boolean
  onClose: () => void
  articles: ArticleStock[]
  articleInitial?: ArticleStock | null
  onSuccess: (mouvement: MouvementStock) => void
}

const TYPES_MOUVEMENT = [
  { value: 'ENTREE', label: 'Entrée en stock (Livraison fournisseur)' },
  { value: 'SORTIE_CONSULTATION', label: 'Sortie pour consultation / soin' },
  { value: 'PERTE_PEREMPTION', label: 'Rebut / Péremption / Casse' },
  { value: 'AJUSTEMENT_INVENTAIRE', label: 'Ajustement inventaire physique' },
]

export function MouvementModal({
  isOpen,
  onClose,
  articles,
  articleInitial,
  onSuccess,
}: MouvementModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const [articleId, setArticleId] = useState(articleInitial?.id || articles[0]?.id || '')
  const [typeMouvement, setTypeMouvement] = useState<TypeMouvementStock>('ENTREE')
  const [quantite, setQuantite] = useState(1)
  const [motif, setMotif] = useState('')

  const selectedArticle = articles.find((a) => a.id === articleId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!articleId) {
      addToast({ type: 'warning', message: 'Sélectionnez un article.' })
      return
    }
    if (quantite <= 0) {
      addToast({ type: 'warning', message: 'La quantité doit être supérieure à 0.' })
      return
    }

    try {
      setSubmitting(true)
      const res = await stockApi.enregistrerMouvement({
        article_id: articleId,
        type_mouvement: typeMouvement,
        quantite,
        motif: motif.trim() || undefined,
      })
      addToast({ type: 'success', message: 'Mouvement de stock enregistré.' })
      onSuccess(res)
      onClose()
    } catch (err: any) {
      addToast({ type: 'error', message: err.message || "Erreur lors de l'enregistrement." })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Enregistrer un mouvement de stock" size="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="text-xs font-semibold text-card-foreground mb-1 block">Article *</label>
          <select
            className="w-full h-10 px-3 rounded-lg border border-border bg-muted text-sm text-foreground"
            value={articleId}
            onChange={(e) => setArticleId(e.target.value)}
            required
          >
            {articles.map((a) => (
              <option key={a.id} value={a.id}>
                [{a.code}] {a.designation} (Actuel: {a.quantite_stock} {a.unite}s)
              </option>
            ))}
          </select>
        </div>

        <Select
          label="Type de mouvement *"
          options={TYPES_MOUVEMENT}
          value={typeMouvement}
          onChange={(e) => setTypeMouvement(e.target.value as TypeMouvementStock)}
        />

        <Input
          label={
            typeMouvement === 'AJUSTEMENT_INVENTAIRE'
              ? 'Nouvelle quantité exacte en stock *'
              : 'Quantité à ajouter / déduire *'
          }
          type="number"
          min={typeMouvement === 'AJUSTEMENT_INVENTAIRE' ? 0 : 1}
          value={quantite}
          onChange={(e) => setQuantite(parseInt(e.target.value) || 1)}
          required
          helperText={
            selectedArticle
              ? `Unité : ${selectedArticle.unite} | Stock actuel : ${selectedArticle.quantite_stock}`
              : undefined
          }
        />

        <Input
          label="Motif / Justification"
          placeholder="Ex: Facture Fournisseur N° F-2026-89 / Pose d'implant..."
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
        />

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Validation...' : 'Valider le mouvement'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
