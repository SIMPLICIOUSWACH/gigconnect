import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Button from './Button'

const navLinkClass = ({ isActive }) =>
  `h-full flex items-center px-4 text-nav border-b-2 transition-colors duration-150 ${
    isActive
      ? 'border-primary text-primary'
      : 'border-transparent text-muted hover:text-ink hover:bg-bg rounded-t-md'
  }`

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-surface border-b border-border">
      <div className="h-16 px-8 flex items-center justify-between">
        <Link to="/dashboard" className="flex items-center gap-2 text-[17px] font-semibold text-primary">
          <span className="w-2.5 h-2.5 rounded-full bg-primary inline-block" />
          GigConnect
        </Link>
        {user && (
          <div className="h-full flex items-center gap-2">
            <NavLink to="/dashboard" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/settings/account" className={navLinkClass}>
              Settings
            </NavLink>
            <span className="text-nav text-muted ml-2">{user.full_name}</span>
            <Button variant="secondary" onClick={handleLogout} className="ml-2 py-2 px-4">
              Log out
            </Button>
          </div>
        )}
      </div>
    </nav>
  )
}
