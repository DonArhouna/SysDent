import { type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Modal } from './modal'
import { Button } from './button'

export interface ConfirmDialogProps {
  open?: boolean
  isOpen?: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  title: ReactNode
  message: ReactNode
  children?: ReactNode
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'primary'
  loading?: boolean
}

export function ConfirmDialog({
  open,
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  children,
  confirmText = 'Confirmer',
  cancelText = 'Annuler',
  variant = 'danger',
  loading = false,
}: ConfirmDialogProps) {
  const isDialogOpen = open ?? isOpen ?? false

  return (
    <Modal open={isDialogOpen} onClose={onClose} maxWidth="sm">
      <div className="flex flex-col items-center text-center p-2">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-danger/10 text-danger">
          <AlertTriangle className="h-7 w-7" />
        </div>
        <h4 className="text-lg font-bold text-foreground">{title}</h4>
        <div className="mt-2 text-sm text-muted-foreground leading-relaxed">{message}</div>
        {children && <div className="mt-3 w-full text-left">{children}</div>}

        <div className="mt-6 flex w-full gap-3 justify-center">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={loading}
            className="flex-1"
          >
            {cancelText}
          </Button>
          <Button
            type="button"
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={() => void onConfirm()}
            disabled={loading}
            className="flex-1"
          >
            {loading ? 'Traitement…' : confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
