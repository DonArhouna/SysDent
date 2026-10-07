import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Modal } from '@/components/ui/modal'
import { useToastStore } from '@/stores/toast-store'
import { stockApi } from '../services/stock-api'
import type { ArticleStock, Fournisseur } from '../types'
import { FournisseurModal } from './fournisseur-modal'
import { Plus, Trash2 } from 'lucide-react'

interface Ligne {
  article_id: string
  quantite: number
  prix_unitaire: number
}

/**
 * Création d'un bon de commande.
 *
 * Deux règles du métier, visibles ici plutôt que de le cacher dans le code :
 *
 * - **une commande n'ajoute rien au stock.** Le matériel n'existe qu'à la
 *   réception. Émettre un bon de commande, c'est commander, pas livrer — et
 *   l'écran le dit, pour que personne ne s'étonne de ne pas voir son stock
 *   bouger ;
 * - **une commande naît en brouillon**, et c'est au gestionnaire qu'il revient
 *   de l'envoyer. On ne commande pas chez un fournisseur depuis le dos d'un
 *   autre : l'envoi est une action distincte, volontaire.
 */
export function NouvelleCommandeModal({
  isOpen,
  fournisseurs,
  articles,
  onClose,
}: {
  isOpen: boolean
  fournisseurs: Fournisseur[]
  articles: ArticleStock[]
  onClose: () => void
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const [fournisseurId, setFournisseurId] = useState('')
  const [notes, setNotes] = useState('')
  const [lignes, setLignes] = useState<Ligne[]>([])
  const [erreur, setErreur] = useState('')
  const [fournisseurEnCreation, setFournisseurEnCreation] = useState(false)

  const reinitialiser = () => {
    setFournisseurId('')
    setNotes('')
    setLignes([])
    setErreur('')
  }

  const fermer = () => {
    reinitialiser()
    onClose()
  }

  const ajouterLigne = () => {
    const article = articles[0]
    if (!article) {
      setErreur('Aucun article au catalogue : créez d’abord un article à commander.')
      return
    }
    setLignes((precedent) => [
      ...precedent,
      {
        article_id: article.id,
        quantite: 1,
        // Le prix d'achat de l'article est le point de départ, pas une imposition :
        // un tarif négocié se saisit.
        prix_unitaire: Number(article.prix_achat ?? 0),
      },
    ])
  }

  const total = lignes.reduce(
    (somme, l) => somme + l.quantite * l.prix_unitaire,
    0,
  )

  const creer = useMutation({
    mutationFn: () =>
      stockApi.creerCommande({
        fournisseur_id: fournisseurId,
        notes: notes.trim() || undefined,
        lignes: lignes.map((l) => ({
          article_id: l.article_id,
          quantite: l.quantite,
          prix_unitaire: l.prix_unitaire,
        })),
      }),
    onSuccess: (commande) => {
      addToast({
        type: 'success',
        message: `Commande ${commande.numero} créée en brouillon. Le stock ne bouge pas avant la réception.`,
      })
      fermer()
      void client.invalidateQueries({ queryKey: ['stock'] })
    },
    onError: (e) => {
      setErreur(e instanceof Error ? e.message : 'Création impossible.')
    },
  })

  const valide =
    fournisseurId !== '' &&
    lignes.length > 0 &&
    lignes.every((l) => l.article_id && l.quantite > 0 && l.prix_unitaire >= 0)

  return (
    <Modal
      isOpen={isOpen}
      onClose={fermer}
      title="Nouvelle commande fournisseur"
      description="Elle naît en brouillon : le stock ne changera qu'à la réception."
      maxWidth="2xl"
    >
      <FournisseurModal
        isOpen={fournisseurEnCreation}
        onClose={() => setFournisseurEnCreation(false)}
        onCree={(f) => setFournisseurId(f.id)}
      />

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          setErreur('')
          if (!valide) {
            setErreur('Choisissez un fournisseur et au moins une ligne valide.')
            return
          }
          creer.mutate()
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="c-fournisseur" required>
              Fournisseur
            </Label>
            <div className="flex gap-2">
              <Select
                id="c-fournisseur"
                value={fournisseurId}
                onChange={(e) => setFournisseurId(e.target.value)}
                required
              >
                <option value="">Choisir un fournisseur</option>
                {fournisseurs.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.nom}
                  </option>
                ))}
              </Select>
              {/* Découvrir qu'un fournisseur manque au moment de commander,
                  c'est le moment naturel pour le créer — pas d'aller le créer
                  dans un autre écran, en perdant la commande en cours. */}
              <Button
                type="button"
                variant="outline"
                onClick={() => setFournisseurEnCreation(true)}
                title="Ajouter un fournisseur"
              >
                <Plus className="h-4 w-4" />
                <span className="sr-only">Ajouter un fournisseur</span>
              </Button>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="c-notes">Note</Label>
            <Input
              id="c-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex. livrable avant le 15"
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Lignes de commande</Label>
            <Button type="button" variant="outline" size="sm" onClick={ajouterLigne}>
              <Plus className="h-3.5 w-3.5" /> Ajouter une ligne
            </Button>
          </div>

          {lignes.length === 0 ? (
            <p className="rounded-xl2 border bg-card/60 px-3 py-3 text-sm text-muted-foreground">
              Aucune ligne. Une commande sans article n'a pas de sens.
            </p>
          ) : (
            <div className="space-y-2">
              {lignes.map((ligne, index) => (
                <div
                  key={index}
                  className="flex flex-wrap items-end gap-2 rounded-xl2 border bg-card/60 px-3 py-2"
                >
                  <div className="min-w-[180px] flex-1 space-y-1">
                    <Label className="text-xs">Article</Label>
                    <Select
                      value={ligne.article_id}
                      onChange={(e) =>
                        setLignes((p) =>
                          p.map((l, i) =>
                            i === index
                              ? {
                                  ...l,
                                  article_id: e.target.value,
                                  prix_unitaire: Number(
                                    articles.find((a) => a.id === e.target.value)?.prix_achat ?? 0,
                                  ),
                                }
                              : l,
                          ),
                        )
                      }
                    >
                      {articles.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.designation}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="w-24 space-y-1">
                    <Label className="text-xs">Quantité</Label>
                    <Input
                      type="number"
                      min={1}
                      value={ligne.quantite}
                      onChange={(e) =>
                        setLignes((p) =>
                          p.map((l, i) =>
                            i === index ? { ...l, quantite: Number(e.target.value) } : l,
                          ),
                        )
                      }
                    />
                  </div>
                  <div className="w-32 space-y-1">
                    <Label className="text-xs">Prix unitaire</Label>
                    <Input
                      type="number"
                      min={0}
                      value={ligne.prix_unitaire}
                      onChange={(e) =>
                        setLignes((p) =>
                          p.map((l, i) =>
                            i === index ? { ...l, prix_unitaire: Number(e.target.value) } : l,
                          ),
                        )
                      }
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Retirer la ligne ${index + 1}`}
                    onClick={() => setLignes((p) => p.filter((_, i) => i !== index))}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between rounded-xl2 border bg-surface/60 px-3 py-2">
          <span className="text-sm text-muted-foreground">Total de la commande</span>
          <span className="text-base font-semibold tabular-nums">
            {new Intl.NumberFormat('fr-FR').format(total)} FCFA
          </span>
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
          <Button type="button" variant="outline" onClick={fermer}>
            Annuler
          </Button>
          <Button type="submit" disabled={creer.isPending || !valide}>
            Créer la commande
          </Button>
        </div>
      </form>
    </Modal>
  )
}
