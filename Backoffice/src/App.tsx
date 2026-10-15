import { Navigate, Route, Routes } from 'react-router-dom'

import { ErrorBoundary } from '@/components/ui/error-boundary'
import { PermissionGuard, RouteGuard } from '@/guards/route-guard'
import { LoginPage } from '@/features/auth/login-page'
import { EnrolementPage } from '@/features/auth/enrolement-page'
import { CodesSecoursPage } from '@/features/auth/codes-secours-page'
import { ForbiddenPage } from '@/pages/forbidden'
import { NotFoundPage } from '@/pages/not-found'
import { DashboardPage } from '@/features/dashboard/dashboard-page'
import { CabinetsPage } from '@/features/cabinets/cabinets-page'
import { CabinetDetailPage } from '@/features/cabinets/cabinet-detail-page'
import { EquipePage } from '@/features/equipe/equipe-page'
import { RolesPage } from '@/features/equipe/roles-page'
import { AuditPage } from '@/features/audit/audit-page'
import { SantePage } from '@/features/sante/sante-page'
import { PlansPage } from '@/features/offres/plans-page'
import { AbonnementsPage } from '@/features/offres/abonnements-page'
import { FacturesPage } from '@/features/offres/factures-page'
import { ComptePage } from '@/features/compte/compte-page'
import { AgendaPage } from '@/features/agenda/agenda-page'
import { PERMISSIONS } from '@/lib/plateforme'

/**
 * Écrans d'administration : chacun derrière la permission que son API exige.
 * Le backend reste garant ; la garde évite seulement un écran plein de 403.
 */
const ECRANS = [
  { chemin: '/cabinets', permission: PERMISSIONS.cabinetsLire, element: <CabinetsPage /> },
  { chemin: '/cabinets/:id', permission: PERMISSIONS.cabinetsLire, element: <CabinetDetailPage /> },
  { chemin: '/abonnements', permission: PERMISSIONS.abonnementsLire, element: <AbonnementsPage /> },
  { chemin: '/plans', permission: PERMISSIONS.plansLire, element: <PlansPage /> },
  { chemin: '/factures', permission: PERMISSIONS.facturationLire, element: <FacturesPage /> },
  { chemin: '/equipe', permission: PERMISSIONS.equipeLire, element: <EquipePage /> },
  { chemin: '/roles', permission: PERMISSIONS.equipeLire, element: <RolesPage /> },
  { chemin: '/audit', permission: PERMISSIONS.auditLire, element: <AuditPage /> },
  { chemin: '/sante', permission: PERMISSIONS.sante, element: <SantePage /> },
  { chemin: '/agenda', permission: PERMISSIONS.agendaLire, element: <AgendaPage /> },
]

/**
 * Racine du backoffice.
 *
 * Une route demandée qui n'existe pas doit
 * mener à la connexion si la session est fermée, et à une page 403 propre si elle
 * est ouverte — jamais à un écran vide.
 */
export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/enrolement" element={<EnrolementPage />} />
        {/* Regeneration des codes de secours : ouverte a toute session, cote
            compte propre. Une session seule ne suffit pas — le serveur exige en
            plus un TOTP valide sur le secret actif et un motif journalise. */}
        <Route
          path="/codes-secours"
          element={
            <RouteGuard>
              <CodesSecoursPage />
            </RouteGuard>
          }
        />
        <Route
          path="/403"
          element={
            <RouteGuard>
              <ForbiddenPage />
            </RouteGuard>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RouteGuard>
              <DashboardPage />
            </RouteGuard>
          }
        />
        {/* Mon compte : ouvert a toute session, comme les codes de secours. */}
        <Route
          path="/compte"
          element={
            <RouteGuard>
              <ComptePage />
            </RouteGuard>
          }
        />
        {ECRANS.map(({ chemin, permission, element }) => (
          <Route
            key={chemin}
            path={chemin}
            element={
              <RouteGuard>
                <PermissionGuard permission={permission}>{element}</PermissionGuard>
              </RouteGuard>
            }
          />
        ))}
        <Route
          path="/"
          element={
            <RouteGuard>
              <Navigate to="/dashboard" replace />
            </RouteGuard>
          }
        />
        <Route
          path="*"
          element={
            <RouteGuard>
              <NotFoundPage />
            </RouteGuard>
          }
        />
      </Routes>
    </ErrorBoundary>
  )
}
