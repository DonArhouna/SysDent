import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Modal } from '@/components/ui/modal'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useToastStore } from '@/stores/toast-store'
import { useCabinetStore } from '@/stores/cabinet-store'
import { formatDateTimeFr } from '@/lib/format'
import { ApiError } from '@/lib/api'
import { ROLES, libelleRole, utilisateursApi } from '../services/utilisateurs-api'
import { UtilisateurModal } from '../components/utilisateur-modal'
import type { Utilisateur } from '../types'
import { KeyRound, Pencil, RefreshCw, UserPlus, UsersRound } from 'lucide-react'

/**
 * Administration des comptes du cabinet.
 *
 * L'écran porte trois décisions métier qu'il vaut la peine de connaître :
 *
 * - **désactiver n'est pas supprimer.** Une consultation, un acte, une clôture de
 *   caisse référencent le compte. Désactiver coupe l'accès et conserve la trace ;
 *   supprimer effacerait l'auteur d'un acte médical ;
 * - **le mot de passe ne se modifie pas ici.** La réinitialisation renvoie un
 *   mot de passe temporaire affiché **une fois**, et coupe les sessions ouvertes ;
 * - **le dernier administrateur ne peut pas être neutralisé.** Un cabinet qui se
 *   verrouille n'a personne pour le rouvrir.
 */
export function UtilisateursPage() {
  const client = useQueryClient()
  const { addToast } = useToastStore()
  const cabinetActifId = useCabinetStore((etat) => etat.cabinetActifId)

  const [recherche, setRecherche] = useState('')
  const [roleFiltre, setRoleFiltre] = useState('')
  const [etatFiltre, setEtatFiltre] = useState('')
  const [modaleOuverte, setModaleOuverte] = useState(false)
  const [selectionne, setSelectionne] = useState<Utilisateur | null>(null)
  const [aDesactiver, setADesactiver] = useState<Utilisateur | null>(null)
  const [aReinitialiser, setAReinitialiser] = useState<Utilisateur | null>(null)
  const [motDePasseAffiche, setMotDePasseAffiche] = useState<string | null>(null)

  const liste = useQuery({
    queryKey: ['utilisateurs', recherche, roleFiltre, etatFiltre],
    queryFn: () =>
      utilisateursApi.lister({
        q: recherche.trim() || undefined,
        role: roleFiltre || undefined,
        actif: etatFiltre === '' ? undefined : etatFiltre === 'actif',
        limit: 100,
      }),
  })

  const desactiver = useMutation({
    mutationFn: (id: string) => utilisateursApi.desactiver(id),
    onSuccess: (u) => {
      addToast({
        type: 'success',
        message: `${u.prenom} ${u.nom} est désactivé. Ses données restent consultables.`,
      })
      setADesactiver(null)
      void client.invalidateQueries({ queryKey: ['utilisateurs'] })
    },
    onError: (e) => {
      const message = e instanceof ApiError ? e.message : 'Désactivation impossible.'
      addToast({ type: 'error', message })
    },
  })

  const reactiver = useMutation({
    mutationFn: (id: string) => utilisateursApi.modifier(id, { actif: true }),
    onSuccess: (u) => {
      addToast({ type: 'success', message: `${u.prenom} ${u.nom} est de nouveau actif.` })
      void client.invalidateQueries({ queryKey: ['utilisateurs'] })
    },
  })

  const reinitialiser = useMutation({
    mutationFn: (id: string) => utilisateursApi.reinitialiserMotDePasse(id),
    onSuccess: (rep) => {
      // Le mot de passe temporaire n'est renvoyé qu'une fois : c'est le dernier
      // moment où il est visible. Le dire est la moitié du travail.
      setMotDePasseAffiche(rep.temporaire)
      setAReinitialiser(null)
      void client.invalidateQueries({ queryKey: ['utilisateurs'] })
    },
  })

  const utilisateurs = liste.data?.items ?? []
  const chargement = liste.isPending
  const erreur = liste.error

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        titre="Utilisateurs"
        sousTitre="Comptes, rôles et accès au cabinet"
        onRefresh={() => void liste.refetch()}
      >
        <Button
          onClick={() => {
            setSelectionne(null)
            setModaleOuverte(true)
          }}
        >
          <UserPlus className="h-4 w-4" /> Ajouter un utilisateur
        </Button>
      </PageHeader>

      <Card>
        <CardContent className="pt-6">
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <Input
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher un nom, prénom ou email"
              aria-label="Rechercher un utilisateur"
            />
            <Select
              value={roleFiltre}
              onChange={(e) => setRoleFiltre(e.target.value)}
              aria-label="Filtrer par rôle"
            >
              <option value="">Tous les rôles</option>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </Select>
            <Select
              value={etatFiltre}
              onChange={(e) => setEtatFiltre(e.target.value)}
              aria-label="Filtrer par état"
            >
              <option value="">Tous les comptes</option>
              <option value="actif">Comptes actifs</option>
              <option value="inactif">Comptes désactivés</option>
            </Select>
          </div>

          {chargement ? (
            <Skeleton className="h-56 w-full" />
          ) : erreur ? (
            <EmptyState
              icon={UsersRound}
              titre="Comptes indisponibles"
              description="La liste des comptes n'a pas pu être chargée. Vérifiez que le backend est démarré puis réessayez."
            >
              <Button variant="outline" onClick={() => void liste.refetch()}>
                <RefreshCw className="h-4 w-4" /> Réessayer
              </Button>
            </EmptyState>
          ) : utilisateurs.length === 0 ? (
            <EmptyState
              icon={UsersRound}
              titre="Aucun compte trouvé"
              description={
                recherche || roleFiltre || etatFiltre
                  ? 'Aucun compte ne correspond à ces filtres.'
                  : 'Un cabinet a besoin d’au moins un administrateur. Ajoutez vos collaborateurs.'
              }
            >
              <Button variant="outline" onClick={() => void liste.refetch()}>
                <RefreshCw className="h-4 w-4" /> Rafraîchir
              </Button>
            </EmptyState>
          ) : (
            <Table>
              <THead>
                <TRow>
                  <TH>Utilisateur</TH>
                  <TH>Rôle</TH>
                  <TH>Site</TH>
                  <TH>État</TH>
                  <TH>Dernière connexion</TH>
                  <TH className="text-right">Actions</TH>
                </TRow>
              </THead>
              <TBody>
                {utilisateurs.map((u) => (
                  <TRow key={u.id} className={u.actif ? undefined : 'opacity-60'}>
                    <TD>
                      <span className="block font-medium">
                        {u.prenom} {u.nom}
                      </span>
                      <span className="block text-xs text-muted-foreground">{u.email}</span>
                    </TD>
                    <TD className="text-sm">{libelleRole(u.role)}</TD>
                    <TD className="text-sm text-muted-foreground">{u.cabinet_nom ?? '—'}</TD>
                    <TD>
                      <StatusBadge tone={u.actif ? 'success' : 'neutral'}>
                        {u.actif ? 'Actif' : 'Désactivé'}
                      </StatusBadge>
                    </TD>
                    <TD className="text-xs text-muted-foreground">
                      {u.dernier_login ? formatDateTimeFr(u.dernier_login) : 'Jamais'}
                    </TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setSelectionne(u)
                            setModaleOuverte(true)
                          }}
                          aria-label={`Modifier ${u.prenom} ${u.nom}`}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setAReinitialiser(u)}
                          aria-label={`Réinitialiser le mot de passe de ${u.prenom} ${u.nom}`}
                        >
                          <KeyRound className="h-3.5 w-3.5" />
                        </Button>
                        {u.actif ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setADesactiver(u)}
                            aria-label={`Désactiver ${u.prenom} ${u.nom}`}
                          >
                            Désactiver
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => reactiver.mutate(u.id)}
                            aria-label={`Réactiver ${u.prenom} ${u.nom}`}
                          >
                            Réactiver
                          </Button>
                        )}
                      </div>
                    </TD>
                  </TRow>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <UtilisateurModal
        key={selectionne?.id ?? 'nouveau'}
        isOpen={modaleOuverte}
        utilisateur={selectionne}
        cabinetId={cabinetActifId}
        onClose={() => setModaleOuverte(false)}
        onSuccess={() => void client.invalidateQueries({ queryKey: ['utilisateurs'] })}
      />

      <ConfirmDialog
        isOpen={Boolean(aDesactiver)}
        onClose={() => setADesactiver(null)}
        onConfirm={() => {
          if (aDesactiver) desactiver.mutate(aDesactiver.id)
        }}
        title={`Désactiver ${aDesactiver?.prenom ?? ''} ${aDesactiver?.nom ?? ''} ?`}
        message="Le compte ne pourra plus se connecter et ses sessions seront fermées. Les consultations, actes et encaissements qu’il a produits restent attribués à son nom : on ne supprime pas la trace d’un acte."
        confirmText="Désactiver"
        variant="danger"
      />

      <ConfirmDialog
        isOpen={Boolean(aReinitialiser)}
        onClose={() => setAReinitialiser(null)}
        onConfirm={() => {
          if (aReinitialiser) reinitialiser.mutate(aReinitialiser.id)
        }}
        title={`Réinitialiser le mot de passe de ${aReinitialiser?.prenom ?? ''} ?`}
        message="Un mot de passe temporaire sera généré et affiché une seule fois. Toutes les sessions ouvertes de ce compte seront fermées."
        confirmText="Réinitialiser"
        variant="warning"
      />

      <ModalMotDePasseTemporaire
        temporaire={motDePasseAffiche}
        nom={aReinitialiser ? `${aReinitialiser.prenom} ${aReinitialiser.nom}` : ''}
        onClose={() => setMotDePasseAffiche(null)}
      />
    </div>
  )
}

/**
 * Affichage unique du mot de passe temporaire.
 *
 * Il ne sera plus jamais consultable : le serveur n'en garde que l'empreinte.
 * L'avertir est aussi important que de l'afficher.
 */
function ModalMotDePasseTemporaire({
  temporaire,
  nom,
  onClose,
}: {
  temporaire: string | null
  nom: string
  onClose: () => void
}) {
  const { addToast } = useToastStore()

  return (
    <Modal
      isOpen={temporaire !== null}
      onClose={onClose}
      title={`Mot de passe provisoire${nom ? ` — ${nom}` : ''}`}
      description="Communiquez-le maintenant : il ne sera plus jamais affiché."
      maxWidth="md"
    >
      <div className="space-y-4">
        <code className="block select-all rounded-xl2 border bg-surface px-4 py-3 text-center font-mono text-lg tracking-wider">
          {temporaire}
        </code>
        <p className="text-xs text-muted-foreground">
          Seul son empreinte est conservée. Demandez à l’utilisateur de le changer à sa
          première connexion.
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              if (temporaire) {
                void navigator.clipboard?.writeText(temporaire)
                addToast({ type: 'success', message: 'Mot de passe copié.' })
              }
            }}
          >
            Copier
          </Button>
          <Button onClick={onClose}>J'ai noté</Button>
        </div>
      </div>
    </Modal>
  )
}
