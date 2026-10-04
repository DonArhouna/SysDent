import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { formatDateTimeFr } from '@/lib/format'
import { auditApi } from '../services/audit-api'
import type { AuditLog } from '../types'
import { ChevronDown, ChevronRight, ShieldAlert, User } from 'lucide-react'

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
      const res = await auditApi.lister({
        resource_type: resourceType || undefined,
        resource_id: resourceId.trim() || undefined,
        page,
        limit: 25,
      })
      setLogs(res.items)
      setTotalRecords(res.meta.total_records)
    } catch {
      //
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
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2.5">
          <ShieldAlert className="w-6 h-6 text-primary" />
          Journal d'Audit & Traçabilité Médico-Légale
        </h1>
        <p className="text-sm text-muted-foreground">
          Enregistrement inviolable de toutes les actions cliniques et administratives du cabinet.
        </p>
      </div>

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
          <div className="p-8 text-center text-sm text-muted-foreground">
            Chargement des traces d'audit...
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            Aucun événement d'audit enregistré pour ces filtres.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-card-foreground">
              <thead className="bg-muted text-muted-foreground uppercase tracking-wider font-semibold border-b border-border">
                <tr>
                  <th className="px-4 py-3 w-8"></th>
                  <th className="px-4 py-3">Horodatage</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Ressource</th>
                  <th className="px-4 py-3">Utilisateur</th>
                  <th className="px-4 py-3">Adresse IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono">
                {logs.map((log) => {
                  const isExpanded = expandedLogId === log.id
                  const aChanges = log.changes && Object.keys(log.changes).length > 0

                  return (
                    <tr key={log.id} className="hover:bg-muted transition-colors">
                      <td className="px-4 py-3 text-center">
                        {aChanges && (
                          <button
                            type="button"
                            onClick={() => toggleExpand(log.id)}
                            className="text-muted-foreground hover:text-primary"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-3 text-card-foreground font-sans">
                        {formatDateTimeFr(log.timestamp)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded font-bold text-[10px] bg-muted text-primary border border-border">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-foreground font-semibold">{log.resource_type}</span>{' '}
                        <span className="text-muted-foreground text-[10px]">
                          ({log.resource_id.slice(0, 8)}...)
                        </span>
                      </td>
                      <td className="px-4 py-3 font-sans text-card-foreground">
                        {log.user_email ? (
                          <span className="flex items-center gap-1.5">
                            <User className="w-3.5 h-3.5 text-muted-foreground" />
                            {log.user_email}
                          </span>
                        ) : (
                          <span className="text-muted-foreground italic">Système</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-[11px]">
                        {log.ip_address || '-'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
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
