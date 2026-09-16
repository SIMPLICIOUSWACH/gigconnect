import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Button from './Button'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-white border-b border-navy-100 px-6 py-3 flex items-center justify-between">
      <Link to="/dashboard" className="flex items-center gap-2 font-bold text-navy-900">
        <span className="w-2.5 h-2.5 rounded-full bg-navy-600 inline-block" />
        GigConnect
      </Link>
      {user && (
        <div className="flex items-center gap-4 text-sm">
          <Link to="/dashboard" className="text-navy-600 hover:text-navy-900">
            Dashboard
          </Link>
          <Link to="/settings/account" className="text-navy-600 hover:text-navy-900">
            Settings
          </Link>
          <span className="text-navy-400">{user.full_name}</span>
          <Button variant="secondary" onClick={handleLogout}>
            Log out
          </Button>
        </div>
      )}
    </nav>
  )
}
