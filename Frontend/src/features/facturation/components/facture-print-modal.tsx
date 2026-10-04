import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { formatDateFr, formatDateTimeFr, formatFcfa } from '@/lib/format'
import type { FactureResponse } from '../types'
import { CheckCircle2, Clock, Printer } from 'lucide-react'

interface FacturePrintModalProps {
  isOpen: boolean
  onClose: () => void
  facture: FactureResponse | null
  patientNom?: string
}

export function FacturePrintModal({
  isOpen,
  onClose,
  facture,
  patientNom,
}: FacturePrintModalProps) {
  if (!facture) return null

  const handlePrint = () => {
    window.print()
  }

  const estPayee = facture.statut === 'PAYEE'
  const estPartielle = facture.statut === 'PARTIELLEMENT_PAYEE'

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Facture ${facture.numero}`} size="lg">
      <div className="space-y-6">
        {/* Actions bar */}
        <div className="flex items-center justify-between no-print bg-slate-900/60 p-3 rounded-xl border border-slate-700/60">
          <div className="flex items-center gap-2">
            {estPayee ? (
              <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-950/40 border border-emerald-700/50 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" /> Facture entièrement acquittée
              </span>
            ) : estPartielle ? (
              <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-cyan-950/40 border border-cyan-700/50 text-cyan-400">
                <Clock className="w-3.5 h-3.5" /> Partiellement réglée
              </span>
            ) : (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-950/40 border border-amber-700/50 text-amber-400">
                En attente de paiement
              </span>
            )}
          </div>
          <Button variant="primary" size="sm" onClick={handlePrint} className="text-xs">
            <Printer className="w-3.5 h-3.5 mr-1.5" /> Imprimer la facture (A4)
          </Button>
        </div>

        {/* Printable Area */}
        <div
          id="facture-print-area"
          className="bg-white text-slate-900 p-8 rounded-xl shadow-lg border border-slate-200 font-sans print:p-0 print:border-none print:shadow-none min-h-[600px] flex flex-col justify-between"
        >
          <div>
            {/* Header */}
            <div className="border-b-2 border-slate-900 pb-5 mb-6 flex justify-between items-start">
              <div>
                <h2 className="text-xl font-black text-slate-900 tracking-tight">
                  CLINIQUE MÉDICO-DENTAIRE SYSDENT PRO
                </h2>
                <p className="text-xs text-slate-600 font-medium">
                  Soins Dentaires Spécialisés • Implantologie • Orthodontie
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Avenue Cheikh Anta Diop, Dakar • Tél: +221 33 824 00 00
                </p>
                <p className="text-[10px] text-slate-400 font-mono">
                  NINEA: 004829102 2V2 • RCCM: SN-DKR-2022-B-1190
                </p>
              </div>
              <div className="text-right">
                <div className="inline-block bg-slate-900 text-white px-3 py-1 rounded font-mono font-bold text-sm tracking-wider mb-2">
                  FACTURE N° {facture.numero}
                </div>
                <p className="text-xs text-slate-600">
                  Date d'émission : <strong>{formatDateFr(facture.date_emission)}</strong>
                </p>
                {facture.date_echeance && (
                  <p className="text-xs text-slate-600 mt-0.5">
                    Échéance : <strong>{formatDateFr(facture.date_echeance)}</strong>
                  </p>
                )}
              </div>
            </div>

            {/* Facturé à */}
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-6 flex justify-between items-center text-xs">
              <div>
                <span className="text-slate-500 uppercase font-semibold text-[10px] tracking-wider block">
                  Facturé au patient
                </span>
                <p className="text-sm font-bold text-slate-900 mt-0.5">
                  {patientNom || 'Patient du cabinet'}
                </p>
                <p className="text-[11px] text-slate-500 font-mono mt-0.5">
                  ID: {facture.patient_id}
                </p>
              </div>
              <div className="text-right">
                <span className="text-slate-500 uppercase font-semibold text-[10px] tracking-wider block">
                  Statut de paiement
                </span>
                <span
                  className={`inline-block mt-1 font-bold text-xs px-2.5 py-0.5 rounded ${
                    estPayee
                      ? 'bg-emerald-100 text-emerald-800'
                      : estPartielle
                      ? 'bg-cyan-100 text-cyan-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {facture.statut}
                </span>
              </div>
            </div>

            {/* Tableau des lignes */}
            <div className="mb-6 overflow-hidden border border-slate-200 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200 uppercase text-[10px]">
                  <tr>
                    <th className="px-4 py-2.5">Désignation des actes & prestations</th>
                    <th className="px-4 py-2.5 text-center">Qté</th>
                    <th className="px-4 py-2.5 text-right">Prix Unitaire</th>
                    <th className="px-4 py-2.5 text-right">Montant (FCFA)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {facture.lignes.map((ligne, idx) => (
                    <tr key={idx}>
                      <td className="px-4 py-2.5 text-slate-900 font-medium">
                        {ligne.designation}
                      </td>
                      <td className="px-4 py-2.5 text-center text-slate-600">{ligne.quantite}</td>
                      <td className="px-4 py-2.5 text-right text-slate-600 font-mono">
                        {formatFcfa(ligne.prix_unitaire)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-slate-900 font-mono font-bold">
                        {formatFcfa(ligne.montant)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Totaux */}
            <div className="flex justify-end mb-6">
              <div className="w-72 space-y-1.5 text-xs bg-slate-50 p-4 rounded-lg border border-slate-200">
                <div className="flex justify-between text-slate-600">
                  <span>Montant Total :</span>
                  <span className="font-mono font-bold text-slate-900">
                    {formatFcfa(facture.montant_total)}
                  </span>
                </div>
                {Number(facture.montant_tva) > 0 && (
                  <div className="flex justify-between text-slate-600">
                    <span>TVA :</span>
                    <span className="font-mono text-slate-900">
                      {formatFcfa(facture.montant_tva)}
                    </span>
                  </div>
                )}
                <div className="flex justify-between text-emerald-700 font-medium pt-1 border-t border-slate-200">
                  <span>Montant Déjà Encaissé :</span>
                  <span className="font-mono font-bold">-{formatFcfa(facture.montant_paye)}</span>
                </div>
                <div className="flex justify-between text-slate-900 font-black text-sm pt-2 border-t-2 border-slate-900">
                  <span>NET RESTANT DÛ :</span>
                  <span className="font-mono text-cyan-800">
                    {formatFcfa(facture.montant_restant)}
                  </span>
                </div>
              </div>
            </div>

            {/* Historique des paiements & Reçus */}
            {facture.paiements && facture.paiements.length > 0 && (
              <div className="mb-6">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-2">
                  Versements & Reçus d'encaissement
                </h4>
                <div className="border border-slate-200 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200 text-[10px]">
                      <tr>
                        <th className="px-3 py-2">N° Reçu</th>
                        <th className="px-3 py-2">Date</th>
                        <th className="px-3 py-2">Mode</th>
                        <th className="px-3 py-2">Référence</th>
                        <th className="px-3 py-2 text-right">Montant</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {facture.paiements.map((p) => (
                        <tr key={p.id}>
                          <td className="px-3 py-1.5 font-mono font-bold text-slate-800">
                            {p.recu_numero}
                          </td>
                          <td className="px-3 py-1.5 text-slate-600">
                            {formatDateTimeFr(p.date_paiement)}
                          </td>
                          <td className="px-3 py-1.5 uppercase text-[10px] text-slate-700">
                            {p.mode}
                          </td>
                          <td className="px-3 py-1.5 font-mono text-[10px] text-slate-500">
                            {p.reference || '-'}
                          </td>
                          <td className="px-3 py-1.5 text-right font-mono font-bold text-emerald-700">
                            {formatFcfa(p.montant)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Footer & Signature */}
          <div className="border-t border-slate-200 pt-4 mt-8 flex justify-between items-end">
            <div className="text-[10px] text-slate-500 max-w-sm space-y-1">
              <p className="font-semibold text-slate-700">Modalités de règlement :</p>
              <p>• Wave / Orange Money : Envoyer au +221 77 000 00 00 avec N° Facture</p>
              <p>• Virement bancaire : BOA SN001 01001 12345678901 22</p>
              <p className="text-[9px] text-slate-400">
                Document généré électroniquement par SysDent Pro. Fait foi de facture acquittée si
                le solde est nul.
              </p>
            </div>
            <div className="text-center w-48">
              <p className="text-xs text-slate-600 mb-2">Cachet de la Caisse</p>
              {estPayee ? (
                <div className="border-2 border-emerald-600 rounded-lg p-2 text-emerald-800 font-mono text-center">
                  <span className="font-black text-xs block">ACQUITTÉ</span>
                  <span className="text-[9px] block">SysDent Caisse Centrale</span>
                </div>
              ) : (
                <div className="h-16 border-b border-dashed border-slate-400"></div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}
