import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CalendarPlus,
  CornerDownLeft,
  LogOut,
  Search,
  Settings,
  UserRound,
  type LucideIcon,
} from 'lucide-react'
import { NAVIGATION } from '@/lib/navigation'
import { useAuthStore, possedePermission } from '@/stores/auth-store'
import { cn } from '@/lib/utils'

/**
 * Palette de commandes — `Ctrl/⌘ + K`.
 *
 * ## Ce qui remplace le champ « aller vers /patients?q= »
 *
 * L'ancien champ naviguait vers la liste des patients quel que soit le mot
 * saisi : taper « facture » menait à une recherche de patients qui ne trouveait
 * rien. Ici on cherche **dans tout l'application** : pages, puis actions
 * ponctuelles. Les entrées sont filtrées par permission — on ne propose pas à un
 * secrétaire d'ouvrir l'écran RBAC.
 *
 * Navigation clavier complète : ↑ ↓ pour se déplacer, `Entrée` pour ouvrir,
 * `Échap` pour fermer. Le focus revient au déclencheur à la fermeture.
 */

interface Resultat {
  id: string
  libelle: string
  groupe: string
  icone: LucideIcon
  hint?: string
  action: () => void
}

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const profil = useAuthStore((etat) => etat.profil)
  const deconnexion = useAuthStore((etat) => etat.deconnexion)
  const naviguer = useNavigate()
  const [terme, setTerme] = useState('')
  const [index, setIndex] = useState(0)
  const champRef = useRef<HTMLInputElement>(null)
  const listeRef = useRef<HTMLUListElement>(null)

  const resultats = useMemo<Resultat[]>(() => {
    const tous: Resultat[] = []

    // 1. Les pages, filtrées par permission.
    for (const section of NAVIGATION) {
      for (const item of section.items) {
        if (!item.href) continue
        if (item.permission && !possedePermission(profil, item.permission)) continue
        tous.push({
          id: `nav:${item.href}`,
          libelle: item.label,
          groupe: 'Pages',
          icone: item.icon,
          hint: item.href,
          action: () => naviguer(item.href as string),
        })
      }
    }

    // 2. Les actions ponctuelles.
    const actions: Resultat[] = [
      {
        id: 'action:rdv',
        libelle: 'Prendre un rendez-vous',
        groupe: 'Actions',
        icone: CalendarPlus,
        hint: 'Agenda',
        action: () => naviguer('/agenda'),
      },
      {
        id: 'action:compte',
        libelle: 'Mon compte',
        groupe: 'Compte',
        icone: UserRound,
        action: () => naviguer('/compte'),
      },
      {
        id: 'action:parametres',
        libelle: 'Paramètres',
        groupe: 'Compte',
        icone: Settings,
        action: () => naviguer('/parametres'),
      },
      {
        id: 'action:deconnexion',
        libelle: 'Se déconnecter',
        groupe: 'Compte',
        icone: LogOut,
        action: () => deconnexion(),
      },
    ]
    tous.push(...actions)

    const q = terme.trim().toLowerCase()
    if (!q) return tous
    // `startsWith` d'abord : taper « pat » place « Patients » en tête plutôt
    // que de le noyer dans l'ordre alphabétique.
    return tous
      .filter((r) => r.libelle.toLowerCase().includes(q))
      .sort((a, b) => {
        const ai = a.libelle.toLowerCase().startsWith(q) ? 0 : 1
        const bi = b.libelle.toLowerCase().startsWith(q) ? 0 : 1
        return ai - bi
      })
  }, [terme, profil, naviguer, deconnexion])

  // Borne l'index quand le filtre change.
  useEffect(() => setIndex(0), [terme])

  useEffect(() => {
    champRef.current?.focus()
  }, [])

  // Fait défiler l'entrée active dans la liste.
  useEffect(() => {
    listeRef.current
      ?.querySelector<HTMLElement>(`[data-index="${index}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  }, [index])

  const executer = (r: Resultat | undefined) => {
    if (!r) return
    onClose()
    r.action()
  }

  const surTouche = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIndex((i) => (resultats.length ? (i + 1) % resultats.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setIndex((i) => (resultats.length ? (i - 1 + resultats.length) % resultats.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      executer(resultats[index])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  // Empêche le défilement de l'arrière-plan pendant que la palette est ouverte.
  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  /**
   * Échap ferme la palette même si le focus n'est plus dedans.
   *
   * Le `onKeyDown` du panneau ne suffit pas : après un clic sur le fond (ou
   * sur la liste), le focus peut être elsewhere et la touche ne ferait plus
   * rien — l'utilisateur resterait piégé dans la palette, qui masque l'écran.
   */
  useEffect(() => {
    const surEchap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', surEchap)
    return () => document.removeEventListener('keydown', surEchap)
  }, [onClose])

  let groupeCourant = ''

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Palette de commandes — results"
    >
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />

      <div
        className="floating-panel relative w-full max-w-xl overflow-hidden rounded-xl2 animate-in fade-in zoom-in-95 duration-150"
        onKeyDown={surTouche}
      >
        <div className="flex items-center gap-3 border-b border-surface-border px-4">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <input
            ref={champRef}
            value={terme}
            onChange={(e) => setTerme(e.target.value)}
            placeholder="Rechercher une page, une action…"
            className="h-14 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            aria-label="Rechercher dans l'application"
            aria-activedescendant={resultats[index] ? `cmd-${resultats[index].id}` : undefined}
          />
          <kbd className="shrink-0 rounded-md border border-surface-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            Échap
          </kbd>
        </div>

        <ul ref={listeRef} className="max-h-[52vh] overflow-y-auto p-2" role="listbox">
          {resultats.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">
              Aucun résultat pour « {terme} ».
            </li>
          )}
          {resultats.map((r, i) => {
            const Icone = r.icone
            const nouveauGroupe = r.groupe !== groupeCourant
            groupeCourant = r.groupe
            return (
              <li key={r.id}>
                {nouveauGroupe && (
                  <p className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {r.groupe}
                  </p>
                )}
                <button
                  type="button"
                  id={`cmd-${r.id}`}
                  data-index={i}
                  role="option"
                  aria-selected={i === index}
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => executer(r)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-100',
                    i === index ? 'bg-primary/12 text-foreground' : 'text-muted-foreground',
                  )}
                >
                  <Icone
                    className={cn('h-4 w-4 shrink-0', i === index && 'text-primary')}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1 truncate">{r.libelle}</span>
                  {r.hint && (
                    <span className="shrink-0 font-mono text-[11px] text-muted-foreground/70">
                      {r.hint}
                    </span>
                  )}
                  {i === index ? (
                    <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                  ) : (
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 opacity-0" aria-hidden />
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}