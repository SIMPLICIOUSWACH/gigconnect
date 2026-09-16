import { Outlet } from 'react-router-dom'
import { BadgeCheck, Bell, Briefcase, Building2, Lock, Shield, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import SidebarItem from '../components/SidebarItem'

const SHARED_NAV = [
  { to: '/settings/account', label: 'Account', icon: User },
  { to: '/settings/security', label: 'Security', icon: Shield },
  { to: '/settings/notifications', label: 'Notifications', icon: Bell },
  { to: '/settings/privacy', label: 'Privacy & Data', icon: Lock },
]

export default function SettingsLayout() {
  const { user } = useAuth()

  const roleNav =
    user?.role === 'client'
      ? [{ to: '/settings/company-profile', label: 'Company Profile', icon: Building2 }]
      : user?.role === 'freelancer'
        ? [
            { to: '/settings/freelancer-profile', label: 'Profile & Portfolio', icon: Briefcase },
            { to: '/settings/verification', label: 'Verification', icon: BadgeCheck },
          ]
        : []

  return (
    <div className="flex gap-8 items-start">
      <aside className="w-60 shrink-0 space-y-1">
        {SHARED_NAV.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
        {roleNav.length > 0 && <div className="border-t border-border my-3" />}
        {roleNav.map((item) => (
          <SidebarItem key={item.to} {...item} />
        ))}
      </aside>
      <div className="flex-1 max-w-[960px]">
        <Outlet />
      </div>
    </div>
  )
}
