import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Pencil, Plus, Search, WifiOff } from 'lucide-react'

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
import {
  PERM_ASSURANCE_READ,
  PERM_ORGANISMES_WRITE,
  type OrganismeAssurance,
} from '../types'
import { OrganismeModal } from '../components/organisme-modal'
import { EtatErreurModule } from '../components/etat-erreur'

const TAILLE_PAGE = 20

/**
 * Ecran «Prise en charge« : les organismes payeurs du cabinet.
 *
 * **Le secretariat lit, il n'ecrit pas.** Il enregistre les droits d'un patient
 * depuis la fiche patient, mais il ne touche ni aux organismes ni a leur nature.
 * La raison tient : un organisme erroneous se propage a tous les patients qui le
 * designent, alors qu'un droit errone ne concerne qu'une fiche.
 *
 * Aucun bouton d'ecriture n'est rendu sans `ASSURANCE:WRITE`. Un bouton visible
 * qui repond 403 apprend au secretaire qu'il a echoue, alors que son profil n'a
 * jamais eu ce droit.
 */
export function OrganismesPage() {
  const [params, setParams] = useSearchParams()
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const profil = useAuthStore((e) => e.profil)

  const peutLire = possedePermission(profil, PERM_ASSURANCE_READ)
  // Un organisme est un referentiel : son ecriture est reservee a l'admin, pas
  // au secretariat. Voir `PERM_ORGANISMES_WRITE`.
  const peutEcrire = possedePermission(profil, PERM_ORGANISMES_WRITE)

  const page = Number(params.get('page') ?? '1') || 1
  const rechercheUrl = params.get('q') ?? ''
  const typeUrl = params.get('type') ?? ''
  const actifUrl = params.get('actif')

  const [terme, setTerme] = useState(rechercheUrl)
  useEffect(() => setTerme(rechercheUrl), [rechercheUrl])

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

  const organismes = useQuery({
    queryKey: ['tarification', 'organismes', page, rechercheUrl, typeUrl, actifUrl],
    queryFn: () =>
      tarificationApi.listerOrganismes({
        page,
        limit: TAILLE_PAGE,
        q: rechercheUrl || undefined,
        type_organisme: typeUrl || undefined,
        actif: actifUrl === null ? undefined : actifUrl === 'true',
      }),
    enabled: peutLire,
  })

  const [edition, setEdition] = useState<OrganismeAssurance | null>(null)
  const [modaleOuverte, setModaleOuverte] = useState(false)

  const basculerActif = useMutation({
    mutationFn: ({ organisme, actif }: { organisme: OrganismeAssurance; actif: boolean }) =>
      tarificationApi.modifierOrganisme(organisme.id, { actif }),
    onSuccess: (_r, variables) => {
      addToast({
        type: 'success',
        message: variables.actif
          ? `${variables.organisme.nom} reactive.`
          : `${variables.organisme.nom} desactive.`,
      })
      void client.invalidateQueries({ queryKey: ['tarification'] })
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "L'organisme n'a pas pu etre modifie.",
      }),
  })

  const lignes = organismes.data?.items ?? []

  if (!peutLire) {
    return (
      <div className="space-y-6">
        <PageHeader titre="Prise en charge" sousTitre="Organismes payeurs du cabinet" />
        <EmptyState
          icon={WifiOff}
          titre="Acces non autorise"
          description="Votre profil ne peut pas consulter les organismes de prise en charge."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        titre="Prise en charge"
        sousTitre="Organismes payeurs connus du cabinet : assurance et mutuelle"
        onRefresh={() => void organismes.refetch()}
      >
        {peutEcrire && (
          <Button
            variant="primary"
            onClick={() => {
              setEdition(null)
              setModaleOuverte(true)
            }}
          >
            <Plus className="h-4 w-4" /> Nouvel organisme
          </Button>
        )}
      </PageHeader>

      <p className="text-xs text-muted-foreground">
        Les droits d'un patient, son numero de police et son taux se saisissent dans sa fiche,
        onglet « Prise en charge ». Les taux sont propre au cabinet : ils ne sont pas lus ici.
      </p>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative sm:max-w-xs sm:flex-1">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Rechercher un organisme..."
            aria-label="Rechercher un organisme"
            value={terme}
            onChange={(e) => setTerme(e.target.value)}
          />
        </div>
        <Select
          aria-label="Filtrer par nature"
          className="sm:w-52"
          value={typeUrl}
          onChange={(e) => changerFiltre('type', e.target.value || null)}
          options={[
            { value: '', label: 'Assurance et mutuelle' },
            { value: 'ASSURANCE', label: 'Assurance' },
            { value: 'MUTUELLE', label: 'Mutuelle' },
          ]}
        />
        <Select
          aria-label="Filtrer sur les organismes actifs ou desactives"
          className="sm:w-52"
          value={actifUrl ?? ''}
          onChange={(e) => changerFiltre('actif', e.target.value || null)}
          options={[
            { value: '', label: 'Tous' },
            { value: 'true', label: 'Actifs seulement' },
            { value: 'false', label: 'Desactives seulement' },
          ]}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Organismes payeurs</CardTitle>
        </CardHeader>
        <CardContent>
          {organismes.isPending ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : organismes.isError ? (
            <EtatErreurModule
              error={organismes.error}
              libelle="Organismes"
              onReessayer={() => void organismes.refetch()}
            />
          ) : lignes.length === 0 ? (
            <EmptyState
              icon={Search}
              titre={rechercheUrl ? 'Aucun organisme ne correspond' : 'Aucun organisme'}
              description={
                rechercheUrl
                  ? `Aucun organisme dont le nom contient « ${rechercheUrl} ».`
                  : "Saisissez d'abord les organismes que le cabinet retrouve dans le cabinet du patient : sans eux, aucune prise en charge n'est saisissable."
              }
            />
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH>Code</TH>
                  <TH>Nom</TH>
                  <TH>Nature</TH>
                  {peutEcrire && <TH className="text-right">Actions</TH>}
                </TRow>
              </THead>
              <TBody>
                {lignes.map((organisme) => (
                  <TRow key={organisme.id}>
                    <TD className="font-mono text-xs">{organisme.code}</TD>
                    <TD className="font-medium text-foreground">
                      {organisme.nom}
                      {!organisme.actif && (
                        <StatusBadge tone="warning" className="ml-2">
                          desactive
                        </StatusBadge>
                      )}
                    </TD>
                    <TD>
                      <StatusBadge tone={organisme.type_organisme === 'MUTUELLE' ? 'info' : 'neutral'}>
                        {organisme.type_organisme === 'MUTUELLE' ? 'Mutuelle' : 'Assurance'}
                      </StatusBadge>
                    </TD>
                    {peutEcrire && (
                      <TD className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEdition(organisme)
                              setModaleOuverte(true)
                            }}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                            <span className="sr-only">Modifier {organisme.nom}</span>
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={basculerActif.isPending}
                            onClick={() =>
                              basculerActif.mutate({ organisme, actif: !organisme.actif })
                            }
                          >
                            {organisme.actif ? 'Desactiver' : 'Reactiver'}
                            <span className="sr-only"> {organisme.nom}</span>
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
          meta={organismes.data?.meta}
          page={page}
          limit={TAILLE_PAGE}
          onPageChange={(p) => changerFiltre('page', String(p))}
          libelle="organismes"
        />
      </Card>

      <OrganismeModal
        isOpen={modaleOuverte}
        organisme={edition}
        onClose={() => setModaleOuverte(false)}
        onSuccess={() => void organismes.refetch()}
      />
    </div>
  )
}
