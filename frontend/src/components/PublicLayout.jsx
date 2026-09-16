import { Outlet } from 'react-router-dom'
import PublicFooter from './PublicFooter'
import PublicNav from './PublicNav'

export default function PublicLayout() {
  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <PublicNav />
      <main className="flex-1">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  )
}
