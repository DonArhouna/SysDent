import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { formatFcfa, formatDateTimeFr } from '@/lib/format'
import { facturationApi } from '../services/facturation-api'
import type { JournalCaisseItem } from '../types'
import {
  ArrowLeft,
  Banknote,
  CreditCard,
  Printer,
  Smartphone,
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
  const [modeFiltre, setModeFiltre] = useState('')
  const [dateDebut, setDateDebut] = useState(new Date().toISOString().split('T')[0])
  const [dateFin, setDateFin] = useState(new Date().toISOString().split('T')[0])
  const [page] = useState(1)

  const chargerJournal = async () => {
    try {
      setLoading(true)
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 no-print">
        <div className="flex items-center gap-3">
          <Link to="/factures">
            <Button variant="outline" size="sm" className="h-9 px-2.5">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2.5">
              <Banknote className="w-6 h-6 text-success" />
              Journal de Caisse & Règlements
            </h1>
            <p className="text-sm text-muted-foreground">
              Traçabilité chronologique de tous les encaissements effectués au cabinet.
            </p>
          </div>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={handlePrint}
          className="flex items-center gap-1.5 text-xs self-start sm:self-auto"
        >
          <Printer className="w-4 h-4" /> Imprimer le journal (A4)
        </Button>
      </div>

      {/* Cartes KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-card p-4 rounded-xl border border-border">
          <span className="text-xs text-muted-foreground block font-medium">Recette Totale Période</span>
          <span className="text-xl font-bold text-success font-mono">
            {formatFcfa(totalGeneral)}
          </span>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border">
          <span className="text-xs text-muted-foreground block font-medium flex items-center gap-1.5">
            <Banknote className="w-3.5 h-3.5 text-card-foreground" /> Caisse Espèces
          </span>
          <span className="text-lg font-bold text-foreground font-mono">
            {formatFcfa(totalEspeces)}
          </span>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border">
          <span className="text-xs text-muted-foreground block font-medium flex items-center gap-1.5">
            <Smartphone className="w-3.5 h-3.5 text-primary" /> Wave & Orange Money
          </span>
          <span className="text-lg font-bold text-primary font-mono">
            {formatFcfa(totalMobile)}
          </span>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border">
          <span className="text-xs text-muted-foreground block font-medium flex items-center gap-1.5">
            <CreditCard className="w-3.5 h-3.5 text-accent-purple" /> Cartes Bancaires (TPE)
          </span>
          <span className="text-lg font-bold text-accent-purple font-mono">
            {formatFcfa(totalCartes)}
          </span>
        </div>
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
          <div className="p-8 text-center text-sm text-muted-foreground">
            Chargement des écritures de caisse...
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucun encaissement enregistré sur cette période.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-card-foreground">
              <thead className="bg-muted text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                <tr>
                  <th className="px-4 py-3">Date & Heure</th>
                  <th className="px-4 py-3">N° Reçu</th>
                  <th className="px-4 py-3">Facture N°</th>
                  <th className="px-4 py-3">Patient</th>
                  <th className="px-4 py-3">Mode</th>
                  <th className="px-4 py-3">Réf. transaction</th>
                  <th className="px-4 py-3 text-right">Montant</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((it) => (
                  <tr key={it.id} className="hover:bg-muted transition-colors">
                    <td className="px-4 py-3 text-card-foreground">
                      {formatDateTimeFr(it.date_paiement)}
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-primary">
                      {it.recu_numero}
                    </td>
                    <td className="px-4 py-3 font-mono">
                      <Link
                        to={`/factures/${it.facture_id}`}
                        className="text-foreground hover:text-primary"
                      >
                        {it.facture_numero}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-medium text-foreground">
                      {it.patient_nom ? `${it.patient_nom.toUpperCase()} ${it.patient_prenom}` : '-'}
                    </td>
                    <td className="px-4 py-3 uppercase text-[10px] font-bold text-card-foreground">
                      {it.mode}
                    </td>
                    <td className="px-4 py-3 font-mono text-muted-foreground text-[11px]">
                      {it.reference || '-'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-success">
                      {formatFcfa(it.montant)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
