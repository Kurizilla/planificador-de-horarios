import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <p style={{ padding: '2rem', fontFamily: 'system-ui' }}>Cargando…</p>
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return children
}
