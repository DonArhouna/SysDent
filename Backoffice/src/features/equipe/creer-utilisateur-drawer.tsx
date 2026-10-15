import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { api, type ApiReponse } from '@/lib/api'
import { messageErreur } from '@/lib/libelles'
import type { Role, UtilisateurCreation } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'

/**
 * Pré-contrôle de la politique du backend : 12 caractères, majuscule,
 * minuscule, chiffre, spécial, et pas l'identifiant de l'adresse e-mail (3
 * caractères ou plus). Le serveur reste juge ; ceci évite un aller-retour.
 */
function motDePasseConforme(mdp: string, email: string): boolean {
  const identifiant = email.split('@')[0]?.toLowerCase() ?? ''
  return (
    mdp.length >= 12 &&
    /[A-Z]/.test(mdp) &&
    /[a-z]/.test(mdp) &&
    /\d/.test(mdp) &&
    /[^A-Za-z0-9]/.test(mdp) &&
    !(identifiant.length >= 3 && mdp.toLowerCase().includes(identifiant))
  )
}

/**
 * Création d'un compte de la console.
 *
 * Le second facteur **n'est pas préparé ici** (`activer_2fa: false`) : à sa
 * première connexion, la personne choisit elle-même QR code ou e-mail. Préparer
 * un secret depuis ce poste obligerait à le lui transmettre, ce qui en ferait un
 * secret partagé.
 *
 * Le mot de passe initial est à communiquer hors de la console ; le serveur ne
 * le renvoie jamais.
 */
export function CreerUtilisateurDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient()
  const [f, setF] = useState({ email: '', prenom: '', nom: '', telephone: '', mot_de_passe: '' })
  const [roles, setRoles] = useState<string[]>([])

  const listeRoles = useQuery({
    queryKey: ['roles'],
    queryFn: () => api.get<ApiReponse<Role[]>>('/platform/roles'),
    enabled: open,
  })

  const creation = useMutation({
    mutationFn: (corps: UtilisateurCreation) => api.post('/platform/users', corps),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['equipe'] })
      void client.invalidateQueries({ queryKey: ['roles'] })
      toast.success(`Compte ${f.email} créé.`)
      fermer()
    },
  })

  const fermer = () => {
    setF({ email: '', prenom: '', nom: '', telephone: '', mot_de_passe: '' })
    setRoles([])
    creation.reset()
    onClose()
  }

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    creation.mutate({ ...f, telephone: f.telephone.trim() || null, roles, activer_2fa: false })
  }

  const mdpOk = motDePasseConforme(f.mot_de_passe, f.email)

  return (
    <Drawer open={open} onClose={creation.isPending ? () => undefined : fermer} title="Nouveau compte" description="Accès à la console plateforme." width="lg">
      <form className="space-y-5" onSubmit={soumettre}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Prénom" required value={f.prenom} onChange={(e) => setF({ ...f, prenom: e.target.value })} autoFocus />
          <Input label="Nom" required value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} />
        </div>
        <Input label="E-mail" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <Input label="Téléphone" value={f.telephone} onChange={(e) => setF({ ...f, telephone: e.target.value })} />
        <Input
          label="Mot de passe initial"
          type="password"
          autoComplete="new-password"
          required
          value={f.mot_de_passe}
          onChange={(e) => setF({ ...f, mot_de_passe: e.target.value })}
          helperText="12 caractères minimum, avec majuscule, minuscule, chiffre et caractère spécial, sans reprendre l'adresse e-mail. À transmettre hors de la console."
          error={f.mot_de_passe && !mdpOk ? 'Ne respecte pas encore la politique.' : undefined}
        />

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Rôles</legend>
          {listeRoles.isPending ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : (
            (listeRoles.data?.data ?? []).map((r) => (
              <label key={r.code} className="flex items-start gap-3 rounded-xl border border-border p-3 text-sm transition-colors hover:bg-muted/40">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={roles.includes(r.code)}
                  onChange={(e) => setRoles((rs) => (e.target.checked ? [...rs, r.code] : rs.filter((x) => x !== r.code)))}
                />
                <span>
                  <span className="font-medium">{r.libelle}</span>
                  {r.description && <span className="block text-xs text-muted-foreground">{r.description}</span>}
                </span>
              </label>
            ))
          )}
        </fieldset>

        <p className="rounded-xl bg-muted/50 p-3 text-xs text-muted-foreground">
          La double authentification sera configurée par la personne à sa première connexion
          (QR code ou code par e-mail).
        </p>

        {creation.isError && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {messageErreur(creation.error)}
          </p>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={fermer} disabled={creation.isPending}>
            Annuler
          </Button>
          <Button type="submit" disabled={creation.isPending || !mdpOk || roles.length === 0}>
            {creation.isPending ? 'Création…' : 'Créer le compte'}
          </Button>
        </div>
      </form>
    </Drawer>
  )
}
