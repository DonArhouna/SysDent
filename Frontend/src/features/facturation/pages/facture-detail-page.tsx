import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { useToastStore } from '@/stores/toast-store'
import { facturationApi } from '../services/facturation-api'
import { tonStatutFacture } from './factures-list-page'
import { formatFcfa, formatDateFr, formatDateTimeFr } from '@/lib/format'
import type {
  FactureResponse,
  PlanEchelonnementResponse,
} from '../types'
import { PaiementModal } from '../components/paiement-modal'
import { EchelonnementModal } from '../components/echelonnement-modal'
import { FacturePrintModal } from '../components/facture-print-modal'
import {
  ArrowLeft,
  Ban,
  Calendar,
  CreditCard,
  Layers,
  Printer,
  RefreshCw,
  WifiOff,
} from 'lucide-react'

export function FactureDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { addToast } = useToastStore()

  const [facture, setFacture] = useState<FactureResponse | null>(null)
  const [echelonnement, setEchelonnement] = useState<PlanEchelonnementResponse | null>(null)
  const [loading, setLoading] = useState(true)
  /** Distingue « facture absente » d'un échec de chargement réseau. */
  const [erreurChargement, setErreurChargement] = useState(false)

  // Modales
  const [isPaiementOpen, setIsPaiementOpen] = useState(false)
  const [selectedEcheanceId, setSelectedEcheanceId] = useState<string | null>(null)
  const [selectedMontantEcheance, setSelectedMontantEcheance] = useState<number | null>(null)
  const [isEchelonnementOpen, setIsEchelonnementOpen] = useState(false)
  const [isPrintOpen, setIsPrintOpen] = useState(false)

  // Annulation
  const [isAnnulerOpen, setIsAnnulerOpen] = useState(false)
  const [motifAnnulation, setMotifAnnulation] = useState('')
  const [annulant, setAnnulant] = useState(false)

  const chargerDetails = async () => {
    if (!id) return
    try {
      setLoading(true)
      setErreurChargement(false)
      const [resFacture, resEchelonnement] = await Promise.all([
        facturationApi.obtenirFacture(id),
        facturationApi.obtenirEchelonnement(id),
      ])
      setFacture(resFacture.data)
      setEchelonnement(resEchelonnement.data ?? null)
    } catch {
      // toast géré par l'intercepteur API
      setErreurChargement(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerDetails()
  }, [id])

  const handleConfirmerAnnulation = async () => {
    if (!facture || !motifAnnulation.trim()) {
      addToast({ type: 'warning', message: "Le motif d'annulation est obligatoire." })
      return
    }
    try {
      setAnnulant(true)
      const res = await facturationApi.annulerFacture(facture.id, motifAnnulation.trim())
      addToast({ type: 'success', message: `Facture ${res.data.numero} annulée.` })
      setFacture(res.data)
      setIsAnnulerOpen(false)
    } catch {
      // toast géré par l'intercepteur
    } finally {
      setAnnulant(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-24 w-full rounded-xl2" />
        <Skeleton className="h-64 w-full rounded-xl2" />
      </div>
    )
  }

  if (!facture) {
    return (
      <EmptyState
        icon={erreurChargement ? WifiOff : CreditCard}
        titre={erreurChargement ? 'Facture indisponible' : 'Facture introuvable'}
        description={
          erreurChargement
            ? "La facture n'a pas pu être chargée. Vérifiez que le backend est démarré puis réessayez."
            : "La facture demandée n'existe pas ou a été supprimée."
        }
      >
        {erreurChargement ? (
          <Button variant="outline" size="sm" onClick={() => void chargerDetails()}>
            <RefreshCw className="h-4 w-4 mr-1.5" /> Réessayer
          </Button>
        ) : (
          <Link to="/factures">
            <Button variant="outline" size="sm">
              <ArrowLeft className="w-4 h-4 mr-1.5" /> Retour aux factures
            </Button>
          </Link>
        )}
      </EmptyState>
    )
  }

  const estPayee = facture.statut === 'PAYEE'
  const estAnnulee = facture.statut === 'ANNULEE'
  const sansPaiement = facture.paiements.length === 0

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <PageHeader
        titre={
          <span className="flex flex-wrap items-center gap-2.5 font-mono">
            {facture.numero}
            <StatusBadge tone={tonStatutFacture(facture.statut)} className="font-sans">
              {facture.statut}
            </StatusBadge>
          </span>
        }
        sousTitre={
          <>
            Émise le {formatDateFr(facture.date_emission)} • Patient :{' '}
            <Link
              to={`/patients/${facture.patient_id}`}
              className="text-primary hover:underline"
            >
              Voir dossier patient
            </Link>
          </>
        }
        retour={{ to: '/factures', label: 'Retour aux factures' }}
      >
        <>

          {!estPayee && !estAnnulee && (
            <Button
              variant="primary"
              size="sm"
              className="flex items-center gap-1.5 text-xs"
              onClick={() => {
                setSelectedEcheanceId(null)
                setSelectedMontantEcheance(null)
                setIsPaiementOpen(true)
              }}
            >
              <CreditCard className="w-4 h-4" /> Encaisser un règlement
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            className="flex items-center gap-1.5 text-xs"
            onClick={() => setIsPrintOpen(true)}
          >
            <Printer className="w-4 h-4" /> Imprimer la facture
          </Button>

          {!estAnnulee && sansPaiement && (
            <Button
              variant="danger"
              size="sm"
              className="flex items-center gap-1 text-xs"
              onClick={() => setIsAnnulerOpen(true)}
            >
              <Ban className="w-3.5 h-3.5" /> Annuler
            </Button>
          )}
        </>
      </PageHeader>

      {/* Synthèse financière */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-card p-4 rounded-xl border border-border text-center">
          <span className="text-xs text-muted-foreground block">Montant Total des Actes</span>
          <span className="text-xl font-bold font-mono text-foreground">
            {formatFcfa(facture.montant_total)}
          </span>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border text-center">
          <span className="text-xs text-muted-foreground block">TVA Appliquée</span>
          <span className="text-xl font-bold font-mono text-card-foreground">
            {formatFcfa(facture.montant_tva)}
          </span>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border text-center">
          <span className="text-xs text-muted-foreground block">Montant Encaissé</span>
          <span className="text-xl font-bold font-mono text-success">
            {formatFcfa(facture.montant_paye)}
          </span>
        </div>
        <div className="bg-card p-4 rounded-xl border border-border text-center">
          <span className="text-xs text-muted-foreground block">Solde Restant Dû</span>
          <span className="text-xl font-bold font-mono text-primary">
            {formatFcfa(facture.montant_restant)}
          </span>
        </div>
      </div>

      {/* Lignes de la facture */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">
          Prestations & Actes facturés ({facture.lignes.length})
        </h3>
        <div className="overflow-x-auto border border-border rounded-lg">
          <table className="w-full text-left text-xs text-card-foreground">
            <thead className="bg-muted text-muted-foreground uppercase text-[10px] border-b border-border">
              <tr>
                <th className="px-4 py-2.5">Désignation</th>
                <th className="px-4 py-2.5 text-center">Quantité</th>
                <th className="px-4 py-2.5 text-right">Prix unitaire</th>
                <th className="px-4 py-2.5 text-right">Total HT</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {facture.lignes.map((l) => (
                <tr key={l.id} className="hover:bg-muted">
                  <td className="px-4 py-3 font-medium text-foreground">{l.designation}</td>
                  <td className="px-4 py-3 text-center text-muted-foreground">{l.quantite}</td>
                  <td className="px-4 py-3 text-right font-mono text-muted-foreground">
                    {formatFcfa(l.prix_unitaire)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-foreground">
                    {formatFcfa(l.montant)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section Échelonnement (RG08) */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary" />
            <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">
              Plan d'échelonnement (Versements échelonnés)
            </h3>
          </div>
          {!echelonnement && !estPayee && !estAnnulee && (
            <Button
              variant="outline"
              size="sm"
              className="text-xs"
              onClick={() => setIsEchelonnementOpen(true)}
            >
              Créer un plan d'échelonnement
            </Button>
          )}
        </div>

        {echelonnement ? (
          <div className="space-y-4">
            <div className="p-3 bg-muted rounded-lg border border-border text-xs flex justify-between items-center text-card-foreground">
              <span>
                Plan actif : <strong>{echelonnement.nombre_echeances} échéances</strong> ({echelonnement.frequence})
              </span>
              <span>
                Début : <strong>{formatDateFr(echelonnement.date_debut)}</strong>
              </span>
              <span>
                Montant échelonné : <strong>{formatFcfa(echelonnement.montant_total)}</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {echelonnement.echeances.map((ech) => {
                const echPayee = ech.statut === 'PAYEE'
                return (
                  <div
                    key={ech.id}
                    className={`p-3.5 rounded-xl border flex flex-col justify-between ${
                      echPayee
                        ? 'bg-success/15 border-success/40 text-success'
                        : 'bg-muted border-border text-foreground'
                    }`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-bold text-xs">Échéance #{ech.numero}</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                          echPayee
                            ? 'bg-success/15 text-success border border-success/40'
                            : 'bg-muted text-card-foreground'
                        }`}
                      >
                        {ech.statut}
                      </span>
                    </div>

                    <div className="text-sm font-mono font-bold mb-1">
                      {formatFcfa(ech.montant_prevu)}
                    </div>

                    <div className="text-[11px] text-muted-foreground flex items-center gap-1 mb-3">
                      <Calendar className="w-3.5 h-3.5" />
                      Prévue le {formatDateFr(ech.date_prevue)}
                    </div>

                    {!echPayee && !estAnnulee && (
                      <Button
                        variant="primary"
                        size="sm"
                        className="w-full text-xs h-8"
                        onClick={() => {
                          setSelectedEcheanceId(ech.id)
                          setSelectedMontantEcheance(Number(ech.montant_prevu))
                          setIsPaiementOpen(true)
                        }}
                      >
                        Encaisser cette échéance
                      </Button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">
            Aucun plan d'échelonnement actif sur cette facture.
          </p>
        )}
      </div>

      {/* Historique des paiements & reçus */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">
          Historique des encaissements & reçus ({facture.paiements.length})
        </h3>

        {facture.paiements.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">Aucun versement enregistré à ce jour.</p>
        ) : (
          <div className="overflow-x-auto border border-border rounded-lg">
            <table className="w-full text-left text-xs text-card-foreground">
              <thead className="bg-muted text-muted-foreground uppercase text-[10px] border-b border-border">
                <tr>
                  <th className="px-4 py-2.5">Reçu N°</th>
                  <th className="px-4 py-2.5">Date & Heure</th>
                  <th className="px-4 py-2.5">Mode</th>
                  <th className="px-4 py-2.5">Référence</th>
                  <th className="px-4 py-2.5 text-right">Montant</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {facture.paiements.map((p) => (
                  <tr key={p.id} className="hover:bg-muted">
                    <td className="px-4 py-3 font-mono font-bold text-primary">
                      {p.recu_numero}
                    </td>
                    <td className="px-4 py-3 text-card-foreground">
                      {formatDateTimeFr(p.date_paiement)}
                    </td>
                    <td className="px-4 py-3 uppercase text-[11px] font-semibold text-foreground">
                      {p.mode}
                    </td>
                    <td className="px-4 py-3 font-mono text-muted-foreground text-[11px]">
                      {p.reference || '-'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-success">
                      {formatFcfa(p.montant)}
                    </td>
                  </tr>
                ))}
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
          setSelectedEcheanceId(null)
          setSelectedMontantEcheance(null)
        }}
        facture={facture}
        echeanceId={selectedEcheanceId}
        montantPrevuEcheance={selectedMontantEcheance}
        onSuccess={() => {
          chargerDetails()
        }}
      />

      {/* Modale Échelonnement */}
      <EchelonnementModal
        isOpen={isEchelonnementOpen}
        onClose={() => setIsEchelonnementOpen(false)}
        facture={facture}
        onSuccess={() => {
          chargerDetails()
        }}
      />

      {/* Modale Impression */}
      <FacturePrintModal
        isOpen={isPrintOpen}
        onClose={() => setIsPrintOpen(false)}
        facture={facture}
      />

      {/* Confirmation Annulation */}
      <ConfirmDialog
        isOpen={isAnnulerOpen}
        onClose={() => setIsAnnulerOpen(false)}
        onConfirm={handleConfirmerAnnulation}
        title={`Annuler la facture ${facture.numero} ?`}
        message="Cette action est irréversible. L'annulation sera tracée dans le journal d'audit légal."
        confirmText={annulant ? 'Annulation...' : 'Confirmer l’annulation'}
        variant="danger"
      >
        <div className="mt-3">
          <label className="text-xs font-semibold text-card-foreground block mb-1">
            Motif d'annulation obligatoire :
          </label>
          <input
            type="text"
            className="w-full h-9 px-3 rounded-lg border border-border bg-card text-xs text-foreground"
            placeholder="Ex: Erreur de saisie des actes..."
            value={motifAnnulation}
            onChange={(e) => setMotifAnnulation(e.target.value)}
          />
        </div>
      </ConfirmDialog>
    </div>
  )
}
