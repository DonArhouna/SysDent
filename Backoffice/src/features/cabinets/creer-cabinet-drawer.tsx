import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, MailCheck, MailWarning } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { api, type ApiReponse } from '@/lib/api'
import { messageErreur, montant } from '@/lib/libelles'
import type { CabinetCreation, CabinetCree, Plan } from '@/lib/plateforme'
import { ChoixLogo, envoyerLogo } from './logo-cabinet'

const VIDE: CabinetCreation = {
  nom: '',
  admin_email: '',
  admin_prenom: '',
  admin_nom: '',
  telephone: '',
  ville: '',
  pays: 'Sénégal',
  ninea: '',
  statut_initial: 'ESSAI',
  jours_essai: 14,
  plan_code: '',
  langue: 'fr',
  devise: 'XOF',
  fuseau_horaire: 'Africa/Dakar',
}

/** Champs texte vides envoyés `null` : le backend distingue « absent » de « chaîne vide ». */
function nettoyer(f: CabinetCreation): CabinetCreation {
  const sortie: Record<string, unknown> = {}
  for (const [cle, valeur] of Object.entries(f)) {
    sortie[cle] = typeof valeur === 'string' && valeur.trim() === '' ? null : valeur
  }
  return sortie as CabinetCreation
}

/**
 * Création et provisionnement d'un cabinet.
 *
 * Le serveur crée la base du cabinet, applique les gabarits et **envoie
 * l'invitation** au premier administrateur : c'est lui qui choisira son mot de
 * passe. La console ne fixe jamais le mot de passe d'un client.
 */
export function CreerCabinetDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [f, setF] = useState<CabinetCreation>(VIDE)
  const [resultat, setResultat] = useState<CabinetCree | null>(null)
  const [logo, setLogo] = useState<File | null>(null)
  // `null` : pas de logo choisi ; sinon, message d'échec ou chaîne vide si envoyé.
  const [erreurLogo, setErreurLogo] = useState<string | null>(null)

  const plans = useQuery({
    queryKey: ['plans', { actifs: true }],
    queryFn: () => api.get<ApiReponse<Plan[]>>('/platform/plans', { params: { actif_seulement: true } }),
    enabled: open,
  })

  const creation = useMutation({
    mutationFn: (corps: CabinetCreation) =>
      api.post<ApiReponse<CabinetCree>>('/platform/tenants', corps),
    onSuccess: async (r) => {
      // Le logo exige l'identifiant du cabinet : il part juste après la création.
      // Un échec ne défait pas le cabinet, il se signale et se rattrape depuis la fiche.
      if (logo) {
        try {
          await envoyerLogo(r.data.tenant.tenant_id, logo)
          setErreurLogo('')
        } catch (e) {
          setErreurLogo(messageErreur(e))
        }
      }
      setResultat(r.data)
      void client.invalidateQueries({ queryKey: ['cabinets'] })
    },
  })

  const fermer = () => {
    setF(VIDE)
    setResultat(null)
    setLogo(null)
    setErreurLogo(null)
    creation.reset()
    onClose()
  }

  const champ = <K extends keyof CabinetCreation>(cle: K, valeur: CabinetCreation[K]) =>
    setF((courant) => ({ ...courant, [cle]: valeur }))

  const soumettre = (e: FormEvent) => {
    e.preventDefault()
    creation.mutate(nettoyer(f))
  }

  const optionsPlans = [
    { value: '', label: 'Plan par défaut' },
    ...(plans.data?.data ?? []).map((p) => ({
      value: p.code,
      label: `${p.nom} — ${montant(p.prix, p.devise)}${p.plan_defaut ? ' (défaut)' : ''}`,
    })),
  ]

  return (
    <Drawer
      open={open}
      onClose={creation.isPending ? () => undefined : fermer}
      title={resultat ? 'Cabinet créé' : 'Nouveau cabinet'}
      description={resultat ? undefined : "Le premier administrateur recevra une invitation par e-mail."}
      width="lg"
    >
      {resultat ? (
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-xl border border-success/30 bg-success/10 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
            <div className="text-sm">
              <p className="font-semibold text-foreground">{resultat.tenant.nom} est prêt.</p>
              <p className="text-muted-foreground">{resultat.etapes.length} étape(s) de provisionnement accomplie(s).</p>
            </div>
          </div>
          {erreurLogo && (
            <p role="alert" className="flex items-center gap-2 text-sm text-warning">
              <MailWarning className="h-4 w-4" aria-hidden />
              Logo non enregistré : {erreurLogo} Vous pourrez l'ajouter depuis la fiche du cabinet.
            </p>
          )}
          {resultat.invitation_admin_envoyee ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <MailCheck className="h-4 w-4 text-success" aria-hidden />
              Invitation envoyée à l'administrateur du cabinet.
            </p>
          ) : (
            <p role="alert" className="flex items-center gap-2 text-sm text-warning">
              <MailWarning className="h-4 w-4" aria-hidden />
              L'invitation n'a pas pu être envoyée. Vérifiez la configuration SMTP.
            </p>
          )}
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {resultat.etapes.map((etape) => (
              <li key={etape}>{etape}</li>
            ))}
          </ul>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={fermer}>
              Fermer
            </Button>
            <Button
              onClick={() => {
                const id = resultat.tenant.tenant_id
                fermer()
                navigate(`/cabinets/${id}`)
              }}
            >
              Ouvrir la fiche
            </Button>
          </div>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={soumettre}>
          <fieldset className="space-y-3">
            <legend className="mb-1 text-sm font-semibold">Cabinet</legend>
            <Input label="Nom du cabinet" required minLength={2} maxLength={150} value={f.nom} onChange={(e) => champ('nom', e.target.value)} autoFocus />
            <ChoixLogo fichier={logo} onChange={setLogo} />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Téléphone" value={f.telephone ?? ''} onChange={(e) => champ('telephone', e.target.value)} />
              <Input label="NINEA" value={f.ninea ?? ''} onChange={(e) => champ('ninea', e.target.value)} />
              <Input label="Ville" value={f.ville ?? ''} onChange={(e) => champ('ville', e.target.value)} />
              <Input label="Pays" value={f.pays ?? ''} onChange={(e) => champ('pays', e.target.value)} />
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="mb-1 text-sm font-semibold">Premier administrateur</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Prénom" required value={f.admin_prenom} onChange={(e) => champ('admin_prenom', e.target.value)} />
              <Input label="Nom" required value={f.admin_nom} onChange={(e) => champ('admin_nom', e.target.value)} />
            </div>
            <Input label="E-mail" type="email" required value={f.admin_email} onChange={(e) => champ('admin_email', e.target.value)} helperText="L'invitation part à cette adresse." />
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="mb-1 text-sm font-semibold">Offre</legend>
            <Select label="Plan" options={optionsPlans} value={f.plan_code ?? ''} onChange={(e) => champ('plan_code', e.target.value)} />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Démarrage"
                options={[
                  { value: 'ESSAI', label: "Période d'essai" },
                  { value: 'ACTIF', label: 'Actif immédiatement' },
                ]}
                value={f.statut_initial ?? 'ESSAI'}
                onChange={(e) => champ('statut_initial', e.target.value)}
              />
              {f.statut_initial === 'ESSAI' && (
                <Input
                  label="Jours d'essai"
                  type="number"
                  min={1}
                  max={365}
                  value={f.jours_essai ?? 14}
                  onChange={(e) => champ('jours_essai', Number(e.target.value))}
                />
              )}
            </div>
          </fieldset>

          {creation.isError && (
            <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {messageErreur(creation.error)}
            </p>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={fermer} disabled={creation.isPending}>
              Annuler
            </Button>
            <Button type="submit" disabled={creation.isPending}>
              {creation.isPending ? 'Création en cours…' : 'Créer le cabinet'}
            </Button>
          </div>
        </form>
      )}
    </Drawer>
  )
}
