import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
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
} from 'lucide-react'

export function DevisListPage() {
  const navigate = useNavigate()
  const { addToast } = useToastStore()

  const [devisList, setDevisList] = useState<DevisResponse[]>([])
  const [loading, setLoading] = useState(true)
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
      const res = await facturationApi.listerDevis({
        q: recherche.trim() || undefined,
        statut: statutFiltre || undefined,
        limit: 50,
      })
      setDevisList(res.items)
    } catch {
      // toast géré par l'intercepteur API
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2.5">
            <FileSpreadsheet className="w-6 h-6 text-primary" />
            Devis & Plans de Traitement
          </h1>
          <p className="text-sm text-muted-foreground">
            Émission des devis chiffrés, signature patient et conversion automatique en facture.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/factures">
            <Button variant="outline" className="text-xs border-border">
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
        </div>
      </div>

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
          <div className="p-8 text-center text-sm text-muted-foreground">Chargement des devis...</div>
        ) : devisList.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">Aucun devis trouvé.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-card-foreground">
              <thead className="bg-muted text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                <tr>
                  <th className="px-4 py-3">N° Devis</th>
                  <th className="px-4 py-3">Actes / Prestations</th>
                  <th className="px-4 py-3 text-right">Montant Total</th>
                  <th className="px-4 py-3">Validité</th>
                  <th className="px-4 py-3 text-center">Statut</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {devisList.map((d) => {
                  const estAccepte = d.statut === 'ACCEPTE'
                  const estRefuse = d.statut === 'REFUSE'
                  const estEnvoye = d.statut === 'ENVOYE'
                  const estBrouillon = d.statut === 'BROUILLON'
                  const estConverti = Boolean(d.facture_id)

                  return (
                    <tr key={d.id} className="hover:bg-muted transition-colors">
                      <td className="px-4 py-3 font-mono font-bold text-foreground">{d.numero}</td>
                      <td className="px-4 py-3">
                        <div className="space-y-0.5 max-w-sm">
                          {d.lignes.slice(0, 2).map((l, i) => (
                            <div key={i} className="truncate text-foreground">
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
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-bold text-foreground">
                        {formatFcfa(d.montant_total)}
                      </td>
                      <td className="px-4 py-3 text-card-foreground">
                        {d.date_validite ? formatDateFr(d.date_validite) : 'Indéterminée'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            estAccepte
                              ? 'bg-success/15 border border-success/40 text-success'
                              : estRefuse
                              ? 'bg-danger/15 border border-danger/40 text-danger'
                              : estEnvoye
                              ? 'bg-primary/15 border border-primary/40 text-primary'
                              : 'bg-muted border border-border text-muted-foreground'
                          }`}
                        >
                          {d.statut}
                        </span>
                        {estConverti && (
                          <span className="block text-[9px] text-primary mt-0.5">
                            Facturé ✓
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
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
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
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
