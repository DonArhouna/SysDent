import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge, type StatusTone } from '@/components/ui/status-badge'
import { StatCard } from '@/components/dashboard/stat-card'
import {
  FileText,
  Clock,
  CheckCircle2,
  RefreshCw,
  WifiOff,
} from 'lucide-react'
import { formatFcfa, formatDateFr } from '@/lib/format'
import { facturationApi } from '../services/facturation-api'
import type { FactureResponse } from '../types'
import { PaiementModal } from '../components/paiement-modal'
import { FacturePrintModal } from '../components/facture-print-modal'
import {
  Banknote,
  Eye,
  FileSpreadsheet,
  Printer,
  Search,
} from 'lucide-react'

/** Statut facture → badge sémantique (source unique pour liste et détail). */
export function tonStatutFacture(statut: string): StatusTone {
  switch (statut) {
    case 'PAYEE':
      return 'success'
    case 'PARTIELLEMENT_PAYEE':
      return 'info'
    case 'ANNULEE':
      return 'neutral'
    default:
      return 'warning'
  }
}

const STATUT_OPTIONS = [
  { value: '', label: 'Tous les statuts' },
  { value: 'BROUILLON', label: 'Brouillon' },
  { value: 'EMISE', label: 'Émise (Non payée)' },
  { value: 'PARTIELLEMENT_PAYEE', label: 'Partiellement payée' },
  { value: 'PAYEE', label: 'Entièrement payée' },
  { value: 'ANNULEE', label: 'Annulée' },
]

export function FacturesListPage() {
  const [factures, setFactures] = useState<FactureResponse[]>([])
  const [loading, setLoading] = useState(true)
  /** Un chargement échoué ne doit pas s'afficher comme un résultat vide. */
  const [erreurChargement, setErreurChargement] = useState(false)
  const [totalRecords, setTotalRecords] = useState(0)

  // Filtres
  const [recherche, setRecherche] = useState('')
  const [statutFiltre, setStatutFiltre] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [page, setPage] = useState(1)

  // Modales
  const [selectedFacture, setSelectedFacture] = useState<FactureResponse | null>(null)
  const [isPaiementOpen, setIsPaiementOpen] = useState(false)
  const [isPrintOpen, setIsPrintOpen] = useState(false)

  const chargerFactures = async () => {
    try {
      setLoading(true)
      setErreurChargement(false)
      const res = await facturationApi.listerFactures({
        q: recherche.trim() || undefined,
        statut: statutFiltre || undefined,
        date_debut: dateDebut || undefined,
        date_fin: dateFin || undefined,
        page,
        limit: 20,
      })
      setFactures(res.items)
      setTotalRecords(res.meta.total_records)
    } catch {
      // toast géré par l'intercepteur API
      setErreurChargement(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerFactures()
  }, [page, statutFiltre, dateDebut, dateFin])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    chargerFactures()
  }

  // Totaux statistiques rapides
  const totalFacture = factures.reduce((acc, f) => acc + Number(f.montant_total), 0)
  const totalPaye = factures.reduce((acc, f) => acc + Number(f.montant_paye), 0)
  const totalRestant = factures.reduce((acc, f) => acc + Number(f.montant_restant), 0)

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <PageHeader
        titre={`Facturation & Règlements (${totalRecords})`}
        sousTitre="Suivi des factures médicales, encaissements multi-modes (Wave, OM, Espèces) et restes dus."
        onRefresh={() => void chargerFactures()}
      >
        <Link to="/journal-caisse">
          <Button variant="outline" className="flex items-center gap-1.5 text-xs">
            <Banknote className="w-4 h-4 text-success" /> Journal de caisse
          </Button>
        </Link>
        <Link to="/devis">
          <Button variant="outline" className="flex items-center gap-1.5 text-xs">
            <FileSpreadsheet className="w-4 h-4 text-primary" /> Devis & Traitements
          </Button>
        </Link>
      </PageHeader>

      {/* Cartes KPI (totaux calculés sur la page courante — pas d'endpoint stats dédié) */}
      {/* TODO(backend): endpoint dédié GET /facturation/stats pour des totaux globaux. */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Total facturé (page)"
          value={formatFcfa(totalFacture)}
          detail="Somme des factures de la page courante"
          icon={FileText}
          accent="blue"
          chargement={loading}
        />
        <StatCard
          label="Total encaissé"
          value={formatFcfa(totalPaye)}
          detail="Règlements enregistrés sur la page"
          icon={CheckCircle2}
          accent="green"
          chargement={loading}
        />
        <StatCard
          label="Solde restant à recouvrer"
          value={formatFcfa(totalRestant)}
          detail="Restes dus des factures de la page"
          icon={Clock}
          accent="orange"
          chargement={loading}
        />
      </div>

      {/* Barre de recherche & filtres */}
      <form
        onSubmit={handleSearchSubmit}
        className="bg-card p-4 rounded-xl border border-border grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
      >
        <div className="md:col-span-4">
          <Input
            label="Rechercher"
            placeholder="Numéro de facture..."
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
          />
        </div>

        <div className="md:col-span-3">
          <Select
            label="Statut"
            options={STATUT_OPTIONS}
            value={statutFiltre}
            onChange={(e) => setStatutFiltre(e.target.value)}
          />
        </div>

        <div className="md:col-span-2">
          <Input
            label="Date min"
            type="date"
            value={dateDebut}
            onChange={(e) => setDateDebut(e.target.value)}
          />
        </div>

        <div className="md:col-span-2">
          <Input
            label="Date max"
            type="date"
            value={dateFin}
            onChange={(e) => setDateFin(e.target.value)}
          />
        </div>

        <div className="md:col-span-1">
          <Button type="submit" variant="primary" className="w-full h-10 flex items-center justify-center">
            <Search className="w-4 h-4" />
          </Button>
        </div>
      </form>

      {/* Table des factures */}
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
            titre="Factures indisponibles"
            description="Ce module n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
          >
            <Button variant="outline" size="sm" onClick={() => void chargerFactures()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          </EmptyState>
        ) : factures.length === 0 ? (
          <EmptyState
            icon={Search}
            titre="Aucune facture trouvée"
            description="Aucune facture ne correspond aux critères de recherche."
          />
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>Numéro</TH>
                <TH>Émise le</TH>
                <TH className="text-right">Total</TH>
                <TH className="text-right">Payé</TH>
                <TH className="text-right">Reste dû</TH>
                <TH className="text-center">Statut</TH>
                <TH className="text-right">Actions</TH>
              </TRow>
            </THead>
            <TBody>
              {factures.map((f) => {
                const estPayee = f.statut === 'PAYEE'
                const estAnnulee = f.statut === 'ANNULEE'

                return (
                  <TRow key={f.id}>
                    <TD>
                      <Link
                        to={`/factures/${f.id}`}
                        className="font-mono font-bold text-foreground hover:text-primary"
                      >
                        {f.numero}
                      </Link>
                    </TD>
                    <TD className="text-xs">{formatDateFr(f.date_emission)}</TD>
                    <TD className="text-right font-mono font-semibold text-foreground">
                      {formatFcfa(f.montant_total)}
                    </TD>
                    <TD className="text-right font-mono text-success font-medium">
                      {formatFcfa(f.montant_paye)}
                    </TD>
                    <TD className="text-right font-mono font-bold text-primary">
                      {formatFcfa(f.montant_restant)}
                    </TD>
                    <TD className="text-center">
                      <StatusBadge tone={tonStatutFacture(f.statut)}>{f.statut}</StatusBadge>
                    </TD>
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {!estPayee && !estAnnulee && (
                          <Button
                            variant="primary"
                            size="sm"
                            className="text-xs h-7 px-2.5"
                            onClick={() => {
                              setSelectedFacture(f)
                              setIsPaiementOpen(true)
                            }}
                          >
                            Encaisser
                          </Button>
                        )}
                        <Button
                          variant="secondary"
                          size="sm"
                          className="text-xs h-7 px-2"
                          onClick={() => {
                            setSelectedFacture(f)
                            setIsPrintOpen(true)
                          }}
                        >
                          <Printer className="w-3.5 h-3.5" />
                        </Button>
                        <Link to={`/factures/${f.id}`}>
                          <Button variant="outline" size="sm" className="text-xs h-7 px-2">
                            <Eye className="w-3.5 h-3.5" />
                          </Button>
                        </Link>
                      </div>
                    </TD>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        )}
      </div>

      {/* Modale Paiement */}
      <PaiementModal
        isOpen={isPaiementOpen}
        onClose={() => {
          setIsPaiementOpen(false)
          setSelectedFacture(null)
        }}
        facture={selectedFacture}
        onSuccess={() => {
          chargerFactures()
        }}
      />

      {/* Modale Impression */}
      <FacturePrintModal
        isOpen={isPrintOpen}
        onClose={() => {
          setIsPrintOpen(false)
          setSelectedFacture(null)
        }}
        facture={selectedFacture}
      />
    </div>
  )
}
