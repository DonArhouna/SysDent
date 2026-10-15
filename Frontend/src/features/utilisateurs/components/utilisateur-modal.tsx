import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Modal } from '@/components/ui/modal'
import { useToastStore } from '@/stores/toast-store'
import { useAuthStore } from '@/stores/auth-store'
import { CabinetLogo } from '@/components/cabinet-logo'
import { ROLES, utilisateursApi } from '../services/utilisateurs-api'
import type { Utilisateur } from '../types'

interface Formulaire {
  email: string
  prenom: string
  nom: string
  role: string
  telephone: string
  motDePasse: string
  cabinetId: string
}

const VIDE: Formulaire = {
  email: '',
  prenom: '',
  nom: '',
  role: 'SECRETAIRE',
  telephone: '',
  motDePasse: '',
  cabinetId: '',
}

/**
 * Création et modification d'un compte.
 *
 * Deux règles viennent du serveur et non d'ici :
 *
 * - par défaut, **aucun mot de passe n'est fixé ici** : la personne reçoit un
 *   lien d'activation par e-mail et choisit le sien. Un mot de passe saisi ici
 *   est TEMPORAIRE : son changement est imposé à la première connexion ;
 * - un mot de passe tout numérique ou tout alphabétique est refusé : ce compte
 *   donne accès au dossier médical.
 *
 * L'email n'est pas modifiable ici : il est la clé de routage du compte en base
 * master, et le changer ferait perdre l'accès au compte.
 */
export function UtilisateurModal({
  isOpen,
  utilisateur,
  cabinetId,
  onClose,
  onSuccess,
}: {
  isOpen: boolean
  utilisateur?: Utilisateur | null
  cabinetId?: string | null
  onClose: () => void
  onSuccess: () => void
}) {
  const edition = Boolean(utilisateur)
  const profil = useAuthStore((e) => e.profil)
  const { addToast } = useToastStore()

  // L'etat initial est calcule une seule fois : le composant est remonte par le
  // parent (`key`), ce qui reinitialise le formulaire sans effet ni dependance.
  const [v, setV] = useState<Formulaire>(() =>
    utilisateur
      ? {
          email: utilisateur.email,
          prenom: utilisateur.prenom,
          nom: utilisateur.nom,
          role: utilisateur.role,
          telephone: utilisateur.telephone ?? '',
          motDePasse: '',
          cabinetId: utilisateur.cabinet_id ?? '',
        }
      : { ...VIDE, cabinetId: cabinetId ?? '' }
  )
  const [erreur, setErreur] = useState('')
  const [soumission, setSoumission] = useState(false)
  // Lien d'activation (recommandé) ou mot de passe temporaire (dépannage).
  const [modeTemporaire, setModeTemporaire] = useState(false)

  const maj = <K extends keyof Formulaire>(cle: K, valeur: Formulaire[K]) =>
    setV((precedent) => ({ ...precedent, [cle]: valeur }))

  /** Le serveur valide, on explains pourquoi avant. */
  const motDePasseSolide = (valeur: string) =>
    valeur.length >= 10 && /\d/.test(valeur) && /[a-zA-Z]/.test(valeur)

  async function soumettre(e: React.FormEvent) {
    e.preventDefault()
    setErreur('')

    if (!edition && modeTemporaire && !motDePasseSolide(v.motDePasse)) {
      setErreur('Le mot de passe doit faire au moins 10 caractères et mélanger lettres et chiffres.')
      return
    }

    try {
      setSoumission(true)
      if (edition && utilisateur) {
        await utilisateursApi.modifier(utilisateur.id, {
          prenom: v.prenom,
          nom: v.nom,
          role: v.role,
          telephone: v.telephone || null,
        })
        addToast({ type: 'success', message: 'Compte mis à jour.' })
      } else {
        await utilisateursApi.creer({
          email: v.email,
          prenom: v.prenom,
          nom: v.nom,
          mot_de_passe: modeTemporaire ? v.motDePasse : null,
          role: v.role,
          telephone: v.telephone || null,
          cabinet_id: v.cabinetId || null,
        })
        addToast({
          type: 'success',
          message: modeTemporaire
            ? `Compte créé pour ${v.prenom} ${v.nom}. Mot de passe temporaire à changer à la première connexion.`
            : `Compte créé : ${v.prenom} ${v.nom} a reçu son lien d'activation par e-mail.`,
        })
      }
      onSuccess()
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Enregistrement impossible.'
      setErreur(message)
    } finally {
      setSoumission(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={edition ? `Modifier ${v.prenom} ${v.nom}` : 'Ajouter un utilisateur'}
      description={
        edition
          ? 'Rôle, identité et coordonnées du compte.'
          : 'La personne reçoit un lien pour activer son compte.'
      }
      maxWidth="lg"
    >
      <form className="space-y-4" onSubmit={soumettre}>
        {/* Le cabinet dans lequel le compte est créé : repère visible avant de valider. */}
        <div className="flex items-center gap-3 rounded-xl border border-border bg-muted/30 p-3">
          <CabinetLogo url={profil?.cabinet_logo_url} nom={profil?.societe_nom ?? profil?.cabinet_nom} taille="sm" />
          <div className="min-w-0 text-sm">
            <p className="text-xs text-muted-foreground">{edition ? 'Compte du cabinet' : 'Nouveau compte dans'}</p>
            <p className="truncate font-semibold">{profil?.societe_nom ?? profil?.cabinet_nom ?? 'Votre cabinet'}</p>
          </div>
          {!profil?.cabinet_logo_url && <span className="ml-auto text-[10px] text-muted-foreground">Aucun logo</span>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="u-prenom" className="text-sm font-medium" required>
              Prénom
            </Label>
            <Input
              id="u-prenom"
              value={v.prenom}
              onChange={(e) => maj('prenom', e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="u-nom" className="text-sm font-medium" required>
              Nom
            </Label>
            <Input
              id="u-nom"
              value={v.nom}
              onChange={(e) => maj('nom', e.target.value)}
              required
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="u-email" className="text-sm font-medium" required>
            Adresse email
          </Label>
          <Input
            id="u-email"
            type="email"
            value={v.email}
            onChange={(e) => maj('email', e.target.value)}
            disabled={edition}
            required
          />
          {edition && (
            <p className="text-xs text-muted-foreground">
              L'adresse ne change pas : elle est la clé de routage du compte.
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="u-role" className="text-sm font-medium" required>
            Rôle
          </Label>
          <Select
            id="u-role"
            value={v.role}
            onChange={(e) => maj('role', e.target.value)}
            required
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
          <p className="text-xs text-muted-foreground">
            Le rôle porte les permissions. Le serveur les vérifie à chaque appel.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="u-tel" className="text-sm font-medium">
            Téléphone
          </Label>
          <Input
            id="u-tel"
            value={v.telephone}
            onChange={(e) => maj('telephone', e.target.value)}
          />
        </div>

        {!edition && (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Accès au compte</legend>
            <label className="flex items-start gap-2 text-sm">
              <input type="radio" name="u-acces" className="mt-1" checked={!modeTemporaire} onChange={() => setModeTemporaire(false)} />
              <span>
                <span className="font-medium">Envoyer un lien d'activation</span> (recommandé)
                <span className="block text-xs text-muted-foreground">
                  La personne choisit elle-même son mot de passe ; personne d'autre ne le connaît.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="radio" name="u-acces" className="mt-1" checked={modeTemporaire} onChange={() => setModeTemporaire(true)} />
              <span>
                <span className="font-medium">Fixer un mot de passe temporaire</span>
                <span className="block text-xs text-muted-foreground">
                  Si la personne n'a pas accès à ses e-mails. Elle devra le changer à sa première connexion.
                </span>
              </span>
            </label>
            {modeTemporaire && (
              <div className="space-y-1.5 pl-6">
                <Label htmlFor="u-mdp" className="text-sm font-medium" required>
                  Mot de passe temporaire
                </Label>
                <Input
                  id="u-mdp"
                  value={v.motDePasse}
                  onChange={(e) => maj('motDePasse', e.target.value)}
                  required
                  minLength={10}
                />
                <p className="text-xs text-muted-foreground">Au moins 10 caractères, lettres et chiffres.</p>
              </div>
            )}
          </fieldset>
        )}

        {erreur && (
          <p
            role="alert"
            className="rounded-xl2 border border-danger/30 bg-danger/10 px-3 py-2 text-sm"
          >
            {erreur}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" disabled={soumission}>
            {edition ? 'Enregistrer' : 'Créer le compte'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
