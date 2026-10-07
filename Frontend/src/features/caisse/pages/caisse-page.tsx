import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Modal } from '@/components/ui/modal'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { StatCard } from '@/components/dashboard/stat-card'
import { formatFcfa, formatDateTimeFr } from '@/lib/format'
import { useToastStore } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { caisseApi } from '../caisse-api'
import type { ClotureCaissePayload, SessionCaisse } from '../types'
import { Banknote, CreditCard, Lock, RefreshCw, Smartphone, Wallet } from 'lucide-react'

/**
 * Écran Caisse : l'ouverture, la journée en cours, la clôture.
 *
 * Ce que la journée affiche est la raison d'être de l'écran : tant que la caisse
 * est ouverte, le caissier voit ce qu'il a pris et ce qu'il devrait avoir dans le
 * tiroir. Après la clôture, les totaux deviennent une pièce figée — d'où le
 * bandeau qui le dit, pour que personne n'aille « corriger » une journée close.
 */
export function CaissePage() {
  const cabinetActifId = useCabinetStore((etat) => etat.cabinetActifId)
  const sitePret = Boolean(cabinetActifId)
  const site = (cabinetActifId ?? '') as string

  const client = useQueryClient()
  const { addToast } = useToastStore()
  const [ouvertureOuverte, setOuvertureOuverte] = useState(false)
  const [clotureOuverte, setClotureOuverte] = useState(false)

  const sessionQuery = useQuery({
    queryKey: ['caisse', 'courante', site],
    queryFn: () => caisseApi.sessionCourante(site),
    enabled: sitePret,
  })

  const historiqueQuery = useQuery({
    queryKey: ['caisse', 'historique', site],
    queryFn: () => caisseApi.historique(site),
    enabled: sitePret,
  })

  const session = sessionQuery.data ?? null
  const historique = historiqueQuery.data?.data ?? []

  const cloturer = useMutation({
    // Un objet et non deux arguments : `useMutation` ne transmet qu'une seule
    // variable, il faut donc regrouper l'identifiant et la clôture.
    mutationFn: ({ sessionId, ...payload }: { sessionId: string } & ClotureCaissePayload) =>
      caisseApi.cloturer(sessionId, payload),
    onSuccess: (closee) => {
      addToast({
        type: closee.ecart_especes && closee.ecart_especes !== 0 ? 'warning' : 'success',
        message:
          closee.ecart_especes && closee.ecart_especes !== 0
            ? `Session ${closee.numero} close avec un écart de ${formatFcfa(closee.ecart_especes)}.`
            : `Session ${closee.numero} close : tout concorde.`,
      })
      setClotureOuverte(false)
      void client.invalidateQueries({ queryKey: ['caisse'] })
    },
  })

  const recharger = () => {
    void sessionQuery.refetch()
    void historiqueQuery.refetch()
  }

  if (!sitePret) {
    return (
      <div className="space-y-6">
        <PageHeader titre="Caisse" sousTitre="Ouverture, encaissements et clôture de la journée" />
        <EmptyState
          icon={Wallet}
          titre="Aucun site sélectionné"
          description="La caisse appartient à un site : choisissez-en un en haut de l'écran pour ouvrir ou clôturer sa journée."
        >
          <Button variant="outline" onClick={recharger}>
            <RefreshCw className="h-4 w-4" /> Recharger les sites
          </Button>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        titre="Caisse"
        sousTitre="Ouverture, encaissements et clôture de la journée"
        onRefresh={recharger}
      />

      {sessionQuery.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : session ? (
        <SessionOuverte
          session={session}
          onCloturer={() => setClotureOuverte(true)}
          clotureEnCours={cloturer.isPending}
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-4 w-4" />
              Caisse fermée
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Le tiroir est fermé. Tant qu'aucune session n'est ouverte, le serveur refuse les
              encaissements : un montant reçu hors de toute borne temporelle ne se retrouve
              dans aucun rapport.
            </p>
            <Button onClick={() => setOuvertureOuverte(true)}>
              <Banknote className="h-4 w-4" /> Ouvrir la caisse
            </Button>
          </CardContent>
        </Card>
      )}

      <HistoriqueSessions sessions={historique} chargement={historiqueQuery.isPending} />

      <ModalOuverture
        ouvert={ouvertureOuverte}
        cabinetId={site}
        onClose={() => setOuvertureOuverte(false)}
        onOuverte={() => {
          setOuvertureOuverte(false)
          void client.invalidateQueries({ queryKey: ['caisse'] })
        }}
      />

      <ModalCloture
        ouvert={clotureOuverte}
        session={session}
        onClose={() => setClotureOuverte(false)}
        onCloturer={(payload) => {
          if (session) cloturer.mutate({ sessionId: session.id, ...payload })
        }}
        enCours={cloturer.isPending}
      />
    </div>
  )
}

// ------------------------------------------------------------------------------
// Session ouverte
// ------------------------------------------------------------------------------

function SessionOuverte({
  session,
  onCloturer,
  clotureEnCours,
}: {
  session: SessionCaisse
  onCloturer: () => void
  clotureEnCours: boolean
}) {
  const paiements = useQuery({
    queryKey: ['caisse', 'paiements', session.id],
    queryFn: () => caisseApi.paiements(session.id),
  })

  const especesEncaissees = Number(session.total_especes ?? 0)
  // Ce que le tiroir devrait contenir à cet instant. L'écart n'a de sens qu'à la
  // clôture, mais l-anticipation évite la mauvaise surprise le soir.
  const attendu = Number(session.ouverture_especes ?? 0) + especesEncaissees

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <StatusBadge tone="success">Caisse ouverte</StatusBadge>
          <span className="text-sm text-muted-foreground">
            Session {session.numero} ouverte le {formatDateTimeFr(session.ouverte_le)}
            {session.ouverte_par ? ` par ${session.ouverte_par}` : ''}
          </span>
        </div>
        <Button onClick={onCloturer} disabled={clotureEnCours}>
          <Lock className="h-4 w-4" /> Clôturer la journée
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Espèces au tiroir (attendu)"
          value={formatFcfa(attendu)}
          detail={`Dépôt ${formatFcfa(session.ouverture_especes)} + ${formatFcfa(especesEncaissees)} encaissés`}
          icon={Banknote}
          accent="green"
        />
        <StatCard
          label="Total encaissé"
          value={formatFcfa(session.total_encaisse)}
          detail={`${session.nb_paiements} encaissement(s)`}
          icon={Wallet}
          accent="blue"
        />
        <StatCard label="Mobile Money" value={formatFcfa(session.total_mobile_money)} detail="Wave / Orange Money" icon={Smartphone} accent="purple" />
        <StatCard label="Carte bancaire" value={formatFcfa(session.total_carte)} detail="TPE" icon={CreditCard} accent="orange" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Totaux par mode</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-muted-foreground">
            Ces chiffres bougent jusqu'à la clôture. Après, ils sont figés : une journée close
            reste ce qui a été constaté ce jour-là.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <TotalMode label="Espèces" valeur={session.total_especes} />
            <TotalMode label="Carte bancaire" valeur={session.total_carte} />
            <TotalMode label="Virement" valeur={session.total_virement} />
            <TotalMode label="Mobile Money" valeur={session.total_mobile_money} />
            <TotalMode label="Chèque" valeur={session.total_cheque} />
            <TotalMode label="Assurance / Tiers-payant" valeur={session.total_assurance} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Encaissements de la session</CardTitle>
        </CardHeader>
        <CardContent>
          {paiements.isPending ? (
            <Skeleton className="h-32 w-full" />
          ) : (paiements.data?.items ?? []).length === 0 ? (
            <EmptyState
              icon={Wallet}
              titre="Aucun encaissement pour l'instant"
              description="Les paiements enregistrés depuis l'ouverture de la caisse apparaîtront ici."
            />
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH>Reçu</TH>
                  <TH>Date</TH>
                  <TH>Mode</TH>
                  <TH>Référence</TH>
                  <TH>Caissier</TH>
                  <TH className="text-right">Montant</TH>
                </TRow>
              </THead>
              <TBody>
                {(paiements.data?.items ?? []).map((p) => (
                  <TRow key={p.id}>
                    <TD className="font-mono text-xs">{p.recu_numero}</TD>
                    <TD className="text-muted-foreground">{formatDateTimeFr(p.date_paiement)}</TD>
                    <TD>{LIBELLE_MODE[p.mode] ?? p.mode}</TD>
                    <TD className="text-muted-foreground">{p.reference ?? '—'}</TD>
                    <TD className="text-muted-foreground">{p.auteur ?? '—'}</TD>
                    <TD className="text-right font-semibold tabular-nums">
                      {formatFcfa(p.montant)}
                    </TD>
                  </TRow>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function TotalMode({ label, valeur }: { label: string; valeur: number }) {
  return (
    <div className="rounded-xl2 border bg-card/60 px-3 py-2">
      <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="text-base font-semibold tabular-nums">{formatFcfa(valeur)}</span>
    </div>
  )
}

const LIBELLE_MODE: Record<string, string> = {
  ESPECES: 'Espèces',
  CARTE_BANCAIRE: 'Carte bancaire',
  CHEQUE: 'Chèque',
  VIREMENT: 'Virement',
  MOBILE_MONEY: 'Mobile Money',
  ASSURANCE: 'Assurance / Tiers-payant',
}

// ------------------------------------------------------------------------------
// Historique
// ------------------------------------------------------------------------------

function HistoriqueSessions({
  sessions,
  chargement,
}: {
  sessions: SessionCaisse[]
  chargement: boolean
}) {
  const closes = sessions.filter((s) => s.statut === 'CLOSE')

  return (
    <Card>
      <CardHeader>
        <CardTitle>Journées closes</CardTitle>
      </CardHeader>
      <CardContent>
        {chargement ? (
          <Skeleton className="h-24 w-full" />
        ) : closes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune journée close sur ce site. L'écart de caisse n'apparaît qu'après une clôture :
            c'est à ce moment qu'on peut compter.
          </p>
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>Session</TH>
                <TH>Ouverte</TH>
                <TH>Clôturée par</TH>
                <TH className="text-right">Encaissé</TH>
                <TH className="text-right">Écart</TH>
              </TRow>
            </THead>
            <TBody>
              {closes.map((s) => {
                const ecart = Number(s.ecart_especes ?? 0)
                return (
                  <TRow key={s.id}>
                    <TD className="font-mono text-xs">{s.numero}</TD>
                    <TD className="text-muted-foreground">{formatDateTimeFr(s.ouverte_le)}</TD>
                    <TD className="text-muted-foreground">{s.close_par ?? '—'}</TD>
                    <TD className="text-right font-semibold tabular-nums">
                      {formatFcfa(s.total_encaisse)}
                    </TD>
                    <TD
                      className={`text-right font-semibold tabular-nums ${
                        ecart === 0 ? 'text-muted-foreground' : 'text-danger'
                      }`}
                    >
                      {ecart === 0 ? '0 F' : formatFcfa(ecart)}
                    </TD>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

// ------------------------------------------------------------------------------
// Ouverture
// ------------------------------------------------------------------------------

function ModalOuverture({
  ouvert,
  cabinetId,
  onClose,
  onOuverte,
}: {
  ouvert: boolean
  cabinetId: string
  onClose: () => void
  onOuverte: () => void
}) {
  const { addToast } = useToastStore()
  const [depot, setDepot] = useState('0')
  const [notes, setNotes] = useState('')

  const ouvrir = useMutation({
    mutationFn: caisseApi.ouvrir,
    onSuccess: (session) => {
      addToast({ type: 'success', message: `Session ${session.numero} ouverte.` })
      setDepot('0')
      setNotes('')
      onOuverte()
    },
  })

  return (
    <Modal
      isOpen={ouvert}
      onClose={onClose}
      title="Ouvrir la caisse"
      description="Déclarez les espèces déjà présentes dans le tiroir."
      maxWidth="md"
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          ouvrir.mutate({ cabinet_id: cabinetId, ouverture_especes: Number(depot) || 0, notes: notes || undefined })
        }}
      >
        <div className="space-y-1.5">
          <label htmlFor="depot" className="text-sm font-medium">
            Espèces au départ
          </label>
          <Input
            id="depot"
            type="number"
            min={0}
            value={depot}
            onChange={(e) => setDepot(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            C'est votre dépôt, pas de l'argent du cabinet : il sera comparé à ce que vous
            comptera ce soir.
          </p>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="notes-ouverture" className="text-sm font-medium">
            Note (facultatif)
          </label>
          <Textarea
            id="notes-ouverture"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" disabled={ouvrir.isPending}>
            Ouvrir
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ------------------------------------------------------------------------------
// Clôture
// ------------------------------------------------------------------------------

function ModalCloture({
  ouvert,
  session,
  onClose,
  onCloturer,
  enCours,
}: {
  ouvert: boolean
  session: SessionCaisse | null
  onClose: () => void
  onCloturer: (payload: { especes_comptees: number; motif_ecart?: string }) => void
  enCours: boolean
}) {
  const attendu = session ? Number(session.especes_attendues ?? 0) : 0
  const [comptees, setComptees] = useState('')
  const [motif, setMotif] = useState('')

  const compte = Number(comptees)
  const ecart = Number.isFinite(compte) ? compte - attendu : null

  return (
    <Modal
      isOpen={ouvert}
      onClose={onClose}
      title="Clôturer la journée"
      description="Comptiez les espèces du tiroir et déclarez le montant."
      maxWidth="md"
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (!Number.isFinite(compte) || compte < 0) return
          onCloturer({ especes_comptees: compte, motif_ecart: motif || undefined })
        }}
      >
        <div className="rounded-xl2 border bg-surface/60 px-3 py-2 text-sm">
          <span className="text-muted-foreground">Espèces attendues au tiroir : </span>
          <span className="font-semibold tabular-nums">{formatFcfa(attendu)}</span>
          <span className="block text-xs text-muted-foreground">
            Dépôt d'ouverture {formatFcfa(session?.ouverture_especes)} + espèces encaissées{' '}
            {formatFcfa(session?.total_especes)}
          </span>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="comptees" className="text-sm font-medium">
            Espèces comptées
          </label>
          <Input
            id="comptees"
            type="number"
            min={0}
            value={comptees}
            onChange={(e) => setComptees(e.target.value)}
            autoFocus
          />
        </div>

        {ecart !== null && comptees !== '' && (
          <div
            className={`rounded-xl2 border px-3 py-2 text-sm ${
              ecart === 0 ? 'border-border bg-surface/60' : 'border-danger/40 bg-danger/10'
            }`}
          >
            {ecart === 0 ? (
              <span>Le compte est juste.</span>
            ) : (
              <span>
                Écart de <span className="font-semibold tabular-nums">{formatFcfa(ecart)}</span>{' '}
                — {ecart < 0 ? 'il manque' : 'il y a un excédent'}.
              </span>
            )}
          </div>
        )}

        <div className="space-y-1.5">
          <label htmlFor="motif" className="text-sm font-medium">
            Motif de l'écart (facultatif)
          </label>
          <Input
            id="motif"
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Ex. rendu de monnaie égaré"
          />
          <p className="text-xs text-muted-foreground">
            Un écart n'est pas une faute. Si vous ne savez pas pourquoi, laissez vide : une
            explication inventée ne vaut rien.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            type="submit"
            disabled={enCours || comptees === '' || !Number.isFinite(compte) || compte < 0}
          >
            Clôturer
          </Button>
        </div>
      </form>
    </Modal>
  )
}
