import { Keyboard, Moon, Sun } from 'lucide-react'
import { useTheme } from '@/providers/theme-provider'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * « Paramètres » — préférences d'affichage et raccourcis.
 *
 * Volontairement restreint à ce qui est RÉELLEMENT appliqué : le thème.
 *
 * Le mécanisme de thème n'est pas modifié (provider, persistance, classe
 * `dark`) — cet écran ne fait que le piloter via `setTheme`. Le mode
 * « système » n'est pas proposé : le provider ne le gère pas, l'exposer ici
 * ferait un réglage qui ne fonctionne pas.
 *
 * Rien d'inventé : pas de « préférences de notification » ni de « langue »
 * tant qu'ils ne produisent aucun effet. Un écran de réglages qui
 * n'enregistre rien est pire que pas d'écran.
 */

const CHOIX = [
  { cle: 'light' as const, label: 'Clair', icone: Sun },
  { cle: 'dark' as const, label: 'Sombre', icone: Moon },
]

const RACCOURCIS = [
  { touches: 'Ctrl / ⌘ + K', libelle: 'Recherche globale' },
  { touches: '↑ ↓', libelle: 'Naviguer dans les résultats' },
  { touches: 'Entrée', libelle: 'Ouvrir le résultat sélectionné' },
  { touches: 'Échap', libelle: 'Fermer la recherche ou un menu' },
  { touches: 'Clic dehors', libelle: 'Fermer un menu ouvert' },
]

export function ParametresPage() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        titre="Paramètres"
        sousTitre="Préférences d'affichage de cet appareil"
      />

      <Card>
        <CardHeader>
          <CardTitle>Apparence</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-muted-foreground">
            Le thème s'applique immédiatement et reste mémorisé sur cet appareil.
          </p>
          <div
            role="radiogroup"
            aria-label="Thème de l'interface"
            className="grid gap-3 sm:grid-cols-2"
          >
            {CHOIX.map(({ cle, label, icone: Icone }) => {
              const actif = theme === cle
              return (
                <button
                  key={cle}
                  type="button"
                  role="radio"
                  aria-checked={actif}
                  onClick={() => setTheme(cle)}
                  className={cn(
                    'focus-ring flex items-center gap-3 rounded-xl2 border px-4 py-4 transition-all duration-150',
                    actif
                      ? 'border-primary bg-primary/10 text-foreground shadow-float'
                      : 'border-border text-muted-foreground hover:border-primary/40 hover:bg-muted/50',
                  )}
                >
                  <Icone className={cn('h-5 w-5', actif && 'text-primary')} aria-hidden />
                  <span className="flex-1 text-left text-sm font-medium">{label}</span>
                  {actif && (
                    <span className="text-[11px] font-semibold text-primary">Actif</span>
                  )}
                </button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Keyboard className="h-4 w-4" aria-hidden />
            Raccourcis clavier
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2">
            {RACCOURCIS.map((raccourci) => (
              <div key={raccourci.touches} className="flex items-center gap-3 text-sm">
                <dt className="w-32 shrink-0">
                  <kbd className="rounded-md border border-surface-border bg-muted px-2 py-0.5 text-[11px] font-medium">
                    {raccourci.touches}
                  </kbd>
                </dt>
                <dd className="min-w-0 flex-1 truncate text-muted-foreground">
                  {raccourci.libelle}
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>À propos</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            <strong className="text-foreground">SysDent Pro</strong> — gestion
            multi-cabinet médico-dentaire.
          </p>
          <p>
            Ces préférences sont stockées sur cet appareil uniquement. Aucun réglage du
            cabinet n'est modifié depuis cet écran.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}