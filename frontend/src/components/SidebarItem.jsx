import { NavLink } from 'react-router-dom'

export default function SidebarItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 pl-4 pr-3 py-3 rounded-lg text-nav transition-colors duration-150 ${
          isActive ? 'bg-primary text-white' : 'text-muted hover:bg-bg hover:text-ink'
        }`
      }
    >
      <Icon size={19} strokeWidth={2} />
      {label}
    </NavLink>
  )
}
