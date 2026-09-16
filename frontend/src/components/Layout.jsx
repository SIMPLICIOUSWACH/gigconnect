import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-bg">
      <Navbar />
      <main className="px-8 py-10">
        <Outlet />
      </main>
    </div>
  )
}
