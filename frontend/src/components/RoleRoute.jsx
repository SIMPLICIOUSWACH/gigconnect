import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// `role` is one role, or a list of roles that may open the pages inside.
export default function RoleRoute({ role }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (![].concat(role).includes(user.role)) return <Navigate to="/settings/account" replace />
  return <Outlet />
}
