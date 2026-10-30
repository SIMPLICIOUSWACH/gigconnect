import { NavLink } from 'react-router-dom'

export default function SidebarItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 pl-4 pr-3 py-3 rounded-pill text-nav transition-colors duration-150 ${
          isActive ? 'bg-ink text-white font-semibold' : 'text-ink-soft hover:bg-sand hover:text-ink'
        }`
      }
    >
      <Icon size={19} strokeWidth={2} />
      {label}
    </NavLink>
  )
}
