import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { formatFcfa, formatDateFr } from '@/lib/format'
import { facturationApi } from '../services/facturation-api'
import type { FactureResponse } from '../types'
import { PaiementModal } from '../components/paiement-modal'
import { FacturePrintModal } from '../components/facture-print-modal'
import {
  Banknote,
  CheckCircle2,
  Clock,
  CreditCard,
  Eye,
  FileSpreadsheet,
  FileText,
  Printer,
  Search,
} from 'lucide-react'

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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2.5">
            <CreditCard className="w-6 h-6 text-primary" />
            Facturation & Règlements ({totalRecords})
          </h1>
          <p className="text-sm text-muted-foreground">
            Suivi des factures médicales, encaissements multi-modes (Wave, OM, Espèces) et restes dus.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/journal-caisse">
            <Button variant="outline" className="flex items-center gap-1.5 text-xs border-border">
              <Banknote className="w-4 h-4 text-success" /> Journal de caisse
            </Button>
          </Link>
          <Link to="/devis">
            <Button variant="outline" className="flex items-center gap-1.5 text-xs border-border">
              <FileSpreadsheet className="w-4 h-4 text-primary" /> Devis & Traitements
            </Button>
          </Link>
        </div>
      </div>

      {/* Cartes KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card p-4 rounded-xl border border-border flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">Total Facturé (Page)</span>
            <span className="text-xl font-bold text-foreground">{formatFcfa(totalFacture)}</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-card-foreground">
            <FileText className="w-5 h-5" />
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">Total Encaissé</span>
            <span className="text-xl font-bold text-success">{formatFcfa(totalPaye)}</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-success/15 border border-success/40 flex items-center justify-center text-success">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">Solde Restant à Recouvrer</span>
            <span className="text-xl font-bold text-primary">{formatFcfa(totalRestant)}</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-primary/15 border border-primary/40 flex items-center justify-center text-primary">
            <Clock className="w-5 h-5" />
          </div>
        </div>
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
          <div className="p-8 text-center text-sm text-muted-foreground">Chargement des factures...</div>
        ) : factures.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucune facture ne correspond aux critères de recherche.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-card-foreground">
              <thead className="bg-muted text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                <tr>
                  <th className="px-4 py-3">Numéro</th>
                  <th className="px-4 py-3">Émise le</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3 text-right">Payé</th>
                  <th className="px-4 py-3 text-right">Reste dû</th>
                  <th className="px-4 py-3 text-center">Statut</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {factures.map((f) => {
                  const estPayee = f.statut === 'PAYEE'
                  const estPartielle = f.statut === 'PARTIELLEMENT_PAYEE'
                  const estAnnulee = f.statut === 'ANNULEE'

                  return (
                    <tr key={f.id} className="hover:bg-muted transition-colors">
                      <td className="px-4 py-3">
                        <Link
                          to={`/factures/${f.id}`}
                          className="font-mono font-bold text-foreground hover:text-primary"
                        >
                          {f.numero}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-card-foreground">
                        {formatDateFr(f.date_emission)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-foreground">
                        {formatFcfa(f.montant_total)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-success font-medium">
                        {formatFcfa(f.montant_paye)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-primary">
                        {formatFcfa(f.montant_restant)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            estPayee
                              ? 'bg-success/15 border border-success/40 text-success'
                              : estPartielle
                              ? 'bg-primary/15 border border-primary/40 text-primary'
                              : estAnnulee
                              ? 'bg-muted border border-border text-muted-foreground line-through'
                              : 'bg-warning/15 border border-warning/40 text-warning'
                          }`}
                        >
                          {f.statut}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
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
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
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
