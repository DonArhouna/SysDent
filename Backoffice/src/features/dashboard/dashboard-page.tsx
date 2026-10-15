import { useEffect } from 'react'
import {
  Activity,
  AlertTriangle,
  Building2,
  CalendarClock,
  Gauge,
  Megaphone,
  ScrollText,
  TrendingUp,
  UserX,
} from 'lucide-react'

import { StatCard, type AccentStat } from '@/components/dashboard/stat-card'
import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { StatusBadge, type StatusTone } from '@/components/ui/status-badge'
import { possedePermission, useAuthStore } from '@/stores/auth-store'
import { ProchainsRendezVous } from '@/features/agenda/cartes-rendez-vous'
import { PERMISSIONS } from '@/lib/plateforme'
import { useDashboardStore, type VueDashboard } from './dashboard-store'

/**
 * Tableau de bord de la plateforme.
 *
 * **Un seul appel.** Le store fetching déjà tout en une requête : l'écran ne
 * refait pas l'agrégation, il ne fait que la présenter. Quatre appels pour
 * quatre cartes payeraient quatre fois la latence d'une agrégation serveur.
 *
 * **Le chiffre qui ment.** Un ecran qui affiche « 42 cabinets ACTIVE » sans
 * dire combien ont une base laisse croire que 42 cabinets fonctionnent. Un
 * dossier ACTIVE sans base a un login casse. Chaque statut affiche donc son
 * total **et** sa part sans base, sur deux lignes distinctes, jamais dans une
 * meme pastille.
 *
 * **Aucun secret, aucune donnee clinique** : l'API ne les fournit pas, et rien
 * ici n'en invente.
 */

/**
 * Statuts métier vers libellé et ton.
 *
 * Une correspondance, pas une couleur en dur : le ton est celui du composant
 * `StatusBadge`, déjà défini par les tokens. Un statut inconnu de cette table
 * s'affiche tel quel le serveur l'a nommé, plutôt que d'être masqué.
 */
const STATUTS: Record<string, { texte: string; ton: StatusTone }> = {
  ACTIVE: { texte: 'Actif', ton: 'success' },
  TRIAL: { texte: 'Essai', ton: 'info' },
  PROVISIONING: { texte: 'En création', ton: 'info' },
  SUSPENDED: { texte: 'Suspendu', ton: 'warning' },
  CANCELLED: { texte: 'Résilié', ton: 'danger' },
  EXPIRED: { texte: 'Expiré', ton: 'danger' },
}

const NON_DISPONIBLE = 'Non disponible'

function libelleStatut(statut: string): { texte: string; ton: StatusTone } {
  return STATUTS[statut] ?? { texte: statut, ton: 'neutral' }
}

function nombre(valeur: number | null | undefined): string {
  return typeof valeur === 'number' && Number.isFinite(valeur)
    ? valeur.toLocaleString('fr-FR')
    : NON_DISPONIBLE
}

/**
 * Une liste de cabinets. **Aucune section ne casse la page** quand ses données
 * manquent : une liste absente affiche son message, pas une erreur, et ne
 * jette pas le reste du tableau de bord avec elle.
 */
function ListeCabinets({
  titre,
  icone: Icone,
  items,
}: {
  titre: string
  icone: typeof Activity
  items: VueDashboard['essais_proches_expiration']
}) {
  const liste = Array.isArray(items) ? items : []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icone className="h-4 w-4 text-muted-foreground" aria-hidden />
          {titre}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {liste.length === 0 ? (
          <p className="text-sm text-muted-foreground">{NON_DISPONIBLE}</p>
        ) : (
          <ul className="divide-y divide-border">
            {liste.map((item) => (
              <li
                key={item.tenant_id}
                className="flex items-center justify-between gap-3 py-2"
              >
                <span className="min-w-0 truncate text-sm font-medium">
                  {item.nom}
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  {item.plan ? (
                    <span className="text-xs text-muted-foreground">{item.plan}</span>
                  ) : null}
                  <StatusBadge tone={libelleStatut(item.statut).ton}>
                    {libelleStatut(item.statut).texte}
                  </StatusBadge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function ContenuDashboard() {
  const etat = useDashboardStore((s) => s.etat)
  const vue = useDashboardStore((s) => s.vue)
  const messageErreur = useDashboardStore((s) => s.messageErreur)
  const charger = useDashboardStore((s) => s.charger)
  const reessayer = useDashboardStore((s) => s.reessayer)
  const aRegenerer = useAuthStore((s) => s.profil?.codes_secours_a_regenerer)
  const peutVoirAgenda = useAuthStore((s) => possedePermission(s.profil, PERMISSIONS.agendaLire))

  useEffect(() => {
    void charger()
  }, [charger])

  if (etat === 'chargement') {
    return (
      <>
        <PageHeader titre="Tableau de bord" sousTitre="Vue d'ensemble de la plateforme" />
        <GrilleKpi vue={null} chargement />
      </>
    )
  }

  // **Une panne est une panne.** Ni zero, ni carte vide, ni « aucune donnee » :
  // l'ecran dirait que la plateforme n'a aucun cabinet, ce qui est un autre
  // mensonge. Le bouton « Reessayer » est donc obligatoire ici, et le store
  // expose justement `reessayer` pour lui.
  if (etat === 'erreur') {
    return (
      <>
        <PageHeader titre="Tableau de bord" sousTitre="Vue d'ensemble de la plateforme" />
        <EmptyState
          icon={AlertTriangle}
          titre="Le tableau de bord n'a pas pu être chargé"
          description={messageErreur ?? 'Le serveur ne répond pas.'}
        >
          <Button onClick={() => void reessayer()}>Réessayer</Button>
        </EmptyState>
      </>
    )
  }

  if (etat === 'vide' || !vue) {
    return (
      <>
        <PageHeader titre="Tableau de bord" sousTitre="Vue d'ensemble de la plateforme" />
        <EmptyState
          icon={Building2}
          titre="Aucun cabinet"
          description="La plateforme n'a encore aucun cabinet enregistré."
        />
      </>
    )
  }

  return (
    <>
      <PageHeader
        titre="Tableau de bord"
        sousTitre="Vue d'ensemble de la plateforme"
        onRefresh={() => void charger()}
      />

      {aRegenerer ? (
        <div
          role="status"
          className="mb-6 rounded-xl2 border border-warning/30 bg-warning/10 px-4 py-3 text-sm"
        >
          <strong className="font-semibold">Codes de secours à régénérer.</strong>{' '}
          Votre compte n'a aucun code utilisable : sans eux, un second facteur
          bloqué vous laisse sans aucune voie de recours.
        </div>
      ) : null}

      <GrilleKpi vue={vue} />

      {/* Garde AVANT le composant : il appelle des hooks de requête. */}
      {peutVoirAgenda && (
        <div className="mt-6">
          <ProchainsRendezVous />
        </div>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <ListeCabinets
          titre="Essais proches de l'expiration"
          icone={CalendarClock}
          items={vue.essais_proches_expiration}
        />
        <ListeCabinets
          titre="Proches de leurs quotas"
          icone={Gauge}
          items={vue.proches_du_quota}
        />
        <ListeCabinets
          titre="Inactifs depuis 30 jours"
          icone={UserX}
          items={vue.inactifs_30j}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-muted-foreground" aria-hidden />
              Santé de la plateforme
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/*
              `sante` est declare `dict` cote schema : TypeScript le voit
              comme un index de `{}`. On ne fait donc aucune hypothese sur le
              type de la valeur - un objet affiche « Non disponible » plutot
              que « [object Object] » a l'ecran.
            */}
            <p className="text-sm">
              État global :{' '}
              <StatusBadge
                tone={
                  typeof vue.sante?.statut === 'string' && vue.sante.statut === 'ok'
                    ? 'success'
                    : 'warning'
                }
              >
                {typeof vue.sante?.statut === 'string'
                  ? vue.sante.statut
                  : NON_DISPONIBLE}
              </StatusBadge>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Megaphone className="h-4 w-4 text-muted-foreground" aria-hidden />
              Annonces
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!vue.annonces || vue.annonces.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune annonce active.</p>
            ) : (
              <ul className="divide-y divide-border">
                {vue.annonces.map((annonce) => (
                  <li key={annonce.id} className="py-2">
                    <p className="text-sm font-medium">{annonce.titre}</p>
                    <p className="text-xs text-muted-foreground">{annonce.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ScrollText className="h-4 w-4 text-muted-foreground" aria-hidden />
              Dernières actions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!vue.audit || vue.audit.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucune action enregistrée.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {vue.audit.map((entree) => (
                  <li key={entree.id} className="py-2">
                    <p className="text-sm font-medium">{entree.action}</p>
                    <p className="text-xs text-muted-foreground">
                      {entree.acteur_email ?? NON_DISPONIBLE}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}

/**
 * Le tableau de bord, dans le layout applicatif.
 *
 * **L'oubli qui a coûté une session.** `AppShell` porte la sidebar, la navbar
 * et la bascule de thème. L'écran provisoire `/dashboard` s'en enveloppait
 * lui-même ; la page qui l'a remplacé s'en oubliait, et le tableau de bord
 * s'affichait nu — sans aucune navigation. Le type ne voyait rien : le composant
 * compilait, les tests passaient, et l'utilisateur, lui, n'avait plus de moyen
 * de quitter la page.
 *
 * C'est pourquoi le test exige la presence de la sidebar et de la navbar : une
 * page qui rend son contenu n'est pas une page qui rend dans l'application.
 */
export function DashboardPage() {
  return (
    <AppShell>
      <ContenuDashboard />
    </AppShell>
  )
}

/**
 * Les cartes KPI.
 *
 * **Le total et la part sans base sont deux lignes, jamais une.** Les fusionner
 * en « 42 dont 3 casses »irait de l'afficher comme une proportion banale ;
 * les empiler les rend impossibles a confondre.
 */
function GrilleKpi({
  vue,
  chargement,
}: {
  vue: VueDashboard | null
  chargement?: boolean
}) {
  const parStatutBase = vue?.par_statut_base ?? {}
  const statuts = Object.keys(parStatutBase)

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Cabinets au total"
        value={nombre(vue?.total_cabinets)}
        detail="Tous statuts confondus"
        icon={Building2}
        accent="blue"
        chargement={chargement}
      />
      <StatCard
        label="Base absente"
        value={nombre(vue?.total_bases_absentes)}
        detail="Dossiers sans base de données"
        icon={AlertTriangle}
        accent="orange"
        hint={
          vue && vue.total_bases_absentes > 0
            ? 'Le login de ces cabinets échoue'
            : undefined
        }
        chargement={chargement}
      />
      <StatCard
        label="Nouveaux sur 30 jours"
        value={nombre(vue?.nouveaux_30j)}
        detail="Créés dans la période"
        icon={TrendingUp}
        accent="green"
        chargement={chargement}
      />
      <StatCard
        label="Essai restant"
        value={nombre(vue?.essais_restants_jours)}
        detail="Jours avant expiration"
        icon={CalendarClock}
        accent="purple"
        chargement={chargement}
      />

      {statuts.map((statut, index) => {
        const detail = parStatutBase[statut]
        if (!detail) return null
        const accents: AccentStat[] = ['green', 'blue', 'purple', 'orange']
        const absentes = detail.dont_base_absente > 0
        return (
          <StatCard
            key={statut}
            label={libelleStatut(statut).texte}
            value={nombre(detail.total)}
            detail={
              absentes
                ? `${nombre(detail.dont_base_absente)} sans base`
                : 'Toutes les bases sont présentes'
            }
            // Pas de `hint` ici : le composant affiche `hint ?? detail`, donc
            // un hint remplacerait le nombre. Or le nombre est precisement ce
            // que cette carte doit montrer. La consequence ("login casse") est
            // deja portee par la carte "Base absente" plus haut.
            icon={Building2}
            accent={accents[index % accents.length]}
            chargement={chargement}
          />
        )
      })}

      {!chargement && statuts.length === 0 ? (
        <Card className="sm:col-span-2 xl:col-span-4">
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Répartition par statut : {NON_DISPONIBLE}
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}