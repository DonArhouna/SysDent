import { AlertCircle, AlertTriangle, Info, HeartPulse, Baby, Flame, ShieldAlert } from 'lucide-react'
import type { AlerteMedicale } from '../types'
import { cn } from '@/lib/utils'

interface AlertesBannerProps {
  alertes?: AlerteMedicale[]
  className?: string
}

export function AlertesBanner({ alertes, className }: AlertesBannerProps) {
  if (!alertes || alertes.length === 0) return null

  // Séparation des alertes par niveau de gravité
  const graves = alertes.filter((a) => a.niveau === 'GRAVE')
  const moderees = alertes.filter((a) => a.niveau === 'MODERE')
  const infos = alertes.filter((a) => a.niveau === 'INFO')

  const getIcone = (code: string) => {
    switch (code) {
      case 'GROSSESSE':
      case 'ALLAITEMENT':
        return Baby
      case 'ALLERGIE':
        return Flame
      case 'DIABETE':
      case 'HTA':
      case 'ANTECEDENT_CARDIAQUE':
        return HeartPulse
      default:
        return AlertCircle
    }
  }

  return (
    <div className={cn('space-y-2', className)} role="region" aria-label="Alertes médicales du patient">
      {/* Alertes graves / bloquantes en rouge vif */}
      {graves.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-xl border border-danger/40 bg-danger/10 p-3 text-danger dark:bg-danger/20 animate-in fade-in duration-200">
          <div className="flex items-center gap-2 font-bold text-xs sm:text-sm uppercase tracking-wider">
            <ShieldAlert className="h-4 w-4 shrink-0 text-danger animate-pulse" />
            <span>Contre-indications majeures & Risques critiques</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {graves.map((alerte, i) => {
              const Icone = getIcone(alerte.code)
              return (
                <div
                  key={i}
                  className="flex items-center gap-1.5 rounded-lg border border-danger/30 bg-card px-2.5 py-1 text-xs font-semibold text-danger shadow-xs"
                >
                  <Icone className="h-3.5 w-3.5 shrink-0" />
                  <span>{alerte.message}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Alertes modérées en ambre */}
      {moderees.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-xl border border-warning/40 bg-warning/10 p-3 text-warning-foreground dark:bg-warning/20">
          <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-warning dark:text-warning">
            <AlertTriangle className="h-4 w-4 shrink-0 text-warning dark:text-warning" />
            <span>Précautions d'anesthésie & Vigilances</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {moderees.map((alerte, i) => {
              const Icone = getIcone(alerte.code)
              return (
                <div
                  key={i}
                  className="flex items-center gap-1.5 rounded-lg border border-warning/30 bg-card px-2.5 py-1 text-xs font-semibold text-foreground shadow-xs"
                >
                  <Icone className="h-3.5 w-3.5 shrink-0 text-warning dark:text-warning" />
                  <span>{alerte.message}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Alertes d'information en bleu */}
      {infos.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {infos.map((alerte, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 dark:bg-primary/15 px-2.5 py-1 text-xs text-primary dark:text-primary"
            >
              <Info className="h-3 w-3 shrink-0 text-primary" />
              <span>{alerte.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
