import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { useToastStore } from '@/stores/toast-store'
import { ordonnancesApi } from '../services/ordonnances-api'
import type { OrdonnanceResponse } from '../types'
import { OrdonnanceModal } from '../components/ordonnance-modal'
import { OrdonnancePrintView } from '../components/ordonnance-print-view'
import { MedicamentModal } from '../components/medicament-modal'
import { formatDateFr } from '@/lib/format'
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Lock,
  Pill,
  Plus,
  Printer,
  Search,
  RefreshCw,
  WifiOff,
} from 'lucide-react'

export function OrdonnancesListPage() {
  const { addToast } = useToastStore()
  const [ordonnances, setOrdonnances] = useState<OrdonnanceResponse[]>([])
  const [loading, setLoading] = useState(true)
  /** Un chargement échoué ne doit pas s'afficher comme un résultat vide. */
  const [erreurChargement, setErreurChargement] = useState(false)
  const [filtreStatut, setFiltreStatut] = useState<'TOUS' | 'SIGNE' | 'NON_SIGNE'>('TOUS')
  const [recherche, setRecherche] = useState('')

  // Modales
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isMedicamentOpen, setIsMedicamentOpen] = useState(false)
  const [selectedOrdonnance, setSelectedOrdonnance] = useState<OrdonnanceResponse | null>(null)
  const [isPrintOpen, setIsPrintOpen] = useState(false)

  // Confirmation Signature
  const [signConfirmId, setSignConfirmId] = useState<string | null>(null)
  const [signing, setSigning] = useState(false)

  const chargerOrdonnances = async () => {
    try {
      setLoading(true)
      setErreurChargement(false)
      const res = await ordonnancesApi.lister({ limite: 100 })
      setOrdonnances(res.data)
    } catch {
      // toast géré par l'intercepteur API
      setErreurChargement(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerOrdonnances()
  }, [])

  const handleConfirmerSignature = async () => {
    if (!signConfirmId) return
    try {
      setSigning(true)
      const res = await ordonnancesApi.signer(signConfirmId)
      addToast({
        type: 'success',
        message: `Ordonnance ${res.data.numero} signée et verrouillée.`,
      })
      setOrdonnances((prev) =>
        prev.map((o) => (o.id === signConfirmId ? res.data : o))
      )
      if (selectedOrdonnance?.id === signConfirmId) {
        setSelectedOrdonnance(res.data)
      }
    } catch {
      // toast géré par l'intercepteur
    } finally {
      setSigning(false)
      setSignConfirmId(null)
    }
  }

  const ordonnancesFiltrees = ordonnances.filter((o) => {
    if (filtreStatut === 'SIGNE' && !o.signe) return false
    if (filtreStatut === 'NON_SIGNE' && o.signe) return false
    if (recherche) {
      const q = recherche.toLowerCase()
      const matchNum = o.numero.toLowerCase().includes(q)
      const matchLignes = o.lignes.some(
        (l) =>
          l.medicament_texte?.toLowerCase().includes(q) ||
          l.nom_commercial?.toLowerCase().includes(q) ||
          l.dci?.toLowerCase().includes(q)
      )
      if (!matchNum && !matchLignes) return false
    }
    return true
  })

  return (
    <div className="space-y-6">
      {/* En-tête de la page */}
      <PageHeader
        titre="Ordonnances & Prescriptions"
        sousTitre="Gestion des ordonnances médicales, contrôle des contre-indications et référentiel."
        onRefresh={() => void chargerOrdonnances()}
      >
        <Button
          variant="outline"
          className="flex items-center gap-1.5 text-xs"
          onClick={() => setIsMedicamentOpen(true)}
        >
          <Pill className="w-4 h-4 text-primary" /> Référentiel Médicaments
        </Button>
        <Button
          variant="primary"
          className="flex items-center gap-1.5 text-xs"
          onClick={() => setIsCreateOpen(true)}
        >
          <Plus className="w-4 h-4" /> Nouvelle ordonnance
        </Button>
      </PageHeader>

      {/* Barre de filtres et recherche */}
      <div className="bg-card p-4 rounded-xl border border-border flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
          <Input
            placeholder="Rechercher par numéro ou médicament..."
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            className="pl-9"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Statut :</span>
          <div className="flex rounded-lg bg-muted p-1 border border-border">
            <button
              onClick={() => setFiltreStatut('TOUS')}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                filtreStatut === 'TOUS'
                  ? 'bg-primary text-white'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Toutes ({ordonnances.length})
            </button>
            <button
              onClick={() => setFiltreStatut('SIGNE')}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                filtreStatut === 'SIGNE'
                  ? 'bg-primary text-white'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Signées ({ordonnances.filter((o) => o.signe).length})
            </button>
            <button
              onClick={() => setFiltreStatut('NON_SIGNE')}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                filtreStatut === 'NON_SIGNE'
                  ? 'bg-primary text-white'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Brouillons ({ordonnances.filter((o) => !o.signe).length})
            </button>
          </div>
        </div>
      </div>

      {/* Tableau des ordonnances */}
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
            titre="Les ordonnances indisponibles"
            description="Ce module n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
          >
            <Button variant="outline" size="sm" onClick={() => void chargerOrdonnances()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          </EmptyState>
        ) : ordonnancesFiltrees.length === 0 ? (
          <EmptyState
            icon={FileText}
            titre="Aucune ordonnance trouvée"
            description="Aucune ordonnance ne correspond à ces critères."
          />
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH>Numéro</TH>
                <TH>Date</TH>
                <TH>Médicaments prescrits</TH>
                <TH>Statut</TH>
                <TH className="text-right">Actions</TH>
              </TRow>
            </THead>
            <TBody>
              {ordonnancesFiltrees.map((ord) => (
                <TRow key={ord.id}>
                  <TD className="font-mono font-bold text-foreground text-xs">{ord.numero}</TD>
                  <TD className="text-xs">{formatDateFr(ord.date_ordonnance)}</TD>
                  <TD>
                    <div className="space-y-0.5 max-w-md">
                      {ord.lignes.slice(0, 2).map((l, i) => (
                        <div key={i} className="truncate text-foreground text-xs">
                          • {l.nom_commercial || l.medicament_texte}{' '}
                          <span className="text-muted-foreground text-[11px]">({l.posologie})</span>
                        </div>
                      ))}
                      {ord.lignes.length > 2 && (
                        <div className="text-[11px] text-primary">
                          +{ord.lignes.length - 2} autre(s) médicament(s)
                        </div>
                      )}
                    </div>
                  </TD>
                  <TD>
                    {ord.signe ? (
                      <StatusBadge tone="success">
                        <Lock className="w-3 h-3" /> Signée
                      </StatusBadge>
                    ) : (
                      <StatusBadge tone="warning">
                        <AlertTriangle className="w-3 h-3" /> En attente de signature
                      </StatusBadge>
                    )}
                  </TD>
                  <TD className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {!ord.signe && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs text-success border-success/40 hover:bg-success/15 h-8"
                          onClick={() => setSignConfirmId(ord.id)}
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Signer
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        className="text-xs h-8 flex items-center gap-1"
                        onClick={() => {
                          setSelectedOrdonnance(ord)
                          setIsPrintOpen(true)
                        }}
                      >
                        <Printer className="w-3.5 h-3.5" /> Voir / Imprimer
                      </Button>
                    </div>
                  </TD>
                </TRow>
              ))}
            </TBody>
          </Table>
        )}
      </div>

      {/* Modale de création */}
      <OrdonnanceModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={(nouvelle) => {
          setOrdonnances((prev) => [nouvelle, ...prev])
          setSelectedOrdonnance(nouvelle)
          setIsPrintOpen(true)
        }}
      />

      {/* Modale Référentiel Médicaments */}
      <MedicamentModal
        isOpen={isMedicamentOpen}
        onClose={() => setIsMedicamentOpen(false)}
        onSuccess={() => {
          addToast({ type: 'info', message: 'Référentiel mis à jour.' })
        }}
      />

      {/* Modale d'impression A4 */}
      <OrdonnancePrintView
        isOpen={isPrintOpen}
        onClose={() => {
          setIsPrintOpen(false)
          setSelectedOrdonnance(null)
        }}
        ordonnance={selectedOrdonnance}
        onSigner={(id) => {
          setSignConfirmId(id)
        }}
      />

      {/* Confirmation de signature */}
      <ConfirmDialog
        isOpen={signConfirmId !== null}
        onClose={() => setSignConfirmId(null)}
        onConfirm={handleConfirmerSignature}
        title="Signer électroniquement cette ordonnance ?"
        message="Attention : Une ordonnance médicale signée devient définitive et ne peut plus être modifiée ou supprimée conformément aux exigences médicolégales."
        confirmText={signing ? 'Signature...' : 'Confirmer et signer'}
        variant="warning"
      />
    </div>
  )
}
