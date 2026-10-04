import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge, type StatusTone } from '@/components/ui/status-badge'
import { useToastStore } from '@/stores/toast-store'
import { formatFcfa, formatDateFr } from '@/lib/format'
import { facturationApi } from '../services/facturation-api'
import type { DevisResponse, StatutDevis } from '../types'
import { DevisModal } from '../components/devis-modal'
import {
  ArrowRight,
  CheckCircle2,
  FileCheck,
  FileSpreadsheet,
  Plus,
  Send,
  XCircle,
  RefreshCw,
  WifiOff,
} from 'lucide-react'

/** Statut devis → badge sémantique. */
function tonStatutDevis(statut: string): StatusTone {
  switch (statut) {
    case 'ACCEPTE':
      return 'success'
    case 'REFUSE':
      return 'danger'
    case 'ENVOYE':
      return 'info'
    default:
      return 'neutral'
  }
}

export function DevisListPage() {
  const navigate = useNavigate()
  const { addToast } = useToastStore()

  const [devisList, setDevisList] = useState<DevisResponse[]>([])
  const [loading, setLoading] = useState(true)
  /** Un chargement échoué ne doit pas s'afficher comme un résultat vide. */
  const [erreurChargement, setErreurChargement] = useState(false)
  const [statutFiltre, setStatutFiltre] = useState('')
  const [recherche, setRecherche] = useState('')

  // Modales
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  // Conversion en facture
  const [convertConfirmId, setConvertConfirmId] = useState<string | null>(null)
  const [converting, setConverting] = useState(false)

  const chargerDevis = async () => {
    try {
      setLoading(true)
      setErreurChargement(false)
      const res = await facturationApi.listerDevis({
        q: recherche.trim() || undefined,
        statut: statutFiltre || undefined,
        limit: 50,
      })
      setDevisList(res.items)
    } catch {
      // toast géré par l'intercepteur API
      setErreurChargement(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerDevis()
  }, [statutFiltre])

  const handleChangerStatut = async (
    devisId: string,
    statut: StatutDevis,
    signaturePatient = false
  ) => {
    try {
      const res = await facturationApi.changerStatutDevis(devisId, {
        statut,
        signature_patient: signaturePatient,
      })
      addToast({
        type: 'success',
        message: `Devis mis à jour : ${res.data.statut}`,
      })
      setDevisList((prev) => prev.map((d) => (d.id === devisId ? res.data : d)))
    } catch {
      // toast géré par l'intercepteur
    }
  }

  const handleConfirmerConversion = async () => {
    if (!convertConfirmId) return
    try {
      setConverting(true)
      const res = await facturationApi.convertirDevis(convertConfirmId)
      addToast({
        type: 'success',
        message: `Devis converti en Facture N° ${res.data.numero} avec succès.`,
      })
      setConvertConfirmId(null)
      navigate(`/factures/${res.data.id}`)
    } catch {
      // toast géré par l'intercepteur
    } finally {
      setConverting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        titre="Devis & Plans de Traitement"
        sousTitre="Émission des devis chiffrés, signature patient et conversion automatique en facture."
        onRefresh={() => void chargerDevis()}
      >
        <Link to="/factures">
          <Button variant="outline" className="text-xs">
            Voir les factures
          </Button>
        </Link>
        <Button
          variant="primary"
          className="flex items-center gap-1.5 text-xs"
          onClick={() => setIsCreateOpen(true)}
        >
          <Plus className="w-4 h-4" /> Nouveau devis
        </Button>
      </PageHeader>

      {/* Filtres */}
      <div className="bg-card p-4 rounded-xl border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex-1 max-w-sm">
          <Input
            placeholder="Rechercher par numéro de devis..."
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
          />
        </div>

        <div className="w-64">
          <Select
            options={STATUT_DEVIS_DE_CHOIX}
            value={statutFiltre}
            onChange={(e) => setStatutFiltre(e.target.value)}
          />
        </div>
      </div>

      {/* Tableau des devis */}
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
            titre="Devis indisponibles"
            description="Ce module n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
          >
            <Button variant="outline" size="sm" onClick={() => void chargerDevis()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          </EmptyState>
        ) : devisList.length === 0 ? (
          <EmptyState
            icon={FileSpreadsheet}
            titre="Aucun devis trouvé"
            description="Créez un devis chiffré depuis une consultation ou émettez-en un nouveau."
          >
            <Button variant="outline" size="sm" onClick={() => setIsCreateOpen(true)}>
              <Plus className="w-4 h-4" /> Nouveau devis
            </Button>
          </EmptyState>
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>N° Devis</TH>
                <TH>Actes / Prestations</TH>
                <TH className="text-right">Montant Total</TH>
                <TH>Validité</TH>
                <TH className="text-center">Statut</TH>
                <TH className="text-right">Actions</TH>
              </TRow>
            </THead>
            <TBody>
              {devisList.map((d) => {
                const estAccepte = d.statut === 'ACCEPTE'
                const estEnvoye = d.statut === 'ENVOYE'
                const estBrouillon = d.statut === 'BROUILLON'
                const estConverti = Boolean(d.facture_id)

                return (
                  <TRow key={d.id}>
                    <TD className="font-mono font-bold text-foreground">{d.numero}</TD>
                    <TD>
                      <div className="space-y-0.5 max-w-sm">
                        {d.lignes.slice(0, 2).map((l, i) => (
                          <div key={i} className="truncate text-foreground text-xs">
                            • {l.designation}{' '}
                            {l.dent_numero && (
                              <span className="text-primary font-mono">(d.{l.dent_numero})</span>
                            )}
                          </div>
                        ))}
                        {d.lignes.length > 2 && (
                          <div className="text-[11px] text-primary">
                            +{d.lignes.length - 2} autre(s) prestation(s)
                          </div>
                        )}
                      </div>
                    </TD>
                    <TD className="text-right font-mono font-bold text-foreground">
                      {formatFcfa(d.montant_total)}
                    </TD>
                    <TD className="text-xs">
                      {d.date_validite ? formatDateFr(d.date_validite) : 'Indéterminée'}
                    </TD>
                    <TD className="text-center">
                      <StatusBadge tone={tonStatutDevis(d.statut)}>{d.statut}</StatusBadge>
                      {estConverti && (
                        <span className="block text-[9px] text-primary mt-0.5">Facturé ✓</span>
                      )}
                    </TD>
                    <TD className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {estBrouillon && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-xs h-7 px-2 text-primary border-primary/40"
                              onClick={() => handleChangerStatut(d.id, 'ENVOYE')}
                            >
                              <Send className="w-3 h-3 mr-1" /> Envoyer
                            </Button>
                          )}

                          {estEnvoye && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-xs h-7 px-2 text-success border-success/40"
                                onClick={() => handleChangerStatut(d.id, 'ACCEPTE', true)}
                              >
                                <CheckCircle2 className="w-3 h-3 mr-1" /> Accepter
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-xs h-7 px-2 text-danger border-danger/40"
                                onClick={() => handleChangerStatut(d.id, 'REFUSE')}
                              >
                                <XCircle className="w-3 h-3 mr-1" /> Refuser
                              </Button>
                            </>
                          )}

                          {estAccepte && !estConverti && (
                            <Button
                              variant="primary"
                              size="sm"
                              className="text-xs h-7 px-2.5 flex items-center gap-1"
                              onClick={() => setConvertConfirmId(d.id)}
                            >
                              <FileCheck className="w-3.5 h-3.5" /> Convertir en facture
                            </Button>
                          )}

                          {estConverti && d.facture_id && (
                            <Link to={`/factures/${d.facture_id}`}>
                              <Button variant="secondary" size="sm" className="text-xs h-7 px-2">
                                Voir facture <ArrowRight className="w-3 h-3 ml-1" />
                              </Button>
                            </Link>
                          )}
                        </div>
                    </TD>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        )}
      </div>

      {/* Modale Nouveau Devis */}
      <DevisModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={() => {
          chargerDevis()
        }}
      />

      {/* Confirmation Conversion Devis en Facture (RG14) */}
      <ConfirmDialog
        isOpen={convertConfirmId !== null}
        onClose={() => setConvertConfirmId(null)}
        onConfirm={handleConfirmerConversion}
        title="Convertir ce devis accepté en facture ?"
        message="Conformément à la règle RG14, toutes les prestations du devis seront importées dans une nouvelle facture officielle, sans aucune ressaisie."
        confirmText={converting ? 'Génération...' : 'Créer la facture'}
        variant="primary"
      />
    </div>
  )
}

const STATUT_DEVIS_DE_CHOIX = [
  { value: '', label: 'Tous les statuts' },
  { value: 'BROUILLON', label: 'Brouillons' },
  { value: 'ENVOYE', label: 'Envoyés' },
  { value: 'ACCEPTE', label: 'Acceptés' },
  { value: 'REFUSE', label: 'Refusés' },
]
