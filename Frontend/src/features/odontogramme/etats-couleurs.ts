/**
 * Couleurs des états dentaires.
 *
 * Module séparé de `odontogramme-svg.tsx` à dessein : ce fichier n'exporte
 * que des composants. Mélanger composants et fonctions dans un export casse
 * le Fast Refresh de Vite — l'erreur est silencieuse, l'éditeur recharge mal.
 *
 * ## Pourquoi la couleur vient du backend
 *
 * `GET /odontogramme/referentiel/etats` renvoie ~40 états, chacun avec sa
 * couleur : carie débutante, carie avancée, obturation amalgame, bridge pilier,
 * prothèse totale… Ces teintes sont une **convention de la cartographie
 * dentaire**, pas un choix décoratif. Les ramener à quatre couleurs de
 * thème (`--danger`, `--accent-blue`, `--warning`, `--success`) peindrait
 * huit couronnes et trois bridges de la même teinte : une perte
 * d'information clinique sur l'écran le plus consulté de l'application.
 *
 * Un aplat coloré n'a pas le même problème qu'un texte : bordé, il reste
 * lisible sur fond clair comme sur fond sombre. La bascule de thème n'a donc
 * pas à le piloter.
 *
 * Les tokens ci-dessous ne servent que de **repli**, quand le backend n'en
 * fournit pas — et ils garantissent qu'aucune couleur ne sort du thème.
 *
 * La même fonction sert au dessin des dents ET à la légende : les deux
 * affichent nécessairement la même teinte.
 */

const COULEUR_CARIE = 'hsl(var(--danger))'
const COULEUR_SOIGNEE = 'hsl(var(--accent-blue))'
const COULEUR_COURONNE = 'hsl(var(--warning))'
/** Dent saine : vert sémantique. */
export const COULEUR_SAINE = 'hsl(var(--success))'
/** Croix de dent absente : gris neutre du thème. */
export const COULEUR_ABSENTE = 'hsl(var(--muted-foreground))'

/**
 * Couleur d'un état dentaire.
 *
 * @param etat        Code de l'état (`CARIE_DEBUTANTE`, `COURONNE`…).
 * @param couleurApi  Couleur de référence fournie par le backend, si elle
 *                    existe. Prioritaire : c'est elle qui distingue les états
 *                    entre eux. Les tokens ne prennent le relais que si elle
 *                    est absente.
 */
export function couleurEtatDentaire(
  etat: string | null | undefined,
  couleurApi?: string | null,
): string {
  if (etat && couleurApi) return couleurApi
  if (!etat) return COULEUR_SAINE
  if (etat.includes('ABSENTE') || etat.includes('ABSENT')) return COULEUR_ABSENTE
  if (etat.includes('CARIE')) return COULEUR_CARIE
  if (etat.includes('SOIGNEE') || etat.includes('OBTUR') || etat.includes('TRAITEE')) {
    return COULEUR_SOIGNEE
  }
  if (etat.includes('COURONNE') || etat.includes('BRIDGE') || etat.includes('PROTHESE')) {
    return COULEUR_COURONNE
  }
  return COULEUR_SAINE
}