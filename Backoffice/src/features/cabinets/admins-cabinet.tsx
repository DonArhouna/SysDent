import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AtSign, KeyRound, Link2, ShieldOff, UserCog } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Modal } from '@/components/ui/modal'
import { MotifDialog } from '@/components/ui/motif-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { usePermission } from '@/guards/can'
import { api, type ApiReponse } from '@/lib/api'
import { dateHeure, messageErreur } from '@/lib/libelles'
import { PERMISSIONS, type ActionAccesAdmin, type AdminCabinet } from '@/lib/plateforme'
import { toast } from '@/stores/toast-store'

type Action = 'lien' | 'temporaire' | 'deux_facteurs'

const ACTIONS: Record<Action, { titre: string; description: string; libelle: string; danger?: boolean }> = {
  lien: {
    titre: 'Envoyer un lien de réinitialisation',
    description:
      "La personne reçoit un e-mail et choisit elle-même son nouveau mot de passe. L'ancien ne fonctionne plus et ses sessions sont coupées.",
    libelle: 'Envoyer le lien',
  },
  temporaire: {
    titre: 'Générer un mot de passe temporaire',
    description:
      "À n'utiliser que si la personne n'a pas accès à ses e-mails. Le mot de passe s'affiche une seule fois ; elle devra le changer à sa prochaine connexion.",
    libelle: 'Générer',
    danger: true,
  },
  deux_facteurs: {
    titre: 'Réinitialiser la double authentification',
    description:
      'Pour un téléphone perdu. La 2FA et les codes de secours sont effacés ; la personne la reconfigurera à sa prochaine connexion.',
    libelle: 'Réinitialiser',
    danger: true,
  },
}

function etat(a: AdminCabinet): { texte: string; ton: 'success' | 'warning' | 'neutral' | 'info' } {
  if (!a.actif) return { texte: 'Désactivé', ton: 'neutral' }
  if (a.activation_requise) return { texte: "En attente d'activation", ton: 'warning' }
  if (a.doit_changer_mot_de_passe) return { texte: 'Mot de passe temporaire', ton: 'info' }
  return { texte: 'Actif', ton: 'success' }
}

/**
 * Administrateurs d'un cabinet et dépannage de leur accès.
 *
 * La console ne fixe jamais un mot de passe choisi par un agent : lien de
 * réinitialisation (recommandé), mot de passe temporaire généré par le serveur
 * (affiché une fois), ou remise à zéro de la 2FA. Motif obligatoire, sessions
 * coupées, trace dans les deux journaux.
 */
export function AdminsCabinet({ tenantId }: { tenantId: string }) {
  const client = useQueryClient()
  const peutAgir = usePermission(PERMISSIONS.cabinetsAcces)
  const [cible, setCible] = useState<{ admin: AdminCabinet; action: Action } | null>(null)
  const [temporaire, setTemporaire] = useState<{ email: string; mdp: string } | null>(null)
  const [cibleEmail, setCibleEmail] = useState<AdminCabinet | null>(null)
  const [nouvelEmail, setNouvelEmail] = useState('')

  const changerEmail = useMutation({
    mutationFn: ({ admin, motif }: { admin: AdminCabinet; motif: string }) => {
      const email = nouvelEmail.trim().toLowerCase()
      // Contrôle de forme seulement : le serveur valide vraiment (domaines réservés compris).
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error('Adresse e-mail invalide.')
      return api.post<ApiReponse<AdminCabinet>>(`/platform/tenants/${tenantId}/administrateurs/${admin.id}/email`, {
        nouvel_email: email,
        motif,
      })
    },
    onSuccess: (r) => {
      void client.invalidateQueries({ queryKey: ['cabinet', tenantId, 'administrateurs'] })
      toast.success(`Adresse changée : le lien d'activation est parti à ${r.data.email}.`)
    },
    onError: () => void client.invalidateQueries({ queryKey: ['cabinet', tenantId, 'administrateurs'] }),
  })

  const admins = useQuery({
    queryKey: ['cabinet', tenantId, 'administrateurs'],
    queryFn: () => api.get<ApiReponse<AdminCabinet[]>>(`/platform/tenants/${tenantId}/administrateurs`),
  })

  const agir = useMutation({
    mutationFn: ({ admin, action, motif }: { admin: AdminCabinet; action: Action; motif: string }) =>
      api.post<ApiReponse<ActionAccesAdmin>>(`/platform/tenants/${tenantId}/administrateurs/${admin.id}/acces`, { action, motif }),
    onSuccess: (r, { admin, action }) => {
      void client.invalidateQueries({ queryKey: ['cabinet', tenantId, 'administrateurs'] })
      if (action === 'temporaire' && r.data.mot_de_passe_temporaire) {
        setTemporaire({ email: admin.email, mdp: r.data.mot_de_passe_temporaire })
      } else {
        toast.success(r.message ?? 'Action enregistrée.')
      }
    },
    // Le compte a pu être modifié même si l'e-mail n'est pas parti : on relit.
    onError: () => void client.invalidateQueries({ queryKey: ['cabinet', tenantId, 'administrateurs'] }),
  })

  const liste = admins.data?.data ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <UserCog className="h-4 w-4 text-muted-foreground" aria-hidden />
          Administrateurs du cabinet
        </CardTitle>
      </CardHeader>
      <CardContent>
        {admins.isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : admins.isError ? (
          <p className="text-sm text-danger">{messageErreur(admins.error)}</p>
        ) : liste.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun administrateur.</p>
        ) : (
          <ul className="divide-y divide-border">
            {liste.map((a) => {
              const e = etat(a)
              return (
                <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="font-medium">{`${a.prenom} ${a.nom}`}</p>
                    <p className="truncate text-sm text-muted-foreground">{a.email}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      <StatusBadge tone={e.ton}>{e.texte}</StatusBadge>
                      <StatusBadge tone={a.deux_facteurs ? 'success' : 'warning'}>
                        {a.deux_facteurs ? '2FA active' : '2FA à configurer'}
                      </StatusBadge>
                      Dernière connexion : {dateHeure(a.dernier_login)}
                    </p>
                  </div>
                  {peutAgir && (
                    <div className="flex flex-wrap gap-1.5">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setNouvelEmail('')
                          setCibleEmail(a)
                        }}
                      >
                        <AtSign aria-hidden />
                        Changer l'e-mail
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setCible({ admin: a, action: 'lien' })}>
                        <Link2 aria-hidden />
                        Lien de réinitialisation
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setCible({ admin: a, action: 'temporaire' })}>
                        <KeyRound aria-hidden />
                        Mot de passe temporaire
                      </Button>
                      {a.deux_facteurs && (
                        <Button size="sm" variant="ghost" onClick={() => setCible({ admin: a, action: 'deux_facteurs' })}>
                          <ShieldOff aria-hidden />
                          Réinitialiser la 2FA
                        </Button>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>

      {cible && (
        <MotifDialog
          open
          onClose={() => setCible(null)}
          titre={`${ACTIONS[cible.action].titre} — ${cible.admin.prenom} ${cible.admin.nom}`}
          description={ACTIONS[cible.action].description}
          libelleConfirmer={ACTIONS[cible.action].libelle}
          variante={ACTIONS[cible.action].danger ? 'danger' : 'primary'}
          onConfirm={(motif) => agir.mutateAsync({ ...cible, motif })}
        />
      )}

      {cibleEmail && (
        <MotifDialog
          open
          onClose={() => setCibleEmail(null)}
          titre={`Changer l'e-mail de connexion — ${cibleEmail.prenom} ${cibleEmail.nom}`}
          description={`Adresse actuelle : ${cibleEmail.email}. Un lien d'activation partira à la nouvelle adresse ; la personne y choisira son mot de passe. D'ici là, elle ne pourra plus se connecter.`}
          libelleConfirmer="Changer l'adresse"
          onConfirm={(motif) => changerEmail.mutateAsync({ admin: cibleEmail, motif })}
        >
          <Input
            label="Nouvelle adresse de connexion"
            type="email"
            required
            value={nouvelEmail}
            onChange={(e) => setNouvelEmail(e.target.value)}
            placeholder="prenom.nom@exemple.sn"
          />
        </MotifDialog>
      )}

      {/* Affiché UNE fois : ni le serveur ni l'écran ne pourront le remontrer. */}
      <Modal open={temporaire !== null} onClose={() => setTemporaire(null)} title="Mot de passe temporaire" maxWidth="md">
        {temporaire && (
          <div className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              Communiquez-le à <strong className="text-foreground">{temporaire.email}</strong> par un canal sûr
              (de vive voix de préférence). Il ne sera plus jamais affiché, et la personne devra le changer à sa
              prochaine connexion.
            </p>
            <p className="select-all rounded-xl border bg-muted/40 p-3 text-center font-mono text-lg tracking-wider">{temporaire.mdp}</p>
            <div className="flex justify-end">
              <Button onClick={() => setTemporaire(null)}>J'ai transmis le mot de passe</Button>
            </div>
          </div>
        )}
      </Modal>
    </Card>
  )
}
