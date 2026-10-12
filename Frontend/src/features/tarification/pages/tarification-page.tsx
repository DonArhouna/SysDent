import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Pencil, Plus, RefreshCw, Search, WifiOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { possedePermission, useAuthStore } from '@/stores/auth-store'
import { useToastStore } from '@/stores/toast-store'

import { tarificationApi } from '../services/tarification-api'
import { PERM_TARIFS_READ, PERM_TARIFS_WRITE, formaterMontant, type ActeNomenclature } from '../types'
import { ActeModal } from '../components/acte-modal'
import { TarifsEditor } from '../components/tarifs-editor'

const TAILLE_PAGE = 20

/**
 * Ecran «Tarification« : la nomenclature du cabinet et ses prix.
 *
 * **Les filtres vivent dans l'URL.** Une liste filtree qu'on ne peut pas
 * partager ni retrouver apres un rechargement n'est pas un filtre, c'est un
 * etat ephemere : le praticien cherche « prothese », ferme l'onglet, revient,
 * et la liste a retrouve ses deux mille actes.
 *
 * **Les boutons d'ecriture n'apparaissent que si `TARIFS:WRITE` est present.**
 * Un bouton visible qui repond 403 est une faute : l'utilisateur croit avoir
 * echoue, alors que son profil n'a jamais eu ce droit. Et un 403 ne doit jamais
 * etre rejoue : une mutation n'est pas une lecture, la rejouer ne changera
 * rien et peut dupliquer un effet de bord.
 */
export function TarificationPage() {
  const [params, setParams] = useSearchParams()
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const profil = useAuthStore((e) => e.profil)

  const peutEcrire = possedePermission(profil, PERM_TARIFS_WRITE)
  const peutLire = possedePermission(profil, PERM_TARIFS_READ)

  const page = Number(params.get('page') ?? '1') || 1
  const rechercheUrl = params.get('q') ?? ''
  const categorieUrl = params.get('categorie') ?? ''
  const actifUrl = params.get('actif')

  const [terme, setTerme] = useState(rechercheUrl)
  useEffect(() => setTerme(rechercheUrl), [rechercheUrl])

  // Recherche différée : une requête par frappe saturerait l'API pour un
  // résultat qui n'intéresse que la dernière lettre.
  useEffect(() => {
    if (terme === rechercheUrl) return
    const minuteur = setTimeout(() => {
      const suivant = new URLSearchParams(params)
      if (terme.trim()) suivant.set('q', terme.trim())
      else suivant.delete('q')
      suivant.delete('page')
      setParams(suivant, { replace: true })
    }, 300)
    return () => clearTimeout(minuteur)
  }, [terme, rechercheUrl, params, setParams])

  function changerFiltre(cle: string, valeur: string | null) {
    const suivant = new URLSearchParams(params)
    if (valeur) suivant.set(cle, valeur)
    else suivant.delete(cle)
    suivant.delete('page')
    setParams(suivant, { replace: true })
  }

  const actes = useQuery({
    queryKey: ['tarification', 'actes', page, rechercheUrl, categorieUrl, actifUrl],
    queryFn: () =>
      tarificationApi.listerActes({
        page,
        limit: TAILLE_PAGE,
        q: rechercheUrl || undefined,
        categorie: categorieUrl || undefined,
        actif: actifUrl === null ? undefined : actifUrl === 'true',
      }),
    enabled: peutLire,
  })

  const [edition, setEdition] = useState<ActeNomenclature | null>(null)
  const [modaleOuverte, setModaleOuverte] = useState(false)

  const basculerActif = useMutation({
    mutationFn: ({ acte, actif }: { acte: ActeNomenclature; actif: boolean }) =>
      tarificationApi.modifierActe(acte.id, { actif }),
    onSuccess: (_reponse, variables) => {
      addToast({
        type: 'success',
        message: variables.actif
          ? `${variables.acte.code} retire de la nomenclature.`
          : `${variables.acte.code} reactive.`,
      })
      void client.invalidateQueries({ queryKey: ['tarification'] })
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "L'acte n'a pas pu etre modifie.",
      }),
  })

  const [selection, setSelection] = useState<ActeNomenclature | null>(null)
  const lignes = actes.data?.items ?? []

  // L'acte choisi peut disparaitre du resultat courant (filtre, desactivation) :
  // le panneau doit alors suivre la liste, pas garder un acte fantome.
  const selectionCourante = useMemo(
    () => lignes.find((a) => a.id === selection?.id) ?? null,
    [lignes, selection],
  )

  function recharger() {
    void actes.refetch()
  }

  if (!peutLire) {
    return (
      <div className="space-y-6">
        <PageHeader titre="Tarification" sousTitre="Nomenclature et tarifs du cabinet" />
        <EmptyState
          icon={WifiOff}
          titre="Acces non autorise"
          description="Votre profil ne peut pas consulter la tarification du cabinet."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        titre="Tarification"
        sousTitre="Nomenclature des actes et prix par categorie de patient"
        onRefresh={recharger}
      >
        {peutEcrire && (
          <Button
            variant="primary"
            onClick={() => {
              setEdition(null)
              setModaleOuverte(true)
            }}
          >
            <Plus className="h-4 w-4" /> Nouvel acte
          </Button>
        )}
      </PageHeader>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative sm:max-w-xs sm:flex-1">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Rechercher un code ou un libelle..."
            aria-label="Rechercher un acte"
            value={terme}
            onChange={(e) => setTerme(e.target.value)}
          />
        </div>
        <Select
          aria-label="Filtrer par categorie"
          className="sm:w-48"
          value={categorieUrl}
          onChange={(e) => changerFiltre('categorie', e.target.value || null)}
          options={[
            { value: '', label: 'Toutes les categories' },
            ...Array.from(new Set(lignes.map((a) => a.categorie))).map((c) => ({
              value: c,
              label: c,
            })),
          ]}
        />
        <Select
          aria-label="Filtrer sur les actes actifs ou retires"
          className="sm:w-48"
          value={actifUrl ?? ''}
          onChange={(e) => changerFiltre('actif', e.target.value || null)}
          options={[
            { value: '', label: 'Actifs et retires' },
            { value: 'true', label: 'Actifs seulement' },
            { value: 'false', label: 'Retires seulement' },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Actes de nomenclature</CardTitle>
          </CardHeader>
          <CardContent>
            {actes.isPending ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : actes.isError ? (
              /* Un echec n'est pas une liste vide : afficher « aucun acte » ferait
                 croire que le cabinet n'a pas de nomenclature. */
              <EmptyState
                icon={WifiOff}
                titre="Nomenclature indisponible"
                description="La liste des actes n'a pas pu etre chargee. Verifiez que le backend repond puis reessayez."
              >
                <Button variant="outline" onClick={recharger}>
                  <RefreshCw className="h-4 w-4" /> Reessayer
                </Button>
              </EmptyState>
            ) : lignes.length === 0 ? (
              <EmptyState
                icon={Search}
                titre={
                  rechercheUrl || categorieUrl || actifUrl
                    ? 'Aucun acte ne correspond'
                    : 'Nomenclature vide'
                }
                description={
                  rechercheUrl || categorieUrl || actifUrl
                    ? 'Ajustez la recherche ou les filtres.'
                    : 'Ajoutez le premier acte : sans nomenclature, aucune consultation ne peut etre facturee.'
                }
              />
            ) : (
              <Table>
                <THead>
                  <TRow>
                    <TH>Code</TH>
                    <TH>Libelle</TH>
                    <TH>Categorie</TH>
                    <TH className="text-right">Tarif de base</TH>
                    <TH>Tarifs</TH>
                    {peutEcrire && <TH className="text-right">Actions</TH>}
                  </TRow>
                </THead>
                <TBody>
                  {lignes.map((acte) => (
                    <TRow
                      key={acte.id}
                      className={selectionCourante?.id === acte.id ? 'bg-accent/30' : undefined}
                    >
                      <TD className="font-mono text-xs">{acte.code}</TD>
                      <TD>
                        <span className="font-medium text-foreground">{acte.libelle}</span>
                        {!acte.actif && (
                          <StatusBadge tone="warning" className="ml-2">
                            retire
                          </StatusBadge>
                        )}
                      </TD>
                      <TD className="text-muted-foreground">{acte.categorie}</TD>
                      <TD className="text-right tabular-nums">
                        {formaterMontant(acte.tarif_base)}
                      </TD>
                      <TD className="text-xs text-muted-foreground">
                        {acte.tarifs.length === 0
                          ? 'aucune variante'
                          : acte.tarifs
                              .map(
                                (t) =>
                                  `${t.categorie_code} : ${formaterMontant(t.montant)}`,
                              )
                              .join(', ')}
                      </TD>
                      {peutEcrire && (
                        <TD className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelection(acte)
                                setEdition(acte)
                                setModaleOuverte(true)
                              }}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                              <span className="sr-only">Modifier {acte.libelle}</span>
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={basculerActif.isPending}
                              onClick={() => basculerActif.mutate({ acte, actif: !acte.actif })}
                            >
                              {acte.actif ? 'Retirer' : 'Reactiver'}
                              <span className="sr-only"> {acte.libelle}</span>
                            </Button>
                          </div>
                        </TD>
                      )}
                    </TRow>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
          <Pagination
            meta={actes.data?.meta}
            page={page}
            limit={TAILLE_PAGE}
            onPageChange={(p) => changerFiltre('page', String(p))}
            libelle="actes"
          />
        </Card>

        {peutEcrire && <TarifsEditor acte={selectionCourante} />}
      </div>

      <ActeModal
        isOpen={modaleOuverte}
        acte={edition}
        onClose={() => setModaleOuverte(false)}
        onSuccess={() => void actes.refetch()}
      />
    </div>
  )
}
