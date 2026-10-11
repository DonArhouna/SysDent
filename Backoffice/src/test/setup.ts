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
 * - **jsdom n'implémente pas `matchMedia`**, que la bascule de thème du layout
 *   appelle au rendu. Sans le simulacrole ci-dessous, *toute* page rendue dans
 *   `AppShell` echoue sur un `TypeError` - ce qui rendait le layout impossible a
 *   tester, et donc impossible a exiger. On renvoie « sombre » : le test doit
 *   decider de ce qu'il vérifie, pas subir le theme par defaut de la machine.
 */
beforeEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})