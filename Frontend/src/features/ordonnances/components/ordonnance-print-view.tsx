import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { formatDateFr, formatDateTimeFr } from '@/lib/format'
import type { OrdonnanceResponse } from '../types'
import { CheckCircle2, Lock, Printer } from 'lucide-react'

interface OrdonnancePrintViewProps {
  isOpen: boolean
  onClose: () => void
  ordonnance: OrdonnanceResponse | null
  patientNom?: string
  praticienNom?: string
  onSigner?: (id: string) => void
}

export function OrdonnancePrintView({
  isOpen,
  onClose,
  ordonnance,
  patientNom,
  praticienNom,
  onSigner,
}: OrdonnancePrintViewProps) {
  if (!ordonnance) return null

  const handlePrint = () => {
    window.print()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Ordonnance ${ordonnance.numero}`} size="lg">
      <div className="space-y-6">
        {/* Actions bar */}
        <div className="flex items-center justify-between no-print bg-slate-900/60 p-3 rounded-xl border border-slate-700/60">
          <div className="flex items-center gap-2">
            {ordonnance.signe ? (
              <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-950/40 border border-emerald-700/50 text-emerald-400">
                <Lock className="w-3.5 h-3.5" /> Signée le{' '}
                {ordonnance.date_signature ? formatDateTimeFr(ordonnance.date_signature) : ''}
              </span>
            ) : (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-950/40 border border-amber-700/50 text-amber-400">
                Non signée (Brouillon médical)
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {!ordonnance.signe && onSigner && (
              <Button
                variant="outline"
                size="sm"
                className="text-xs text-emerald-400 border-emerald-700/60 hover:bg-emerald-950/30"
                onClick={() => onSigner(ordonnance.id)}
              >
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Signer l'ordonnance
              </Button>
            )}
            <Button variant="primary" size="sm" onClick={handlePrint} className="text-xs">
              <Printer className="w-3.5 h-3.5 mr-1.5" /> Imprimer (A4)
            </Button>
          </div>
        </div>

        {/* Printable Sheet */}
        <div
          id="ordonnance-print-area"
          className="bg-white text-slate-900 p-8 rounded-xl shadow-lg border border-slate-200 font-sans print:p-0 print:border-none print:shadow-none min-h-[550px] flex flex-col justify-between"
        >
          <div>
            {/* Header */}
            <div className="border-b-2 border-slate-900 pb-4 mb-6 flex justify-between items-start">
              <div>
                <h2 className="text-xl font-black text-slate-900 tracking-tight">
                  CABINET DENTAIRE SYSDENT PRO
                </h2>
                <p className="text-xs text-slate-600 font-medium">
                  Chirurgie Orale • Parodontologie • Prothèse & Esthétique
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Dakar, Sénégal • Tél: +221 33 800 00 00
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-slate-900">
                  {praticienNom ? `Dr. ${praticienNom}` : 'Dr. Praticien Traitant'}
                </p>
                <p className="text-xs text-slate-600">Chirurgien-Dentiste</p>
                <p className="text-[11px] text-slate-500 font-mono mt-1">
                  N° Ordre: 1042-ONCD-SN
                </p>
              </div>
            </div>

            {/* Patient & Date Meta */}
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 mb-6 flex justify-between items-center text-xs">
              <div>
                <span className="text-slate-500">Patient(e) :</span>{' '}
                <strong className="text-slate-900 text-sm ml-1">
                  {patientNom || 'Patient du cabinet'}
                </strong>
              </div>
              <div>
                <span className="text-slate-500">Fait à Dakar, le :</span>{' '}
                <strong className="text-slate-900">
                  {formatDateFr(ordonnance.date_ordonnance)}
                </strong>
              </div>
            </div>

            {/* Rx Identifier */}
            <div className="flex items-center justify-between mb-4">
              <span className="text-2xl font-serif font-black italic text-slate-800">℞</span>
              <span className="text-[11px] font-mono text-slate-400">
                N° : {ordonnance.numero}
              </span>
            </div>

            {/* Prescriptions List */}
            <div className="space-y-4 mb-6">
              {ordonnance.lignes.map((ligne, idx) => (
                <div key={idx} className="pb-3 border-b border-slate-100 last:border-b-0">
                  <div className="flex items-baseline justify-between">
                    <p className="text-sm font-bold text-slate-900">
                      {idx + 1}. {ligne.nom_commercial || ligne.medicament_texte}{' '}
                      {ligne.dci && (
                        <span className="text-xs font-normal text-slate-600">({ligne.dci})</span>
                      )}
                    </p>
                    <span className="text-xs font-semibold text-slate-700">
                      {ligne.quantite} boîte{ligne.quantite > 1 ? 's' : ''}
                    </span>
                  </div>
                  <p className="text-xs text-slate-800 mt-1 pl-4 font-medium">
                    ↳ Posologie : {ligne.posologie} {ligne.duree ? `pendant ${ligne.duree}` : ''}
                  </p>
                  {ligne.instructions && (
                    <p className="text-[11px] text-slate-500 pl-4 italic mt-0.5">
                      Instructions : {ligne.instructions}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Notes générales */}
            {ordonnance.notes_generales && (
              <div className="p-3 bg-slate-50 border-l-2 border-slate-400 rounded text-xs text-slate-700 mb-6 italic">
                <strong className="not-italic text-slate-900">Recommandations :</strong>{' '}
                {ordonnance.notes_generales}
              </div>
            )}
          </div>

          {/* Footer & Signature */}
          <div className="border-t border-slate-200 pt-4 mt-8 flex justify-between items-end">
            <div className="text-[10px] text-slate-400 max-w-xs">
              Cette ordonnance médicale est nominative et sécurisée sous SysDent Pro conformément
              aux normes de traçabilité médico-dentaire.
            </div>
            <div className="text-center w-52">
              <p className="text-xs text-slate-600 mb-2">Signature & Cachet du Praticien</p>
              {ordonnance.signe ? (
                <div className="border border-emerald-600 rounded p-2 bg-emerald-50 text-emerald-900 font-mono text-[10px]">
                  <p className="font-bold">SIGNÉ ÉLECTRONIQUEMENT</p>
                  <p>{ordonnance.date_signature ? formatDateTimeFr(ordonnance.date_signature) : ''}</p>
                  <p className="text-[9px] text-emerald-700">Certifié SysDent-ID</p>
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
