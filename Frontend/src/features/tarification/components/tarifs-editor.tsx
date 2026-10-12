import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { EyeOff, Save, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useToastStore } from '@/stores/toast-store'

import { CODE_CATEGORIE_STANDARD, formaterMontant, type ActeNomenclature } from '../types'
import { tarificationApi } from '../services/tarification-api'
import { normaliserMontant, validerMontant } from './validation'

/**
 * Tarifs d'un acte, par categorie de patient.
 *
 * **Le tarif de base ne se saisit pas dans ce panneau d'edition** - il ne se
 * saisit nulle part apres la creation. C'est ce que le serveur refuse, et pour
 * une raison qui tient : un `PATCH` d'acte qui accepte un prix changerait le
 * montant sous les factures deja emises. Ici on ecrit un **tarif de
 * categorie**, qui est par nature une decision nouvelle et non une reecriture.
 *
 * La categorie `standard` est en tete et non desactivable : c'est le tarif de
 * reference, et le serveur interdit de le retirer. Les autres viennent de
 * l'API, jamais d'une liste ecrite en dur.
 */
export function TarifsEditor({ acte }: { acte: ActeNomenclature | null }) {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const [brouillons, setBrouillons] = useState<Record<string, string>>({})
  const [erreurs, setErreurs] = useState<Record<string, string>>({})

  useEffect(() => {
    setBrouillons({})
    setErreurs({})
  }, [acte?.id])

  const categories = useQuery({
    queryKey: ['tarification', 'categories'],
    queryFn: () => tarificationApi.listerCategories({ limit: 100 }),
  })

  const definir = useMutation({
    mutationFn: ({ categorieCode, montant }: { categorieCode: string; montant: string }) =>
      tarificationApi.definirTarif(acte?.id ?? '', {
        categorie_code: categorieCode,
        montant: normaliserMontant(montant),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['tarification', 'actes'] })
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "Le tarif n'a pas pu etre enregistre.",
      }),
  })

  const retirer = useMutation({
    mutationFn: (tarifId: string) => tarificationApi.supprimerTarif(acte?.id ?? '', tarifId),
    onSuccess: () => {
      addToast({ type: 'success', message: 'Tarif de variante retire.' })
      void client.invalidateQueries({ queryKey: ['tarification', 'actes'] })
    },
    onError: (e) =>
      addToast({
        type: 'error',
        message: e instanceof Error ? e.message : "Le tarif n'a pas pu etre retire.",
      }),
  })

  if (!acte) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Tarifs par categorie</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Selectionnez un acte dans la liste pour voir et ajuster ses tarifs.
          </p>
        </CardContent>
      </Card>
    )
  }

  const toutesCategories = categories.data?.items ?? []
  const tarifParCode = new Map(acte.tarifs.map((t) => [t.categorie_code, t]))

  function enregistrer(categorieCode: string) {
    const brut = brouillons[categorieCode] ?? ''
    const controle = validerMontant(brut)
    if (!controle.valide) {
      setErreurs({ ...erreurs, [categorieCode]: controle.message })
      return
    }
    setErreurs({ ...erreurs, [categorieCode]: '' })
    definir.mutate({ categorieCode, montant: brut })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tarifs par categorie - {acte.code}</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Le tarif d'une facture deja emise ne bouge pas : c'est le prix au moment de l'acte
          qui est fige. Ces tarifs ne concernent que les actes a venir.
        </p>
      </CardHeader>
      <CardContent>
        {categories.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : toutesCategories.length === 0 ? (
          <EmptyState
            titre="Aucune categorie de patient"
            description="La categorie standard est creee a la migration. Si elle est absente, la base n'a pas ete migree."
          />
        ) : (
          <ul className="space-y-3">
            {toutesCategories.map((categorie) => {
              const existant = tarifParCode.get(categorie.code)
              const cle = categorie.code
              return (
                <li
                  key={cle}
                  className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-end"
                >
                  <div className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-foreground">
                      {categorie.libelle}
                      <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                        {cle}
                      </span>
                      {categorie.par_defaut && (
                        <span className="ml-2 text-[11px] text-primary">reference</span>
                      )}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {existant ? `actuel : ${formaterMontant(existant.montant)}` : 'aucun tarif'}
                    </span>
                  </div>

                  <div className="sm:w-44">
                    <Input
                      aria-label={`Montant pour ${categorie.libelle}`}
                      inputMode="decimal"
                      placeholder={existant?.montant ?? '0.00'}
                      value={brouillons[cle] ?? ''}
                      error={erreurs[cle]}
                      onChange={(e) => setBrouillons({ ...brouillons, [cle]: e.target.value })}
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => enregistrer(cle)}
                      disabled={definir.isPending || brouillons[cle]?.trim() === ''}
                    >
                      <Save className="h-3.5 w-3.5" /> Enregistrer
                    </Button>
                    {existant && cle !== CODE_CATEGORIE_STANDARD && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => retirer.mutate(existant.id)}
                        disabled={retirer.isPending}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        <span className="sr-only">Retirer le tarif {categorie.libelle}</span>
                      </Button>
                    )}
                    {existant && cle === CODE_CATEGORIE_STANDARD && (
                      <EyeOff
                        className="h-4 w-4 text-muted-foreground"
                        aria-label="Tarif de reference : il ne peut pas etre retire"
                      />
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}