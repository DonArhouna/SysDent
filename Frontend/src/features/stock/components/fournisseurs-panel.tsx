import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/pagination'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { useToastStore } from '@/stores/toast-store'
import { stockApi } from '../services/stock-api'
import type { Fournisseur } from '../types'
import { FournisseurModal } from './fournisseur-modal'

/** Taille de page, alignée sur celle du panneau Commandes. */
const TAILLE_PAGE = 20

/**
 * Écran « Fournisseurs » — le CRUD manquant.
 *
 * Les fournisseurs étaient une carte de Chips au bas de l'onglet Commandes : on
 * pouvait en ajouter un, mais pas le rechercher, le parcourir ni le modifier
 * depuis un endroit qui soit fait pour ça. Un grossiste qui ne commande plus
 * restait affiché indéfiniment, faute d'action pour le retirer.
 *
 * La liste est **paginée et recherchée**. Deux raisons, et la seconde est celle
 * qui compte : la pagination évite de charger tout le carnet à chaque ouverture,
 * et la recherche évite qu'un fournisseur cherché à la 40e place soit introuvable
 * — c'est le défaut qui rend une liste paginée pire qu'une liste non paginée.
 */
export function FournisseursPanel() {
  const client = useQueryClient()
  const { addToast } = useToastStore()

  const [page, setPage] = useState(1)
  const [terme, setTerme] = useState('')
  const [recherche, setRecherche] = useState('')
  const [edition, setEdition] = useState<Fournisseur | null>(null)
  const [modaleOuverte, setModaleOuverte] = useState(false)

  // Recherche différée : une requête par frappe saturerait l'API pour un
  // résultat qui n'intéresse que la dernière lettre.
  useEffect(() => {
    const minuteur = setTimeout(() => {
      setRecherche(terme.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(minuteur)
  }, [terme])

  const query = useQuery({
    queryKey: ['stock', 'fournisseurs', page, recherche],
    queryFn: () => stockApi.listerFournisseurs({ page, limit: TAILLE_PAGE, q: recherche || undefined }),
  })

  const desactiver = useMutation({
    mutationFn: (f: Fournisseur) => stockApi.modifierFournisseur(f.id, { actif: false }),
    onSuccess: (f) => {
      addToast({ type: 'success', message: `${f.nom} retiré de la liste des fournisseurs.` })
      void client.invalidateQueries({ queryKey: ['stock'] })
    },
    onError: (e) =>
      addToast({ type: 'error', message: e instanceof Error ? e.message : 'Action impossible.' }),
  })

  const fournisseurs = query.data?.items ?? []

  if (query.isPending) {
    return <Skeleton className="h-64 w-full" />
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Input
          value={terme}
          onChange={(e) => setTerme(e.target.value)}
          placeholder="Rechercher un fournisseur…"
          className="sm:max-w-xs"
          aria-label="Rechercher un fournisseur"
        />
        <Button
          onClick={() => {
            setEdition(null)
            setModaleOuverte(true)
          }}
        >
          <Plus className="h-4 w-4" /> Nouveau fournisseur
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Fournisseurs</CardTitle>
        </CardHeader>
        <CardContent>
          {fournisseurs.length === 0 ? (
            <EmptyState
              icon={Plus}
              titre={recherche ? 'Aucun fournisseur ne correspond' : 'Aucun fournisseur'}
              description={
                recherche
                  ? `Aucun fournisseur dont le nom contient « ${recherche} ».`
                  : "Un cabinet commande presque toujours chez quelqu'un : le carnet commence ici. Vous pourrez aussi créer un fournisseur directement depuis la saisie d'une commande."
              }
            />
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH>Raison sociale</TH>
                  <TH>Contact</TH>
                  <TH>Téléphone</TH>
                  <TH>Email</TH>
                  <TH />
                </TRow>
              </THead>
              <TBody>
                {fournisseurs.map((f) => (
                  <TRow key={f.id}>
                    <TD className="font-medium">{f.nom}</TD>
                    <TD>{f.contact ?? '—'}</TD>
                    <TD className="tabular-nums">{f.telephone ?? '—'}</TD>
                    <TD>{f.email ?? '—'}</TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEdition(f)
                            setModaleOuverte(true)
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          <span className="sr-only">Modifier {f.nom}</span>
                        </Button>
                        {f.actif && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={desactiver.isPending}
                            onClick={() => desactiver.mutate(f)}
                          >
                            Retirer
                            <span className="sr-only"> {f.nom} de la liste</span>
                          </Button>
                        )}
                      </div>
                    </TD>
                  </TRow>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
        <Pagination
          meta={query.data?.meta}
          page={page}
          limit={TAILLE_PAGE}
          onPageChange={setPage}
          libelle="fournisseurs"
        />
      </Card>

      <FournisseurModal
        isOpen={modaleOuverte}
        fournisseur={edition}
        onClose={() => setModaleOuverte(false)}
      />
    </div>
  )
}