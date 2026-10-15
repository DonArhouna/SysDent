import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2, KeyRound, LinkIcon } from 'lucide-react'

import { buttonVariants } from '@/components/ui/button'
import { CabinetLogo } from '@/components/cabinet-logo'
import { api, type ApiReponse } from '@/lib/api'
import { NouveauMotDePasse } from '@/features/auth/securite-ui'
import { messageErreur } from '@/features/auth/regles'

interface InfoActivation {
  email: string
  prenom: string
  nom: string
  cabinet_nom?: string | null
  cabinet_logo_url?: string | null
}

/**
 * Activation d'un compte : la personne choisit elle-même son mot de passe.
 *
 * Le jeton vient du lien reçu par e-mail (`?jeton=`). Il est à usage unique et
 * expire : personne d'autre que le titulaire ne connaît jamais le mot de passe.
 * Le jeton n'est stocké nulle part dans le navigateur.
 */
export function ActivationPage() {
  const [params] = useSearchParams()
  const jeton = params.get('jeton') ?? ''
  const [info, setInfo] = useState<InfoActivation | null>(null)
  const [erreurServeur, setErreur] = useState('')
  const erreur = jeton ? erreurServeur : "Ce lien est incomplet. Ouvrez-le directement depuis l'e-mail reçu."
  const [termine, setTermine] = useState(false)

  useEffect(() => {
    if (!jeton) return
    api
      .post<ApiReponse<InfoActivation>>('/auth/activation/verification', { jeton }, { silencieux: true })
      .then((r) => setInfo(r.data))
      .catch((e) => setErreur(messageErreur(e)))
  }, [jeton])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center text-center">
          {/* Le cabinet qui invite, dès que le lien est vérifié : la personne
              doit savoir où elle entre avant de choisir son mot de passe. */}
          {info ? (
            <CabinetLogo url={info.cabinet_logo_url} nom={info.cabinet_nom} taille="lg" legende />
          ) : (
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-xl font-black text-white shadow-lg shadow-primary/30">
              SD
            </span>
          )}
          <h1 className="mt-4 text-2xl font-bold">Activer mon compte</h1>
          {info?.cabinet_nom && <p className="mt-1 text-sm text-muted-foreground">{info.cabinet_nom}</p>}
        </div>

        <div className="space-y-4 rounded-card border border-border bg-card p-6 shadow-sm">
          {termine ? (
            <div className="space-y-4 text-center">
              <CheckCircle2 className="mx-auto h-10 w-10 text-success" aria-hidden />
              <p className="text-sm">Votre compte est activé. Vous pouvez maintenant vous connecter.</p>
              <Link to="/login" className={buttonVariants({ className: 'w-full' })}>
                Se connecter
              </Link>
            </div>
          ) : erreur ? (
            <div className="space-y-4">
              <p role="alert" className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
                <LinkIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {erreur}
              </p>
              <p className="text-xs text-muted-foreground">
                Un lien d'activation ne sert qu'une fois et expire au bout de quelques jours.
                Demandez à l'administrateur de votre cabinet de vous en renvoyer un.
              </p>
              <Link to="/login" className={buttonVariants({ variant: 'outline', className: 'w-full' })}>
                Revenir à la connexion
              </Link>
            </div>
          ) : !info ? (
            <p role="status" className="text-sm text-muted-foreground">Vérification du lien…</p>
          ) : (
            <>
              <div className="flex items-start gap-3">
                <KeyRound className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden />
                <div className="text-sm">
                  <p>
                    Bonjour <strong>{info.prenom}</strong>, choisissez le mot de passe de votre compte.
                  </p>
                  <p className="text-muted-foreground">{info.email}</p>
                </div>
              </div>
              <NouveauMotDePasse
                email={info.email}
                libelleBouton="Activer mon compte"
                onValider={async (mot_de_passe) => {
                  await api.post('/auth/activation', { jeton, mot_de_passe }, { silencieux: true })
                  setTermine(true)
                }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
