import { Navigate, Route, Routes } from 'react-router-dom'

import { ErrorBoundary } from '@/components/ui/error-boundary'
import { RouteGuard } from '@/guards/route-guard'
import { LoginPage } from '@/features/auth/login-page'
import { EnrolementPage } from '@/features/auth/enrolement-page'
import { ForbiddenPage } from '@/pages/forbidden'
import { NotFoundPage } from '@/pages/not-found'

/**
 * Racine du backoffice.
 *
 * Les écrans ne sont pas encore montés : le Lot 1 (tableau de bord) et le Lot 2
 * (cabinets) viennent après ce socle. Une route demandée qui n'existe pas doit
 * mener à la connexion si la session est fermée, et à une page 403 propre si elle
 * est ouverte — jamais à un écran vide.
 */
export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/enrolement" element={<EnrolementPage />} />
        <Route
          path="/403"
          element={
            <RouteGuard>
              <ForbiddenPage />
            </RouteGuard>
          }
        />
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
