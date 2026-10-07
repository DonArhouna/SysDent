import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'
import { ProtectedRoute } from '@/components/auth/can'
import { LoginPage } from '@/pages/login'
import { DashboardPage } from '@/pages/dashboard'
import { ForbiddenPage } from '@/pages/403'
import { NotFoundPage } from '@/pages/404'
import { PatientsListPage } from '@/features/patients/pages/patients-list-page'
import { PatientDetailPage } from '@/features/patients/pages/patient-detail-page'
import { CabinetsPage } from '@/features/cabinets/pages/cabinets-page'
import { PraticiensPage } from '@/features/praticiens/pages/praticiens-page'
import { AgendaPage } from '@/features/rendezvous/pages/agenda-page'
import { ConsultationsListPage } from '@/features/consultations/pages/consultations-list-page'
import { ConsultationDetailPage } from '@/features/consultations/pages/consultation-detail-page'
import { OdontogrammePage } from '@/features/odontogramme/pages/odontogramme-page'
import { OrdonnancesListPage } from '@/features/ordonnances/pages/ordonnances-list-page'
import { FacturesListPage } from '@/features/facturation/pages/factures-list-page'
import { FactureDetailPage } from '@/features/facturation/pages/facture-detail-page'
import { DevisListPage } from '@/features/facturation/pages/devis-list-page'
import { ErrorBoundary } from '@/components/layout/error-boundary'
import { JournalCaissePage } from '@/features/facturation/pages/journal-caisse-page'
import { StockPage } from '@/features/stock/pages/stock-page'
import { RolesPage } from '@/features/rbac/pages/roles-page'
import { MonComptePage } from '@/features/compte/pages/mon-compte-page'
import { ParametresPage } from '@/features/compte/pages/parametres-page'
import { UtilisateursPage } from '@/features/utilisateurs/pages/utilisateurs-page'

export default function App() {
  return (
    <ErrorBoundary zone="Application">
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/403"
        element={
          <AppShell>
            <ForbiddenPage />
          </AppShell>
        }
      />
      <Route
        path="/dashboard"
        element={
          <AppShell>
            <ErrorBoundary zone="Tableau de bord">
              <DashboardPage />
            </ErrorBoundary>
          </AppShell>
        }
      />
      <Route
        path="/patients"
        element={
          <AppShell>
            <ProtectedRoute permission="PATIENTS:READ">
              <PatientsListPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/patients/:id"
        element={
          <AppShell>
            <ProtectedRoute permission="PATIENTS:READ">
              <PatientDetailPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/cabinets"
        element={
          <AppShell>
            <ProtectedRoute permission="CABINETS:READ">
              <CabinetsPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/praticiens"
        element={
          <AppShell>
            <ProtectedRoute permission="PRATICIENS:READ">
              <PraticiensPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/agenda"
        element={
          <AppShell>
            <ProtectedRoute permission="AGENDA:READ">
              <AgendaPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/consultations"
        element={
          <AppShell>
            <ProtectedRoute permission="CONSULTATIONS:READ">
              <ConsultationsListPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/consultations/:id"
        element={
          <AppShell>
            <ProtectedRoute permission="CONSULTATIONS:READ">
              <ConsultationDetailPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/odontogramme"
        element={
          <AppShell>
            <ProtectedRoute permission="ODONTOGRAMME:READ">
              <OdontogrammePage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/ordonnances"
        element={
          <AppShell>
            <ProtectedRoute permission="ORDONNANCES:READ">
              <OrdonnancesListPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/factures"
        element={
          <AppShell>
            <ProtectedRoute permission="FACTURATION:READ">
              <FacturesListPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/factures/:id"
        element={
          <AppShell>
            <ProtectedRoute permission="FACTURATION:READ">
              <FactureDetailPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/caisse"
        element={
          <AppShell>
            <ProtectedRoute permission="FACTURATION:READ">
              <JournalCaissePage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/journal-caisse"
        element={
          <AppShell>
            <ProtectedRoute permission="FACTURATION:READ">
              <JournalCaissePage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/devis"
        element={
          <AppShell>
            <ProtectedRoute permission="FACTURATION:READ">
              <DevisListPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/stock"
        element={
          <AppShell>
            <ProtectedRoute permission="STOCK:READ">
              <StockPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/stock/fournisseurs"
        element={
          <ProtectedRoute permission="STOCK:READ">
            <StockPage ongletInitial="FOURNISSEURS" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stock/commandes"
        element={
          <AppShell>
            <ProtectedRoute permission="STOCK:READ">
              <StockPage ongletInitial="COMMANDES" />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/rbac"
        element={
          <AppShell>
            <ProtectedRoute permission="ADMIN:READ">
              <RolesPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/utilisateurs"
        element={
          <AppShell>
            <ProtectedRoute permission="ADMIN:READ">
              <UtilisateursPage />
            </ProtectedRoute>
          </AppShell>
        }
      />
      <Route
        path="/compte"
        element={
          <AppShell>
            <MonComptePage />
          </AppShell>
        }
      />
      <Route
        path="/parametres"
        element={
          <AppShell>
            <ParametresPage />
          </AppShell>
        }
      />

      <Route
        path="/404"
        element={
          <AppShell>
            <NotFoundPage />
          </AppShell>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
    </ErrorBoundary>
  )
}
