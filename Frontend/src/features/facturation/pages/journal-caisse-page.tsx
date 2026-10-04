import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatCard } from '@/components/dashboard/stat-card'
import { formatFcfa, formatDateTimeFr } from '@/lib/format'
import { facturationApi } from '../services/facturation-api'
import type { JournalCaisseItem } from '../types'
import {
  ArrowLeft,
  Banknote,
  CreditCard,
  Printer,
  Smartphone,
  RefreshCw,
  WifiOff,
} from 'lucide-react'

const MODES_OPTIONS = [
  { value: '', label: 'Tous les modes de règlement' },
  { value: 'ESPECES', label: 'Espèces' },
  { value: 'MOBILE_MONEY', label: 'Mobile Money (Wave / OM)' },
  { value: 'CARTE_BANCAIRE', label: 'Carte Bancaire' },
  { value: 'CHEQUE', label: 'Chèque' },
  { value: 'VIREMENT', label: 'Virement' },
  { value: 'ASSURANCE', label: 'Assurance / Tiers-Payant' },
]

export function JournalCaissePage() {
  const [items, setItems] = useState<JournalCaisseItem[]>([])
  const [loading, setLoading] = useState(true)
  /** Un chargement échoué ne doit pas s'afficher comme un résultat vide. */
  const [erreurChargement, setErreurChargement] = useState(false)
  const [modeFiltre, setModeFiltre] = useState('')
  const [dateDebut, setDateDebut] = useState(new Date().toISOString().split('T')[0])
  const [dateFin, setDateFin] = useState(new Date().toISOString().split('T')[0])
  const [page] = useState(1)

  const chargerJournal = async () => {
    try {
      setLoading(true)
      setErreurChargement(false)
      const res = await facturationApi.journalCaisse({
        date_debut: dateDebut || undefined,
        date_fin: dateFin || undefined,
        mode: modeFiltre || undefined,
        page,
        limit: 100,
      })
      setItems(res.items)
    } catch {
      // toast géré par l'intercepteur API
      setErreurChargement(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerJournal()
  }, [dateDebut, dateFin, modeFiltre, page])

  const handlePrint = () => {
    window.print()
  }

  // Calculs par mode
  const totalGeneral = items.reduce((acc, it) => acc + Number(it.montant), 0)
  const totalEspeces = items
    .filter((it) => it.mode === 'ESPECES')
    .reduce((acc, it) => acc + Number(it.montant), 0)
  const totalMobile = items
    .filter((it) => it.mode === 'MOBILE_MONEY')
    .reduce((acc, it) => acc + Number(it.montant), 0)
  const totalCartes = items
    .filter((it) => it.mode === 'CARTE_BANCAIRE')
    .reduce((acc, it) => acc + Number(it.montant), 0)

  return (
    <div className="space-y-6">
      {/* Retour */}
      <Link
        to="/factures"
        className="no-print inline-flex w-fit items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Retour aux factures
      </Link>

      {/* Header */}
      <PageHeader
        className="no-print"
        titre="Journal de Caisse & Règlements"
        sousTitre="Traçabilité chronologique de tous les encaissements effectués au cabinet."
        onRefresh={() => void chargerJournal()}
      >
        <Button
          variant="secondary"
          size="sm"
          onClick={handlePrint}
          className="flex items-center gap-1.5 text-xs"
        >
          <Printer className="w-4 h-4" /> Imprimer le journal (A4)
        </Button>
      </PageHeader>

      {/* Cartes KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Recette totale période"
          value={formatFcfa(totalGeneral)}
          detail="Tous modes de règlement confondus"
          icon={Banknote}
          accent="green"
          chargement={loading}
        />
        <StatCard
          label="Caisse espèces"
          value={formatFcfa(totalEspeces)}
          detail="Encaissements en espèces"
          icon={Banknote}
          accent="blue"
          chargement={loading}
        />
        <StatCard
          label="Wave & Orange Money"
          value={formatFcfa(totalMobile)}
          detail="Paiements mobile money"
          icon={Smartphone}
          accent="purple"
          chargement={loading}
        />
        <StatCard
          label="Cartes bancaires (TPE)"
          value={formatFcfa(totalCartes)}
          detail="Encaissements par carte"
          icon={CreditCard}
          accent="orange"
          chargement={loading}
        />
      </div>

      {/* Filtres date & mode */}
      <div className="bg-card p-4 rounded-xl border border-border grid grid-cols-1 md:grid-cols-3 gap-3 no-print">
        <Input
          label="Date début"
          type="date"
          value={dateDebut}
          onChange={(e) => setDateDebut(e.target.value)}
        />
        <Input
          label="Date fin"
          type="date"
          value={dateFin}
          onChange={(e) => setDateFin(e.target.value)}
        />
        <Select
          label="Filtrer par mode de règlement"
          options={MODES_OPTIONS}
          value={modeFiltre}
          onChange={(e) => setModeFiltre(e.target.value)}
        />
      </div>

      {/* Tableau du journal */}
      <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
        {loading ? (
          <div className="space-y-3 p-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : erreurChargement ? (
          <EmptyState
            icon={WifiOff}
            titre="Le journal de caisse indisponibles"
            description="Ce module n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
          >
            <Button variant="outline" size="sm" onClick={() => void chargerJournal()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          </EmptyState>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Banknote}
            titre="Aucun encaissement"
            description="Aucun encaissement enregistré sur cette période."
          />
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>Date & Heure</TH>
                <TH>N° Reçu</TH>
                <TH>Facture N°</TH>
                <TH>Patient</TH>
                <TH>Mode</TH>
                <TH>Réf. transaction</TH>
                <TH className="text-right">Montant</TH>
              </TRow>
            </THead>
            <TBody>
              {items.map((it) => (
                <TRow key={it.id}>
                  <TD className="text-xs">{formatDateTimeFr(it.date_paiement)}</TD>
                  <TD className="font-mono font-bold text-primary text-xs">{it.recu_numero}</TD>
                  <TD className="font-mono text-xs">
                    <Link
                      to={`/factures/${it.facture_id}`}
                      className="text-foreground hover:text-primary"
                    >
                      {it.facture_numero}
                    </Link>
                  </TD>
                  <TD className="font-medium text-foreground text-xs">
                    {it.patient_nom ? `${it.patient_nom.toUpperCase()} ${it.patient_prenom}` : '-'}
                  </TD>
                  <TD className="uppercase text-[10px] font-bold text-card-foreground">{it.mode}</TD>
                  <TD className="font-mono text-muted-foreground text-[11px]">{it.reference || '-'}</TD>
                  <TD className="text-right font-mono font-bold text-success">
                    {formatFcfa(it.montant)}
                  </TD>
                </TRow>
              ))}
            </TBody>
          </Table>
        )}
      </div>
    </div>
  )
}
