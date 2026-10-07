import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'

/**
 * Environnement de test.
 *
 * Deux pièges, tous deux rencontrés sur ce projet :
 *
 * - `localStorage` et `sessionStorage` **persistent entre les fichiers de test**
 *   dans le même processus. Un jeton laissé par un test donnerait au suivant une
 *   session qui paraît authentifiée. On repart donc d'un stockage vide.
 * - `api.ts` et le store d'authentification gardent des **singletons au niveau
 *   du module** (promesse de renouvellement partagée, gestionnaire de session
 *   morte). `resetModules` entre les tests est la seule façon de les
 *   réinitialiser ; sans lui, le gestionnaire du test précédent continue de
 *   recevoir les 401 du suivant.
 */
beforeEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})