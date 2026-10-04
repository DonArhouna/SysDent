import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useToastStore } from '@/stores/toast-store'
import { stockApi } from '../services/stock-api'
import type { ArticleStock, ArticleStockCreate } from '../types'

interface ArticleModalProps {
  isOpen: boolean
  onClose: () => void
  article?: ArticleStock | null
  onSuccess: (article: ArticleStock) => void
}

const CATEGORIES = [
  { value: 'Anesthésie', label: 'Anesthésie & Réanimation' },
  { value: 'Consommables & Hygiène', label: 'Consommables & Hygiène' },
  { value: "Matériaux d'obturation", label: "Matériaux d'obturation (Composites, Ciments)" },
  { value: 'Endodontie', label: 'Endodontie (Limes, Solutions d\'irrigation)' },
  { value: 'Chirurgie & Implantologie', label: 'Chirurgie & Implantologie' },
  { value: 'Stérilisation', label: 'Stérilisation & Traçabilité' },
  { value: 'Orthodontie', label: 'Orthodontie' },
]

const UNITES = [
  { value: 'Boîte', label: 'Boîte' },
  { value: 'Cartouche', label: 'Cartouche' },
  { value: 'Seringue', label: 'Seringue' },
  { value: 'Flacon', label: 'Flacon' },
  { value: 'Rouleau', label: 'Rouleau' },
  { value: 'Sachet', label: 'Sachet' },
  { value: 'Unité', label: 'Unité' },
]

export function ArticleModal({ isOpen, onClose, article, onSuccess }: ArticleModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const [code, setCode] = useState('')
  const [designation, setDesignation] = useState('')
  const [categorie, setCategorie] = useState('Anesthésie')
  const [unite, setUnite] = useState('Boîte')
  const [quantiteStock, setQuantiteStock] = useState(1)
  const [seuilAlerte, setSeuilAlerte] = useState(5)
  const [prixAchat, setPrixAchat] = useState(10000)
  const [datePeremption, setDatePeremption] = useState('')
  const [emplacement, setEmplacement] = useState('')

  useEffect(() => {
    if (article) {
      setCode(article.code)
      setDesignation(article.designation)
      setCategorie(article.categorie)
      setUnite(article.unite)
      setQuantiteStock(article.quantite_stock)
      setSeuilAlerte(article.seuil_alerte)
      setPrixAchat(article.prix_achat)
      setDatePeremption(article.date_peremption || '')
      setEmplacement(article.emplacement || '')
    } else {
      setCode(`ART-${Math.floor(100 + Math.random() * 900)}`)
      setDesignation('')
      setCategorie('Anesthésie')
      setUnite('Boîte')
      setQuantiteStock(10)
      setSeuilAlerte(5)
      setPrixAchat(5000)
      setDatePeremption('')
      setEmplacement('')
    }
  }, [article, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!code.trim() || !designation.trim()) {
      addToast({ type: 'warning', message: 'Le code et la désignation sont requis.' })
      return
    }

    try {
      setSubmitting(true)
      const payload: ArticleStockCreate = {
        code: code.trim().toUpperCase(),
        designation: designation.trim(),
        categorie,
        unite,
        quantite_stock: quantiteStock,
        seuil_alerte: seuilAlerte,
        prix_achat: prixAchat,
        date_peremption: datePeremption || null,
        emplacement: emplacement.trim() || null,
      }

      let res: ArticleStock
      if (article) {
        res = await stockApi.modifierArticle(article.id, payload)
        addToast({ type: 'success', message: 'Article mis à jour.' })
      } else {
        res = await stockApi.creerArticle(payload)
        addToast({ type: 'success', message: 'Article ajouté au catalogue.' })
      }
      onSuccess(res)
      onClose()
    } catch (err: any) {
      addToast({ type: 'error', message: err.message || 'Erreur lors de la sauvegarde.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={article ? `Modifier ${article.code}` : 'Nouvel article de stock'}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input
            label="Code Référence *"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          <div className="md:col-span-2">
            <Input
              label="Désignation de l'article *"
              placeholder="Ex: Lidocaïne 2% avec adrénaline"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Select
            label="Catégorie"
            options={CATEGORIES}
            value={categorie}
            onChange={(e) => setCategorie(e.target.value)}
          />
          <Select
            label="Unité de conditionnement"
            options={UNITES}
            value={unite}
            onChange={(e) => setUnite(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input
            label="Quantité en stock *"
            type="number"
            min="0"
            value={quantiteStock}
            onChange={(e) => setQuantiteStock(parseInt(e.target.value) || 0)}
            required
          />
          <Input
            label="Seuil d'alerte critique *"
            type="number"
            min="1"
            value={seuilAlerte}
            onChange={(e) => setSeuilAlerte(parseInt(e.target.value) || 1)}
            required
            helperText="Déclenche l'alerte stock bas."
          />
          <Input
            label="Prix d'achat unitaire (FCFA)"
            type="number"
            min="0"
            value={prixAchat}
            onChange={(e) => setPrixAchat(parseFloat(e.target.value) || 0)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="Date de péremption (si applicable)"
            type="date"
            value={datePeremption}
            onChange={(e) => setDatePeremption(e.target.value)}
          />
          <Input
            label="Emplacement de stockage"
            placeholder="Ex: Armoire A, Tiroir 2"
            value={emplacement}
            onChange={(e) => setEmplacement(e.target.value)}
          />
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Enregistrement...' : article ? 'Modifier' : 'Ajouter au stock'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
