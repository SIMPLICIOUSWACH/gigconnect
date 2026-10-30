import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { initials, profileColour } from '../utils/palette'

export const PROFILE_EDIT_PATH = '/profile/edit'

const navLinkClass = ({ isActive }) =>
  `px-4 py-2.5 rounded-pill text-nav transition-colors duration-150 ${
    isActive ? 'bg-ink text-white font-semibold' : 'text-ink-soft hover:bg-sand hover:text-ink'
  }`

export function LogoMark() {
  return (
    <span aria-hidden="true" className="w-[38px] h-[38px] rounded-input bg-coral grid grid-cols-2 gap-[3px] p-2">
      <span className="bg-white rounded-[3px]" />
      <span className="bg-ink rounded-[3px]" />
      <span className="bg-ink rounded-[3px]" />
      <span className="bg-white rounded-[3px]" />
    </span>
  )
}

function navItems(role) {
  const items = [
    { to: '/dashboard', label: 'Dashboard', end: true },
    { to: '/gigs', label: 'Find gigs', end: true },
  ]
  if (role === 'freelancer') {
    items.push({ to: '/applications', label: 'Applications' })
    items.push({ to: PROFILE_EDIT_PATH, label: 'My profile' })
  }
  if (role === 'client') items.push({ to: '/gigs/mine', label: 'My gigs' })
  return items
}

function AccountMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const colour = user.role === 'freelancer' ? profileColour(user.profile?.profile_colour) : null

  useEffect(() => {
    if (!open) return undefined
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !ref.current?.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Your account"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={`w-11 h-11 rounded-full flex items-center justify-center font-bold text-[15px] ${
          colour ? `${colour.solid} ${colour.text}` : 'bg-sun text-ink'
        }`}
      >
        {initials(user.full_name)}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-56 bg-surface rounded-tile shadow-raised p-2 z-40 flex flex-col"
        >
          <p className="px-3 py-2 text-label text-ink truncate">{user.full_name}</p>
          <Link
            role="menuitem"
            to="/settings/account"
            onClick={() => setOpen(false)}
            className="px-3 py-2.5 rounded-input text-nav text-ink-soft hover:bg-sand hover:text-ink"
          >
            Settings
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={onLogout}
            className="text-left px-3 py-2.5 rounded-input text-nav text-ink-soft hover:bg-sand hover:text-ink"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  )
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="bg-bg">
      <div className="max-w-page mx-auto px-4 sm:px-8 py-[18px] flex flex-wrap items-center gap-5">
        <Link to="/dashboard" className="flex items-center gap-2.5 text-ink">
          <LogoMark />
          <span className="font-display font-extrabold text-[22px] tracking-[-0.02em]">gigconnect</span>
        </Link>
        {user && (
          <>
            <nav aria-label="Main" className="flex-auto flex flex-wrap gap-1.5 justify-center order-last sm:order-none w-full sm:w-auto">
              {navItems(user.role).map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="ml-auto sm:ml-0">
              <AccountMenu user={user} onLogout={handleLogout} />
            </div>
          </>
        )}
      </div>
    </header>
  )
}
