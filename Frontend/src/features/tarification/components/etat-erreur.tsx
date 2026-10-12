import { RefreshCw, WifiOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { ApiError } from '@/lib/api'

/**
 * Code stable renvoyé par le serveur quand le cabinet est en retard de
 * migrations. Il est defini dans `Backend/src/core/schema_perime.py` ; un test
 * verifie que les deux cotes nomment la meme constante.
 */
export const CODE_SCHEMA_EN_RETARD = 'SCHEMA_EN_RETARD'

/**
 * Message affiché quand le cabinet n'a pas encore le schéma du module.
 *
 * **Pourquoi une phrase aussi explicite.** Un 503 sans raison lisible se
 * traduit par « le service ne répond pas » : l'utilisateur réessaie, puis
 * appelle le support, et personne ne peut agir tant que le module n'est pas
 * installé pour ce cabinet. Nommer la mise à jour du schéma indique
 * immédiatement à qui il s'adresser.
 */
export const MESSAGE_SCHEMA_EN_RETARD =
  "Ce module n'est pas encore disponible pour votre cabinet : une mise à jour du schéma est nécessaire. Contactez votre administrateur."

/** Message de repli : le serveur a échoué sans raison identifiable. */
export const MESSAGE_ERREUR_GENERIQUE =
  "La liste n'a pas pu être chargée. Vérifiez que le backend répond puis réessayez."

/** L'erreur est-elle un écart de schéma, plutôt qu'une panne ? */
export function estSchemaEnRetard(error: unknown): boolean {
  return error instanceof ApiError && error.code === CODE_SCHEMA_EN_RETARD
}

type EtatErreurModuleProps = {
  error: unknown
  /** Ce que le module phenotypesait : nomme l'ecran dans le message de repli. */
  libelle: string
  onReessayer: () => void
}

/**
 * Etat d'erreur d'un module de tarification.
 *
 * **Aucun ecran vide.** Une liste vide ferait croire que le cabinet n'a rien
 * declare, alors que la reponse est une erreur : l'utilisateur ne voit pas ce
 * qui s'est passe et ne peut rien signaler.
 *
 * **Aucun bouton d'ecriture.** Le module n'existe pas pour ce cabinet : proposer
 * « Ajouter » menait a une operation qui echouerait, ou pire, a une saisie
 * silencieusement perdue.
 */
export function EtatErreurModule({ error, libelle, onReessayer }: EtatErreurModuleProps) {
  if (estSchemaEnRetard(error)) {
    return (
      <EmptyState icon={WifiOff} titre="Module non disponible" description={MESSAGE_SCHEMA_EN_RETARD}>
        <Button variant="outline" onClick={onReessayer}>
          <RefreshCw className="h-4 w-4" /> Réessayer
        </Button>
      </EmptyState>
    )
  }

  return (
    <EmptyState
      icon={WifiOff}
      titre={`${libelle} indisponible`}
      description={MESSAGE_ERREUR_GENERIQUE}
    >
      <Button variant="outline" onClick={onReessayer}>
        <RefreshCw className="h-4 w-4" /> Réessayer
      </Button>
    </EmptyState>
  )
}