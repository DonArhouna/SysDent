import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastMessage {
  id: string
  titre?: string
  message: string
  type: ToastType
  duree?: number
}

interface ToastState {
  toasts: ToastMessage[]
  ajouterToast: (toast: Omit<ToastMessage, 'id'>) => void
  addToast: (toast: Omit<ToastMessage, 'id'>) => void
  supprimerToast: (id: string) => void
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  ajouterToast: (toast) => {
    const id = Math.random().toString(36).substring(2, 9)
    const nouveau: ToastMessage = { ...toast, id, duree: toast.duree ?? 4000 }

    set((state) => ({
      toasts: [...state.toasts, nouveau],
    }))

    if (nouveau.duree && nouveau.duree > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }))
      }, nouveau.duree)
    }
  },
  addToast: (toast) => get().ajouterToast(toast),
  supprimerToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}))

export const toast = {
  success: (message: string, titre?: string) =>
    useToastStore.getState().ajouterToast({ type: 'success', message, titre }),
  error: (message: string, titre?: string) =>
    useToastStore.getState().ajouterToast({ type: 'error', message, titre, duree: 6000 }),
  warning: (message: string, titre?: string) =>
    useToastStore.getState().ajouterToast({ type: 'warning', message, titre, duree: 5000 }),
  info: (message: string, titre?: string) =>
    useToastStore.getState().ajouterToast({ type: 'info', message, titre }),
}
