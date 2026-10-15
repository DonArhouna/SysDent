import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Mail, ShieldAlert, ShieldCheck, Smartphone } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Modal } from '@/components/ui/modal'
import { StatusBadge } from '@/components/ui/status-badge'
import { api, type ApiReponse } from '@/lib/api'
import { useAuthStore, type EnvoiCode, type PreparationTotp } from '@/stores/auth-store'
import { CodesSecours, ConfigurationDeuxFacteurs } from '@/features/auth/securite-ui'

interface ProfilSecurite {
  deux_facteurs?: boolean
  methodes_2fa?: string[]
  deux_facteurs_obligatoire?: boolean
}

/**
 * Double authentification depuis « Mon compte ».
 *
 * Facultative pour la plupart des rôles, recommandée pour tous : un compte qui
 * consulte des dossiers patients mérite plus qu'un mot de passe. Pour les rôles
 * où elle est obligatoire, elle a déjà été configurée à la connexion.
 */
export function CarteSecurite({ profil }: { profil: ProfilSecurite | null | undefined }) {
  const client = useQueryClient()
  const chargerProfil = useAuthStore((e) => e.chargerProfil)
  const [ouverte, setOuverte] = useState(false)
  const [codes, setCodes] = useState<string[] | null>(null)

  const active = Boolean(profil?.deux_facteurs)
  const methodes = profil?.methodes_2fa ?? []

  const fermer = () => {
    setOuverte(false)
    setCodes(null)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {active ? <ShieldCheck className="h-4 w-4 text-success" /> : <ShieldAlert className="h-4 w-4 text-warning" />}
          Double authentification
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {active ? (
          <>
            <p className="flex flex-wrap items-center gap-2">
              <StatusBadge tone="success">Active</StatusBadge>
              {profil?.deux_facteurs_obligatoire && <StatusBadge tone="info">Obligatoire pour votre rôle</StatusBadge>}
            </p>
            <ul className="space-y-1 text-muted-foreground">
              <li className="flex items-center gap-2">
                <Smartphone className="h-4 w-4" />
                Application : {methodes.includes('totp') ? 'configurée' : 'non configurée'}
              </li>
              <li className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                Code par e-mail : disponible
              </li>
            </ul>
          </>
        ) : (
          <>
            <p className="text-muted-foreground">
              Non activée. Recommandée : à chaque connexion, un code (application ou e-mail) vous
              sera demandé en plus du mot de passe.
            </p>
            <Button onClick={() => setOuverte(true)}>
              <ShieldCheck />
              Activer la double authentification
            </Button>
          </>
        )}
      </CardContent>

      <Modal open={ouverte} onClose={codes ? () => undefined : fermer} title={codes ? 'Vos codes de secours' : 'Activer la double authentification'}>
        {codes ? (
          <CodesSecours
            codes={codes}
            onTerminer={() => {
              fermer()
              void chargerProfil()
              void client.invalidateQueries({ queryKey: ['compte', 'profil'] })
            }}
          />
        ) : (
          <ConfigurationDeuxFacteurs
            preparer={async () => (await api.post<ApiReponse<PreparationTotp>>('/auth/2fa/preparation')).data}
            envoyerCode={async () => (await api.post<ApiReponse<EnvoiCode>>('/auth/2fa/code-email')).data}
            activer={async (methode, code) => {
              const r = await api.post<ApiReponse<{ codes_secours: string[] }>>('/auth/2fa/activation', { methode, code })
              setCodes(r.data.codes_secours)
            }}
            onAnnuler={fermer}
          />
        )}
      </Modal>
    </Card>
  )
}
