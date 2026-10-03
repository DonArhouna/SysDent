import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

/**
 * Thème clair/sombre.
 *
 * Implémentation maison (une centaine de lignes) plutôt qu'une dépendance :
 * la bascule pose/retire la classe `dark` sur `<html>`, ce qui est exactement
 * ce que Tailwind `darkMode: 'class'` attend. La préférence est persistée et
 * le script anti-FOUC de `index.html` lit la même clé avant le premier rendu.
 */
type Theme = 'light' | 'dark'
const CLE = 'sysdent-theme'

const ThemeContext = createContext<{
  theme: Theme
  setTheme: (theme: Theme) => void
  toggle: () => void
}>({ theme: 'dark', setTheme: () => undefined, toggle: () => undefined })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setEtat] = useState<Theme>(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
      ? 'dark'
      : 'light',
  )

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  const setTheme = useCallback((prochain: Theme) => {
    setEtat(prochain)
    try {
      localStorage.setItem(CLE, prochain)
    } catch {
      /* stockage indisponible (navigation privée) : le thème reste en mémoire */
    }
  }, [])

  const toggle = useCallback(() => {
    setEtat((actuel) => {
      const prochain = actuel === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(CLE, prochain)
      } catch {
        /* idem */
      }
      return prochain
    })
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
