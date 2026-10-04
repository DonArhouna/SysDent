import { useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Banknote,
  FileText,
  Receipt,
  RefreshCw,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { api, type ApiReponse, type PageReponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TBody, TD, TH, THead, TRow, TableEmpty } from '@/components/ui/table'
import { StatCard, type AccentStat } from '@/components/dashboard/stat-card'

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

const formatFcfa = (valeur: number) =>
  new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(valeur)

/** Charge l'API, puis `/factures` (émises), `/devis` (envoyés), caisse et cabinets. */
function useStatsCabinet() {
  const aujourdhui = new Date().toISOString().slice(0, 10)

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
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
            Tableau de Bord Global
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Vue d'ensemble en temps réel des patients, des soins et des encaissements
          </p>
        </div>
        <Button variant="outline" onClick={actualiser}>
          <RefreshCw />
          Actualiser
        </Button>
      </div>

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
                        <Badge variant={MODES_CAISSE[ligne.mode] ?? 'neutral'}>
                          {ligne.mode.replace('_', ' ')}
                        </Badge>
                      </TD>
                      <TD className="text-right font-semibold tabular-nums">
                        {formatFcfa(Number(ligne.montant))} FCFA
                      </TD>
                    </TRow>
                  ))}
                </TBody>
              </Table>
            ) : (
              <TableEmpty>
                {derniers.isError
                  ? 'API injoignable — vérifiez que le backend est démarré.'
                  : 'Aucun encaissement enregistré pour le moment.'}
              </TableEmpty>
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
                  className="flex items-center justify-between gap-4 rounded-card border border-border bg-muted/40 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{cabinet.nom}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {cabinet.ville ?? 'Localisation non renseignée'} · {cabinet.nb_salles}{' '}
                      salle(s) · {cabinet.nb_fauteuils_actifs} fauteuil(s) ·{' '}
                      {cabinet.nb_praticiens_actifs} praticien(s)
                    </p>
                  </div>
                  <Badge variant={cabinet.actif ? 'success' : 'neutral'}>
                    {cabinet.actif ? 'Actif' : 'Inactif'}
                  </Badge>
                </div>
              ))
            ) : (
              <div className="rounded-card border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                {cabinets.isError
                  ? 'API injoignable — vérifiez que le backend est démarré.'
                  : 'Aucun cabinet déclaré — provisionnez-en un depuis la console Master.'}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bulle d'aide (maquette) — un conseil pratique par jour. */}
      <AstuceJour />
    </div>
  )
}

const ASTUCES: string[] = [
  "Astuce : Ctrl + K lance une recherche globale depuis n'importe quelle page.",
  "Astuce : cliquez sur une dent de l'odontogramme pour saisir son état et l'historique.",
  'Astuce : le sélecteur de cabinet en haut filtre les données par site.',
  'Astuce : « Voir tout » ouvre le journal de caisse complet avec filtres.',
]

function AstuceJour() {
  const index = new Date().getDate() % ASTUCES.length
  return (
    <div
      role="note"
      className="flex items-start gap-3 rounded-card border border-primary/25 bg-primary/5 px-5 py-4 text-sm text-foreground"
    >
      <span aria-hidden className="icon-chip mt-0.5 h-8 w-8 bg-primary/15 text-primary">
        <Sparkles className="h-4 w-4" />
      </span>
      <p className="leading-relaxed">{ASTUCES[index]}</p>
    </div>
  )
}
