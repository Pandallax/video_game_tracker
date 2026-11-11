import { BrowserRouter, Navigate, Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AppLayout } from './components/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { GamesPage } from './pages/GamesPage'
import { AchievementsPage } from './pages/AchievementsPage'
import { ImportsPage } from './pages/ImportsPage'
import { CopiesPage } from './pages/CopiesPage'
import { CollectionPage } from './pages/CollectionPage'
import { SalesPage } from './pages/SalesPage'

/** Old /copies links (bookmarks, ?edit= / ?game=) now live under Collection. */
function RedirectToCopies() {
  const { search } = useLocation()
  return <Navigate to={`/collection/copies${search}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/games" element={<GamesPage />} />
              <Route path="/games/imports" element={<ImportsPage />} />
              <Route path="/games/:gameId/achievements" element={<AchievementsPage />} />
              <Route path="/collection" element={<CollectionPage />} />
              <Route path="/collection/copies" element={<CopiesPage />} />
              <Route path="/copies" element={<RedirectToCopies />} />
              <Route path="/sales" element={<SalesPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
