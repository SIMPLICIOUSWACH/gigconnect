import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const SHARED_NAV = [
  { to: '/settings/account', label: 'Account' },
  { to: '/settings/security', label: 'Security' },
  { to: '/settings/notifications', label: 'Notifications' },
  { to: '/settings/privacy', label: 'Privacy & Data' },
]

export default function SettingsLayout() {
  const { user } = useAuth()

  const roleNav =
    user?.role === 'client'
      ? [{ to: '/settings/company-profile', label: 'Company Profile' }]
      : user?.role === 'freelancer'
        ? [
            { to: '/settings/freelancer-profile', label: 'Profile & Portfolio' },
            { to: '/settings/verification', label: 'Verification' },
          ]
        : []

  const linkClass = ({ isActive }) =>
    `block px-3 py-2 rounded-lg text-sm ${isActive ? 'bg-navy-600 text-white' : 'text-navy-700 hover:bg-navy-100'}`

  return (
    <div className="flex gap-8">
      <aside className="w-48 shrink-0 space-y-1">
        {SHARED_NAV.map((item) => (
          <NavLink key={item.to} to={item.to} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
        {roleNav.length > 0 && <div className="border-t border-navy-100 my-2" />}
        {roleNav.map((item) => (
          <NavLink key={item.to} to={item.to} className={linkClass}>
            {item.label}
          </NavLink>
        ))}
      </aside>
      <div className="flex-1">
        <Outlet />
      </div>
    </div>
  )
}
