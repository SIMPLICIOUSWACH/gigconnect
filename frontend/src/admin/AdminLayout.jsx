import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { BarChart3, BadgeCheck, Briefcase, ExternalLink, FileText, History, LayoutDashboard, Users } from 'lucide-react'
import { LogoMark } from '../components/Navbar'
import { useAuth } from '../context/AuthContext'
import { fetchVerifications } from './api'
import { ToastProvider } from './components/Toast'
import { AdminContext } from './useAdminData'

const LINKS = [
  { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/verifications', label: 'Verifications', icon: BadgeCheck, badge: true },
  { to: '/admin/gigs', label: 'Gigs', icon: Briefcase },
  { to: '/admin/applications', label: 'Applications', icon: FileText },
  { to: '/admin/audit-log', label: 'Audit log', icon: History },
  { to: '/admin/recommender', label: 'Recommender', icon: BarChart3 },
]

const linkClass = ({ isActive }) =>
  `flex items-center gap-3 px-3.5 py-2.5 rounded-button text-nav whitespace-nowrap transition-colors duration-150 ${
    isActive ? 'bg-ink text-white font-semibold' : 'text-ink-soft hover:bg-sand hover:text-ink'
  }`

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const [pendingCount, setPendingCount] = useState(null)

  const refreshPending = useCallback(() => {
    fetchVerifications({ page_size: 1 })
      .then((data) => setPendingCount(data.count))
      .catch(() => setPendingCount(null))
  }, [])

  useEffect(() => {
    refreshPending()
  }, [refreshPending])

  const context = useMemo(() => ({ pendingCount, refreshPending }), [pendingCount, refreshPending])

  return (
    <AdminContext.Provider value={context}>
      <ToastProvider>
        <div className="min-h-screen bg-bg">
          <header className="max-w-page mx-auto px-4 sm:px-8 py-4 flex items-center justify-between gap-4">
            <Link to="/admin" className="flex items-center gap-2.5 font-display text-[22px] font-bold text-ink tracking-[-0.02em]">
              <LogoMark />
              gigconnect
              <span className="text-badge font-sans bg-ink text-white px-2 py-1 rounded-pill tracking-normal">Admin</span>
            </Link>
            <div className="flex items-center gap-2">
              <Link to="/gigs" className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-pill text-nav text-ink-soft hover:bg-sand hover:text-ink">
                <ExternalLink size={16} aria-hidden="true" />
                View site
              </Link>
              <button
                type="button"
                onClick={logout}
                className="px-3.5 py-2.5 rounded-pill text-nav text-ink-soft hover:bg-sand hover:text-ink"
              >
                Log out
              </button>
            </div>
          </header>

          <div className="max-w-page mx-auto px-4 sm:px-8 pb-16 flex flex-col lg:flex-row gap-6 lg:gap-10">
            <nav aria-label="Admin" className="lg:w-60 shrink-0">
              <p className="text-caption text-muted px-1 mb-2">Signed in as {user?.full_name}</p>
              <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-1 gap-1.5 bg-surface rounded-card shadow-hairline p-2">
                {LINKS.map(({ to, label, icon: Icon, end, badge }) => (
                  <li key={to}>
                    <NavLink to={to} end={end} className={linkClass}>
                      <Icon size={18} aria-hidden="true" className="shrink-0" />
                      <span className="truncate">{label}</span>
                      {badge && pendingCount > 0 && (
                        <span className="ml-auto text-badge bg-coral text-white min-w-[24px] text-center px-1.5 py-0.5 rounded-pill">
                          {pendingCount}
                          <span className="sr-only"> pending</span>
                        </span>
                      )}
                    </NavLink>
                  </li>
                ))}
                <li className="sm:hidden">
                  <Link to="/gigs" className={linkClass({ isActive: false })}>
                    <ExternalLink size={18} aria-hidden="true" />
                    View site
                  </Link>
                </li>
              </ul>
            </nav>
            <main className="flex-1 min-w-0">
              <Outlet />
            </main>
          </div>
        </div>
      </ToastProvider>
    </AdminContext.Provider>
  )
}
