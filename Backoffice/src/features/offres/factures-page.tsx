import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Receipt, Trash2 } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { PageHeader } from '@/components/ui/page-header'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TableEmpty, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { usePermission } from '@/guards/can'
import { api, type PageReponse } from '@/lib/api'
import { date, messageErreur, montant, statutFacture } from '@/lib/libelles'
import { PERMISSIONS, type Facture, type LigneFacture } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'
import { useNomsCabinets } from './noms-cabinets'

const LIMITE = 20

/**
 * Passages de statut proposés. Le backend n'impose pas de machine à états sur
 * les factures : l'écran se limite aux passages qui ont un sens comptable, et
 * ne propose rien sur une facture payée ou annulée.
 */
const SUITES: Record<string, Array<{ statut: string; libelle: string }>> = {
  BROUILLON: [
    { statut: 'EMISE', libelle: 'Émettre' },
    { statut: 'ANNULEE', libelle: 'Annuler' },
  ],
  EMISE: [
    { statut: 'PAYEE', libelle: 'Marquer payée' },
    { statut: 'EN_RETARD', libelle: 'Marquer en retard' },
    { statut: 'ANNULEE', libelle: 'Annuler' },
  ],
  EN_RETARD: [
    { statut: 'PAYEE', libelle: 'Marquer payée' },
    { statut: 'ANNULEE', libelle: 'Annuler' },
  ],
}

const LIGNE_VIDE = { libelle: '', quantite: '1', prix_unitaire: '' }

function NouvelleFacture({ onClose }: { onClose: () => void }) {
  const client = useQueryClient()
  const { cabinets } = useNomsCabinets()
  const [tenant, setTenant] = useState('')
  const [lignes, setLignes] = useState([{ ...LIGNE_VIDE }])
  const [f, setF] = useState({ periode_debut: '', periode_fin: '', date_echeance: '', statut: 'BROUILLON', notes: '' })

  const vers = (l: typeof LIGNE_VIDE): LigneFacture => {
    const quantite = Number(l.quantite) || 0
    const prix = Number(l.prix_unitaire) || 0
    return { libelle: l.libelle.trim(), quantite, prix_unitaire: prix, montant: quantite * prix }
  }
  const total = lignes.reduce((s, l) => s + vers(l).montant, 0)

  const creation = useMutation({
    mutationFn: () =>
      api.post(
        '/platform/invoices',
        {
          lignes: lignes.map(vers).filter((l) => l.libelle),
          periode_debut: f.periode_debut || null,
          periode_fin: f.periode_fin || null,
          date_echeance: f.date_echeance || null,
          statut: f.statut,
          notes: f.notes.trim() || null,
        },
        // Le backend lit `tenant_id` dans le corps ou la query ; la query reste
        // hors du schema type du corps.
        { params: { tenant_id: tenant } },
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['factures'] })
      toast.success('Facture créée.')
      onClose()
    },
  })

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    creation.mutate()
  }

  return (
    <Drawer open onClose={creation.isPending ? () => undefined : onClose} title="Nouvelle facture" width="xl">
      <form className="space-y-5" onSubmit={soumettre}>
        <Select
          label="Cabinet"
          required
          value={tenant}
          onChange={(e) => setTenant(e.target.value)}
          options={[{ value: '', label: 'Choisir un cabinet' }, ...cabinets.map((c) => ({ value: c.tenant_id, label: c.nom }))]}
        />

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Lignes</legend>
          {lignes.map((l, i) => (
            <div key={i} className="grid grid-cols-[1fr_80px_120px_auto] items-end gap-2">
              <Input label={i === 0 ? 'Libellé' : undefined} aria-label="Libellé" required value={l.libelle} onChange={(e) => setLignes((ls) => ls.map((x, j) => (j === i ? { ...x, libelle: e.target.value } : x)))} />
              <Input label={i === 0 ? 'Qté' : undefined} aria-label="Quantité" type="number" min={1} value={l.quantite} onChange={(e) => setLignes((ls) => ls.map((x, j) => (j === i ? { ...x, quantite: e.target.value } : x)))} />
              <Input label={i === 0 ? 'Prix unitaire' : undefined} aria-label="Prix unitaire" type="number" min={0} step="any" required value={l.prix_unitaire} onChange={(e) => setLignes((ls) => ls.map((x, j) => (j === i ? { ...x, prix_unitaire: e.target.value } : x)))} />
              <Button type="button" variant="ghost" size="icon" aria-label="Retirer la ligne" disabled={lignes.length === 1} onClick={() => setLignes((ls) => ls.filter((_, j) => j !== i))}>
                <Trash2 aria-hidden />
              </Button>
            </div>
          ))}
          <div className="flex items-center justify-between pt-1">
            <Button type="button" variant="outline" size="sm" onClick={() => setLignes((ls) => [...ls, { ...LIGNE_VIDE }])}>
              <Plus aria-hidden />
              Ajouter une ligne
            </Button>
            <p className="text-sm">
              Total : <strong>{montant(total)}</strong>
            </p>
          </div>
        </fieldset>

        <div className="grid gap-3 sm:grid-cols-3">
          <Input label="Période du" type="date" value={f.periode_debut} onChange={(e) => setF({ ...f, periode_debut: e.target.value })} />
          <Input label="au" type="date" value={f.periode_fin} onChange={(e) => setF({ ...f, periode_fin: e.target.value })} />
          <Input label="Échéance" type="date" value={f.date_echeance} onChange={(e) => setF({ ...f, date_echeance: e.target.value })} />
        </div>
        <Select
          label="Statut"
          value={f.statut}
          onChange={(e) => setF({ ...f, statut: e.target.value })}
          options={[
            { value: 'BROUILLON', label: 'Brouillon (modifiable)' },
            { value: 'EMISE', label: 'Émise' },
          ]}
        />
        <Textarea label="Notes" rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />

        {creation.isError && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {messageErreur(creation.error)}
          </p>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose} disabled={creation.isPending}>Annuler</Button>
          <Button type="submit" disabled={creation.isPending || !tenant || total <= 0}>
            {creation.isPending ? 'Création…' : 'Créer la facture'}
          </Button>
        </div>
      </form>
    </Drawer>
  )
}

/**
 * Factures émises par l'éditeur aux cabinets.
 *
 * **Aucun paiement n'est encaissé ici** : « Marquer payée » enregistre un
 * paiement constaté ailleurs. Le statut ne doit jamais venir d'un retour de
 * navigateur côté client.
 */
export function FacturesPage() {
  const client = useQueryClient()
  const peutEcrire = usePermission(PERMISSIONS.facturationEcrire)
  const { cabinets, nom } = useNomsCabinets()
  const [tenant, setTenant] = useState('')
  const [statut, setStatut] = useState('')
  const [page, setPage] = useState(1)
  const [creation, setCreation] = useState(false)
  const [changement, setChangement] = useState<{ facture: Facture; statut: string; libelle: string } | null>(null)

  const requete = useQuery({
    queryKey: ['factures', { tenant, statut, page }],
    queryFn: () => api.get<PageReponse<Facture>>('/platform/invoices', { params: { tenant_id: tenant, statut, page, limit: LIMITE } }),
    placeholderData: (precedent) => precedent,
  })

  const changer = useMutation({
    mutationFn: ({ id, statut: s, motif }: { id: string; statut: string; motif: string }) =>
      api.post(`/platform/invoices/${id}/statut`, undefined, { params: { statut: s, motif } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['factures'] })
      toast.success('Statut mis à jour.')
    },
  })

  const factures = requete.data?.items ?? []

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader titre="Factures" sousTitre="Facturation de l'éditeur aux cabinets." onRefresh={() => void requete.refetch()}>
          {peutEcrire && (
            <Button onClick={() => setCreation(true)}>
              <Plus aria-hidden />
              Nouvelle facture
            </Button>
          )}
        </PageHeader>

        <Card className="flex flex-wrap gap-3 p-4">
          <div className="w-64">
            <Select
              aria-label="Filtrer par cabinet"
              value={tenant}
              onChange={(e) => {
                setTenant(e.target.value)
                setPage(1)
              }}
              options={[{ value: '', label: 'Tous les cabinets' }, ...cabinets.map((c) => ({ value: c.tenant_id, label: c.nom }))]}
            />
          </div>
          <div className="w-48">
            <Select
              aria-label="Filtrer par statut"
              value={statut}
              onChange={(e) => {
                setStatut(e.target.value)
                setPage(1)
              }}
              options={[
                { value: '', label: 'Tous les statuts' },
                { value: 'BROUILLON', label: 'Brouillon' },
                { value: 'EMISE', label: 'Émise' },
                { value: 'PAYEE', label: 'Payée' },
                { value: 'EN_RETARD', label: 'En retard' },
                { value: 'ANNULEE', label: 'Annulée' },
              ]}
            />
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          {requete.isError ? (
            <div className="space-y-3 p-6 text-sm">
              <p role="alert" className="text-danger">{messageErreur(requete.error)}</p>
              <Button variant="outline" size="sm" onClick={() => void requete.refetch()}>Réessayer</Button>
            </div>
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH>Numéro</TH>
                  <TH>Cabinet</TH>
                  <TH className="text-right">Montant</TH>
                  <TH>Statut</TH>
                  <TH>Émise le</TH>
                  <TH>Échéance</TH>
                  {peutEcrire && <TH />}
                </TRow>
              </THead>
              <TBody>
                {requete.isPending ? (
                  <TRow><TD colSpan={7}><Skeleton className="h-20 w-full" /></TD></TRow>
                ) : factures.length === 0 ? (
                  <TRow>
                    <TD colSpan={7}>
                      <TableEmpty>
                        <span className="inline-flex items-center gap-2">
                          <Receipt className="h-4 w-4" aria-hidden />
                          Aucune facture.
                        </span>
                      </TableEmpty>
                    </TD>
                  </TRow>
                ) : (
                  factures.map((fa) => {
                    const s = statutFacture(fa.statut)
                    return (
                      <TRow key={fa.id}>
                        <TD className="font-mono text-xs">{fa.numero}</TD>
                        <TD>
                          <Link to={`/cabinets/${fa.tenant_id}`} className="font-medium hover:text-primary hover:underline">{nom(fa.tenant_id)}</Link>
                        </TD>
                        <TD className="text-right font-medium">{montant(fa.montant, fa.devise)}</TD>
                        <TD><StatusBadge tone={s.ton}>{s.texte}</StatusBadge></TD>
                        <TD className="text-muted-foreground">{date(fa.date_emission)}</TD>
                        <TD className="text-muted-foreground">{date(fa.date_echeance)}</TD>
                        {peutEcrire && (
                          <TD>
                            <span className="flex justify-end gap-1">
                              {(SUITES[fa.statut] ?? []).map((suite) => (
                                <Button
                                  key={suite.statut}
                                  size="sm"
                                  variant={suite.statut === 'ANNULEE' ? 'ghost' : 'outline'}
                                  onClick={() => setChangement({ facture: fa, ...suite })}
                                >
                                  {suite.libelle}
                                </Button>
                              ))}
                            </span>
                          </TD>
                        )}
                      </TRow>
                    )
                  })
                )}
              </TBody>
            </Table>
          )}
        </Card>

        <Pagination meta={requete.data?.meta} page={page} limit={LIMITE} onPageChange={setPage} libelle="factures" onPageHorsBornes={() => setPage(1)} />
      </div>

      {creation && <NouvelleFacture onClose={() => setCreation(false)} />}

      {changement && (
        <MotifDialog
          open
          onClose={() => setChangement(null)}
          titre={`${changement.libelle} — ${changement.facture.numero}`}
          description={`${nom(changement.facture.tenant_id)} · ${montant(changement.facture.montant, changement.facture.devise)}`}
          libelleConfirmer={changement.libelle}
          variante={changement.statut === 'ANNULEE' ? 'danger' : 'primary'}
          motifRequis={changement.statut === 'ANNULEE'}
          onConfirm={(motif) => changer.mutateAsync({ id: changement.facture.id, statut: changement.statut, motif })}
        />
      )}
    </AppShell>
  )
}
