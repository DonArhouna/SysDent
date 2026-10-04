import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Banknote,
  Building2,
  FileText,
  LifeBuoy,
  Receipt,
  Sparkles,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TBody, TD, TH, THead, TRow } from '@/components/ui/table'
import { StatCard, type AccentStat } from '@/components/dashboard/stat-card'
import { PageHeader } from '@/components/ui/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { StatusBadge } from '@/components/ui/status-badge'
import { FloatingActionButton } from '@/components/ui/floating-action-button'

/** Ligne du journal de caisse (cf. PaiementService.journal_caisse). */
interface LigneCaisse {
  id: string
  recu_numero: string
  facture_numero: string
  patient: string
  montant: string
  mode: string
  reference: string | null
  date_paiement: string
}

interface Cabinet {
  id: string
  nom: string
  ville: string | null
  actif: boolean
  nb_salles: number
  nb_fauteuils_actifs: number
  nb_praticiens_actifs: number
}

const MODES_CAISSE: Record<string, 'info' | 'success' | 'warning' | 'purple' | 'neutral'> = {
  ESPECES: 'success',
  MOBILE_MONEY: 'info',
  CARTE_BANCAIRE: 'purple',
  VIREMENT: 'neutral',
  CHEQUE: 'warning',
  ASSURANCE: 'neutral',
}

/* Libellés d'interface (i18n de fait) — seules chaînes statiques tolérées. */
const ASTUCES: string[] = [
  "Astuce : Ctrl + K lance une recherche globale depuis n'importe quelle page.",
  "Astuce : cliquez sur une dent de l'odontogramme pour saisir son état et l'historique.",
  'Astuce : le sélecteur de cabinet en haut filtre les données par site.',
  'Astuce : « Voir tout » ouvre le journal de caisse complet avec filtres.',
]

/**
 * Astuce du jour. L'index est figé pour la session (et non recalculé à chaque
 * rendu) : l'astuce affichée reste stable tant que l'onglet est ouvert.
 */
const INDEX_ASTUCE_DU_JOUR = new Date().getDate() % ASTUCES.length

function AstuceJour() {
  const index = INDEX_ASTUCE_DU_JOUR
  return (
    <div
      role="note"
      className="flex items-start gap-3 rounded-xl2 border border-primary/25 bg-primary/5 px-5 py-4 text-sm text-foreground"
    >
      <span aria-hidden className="icon-chip mt-0.5 h-8 w-8 bg-primary/15 text-primary">
        <Sparkles className="h-4 w-4" />
      </span>
      <p className="leading-relaxed">{ASTUCES[index]}</p>
    </div>
  )
}

/** Menu d'aide du FAB : raccourcis et contact support. */
function FabAide() {
  const [ouvert, setOuvert] = useState(false)

  return (
    <>
      {ouvert && (
        <div
          role="dialog"
          aria-label="Aide et assistance"
          className="floating-panel fixed bottom-20 right-5 z-40 w-72 rounded-xl2 p-4 animate-in fade-in slide-in-from-bottom-2 duration-150"
        >
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold">Aide & assistance</p>
            <button
              type="button"
              onClick={() => setOuvert(false)}
              aria-label="Fermer l'aide"
              className="focus-ring rounded-md p-1 text-muted-foreground hover:bg-muted"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            {ASTUCES.map((astuce) => (
              <li key={astuce}>{astuce.replace(/^Astuce : /, '')}</li>
            ))}
          </ul>
          <p className="mt-3 border-t border-border pt-2 text-[11px] text-muted-foreground">
            Support : support@sysdent.pro
          </p>
        </div>
      )}
      <FloatingActionButton
        onClick={() => setOuvert((v) => !v)}
        label="Aide & assistance"
        badge
      >
        <LifeBuoy className="h-5 w-5" aria-hidden />
      </FloatingActionButton>
    </>
  )
}

/** Date du jour (AAAA-MM-JJ), figée pour la session de l'onglet. */
const AUJOURDHUI = new Date().toISOString().slice(0, 10)

const formatFcfa = (valeur: number) =>
  new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(valeur)

/** Charge l'API, puis `/factures` (émises), `/devis` (envoyés), caisse et cabinets. */
function useStatsCabinet() {
  const aujourdhui = AUJOURDHUI

  const patients = useQuery({
    queryKey: ['stats', 'patients'],
    queryFn: () => api.get<PageReponse<unknown>>('/patients?page=1&limit=1'),
  })
  const facturesEmises = useQuery({
    queryKey: ['stats', 'factures-emises'],
    queryFn: () => api.get<PageReponse<unknown>>('/factures?statut=EMISE&limit=1'),
  })
  const devisEnvoyes = useQuery({
    queryKey: ['stats', 'devis-envoyes'],
    queryFn: () => api.get<PageReponse<unknown>>('/devis?statut=ENVOYE&limit=1'),
  })
  const caisseJour = useQuery({
    queryKey: ['stats', 'caisse-jour', aujourdhui],
    queryFn: () =>
      api.get<PageReponse<LigneCaisse>>(
        `/factures/journal-caisse?date_debut=${aujourdhui}&date_fin=${aujourdhui}&limit=100`,
      ),
  })

  return { patients, facturesEmises, devisEnvoyes, caisseJour, aujourdhui }
}

export function DashboardPage() {
  const queryClient = useQueryClient()
  const { patients, facturesEmises, devisEnvoyes, caisseJour } = useStatsCabinet()

  const derniers = useQuery({
    queryKey: ['stats', 'derniers-paiements'],
    queryFn: () => api.get<PageReponse<LigneCaisse>>('/factures/journal-caisse?limit=6'),
  })

  const cabinets = useQuery({
    queryKey: ['stats', 'cabinets'],
    queryFn: () => api.get<ApiReponse<Cabinet[]>>('/cabinets'),
  })

  const encaisseJour = useMemo(() => {
    const items = caisseJour.data?.items ?? []
    return items.reduce((somme, ligne) => somme + Number(ligne.montant), 0)
  }, [caisseJour.data])

  const chiffre = (reponse: PageReponse<unknown> | undefined, fallback = '—') =>
    reponse?.meta?.total_records !== undefined
      ? formatFcfa(reponse.meta.total_records)
      : fallback

  const actualiser = () => {
    void queryClient.invalidateQueries({ queryKey: ['stats'] })
  }

  const cartes: Array<{
    label: string
    value: string
    detail: string
    accent: AccentStat
    hint?: string
    icon: LucideIcon
    chargement?: boolean
  }> = [
    {
      label: 'Total patients',
      value: chiffre(patients.data),
      detail: 'Dossiers enregistrés',
      accent: 'blue',
      icon: Users,
      hint: patients.isError ? 'API injoignable' : undefined,
      chargement: patients.isPending,
    },
    {
      label: 'Factures en attente',
      value: chiffre(facturesEmises.data),
      detail: 'Émises, non soldées',
      accent: 'green',
      icon: FileText,
      hint: facturesEmises.isError ? 'API injoignable' : undefined,
      chargement: facturesEmises.isPending,
    },
    {
      label: 'Devis envoyés',
      value: chiffre(devisEnvoyes.data),
      detail: 'En attente de signature',
      accent: 'purple',
      icon: Receipt,
      hint: devisEnvoyes.isError ? 'API injoignable' : undefined,
      chargement: devisEnvoyes.isPending,
    },
    {
      label: 'Encaissé du jour',
      value: caisseJour.isSuccess ? `${formatFcfa(encaisseJour)} FCFA` : '—',
      detail: `${caisseJour.data?.meta.total_records ?? 0} encaissement(s)`,
      accent: 'orange',
      icon: Banknote,
      hint: caisseJour.isError ? 'API injoignable' : undefined,
      chargement: caisseJour.isPending,
    },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête de page */}
      <PageHeader
        titre="Tableau de Bord Global"
        sousTitre="Vue d'ensemble en temps réel des patients, des soins et des encaissements"
        onRefresh={actualiser}
      />

      {/* Cartes de statistiques */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cartes.map((carte) => (
          <StatCard key={carte.label} {...carte} />
        ))}
      </div>

      {/* Panneaux */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Derniers Encaissements</CardTitle>
            <Button variant="link" size="sm">
              Voir tout →
            </Button>
          </CardHeader>
          <CardContent className="px-0">
            {derniers.data && derniers.data.items.length > 0 ? (
              <Table>
                <THead>
                  <TRow>
                    <TH>Reçu</TH>
                    <TH>Patient</TH>
                    <TH>Mode</TH>
                    <TH className="text-right">Montant</TH>
                  </TRow>
                </THead>
                <TBody>
                  {derniers.data.items.map((ligne) => (
                    <TRow key={ligne.id}>
                      <TD className="font-mono text-xs">{ligne.recu_numero}</TD>
                      <TD className="font-medium">{ligne.patient}</TD>
                      <TD>
                        <StatusBadge tone={MODES_CAISSE[ligne.mode] ?? 'neutral'}>
                          {ligne.mode.replace('_', ' ')}
                        </StatusBadge>
                      </TD>
                      <TD className="text-right font-semibold tabular-nums">
                        {formatFcfa(Number(ligne.montant))} FCFA
                      </TD>
                    </TRow>
                  ))}
                </TBody>
              </Table>
            ) : (
              <EmptyState
                icon={Banknote}
                titre={
                  derniers.isError
                    ? 'API injoignable'
                    : 'Aucun encaissement enregistré'
                }
                description={
                  derniers.isError
                    ? 'Vérifiez que le backend est démarré puis réessayez.'
                    : 'Les paiements encaissés apparaîtront ici.'
                }
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Structure du Cabinet</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {cabinets.data && cabinets.data.data.length > 0 ? (
              cabinets.data.data.map((cabinet) => (
                <div
                  key={cabinet.id}
                  className="flex items-center justify-between gap-4 rounded-xl2 border border-border bg-muted/40 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{cabinet.nom}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {cabinet.ville ?? 'Localisation non renseignée'} · {cabinet.nb_salles}{' '}
                      salle(s) · {cabinet.nb_fauteuils_actifs} fauteuil(s) ·{' '}
                      {cabinet.nb_praticiens_actifs} praticien(s)
                    </p>
                  </div>
                  <StatusBadge tone={cabinet.actif ? 'success' : 'neutral'}>
                    {cabinet.actif ? 'Actif' : 'Inactif'}
                  </StatusBadge>
                </div>
              ))
            ) : (
              <EmptyState
                icon={Building2}
                titre={
                  cabinets.isError ? 'API injoignable' : 'Aucun cabinet déclaré'
                }
                description={
                  cabinets.isError
                    ? 'Vérifiez que le backend est démarré puis réessayez.'
                    : 'Provisionnez-en un depuis la console Master.'
                }
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bulle d'aide (maquette) — un conseil pratique par jour. */}
      <AstuceJour />

      {/* Bouton d'action flottant : menu d'aide. */}
      <FabAide />
    </div>
  )
}
