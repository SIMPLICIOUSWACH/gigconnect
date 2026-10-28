import { Link } from 'react-router-dom'
import { LogoMark } from '../components/Navbar'

export default function Forbidden() {
  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-surface rounded-card shadow-raised p-8 text-center">
        <div className="flex justify-center mb-6">
          <LogoMark />
        </div>
        <p className="text-label text-coral-ink">Error 403</p>
        <h1 className="text-page-title text-ink mt-2">This page is for GigConnect admins</h1>
        <p className="text-body text-ink-soft mt-3">
          Your account doesn&apos;t have access to the admin area. If you think it should, ask a GigConnect
          administrator.
        </p>
        <Link
          to="/dashboard"
          className="mt-8 inline-flex items-center justify-center min-h-[48px] px-5 rounded-button bg-primary text-white text-[15px] font-bold hover:bg-primary-hover"
        >
          Back to your dashboard
        </Link>
      </div>
    </main>
  )
}
