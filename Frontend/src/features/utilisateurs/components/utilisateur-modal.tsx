import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Modal } from '@/components/ui/modal'
import { useToastStore } from '@/stores/toast-store'
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
 * - le mot de passe est **fixé à la création**. Le changer passe par la
 *   réinitialisation, qui coupe les sessions ouvertes — sinon quelqu'un resterait
 *   connecté avec l'ancien ;
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

  const maj = <K extends keyof Formulaire>(cle: K, valeur: Formulaire[K]) =>
    setV((precedent) => ({ ...precedent, [cle]: valeur }))

  /** Le serveur valide, on explains pourquoi avant. */
  const motDePasseSolide = (valeur: string) =>
    valeur.length >= 10 && /\d/.test(valeur) && /[a-zA-Z]/.test(valeur)

  async function soumettre(e: React.FormEvent) {
    e.preventDefault()
    setErreur('')

    if (!edition && !motDePasseSolide(v.motDePasse)) {
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
          mot_de_passe: v.motDePasse,
          role: v.role,
          telephone: v.telephone || null,
          cabinet_id: v.cabinetId || null,
        })
        addToast({
          type: 'success',
          message: `Compte créé pour ${v.prenom} ${v.nom}.`,
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
          : 'Le compte est utilisable dès sa création.'
      }
      maxWidth="lg"
    >
      <form className="space-y-4" onSubmit={soumettre}>
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
          <div className="space-y-1.5">
            <Label htmlFor="u-mdp" className="text-sm font-medium" required>
              Mot de passe initial
            </Label>
            <Input
              id="u-mdp"
              value={v.motDePasse}
              onChange={(e) => maj('motDePasse', e.target.value)}
              required
              minLength={10}
            />
            <p className="text-xs text-muted-foreground">
              Au moins 10 caractères, lettres et chiffres. Communicable au téléphone.
            </p>
          </div>
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
