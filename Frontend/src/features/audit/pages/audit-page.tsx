import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { formatDateTimeFr } from '@/lib/format'
import { auditApi } from '../services/audit-api'
import type { AuditLog } from '../types'
import {
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  User,
  RefreshCw,
  WifiOff,
} from 'lucide-react'

const RESOURCE_TYPES = [
  { value: '', label: 'Toutes les ressources' },
  { value: 'Patient', label: 'Dossiers Patients' },
  { value: 'Consultation', label: 'Consultations' },
  { value: 'Ordonnance', label: 'Ordonnances' },
  { value: 'Medicament', label: 'Référentiel Médicaments' },
  { value: 'Facture', label: 'Factures & Règlements' },
  { value: 'Devis', label: 'Devis' },
  { value: 'RendezVous', label: 'Rendez-vous' },
  { value: 'Utilisateur', label: 'Comptes Utilisateurs' },
]

export function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  /** Un chargement échoué ne doit pas s'afficher comme un résultat vide. */
  const [erreurChargement, setErreurChargement] = useState(false)
  const [, setTotalRecords] = useState(0)

  // Filtres
  const [resourceType, setResourceType] = useState('')
  const [resourceId, setResourceId] = useState('')
  const [page, setPage] = useState(1)

  // Détail déployé
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null)

  const chargerLogs = async () => {
    try {
      setLoading(true)
      setErreurChargement(false)
      const res = await auditApi.lister({
        resource_type: resourceType || undefined,
        resource_id: resourceId.trim() || undefined,
        page,
        limit: 25,
      })
      setLogs(res.items)
      setTotalRecords(res.meta.total_records)
    } catch {
      // Erreur déjà signalée par le toast global de l'API client.
      setErreurChargement(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    chargerLogs()
  }, [resourceType, page])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    chargerLogs()
  }

  const toggleExpand = (id: string) => {
    setExpandedLogId(expandedLogId === id ? null : id)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        titre="Journal d'Audit & Traçabilité Médico-Légale"
        sousTitre="Enregistrement inviolable de toutes les actions cliniques et administratives du cabinet."
        onRefresh={() => void chargerLogs()}
      />

      {/* Filtres */}
      <form
        onSubmit={handleSearchSubmit}
        className="bg-card p-4 rounded-xl border border-border grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
      >
        <div className="md:col-span-5">
          <Select
            label="Type d'entité tracée"
            options={RESOURCE_TYPES}
            value={resourceType}
            onChange={(e) => {
              setResourceType(e.target.value)
              setPage(1)
            }}
          />
        </div>

        <div className="md:col-span-5">
          <Input
            label="ID de la ressource (UUID)"
            placeholder="Ex: 8b730f0c-..."
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
          />
        </div>

        <div className="md:col-span-2">
          <Button type="submit" variant="primary" className="w-full h-10 text-xs">
            Filtrer
          </Button>
        </div>
      </form>

      {/* Table Audit */}
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
            titre="Le journal d'audit indisponibles"
            description="Ce module n'a pas pu être chargé. Vérifiez que le backend est démarré puis réessayez."
          >
            <Button variant="outline" size="sm" onClick={() => void chargerLogs()}>
              <RefreshCw className="h-4 w-4" /> Réessayer
            </Button>
          </EmptyState>
        ) : logs.length === 0 ? (
          <EmptyState
            icon={ShieldAlert}
            titre="Aucun événement d'audit"
            description="Aucun événement d'audit enregistré pour ces filtres."
          />
        ) : (
          <Table>
            <THead>
              <TRow>
                <TH className="w-8"></TH>
                <TH>Horodatage</TH>
                <TH>Action</TH>
                <TH>Ressource</TH>
                <TH>Utilisateur</TH>
                <TH>Adresse IP</TH>
              </TRow>
            </THead>
            <TBody className="font-mono">
              {logs.map((log) => {
                const isExpanded = expandedLogId === log.id
                const aChanges = log.changes && Object.keys(log.changes).length > 0

                return (
                  <TRow key={log.id}>
                    <TD className="text-center">
                      {aChanges && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(log.id)}
                          aria-label={isExpanded ? 'Replier le détail' : 'Déployer le détail'}
                          className="text-muted-foreground hover:text-primary"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                      )}
                    </TD>
                    <TD className="font-sans">
                      {formatDateTimeFr(log.timestamp)}
                    </TD>
                    <TD>
                      <StatusBadge tone="info" className="font-mono uppercase">
                        {log.action}
                      </StatusBadge>
                    </TD>
                    <TD>
                      <span className="text-foreground font-semibold">{log.resource_type}</span>{' '}
                      <span className="text-muted-foreground text-[10px]">
                        ({log.resource_id.slice(0, 8)}...)
                      </span>
                    </TD>
                    <TD className="font-sans">
                      {log.user_email ? (
                        <span className="flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-muted-foreground" />
                          {log.user_email}
                        </span>
                      ) : (
                        <span className="text-muted-foreground italic">Système</span>
                      )}
                    </TD>
                    <TD className="text-muted-foreground text-[11px]">
                      {log.ip_address || '-'}
                    </TD>
                  </TRow>
                )
              })}
            </TBody>
          </Table>
        )}

        {/* Détail JSON si déployé */}
        {expandedLogId && (
          <div className="p-4 bg-background border-t border-border text-xs">
            <span className="text-muted-foreground font-semibold block mb-2">
              Modifications de données enregistrées (Audit Diff) :
            </span>
            <pre className="p-3 bg-card rounded-lg text-success font-mono text-[11px] overflow-x-auto border border-border">
              {JSON.stringify(
                logs.find((l) => l.id === expandedLogId)?.changes || {},
                null,
                2
              )}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
