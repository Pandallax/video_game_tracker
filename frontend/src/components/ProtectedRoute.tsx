import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute() {
  const { authenticated } = useAuth()

  if (authenticated === null) return <div className="page-loading">Loading...</div>
  if (!authenticated) return <Navigate to="/login" replace />

  return <Outlet />
}
