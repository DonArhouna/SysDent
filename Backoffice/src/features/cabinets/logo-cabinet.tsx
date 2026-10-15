import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { api, envoyerFichier, urlRessource } from '@/lib/api'
import { messageErreur } from '@/lib/libelles'
import { cn } from '@/lib/utils'
import { toast } from '@/stores/toast-store'

const TYPES = ['image/png', 'image/jpeg', 'image/webp']
const TAILLE_MAX = 512 * 1024

/** Contrôle immédiat ; le serveur revérifie sur le contenu du fichier. */
export function erreurFichierLogo(f: File): string | null {
  if (!TYPES.includes(f.type)) return 'Format non accepté : PNG, JPEG ou WebP.'
  if (f.size > TAILLE_MAX) return `Fichier trop lourd (${Math.round(f.size / 1024)} Ko) : 512 Ko maximum.`
  return null
}

/** Envoie le logo d'un cabinet ; rend sa nouvelle adresse. */
export async function envoyerLogo(tenantId: string, fichier: File): Promise<string> {
  const r = await envoyerFichier<{ data: { logo_url: string } }>(`/platform/tenants/${tenantId}/logo`, 'fichier', fichier)
  return r.data.logo_url
}

/**
 * Logo du cabinet, ou à défaut un repère EXPLICITE : ses initiales dans un
 * cadre en pointillés, annoncé « Aucun logo » (infobulle et lecteur d'écran).
 * Un logo absent ne doit pas se confondre avec une image qui charge mal.
 */
export function ApercuLogo({ url, nom, taille = 'md' }: { url?: string | null; nom: string; taille?: 'sm' | 'md' | 'lg' }) {
  const [casse, setCasse] = useState(false)
  const dims = taille === 'lg' ? 'h-16 w-16 text-lg' : taille === 'sm' ? 'h-8 w-8 text-[11px]' : 'h-10 w-10 text-sm'
  const src = urlRessource(url)
  if (src && !casse) {
    return <img src={src} alt={`Logo de ${nom}`} onError={() => setCasse(true)} className={cn(dims, 'shrink-0 rounded-xl border border-border bg-white object-contain p-1')} />
  }
  // Initiales des mots significatifs (« Cabinet Démo SysDent » -> « CD »).
  const initiales = nom
    .split(/\s+/)
    .filter((m) => /^[\p{L}\d]/u.test(m))
    .slice(0, 2)
    .map((m) => m[0]?.toUpperCase())
    .join('')
  return (
    <span
      role="img"
      aria-label={casse ? `Logo de ${nom} indisponible` : `${nom} : aucun logo`}
      title={casse ? 'Logo indisponible' : 'Aucun logo'}
      className={cn(dims, 'flex shrink-0 items-center justify-center rounded-xl border border-dashed border-muted-foreground/40 bg-muted/50 font-bold text-muted-foreground')}
    >
      {initiales || '?'}
    </span>
  )
}

/**
 * Sélection d'un logo AVANT la création du cabinet : aperçu local, envoyé une
 * fois le cabinet créé (il faut son identifiant).
 */
export function ChoixLogo({ fichier, onChange }: { fichier: File | null; onChange: (f: File | null) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  const [erreur, setErreur] = useState('')
  // Adresse locale de l'aperçu, libérée quand le fichier change.
  const apercu = useMemo(() => (fichier ? URL.createObjectURL(fichier) : null), [fichier])
  useEffect(() => () => {
    if (apercu) URL.revokeObjectURL(apercu)
  }, [apercu])

  return (
    <div className="space-y-2">
      <span className="block text-xs font-semibold text-foreground">Logo (optionnel)</span>
      <div className="flex items-center gap-3">
        {fichier && apercu ? (
          <img src={apercu} alt="Aperçu du logo" className="h-14 w-14 rounded-xl border border-border bg-white object-contain p-1" />
        ) : (
          <span className="flex h-14 w-14 items-center justify-center rounded-xl border border-dashed border-border text-muted-foreground">
            <ImagePlus className="h-5 w-5" aria-hidden />
          </span>
        )}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => ref.current?.click()}>
            {fichier ? 'Changer' : 'Choisir une image'}
          </Button>
          {fichier && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange(null)}>
              Retirer
            </Button>
          )}
        </div>
        <input
          ref={ref}
          type="file"
          accept={TYPES.join(',')}
          className="hidden"
          aria-label="Logo du cabinet"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null
            e.target.value = ''
            if (!f) return
            const probleme = erreurFichierLogo(f)
            setErreur(probleme ?? '')
            if (!probleme) onChange(f)
          }}
        />
      </div>
      <p className={cn('text-xs', erreur ? 'text-danger' : 'text-muted-foreground')}>
        {erreur || 'PNG, JPEG ou WebP, 512 Ko maximum. Affiché dans l’application du cabinet.'}
      </p>
    </div>
  )
}

/** Logo d'un cabinet existant, avec Changer / Retirer (fiche du cabinet). */
export function LogoCabinet({ tenantId, nom, url, modifiable }: { tenantId: string; nom: string; url?: string | null; modifiable: boolean }) {
  const client = useQueryClient()
  const ref = useRef<HTMLInputElement>(null)

  const rafraichir = () => {
    void client.invalidateQueries({ queryKey: ['cabinet', tenantId] })
    void client.invalidateQueries({ queryKey: ['cabinets'] })
  }
  const envoi = useMutation({
    mutationFn: (f: File) => envoyerLogo(tenantId, f),
    onSuccess: () => {
      rafraichir()
      toast.success('Logo enregistré.')
    },
    onError: (e) => toast.error(messageErreur(e)),
  })
  const retrait = useMutation({
    mutationFn: () => api.delete(`/platform/tenants/${tenantId}/logo`),
    onSuccess: () => {
      rafraichir()
      toast.success('Logo retiré.')
    },
    onError: (e) => toast.error(messageErreur(e)),
  })

  return (
    <div className="flex items-center gap-3">
      <div className="flex flex-col items-center gap-1">
        <ApercuLogo url={url} nom={nom} taille="lg" />
        {!url && <span className="text-[10px] text-muted-foreground">Aucun logo</span>}
      </div>
      {modifiable && (
        <div className="flex flex-col gap-1">
          <Button size="sm" variant="outline" onClick={() => ref.current?.click()} disabled={envoi.isPending}>
            <ImagePlus aria-hidden />
            {envoi.isPending ? 'Envoi…' : url ? 'Changer le logo' : 'Ajouter un logo'}
          </Button>
          {url && (
            <Button size="sm" variant="ghost" onClick={() => retrait.mutate()} disabled={retrait.isPending}>
              <Trash2 aria-hidden />
              Retirer
            </Button>
          )}
          <input
            ref={ref}
            type="file"
            accept={TYPES.join(',')}
            className="hidden"
            aria-label="Nouveau logo du cabinet"
            onChange={(e) => {
              const f = e.target.files?.[0]
              e.target.value = ''
              if (!f) return
              const probleme = erreurFichierLogo(f)
              if (probleme) toast.error(probleme)
              else envoi.mutate(f)
            }}
          />
        </div>
      )}
    </div>
  )
}
