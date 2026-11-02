import { Outlet, useMatch } from 'react-router-dom'
import Navbar from './Navbar'

export default function Layout() {
  // Browse gigs has a full-width band, so it lays out its own sections.
  const fullBleed = useMatch({ path: '/gigs', end: true })

  return (
    <div className="min-h-screen bg-bg text-ink">
      <Navbar />
      <main className={fullBleed ? '' : 'max-w-page mx-auto px-4 sm:px-8 pt-2 pb-12'}>
        <Outlet />
      </main>
    </div>
  )
}
