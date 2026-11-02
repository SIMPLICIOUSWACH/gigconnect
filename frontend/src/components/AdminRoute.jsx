import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Forbidden from '../pages/Forbidden'

export const ADMIN_HOME = '/admin'

// The admin area's guard: not logged in goes to the login page, logged in without the admin role sees a 403 page.
// The server checks the role on every /api/admin/ call as well; this only decides what to show.
export default function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== 'admin') return <Forbidden />
  return children
}
