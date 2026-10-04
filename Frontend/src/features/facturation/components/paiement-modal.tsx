import { useState } from 'react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { useToastStore } from '@/stores/toast-store'
import { facturationApi } from '../services/facturation-api'
import { formatFcfa } from '@/lib/format'
import type { FactureResponse, ModePaiement, PaiementResponse } from '../types'

interface PaiementModalProps {
  isOpen: boolean
  onClose: () => void
  facture: FactureResponse | null
  echeanceId?: string | null
  montantPrevuEcheance?: number | null
  onSuccess: (paiement: PaiementResponse) => void
}

const MODES_PAIEMENT = [
  { value: 'ESPECES', label: 'Espèces (Caisse)' },
  { value: 'MOBILE_MONEY', label: 'Mobile Money (Wave / Orange Money)' },
  { value: 'CARTE_BANCAIRE', label: 'Carte Bancaire (TPE)' },
  { value: 'CHEQUE', label: 'Chèque bancaire' },
  { value: 'VIREMENT', label: 'Virement bancaire' },
  { value: 'ASSURANCE', label: 'Tiers-Payant / Assurance' },
]

export function PaiementModal({
  isOpen,
  onClose,
  facture,
  echeanceId,
  montantPrevuEcheance,
  onSuccess,
}: PaiementModalProps) {
  const { addToast } = useToastStore()
  const [submitting, setSubmitting] = useState(false)

  const resteAPayer = Number(facture?.montant_restant || 0)
  const [montant, setMontant] = useState<string>(
    montantPrevuEcheance ? String(montantPrevuEcheance) : String(resteAPayer)
  )
  const [mode, setMode] = useState<ModePaiement>('MOBILE_MONEY')
  const [reference, setReference] = useState('')

  if (!facture) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const montantNum = parseFloat(montant)
    if (isNaN(montantNum) || montantNum <= 0) {
      addToast({ type: 'warning', message: 'Veuillez saisir un montant valide.' })
      return
    }

    if (!echeanceId && montantNum > resteAPayer) {
      addToast({
        type: 'error',
        message: `Le montant (${formatFcfa(montantNum)}) dépasse le reste à payer (${formatFcfa(resteAPayer)}).`,
      })
      return
    }

    try {
      setSubmitting(true)
      const res = await facturationApi.encaisser(facture.id, {
        montant: montantNum,
        mode,
        reference: reference.trim() || undefined,
        echeance_id: echeanceId || undefined,
      })
      addToast({
        type: 'success',
        message: `Paiement enregistré ! Reçu N° ${res.data.recu_numero}`,
      })
      onSuccess(res.data)
      onClose()
    } catch {
      // toast géré par l'intercepteur API
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Encaisser un paiement - Facture ${facture.numero}`}
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Synthèse montants */}
        <div className="p-4 rounded-xl bg-card border border-border grid grid-cols-3 gap-2 text-center">
          <div>
            <span className="text-[11px] text-muted-foreground block">Total Facture</span>
            <span className="text-xs font-bold text-foreground">
              {formatFcfa(facture.montant_total)}
            </span>
          </div>
          <div>
            <span className="text-[11px] text-muted-foreground block">Déjà Payé</span>
            <span className="text-xs font-bold text-success">
              {formatFcfa(facture.montant_paye)}
            </span>
          </div>
          <div>
            <span className="text-[11px] text-muted-foreground block">Reste Dû</span>
            <span className="text-xs font-bold text-primary">
              {formatFcfa(facture.montant_restant)}
            </span>
          </div>
        </div>

        {echeanceId && (
          <div className="p-2.5 rounded-lg bg-accent-purple/15 border border-accent-purple/40 text-xs text-accent-purple">
            Paiement d'une échéance planifiée : montant exigé ={' '}
            <strong>{formatFcfa(montantPrevuEcheance || 0)}</strong>
          </div>
        )}

        <div className="space-y-4">
          <Input
            label="Montant à encaisser (FCFA) *"
            type="number"
            step="1"
            min="1"
            max={echeanceId ? montantPrevuEcheance || undefined : resteAPayer}
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
            disabled={Boolean(echeanceId)}
            required
            helperText={
              !echeanceId
                ? `Possibilité de paiement partiel (Max: ${formatFcfa(resteAPayer)})`
                : undefined
            }
          />

          <Select
            label="Mode de règlement *"
            options={MODES_PAIEMENT}
            value={mode}
            onChange={(e) => setMode(e.target.value as ModePaiement)}
          />

          <Input
            label={
              mode === 'MOBILE_MONEY'
                ? 'ID de transaction (Wave / Orange Money)'
                : mode === 'CHEQUE'
                ? 'Numéro de chèque & Banque'
                : 'Référence / Reçu externe (optionnel)'
            }
            placeholder={
              mode === 'MOBILE_MONEY'
                ? 'Ex: WAV-98234-SN'
                : mode === 'CHEQUE'
                ? 'Ex: CHQ 872394 CBAO'
                : 'Référence'
            }
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            required={mode === 'MOBILE_MONEY' || mode === 'CHEQUE'}
          />
        </div>

        {/* Moyens rapides */}
        {!echeanceId && resteAPayer > 0 && (
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="text-xs flex-1"
              onClick={() => setMontant(String(resteAPayer))}
            >
              Solde total ({formatFcfa(resteAPayer)})
            </Button>
            {resteAPayer >= 20000 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="text-xs flex-1"
                onClick={() => setMontant(String(Math.round(resteAPayer / 2)))}
              >
                Acompte 50% ({formatFcfa(Math.round(resteAPayer / 2))})
              </Button>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-3 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Validation...' : 'Valider le paiement & Émettre reçu'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
