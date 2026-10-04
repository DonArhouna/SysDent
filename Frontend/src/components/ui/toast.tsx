import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { useToastStore, type ToastType } from '@/stores/toast-store'
import { cn } from '@/lib/utils'

const ICONES: Record<ToastType, React.ComponentType<{ className?: string }>> = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const STYLES: Record<ToastType, { border: string; bg: string; iconColor: string }> = {
  success: {
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-50 dark:bg-emerald-950/80 text-emerald-900 dark:text-emerald-100',
    iconColor: 'text-emerald-600 dark:text-emerald-400',
  },
  error: {
    border: 'border-rose-500/30',
    bg: 'bg-rose-50 dark:bg-rose-950/80 text-rose-900 dark:text-rose-100',
    iconColor: 'text-rose-600 dark:text-rose-400',
  },
  warning: {
    border: 'border-amber-500/30',
    bg: 'bg-amber-50 dark:bg-amber-950/80 text-amber-900 dark:text-amber-100',
    iconColor: 'text-amber-600 dark:text-amber-400',
  },
  info: {
    border: 'border-blue-500/30',
    bg: 'bg-blue-50 dark:bg-blue-950/80 text-blue-900 dark:text-blue-100',
    iconColor: 'text-blue-600 dark:text-blue-400',
  },
}

export function ToastContainer() {
  const toasts = useToastStore((state) => state.toasts)
  const supprimerToast = useToastStore((state) => state.supprimerToast)

  if (toasts.length === 0) return null

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed top-4 right-4 z-50 flex max-h-screen w-full max-w-sm flex-col gap-2 p-2 sm:max-w-md"
    >
      {toasts.map((t) => {
        const Icone = ICONES[t.type]
        const style = STYLES[t.type]

        return (
          <div
            key={t.id}
            role="alert"
            className={cn(
              'pointer-events-auto flex items-start gap-3 rounded-lg border p-3.5 shadow-lg backdrop-blur transition-all duration-200 animate-in fade-in slide-in-from-top-2',
              style.border,
              style.bg,
            )}
          >
            <Icone className={cn('h-5 w-5 shrink-0 mt-0.5', style.iconColor)} />
            <div className="flex-1 min-w-0">
              {t.titre && <p className="text-sm font-semibold leading-tight mb-0.5">{t.titre}</p>}
              <p className="text-xs sm:text-sm leading-relaxed">{t.message}</p>
            </div>
            <button
              type="button"
              onClick={() => supprimerToast(t.id)}
              className="shrink-0 rounded-md p-1 opacity-70 transition-opacity hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10"
              aria-label="Fermer la notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
