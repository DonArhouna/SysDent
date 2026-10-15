import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { KeyRound, LifeBuoy, Mail, ShieldAlert, ShieldCheck, Smartphone } from 'lucide-react'

import { AppShell } from '@/components/layout/app-shell'
import { Avatar, initiales } from '@/components/ui/avatar'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatusBadge } from '@/components/ui/status-badge'
import { api } from '@/lib/api'
import { dateHeure, libelleRole, messageErreur, statutCompte } from '@/lib/libelles'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from '@/stores/toast-store'

/** Pré-contrôle de la politique du backend (le serveur reste juge). */
function reglesManquantes(mdp: string, email: string): string[] {
  const identifiant = email.split('@')[0]?.toLowerCase() ?? ''
  const regles: Array<[boolean, string]> = [
    [mdp.length >= 12, '12 caractères minimum'],
    [/[A-Z]/.test(mdp), 'une majuscule'],
    [/[a-z]/.test(mdp), 'une minuscule'],
    [/\d/.test(mdp), 'un chiffre'],
    [/[^A-Za-z0-9]/.test(mdp), 'un caractère spécial'],
    [!(identifiant.length >= 3 && mdp.toLowerCase().includes(identifiant)), "sans reprendre l'adresse e-mail"],
  ]
  return regles.filter(([ok]) => !ok).map(([, libelle]) => libelle)
}

function ChangerMotDePasse({ email }: { email: string }) {
  const [f, setF] = useState({ ancien: '', nouveau: '', confirmation: '' })

  const changement = useMutation({
    mutationFn: () => api.post('/platform/auth/mot-de-passe', { ancien: f.ancien, nouveau: f.nouveau }),
    onSuccess: () => {
      setF({ ancien: '', nouveau: '', confirmation: '' })
      toast.success('Mot de passe modifié.')
    },
  })

  const manquantes = f.nouveau ? reglesManquantes(f.nouveau, email) : []
  const differents = f.confirmation !== '' && f.confirmation !== f.nouveau
  const pret = f.ancien && f.nouveau && manquantes.length === 0 && f.confirmation === f.nouveau

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    changement.mutate()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <KeyRound className="h-4 w-4 text-muted-foreground" aria-hidden />
          Changer mon mot de passe
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-3" onSubmit={soumettre}>
          {/* Champ caché : les gestionnaires de mots de passe rattachent ainsi le nouveau au bon compte. */}
          <input type="text" name="username" autoComplete="username" value={email} readOnly hidden />
          <Input label="Mot de passe actuel" type="password" autoComplete="current-password" required value={f.ancien} onChange={(e) => setF({ ...f, ancien: e.target.value })} />
          <Input
            label="Nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            required
            value={f.nouveau}
            onChange={(e) => setF({ ...f, nouveau: e.target.value })}
            error={manquantes.length ? `Il manque : ${manquantes.join(', ')}.` : undefined}
            helperText="12 caractères minimum, avec majuscule, minuscule, chiffre et caractère spécial."
          />
          <Input
            label="Confirmer le nouveau mot de passe"
            type="password"
            autoComplete="new-password"
            required
            value={f.confirmation}
            onChange={(e) => setF({ ...f, confirmation: e.target.value })}
            error={differents ? 'Les deux saisies ne correspondent pas.' : undefined}
          />
          {changement.isError && (
            <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {messageErreur(changement.error)}
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" disabled={!pret || changement.isPending}>
              {changement.isPending ? 'Enregistrement…' : 'Changer le mot de passe'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

/**
 * Mon compte : profil, sécurité et mot de passe du compte connecté.
 *
 * Tout vient de `/platform/auth/me` ; rien n'est modifiable ici sauf le mot de
 * passe. Nom, rôles et e-mail se changent par un Super Admin depuis « Équipe »,
 * ce qui laisse une trace d'un tiers au journal d'audit.
 */
export function ComptePage() {
  const profil = useAuthStore((e) => e.profil)
  const chargerProfil = useAuthStore((e) => e.chargerProfil)

  // Le layout charge le profil s'il manque : le rendre quand meme, plutot
  // qu'un ecran blanc qui ne declencherait jamais ce chargement.
  if (!profil) {
    return (
      <AppShell>
        <p role="status" className="text-sm text-muted-foreground">Chargement du profil…</p>
      </AppShell>
    )
  }

  const s = statutCompte(profil.statut)
  const methodes = profil.methodes_2fa ?? []
  const roles = profil.roles ?? (profil.role ? [profil.role] : [])

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader titre="Mon compte" sousTitre="Votre profil et la sécurité de votre accès." onRefresh={() => void chargerProfil()} />

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-1">
            <CardContent className="flex flex-col items-center gap-3 pt-6 text-center">
              <Avatar initials={initiales(profil.prenom, profil.nom)} size="lg" />
              <div>
                <p className="text-lg font-semibold">{`${profil.prenom} ${profil.nom}`}</p>
                <p className="text-sm text-muted-foreground">{profil.email}</p>
              </div>
              <div className="flex flex-wrap justify-center gap-1">
                {roles.map((r) => (
                  <StatusBadge key={r} tone="purple">{libelleRole(r)}</StatusBadge>
                ))}
                {profil.statut && <StatusBadge tone={s.ton}>{s.texte}</StatusBadge>}
              </div>
              <dl className="mt-2 w-full space-y-2 border-t border-border pt-4 text-left text-sm">
                {profil.telephone && (
                  <div className="flex justify-between gap-2">
                    <dt className="text-muted-foreground">Téléphone</dt>
                    <dd>{profil.telephone}</dd>
                  </div>
                )}
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Dernière connexion</dt>
                  <dd>{dateHeure(profil.dernier_login)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Compte créé le</dt>
                  <dd>{dateHeure(profil.cree_le)}</dd>
                </div>
              </dl>
              <p className="text-xs text-muted-foreground">
                Nom, e-mail et rôles se modifient par un Super Admin, depuis « Équipe ».
              </p>
            </CardContent>
          </Card>

          <div className="space-y-6 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  {profil.deux_facteurs_actif ? (
                    <ShieldCheck className="h-4 w-4 text-success" aria-hidden />
                  ) : (
                    <ShieldAlert className="h-4 w-4 text-warning" aria-hidden />
                  )}
                  Double authentification
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                {profil.deux_facteurs_actif ? (
                  <>
                    <p className="text-muted-foreground">Active. À chaque connexion, vous pouvez utiliser :</p>
                    <ul className="grid gap-2 sm:grid-cols-2">
                      <li className={`flex items-center gap-3 rounded-xl border p-3 ${methodes.includes('totp') ? 'border-success/30 bg-success/5' : 'border-border opacity-60'}`}>
                        <Smartphone className="h-5 w-5 shrink-0" aria-hidden />
                        <span>
                          <span className="block font-medium">Application</span>
                          <span className="text-xs text-muted-foreground">{methodes.includes('totp') ? 'Configurée' : 'Non configurée'}</span>
                        </span>
                      </li>
                      <li className={`flex items-center gap-3 rounded-xl border p-3 ${methodes.includes('email') ? 'border-success/30 bg-success/5' : 'border-border opacity-60'}`}>
                        <Mail className="h-5 w-5 shrink-0" aria-hidden />
                        <span>
                          <span className="block font-medium">Code par e-mail</span>
                          <span className="text-xs text-muted-foreground">{profil.email}</span>
                        </span>
                      </li>
                    </ul>
                  </>
                ) : (
                  <p className="text-warning">Non configurée : elle vous sera demandée à la prochaine connexion.</p>
                )}

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted/50 p-3">
                  <span className="flex items-center gap-2">
                    <LifeBuoy className="h-4 w-4 text-muted-foreground" aria-hidden />
                    {profil.codes_secours_a_regenerer
                      ? <span className="text-warning">Vos codes de secours doivent être régénérés.</span>
                      : 'Codes de secours : à utiliser si vous perdez votre téléphone.'}
                  </span>
                  {methodes.includes('totp') ? (
                    <Link to="/codes-secours" className={buttonVariants({ size: 'sm', variant: 'outline' })}>
                      Régénérer les codes
                    </Link>
                  ) : profil.deux_facteurs_actif ? (
                    <span className="text-xs text-muted-foreground">
                      Régénération possible uniquement avec une application configurée.
                    </span>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            <ChangerMotDePasse email={profil.email} />

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Mes permissions</CardTitle>
              </CardHeader>
              <CardContent>
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground">
                    {profil.permissions.length} permission(s) effective(s)
                  </summary>
                  <ul className="mt-3 grid gap-1 font-mono text-xs text-muted-foreground sm:grid-cols-2">
                    {profil.permissions.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </details>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
