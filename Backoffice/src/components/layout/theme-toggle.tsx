import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/providers/theme-provider'

/** Bouton soleil/lune de la topbar (thème clair/sombre). */
export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const sombre = theme === 'dark'
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={sombre ? 'Passer en mode clair' : 'Passer en mode sombre'}
      onClick={toggle}
    >
      {sombre ? <Sun /> : <Moon />}
    </Button>
  )
}
