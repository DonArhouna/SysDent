import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Modal } from '@/components/ui/modal'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { formatFcfa, formatDateFr } from '@/lib/format'
import { useToastStore } from '@/stores/toast-store'
import { stockApi } from '../services/stock-api'
import { NouvelleCommandeModal } from './nouvelle-commande-modal'
import { FournisseurModal } from './fournisseur-modal'
import type { ArticleStock, CommandeFournisseur, Fournisseur, LigneCommande } from '../types'
import { CheckCircle2, PackageCheck, Plus, Truck } from 'lucide-react'

/**
 * Commandes fournisseurs et réceptions.
 *
 * Deux règles du métier sont visibles ici, et pas seulement dans le code :
 *
 * - **une commande n'ajoute rien au stock.** Le matériel n'existe qu'à la
 *   réception ; émettre un bon de commande, c'est commander, pas livrer.
 * - **la réception crédite immédiatement le stock**, sans validation à deux
 *   mains. Dans un cabinet d'une ou deux personnes, la double validation
 *   empêcherait la réception — et un stock qu'on ne met pas à jour est un stock
 *   faux, ce qui est pire.
 *
 * Ce qui remplace le second regard, c'est la trace : qui, quand, quelle commande.
 */
export function CommandesPanel({
  cabinetId,
  articles = [],
}: {
  cabinetId: string
  /** Catalogue du site : une ligne de commande porte sur un article existant. */
  articles?: ArticleStock[]
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const [commandeReceptionnee, setCommandeReceptionnee] = useState<CommandeFournisseur | null>(null)

  const commandesQuery = useQuery({
    queryKey: ['stock', 'commandes'],
    queryFn: () => stockApi.listerCommandes(),
  })
  const fournisseursQuery = useQuery({
    queryKey: ['stock', 'fournisseurs'],
    queryFn: () => stockApi.listerFournisseurs(),
  })

  const commandes = commandesQuery.data?.data ?? []
  const [creationOuverte, setCreationOuverte] = useState(false)
  const [fournisseurEdite, setFournisseurEdite] = useState<Fournisseur | null>(null)
  const [fournisseurEditeOuvert, setFournisseurEditeOuvert] = useState(false)

  const envoyer = useMutation({
    mutationFn: ({ id, statut }: { id: string; statut: string }) =>
      stockApi.changerStatutCommande(id, statut),
    onSuccess: () => {
      addToast({ type: 'success', message: 'Commande envoyée au fournisseur.' })
      void client.invalidateQueries({ queryKey: ['stock'] })
    },
  })

  const rafraichir = () => {
    void commandesQuery.refetch()
  }

  const listeFournisseurs = fournisseursQuery.data?.data ?? []
  const fournisseurs = new Map(
    (fournisseursQuery.data?.data ?? []).map((f) => [f.id, f.nom])
  )

  if (commandesQuery.isPending) {
    return <Skeleton className="h-64 w-full" />
  }

  if (commandes.length === 0) {
    return (
      <EmptyState
        icon={Truck}
        titre="Aucune commande fournisseur"
        description="Les commandes et leurs réceptions apparaîtront ici. Émettre une commande n'ajoute rien au stock : le matériel n'arrive qu'à la réception."
      >
        <Button variant="outline" onClick={rafraichir}>
          Rafraîchir
        </Button>
      </EmptyState>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Button onClick={() => setCreationOuverte(true)}>
          <Plus className="h-4 w-4" /> Nouvelle commande
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Commandes fournisseurs</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TRow>
                <TH>Numéro</TH>
                <TH>Fournisseur</TH>
                <TH>Date</TH>
                <TH>Statut</TH>
                <TH>Réception</TH>
                <TH className="text-right">Montant</TH>
                <TH />
              </TRow>
            </THead>
            <TBody>
              {commandes.map((c) => {
                const solde = c.lignes.filter((l) => l.quantite_recue < l.quantite_commandee)
                return (
                  <TRow key={c.id}>
                    <TD className="font-mono text-xs">{c.numero}</TD>
                    <TD>{c.fournisseur_nom ?? fournisseurs.get(c.fournisseur_id) ?? '—'}</TD>
                    <TD className="text-muted-foreground">{formatDateFr(c.date_commande)}</TD>
                    <TD>
                      <StatusBadge tone={TON[c.statut] ?? 'neutral'}>{c.statut}</StatusBadge>
                    </TD>
                    <TD className="text-xs text-muted-foreground">
                      {c.lignes.length === 0
                        ? '—'
                        : `${c.lignes.filter((l) => l.quantite_recue >= l.quantite_commandee).length}/${c.lignes.length} ligne(s)`}
                    </TD>
                    <TD className="text-right font-semibold tabular-nums">
                      {formatFcfa(c.montant_total)}
                    </TD>
                    <TD className="text-right">
                      {c.statut === 'BROUILLON' && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={envoyer.isPending}
                          onClick={() => envoyer.mutate({ id: c.id, statut: 'ENVOYEE' })}
                        >
                          Envoyer
                        </Button>
                      )}
                      {c.statut === 'ENVOYEE' && (
                        <Button size="sm" onClick={() => setCommandeReceptionnee(c)}>
                          <PackageCheck className="h-3.5 w-3.5" /> Réceptionner
                        </Button>
                      )}
                      {c.statut === 'PARTIELLEMENT_REÇUE' && solde.length > 0 && (
                        <Button size="sm" onClick={() => setCommandeReceptionnee(c)}>
                          <PackageCheck className="h-3.5 w-3.5" /> Réceptionner le solde
                        </Button>
                      )}
                    </TD>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      {/* Fournisseurs : ils changent, on doit pouvoir les gérer sur place. */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-3">
            <span>Fournisseurs</span>
            <Button size="sm" variant="outline" onClick={() => setFournisseurEditeOuvert(true)}>
              <Plus className="h-3.5 w-3.5" /> Ajouter
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {listeFournisseurs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun fournisseur. Ajoutez-le ici, ou directement depuis une nouvelle commande.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {listeFournisseurs.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => {
                    setFournisseurEdite(f)
                    setFournisseurEditeOuvert(true)
                  }}
                  className="rounded-lg border bg-card/70 px-2.5 py-1.5 text-xs transition-colors hover:bg-muted"
                >
                  <span className="font-medium">{f.nom}</span>
                  {f.telephone && (
                    <span className="ml-2 text-muted-foreground">{f.telephone}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <FournisseurModal
        isOpen={fournisseurEditeOuvert}
        fournisseur={fournisseurEdite}
        onClose={() => setFournisseurEditeOuvert(false)}
      />

      <NouvelleCommandeModal
        isOpen={creationOuverte}
        fournisseurs={listeFournisseurs}
        articles={articles ?? []}
        onClose={() => setCreationOuverte(false)}
      />

      <ModalReception
        commande={commandeReceptionnee}
        siteId={cabinetId}
        onClose={() => setCommandeReceptionnee(null)}
      />
    </div>
  )
}

const TON: Record<string, 'neutral' | 'info' | 'success' | 'warning' | 'danger'> = {
  BROUILLON: 'neutral',
  ENVOYEE: 'info',
  'PARTIELLEMENT_REÇUE': 'warning',
  RECUE: 'success',
  ANNULEE: 'danger',
}

/**
 * Réception d'une commande.
 *
 * Seules les quantités restant à livrer sont proposées : une réception
 * supérieure à la commande est refusée par le serveur, autant ne pas proposer un
 * chiffre que l'utilisateur ne peut pas valider.
 */
function ModalReception({
  commande,
  siteId,
  onClose,
}: {
  commande: CommandeFournisseur | null
  siteId: string
  onClose: () => void
}) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const [quantites, setQuantites] = useState<Record<string, string>>({})

  const aReceptionner = commande?.lignes.filter(
    (l) => l.quantite_recue < l.quantite_commandee
  )

  const receptionner = useMutation({
    mutationFn: async () => {
      if (!commande) return
      const lignes = (aReceptionner ?? [])
        .map((l) => ({
          ligne_commande_id: l.id,
          quantite_recue: Number(quantites[l.id] ?? l.quantite_commandee - l.quantite_recue),
        }))
        .filter((l) => l.quantite_recue > 0)
      if (lignes.length === 0) {
        throw new Error('Saisissez au moins une quantité reçue supérieure à zéro.')
      }
      return stockApi.enregistrerReception(commande.id, siteId, { lignes })
    },
    onSuccess: () => {
      addToast({
        type: 'success',
        message: 'Réception enregistrée : le stock est crédité.',
      })
      setQuantites({})
      onClose()
      void client.invalidateQueries({ queryKey: ['stock'] })
    },
  })

  return (
    <Modal
      isOpen={Boolean(commande)}
      onClose={onClose}
      title={`Réceptionner ${commande?.numero ?? ''}`}
      description="Le stock est crédité immédiatement, et l'opération est tracée."
      maxWidth="lg"
    >
      {!commande ? null : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            receptionner.mutate()
          }}
        >
          <p className="text-xs text-muted-foreground">
            Les quantités restant à livrer sont pré-remplies. Mettez 0 pour une ligne non
            reçue : elle pourra l'être plus tard.
          </p>
          <div className="space-y-2">
            {(aReceptionner ?? []).map((l) => (
              <LigneReception
                key={l.id}
                ligne={l}
                valeur={quantites[l.id]}
                onChange={(ligneId, valeur) =>
                  // Mise à jour fonctionnelle : reconstruire l'objet ici
                  // effacerait les quantités saisies sur les autres lignes.
                  setQuantites((precedent) => ({ ...precedent, [ligneId]: valeur }))
                }
              />
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={receptionner.isPending}>
              <CheckCircle2 className="h-4 w-4" /> Valider la réception
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}

function LigneReception({
  ligne,
  valeur,
  onChange,
}: {
  ligne: LigneCommande
  valeur: string | undefined
  onChange: (ligneId: string, valeur: string) => void
}) {
  const restant = ligne.quantite_commandee - ligne.quantite_recue
  const designation = ligne.article_designation ?? ligne.article_code ?? 'Article'
  return (
    <div className="flex items-center gap-3 rounded-xl2 border bg-surface/60 px-3 py-2">
      <div className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{designation}</span>
        <span className="text-xs text-muted-foreground">
          {ligne.quantite_recue} / {ligne.quantite_commandee} reçu · {formatFcfa(ligne.prix_unitaire)}
        </span>
      </div>
      <Input
        type="number"
        min={0}
        max={restant}
        value={valeur ?? String(restant)}
        onChange={(e) => onChange(ligne.id, e.target.value)}
        className="w-24"
        aria-label={`Quantité reçue pour ${designation}`}
      />
    </div>
  )
}
