import { useQuery } from '@tanstack/react-query'
import { UserPlus, UsersRound } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { utilisateursApi } from '../services/utilisateurs-api'

/**
 * Gestion des utilisateurs du cabinet.
 *
 * ## Pourquoi cette page affiche un état « indisponible »
 *
 * Le backend n'expose **aucune** route utilisateur (constaté le 4 octobre 2026
 * sur le schéma OpenAPI). Un compte n'existe qu'implicitement, à la
 * provisionnement d'une société : un cabinet ne peut donc pas ajouter de
 * secrétaire, de comptable ni de praticien supplémentaire.
 *
 * Plutôt qu'un tableau vide qui ferait croire à un bug — ou qu'une liste
 * fictive, qui ferait planer un risque fictif — l'écran dit la vérité et
 * indique ce qu'il faut livrer. L'interface de saisie sera branchée le jour où
 * l'API existera ; c'est le seul écran où une page « pas encore » se justifie :
 * il n'y a aucun moyen de faire autrement côté client.
 */
export function UtilisateursPage() {
  const { isError } = useQuery({
    queryKey: ['utilisateurs'],
    queryFn: () => utilisateursApi.lister({ limit: 50 }),
    retry: false,
  })

  const indisponible = isError

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        titre="Utilisateurs"
        sousTitre="Comptes, rôles et accès au cabinet"
      />

      <Card>
        <CardContent className="pt-6">
          <EmptyState
            icon={indisponible ? UserPlus : UsersRound}
            titre={
              indisponible
                ? "Module Utilisateurs non disponible"
                : 'Aucun utilisateur'
            }
            description={
              indisponible
                ? "Le backend n'expose pas encore les endpoints /utilisateurs. Un compte n'est créé qu'à la provisionnement d'une société : impossible d'ajouter une secrétaire, un comptable ou un praticien supplémentaire. L'interface de saisie sera branchée dès que l'API existera."
                : 'Aucun compte pour le moment.'
            }
          />

          {indisponible && (
            <div className="mt-4 rounded-xl2 border border-warning/30 bg-warning/5 p-4">
              <p className="text-sm font-semibold">Ce qu'il manque côté API</p>
              <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
                {[
                  'GET /utilisateurs — liste paginée, filtrable (rôle, actif, recherche)',
                  'POST /utilisateurs — création avec rôle et mot de passe initial',
                  'PATCH /utilisateurs/{id} — identité, rôle, téléphone',
                  'POST /utilisateurs/{id}/mot-de-passe — réinitialisation',
                  'DELETE /utilisateurs/{id} — désactivation (jamais de suppression physique)',
                  'Permissions ADMIN:USER:* dans la matrice RBAC',
                ].map((ligne) => (
                  <li key={ligne} className="flex gap-2">
                    <span aria-hidden className="text-warning">
                      •
                    </span>
                    <span className="font-mono">{ligne}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 border-t border-warning/20 pt-2 text-[11px] text-muted-foreground">
                TODO(backend): module Utilisateurs — P0. Voir PLAN_RESTE_A_FAIRE.md §2 B10.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}