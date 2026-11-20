import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { verifyEmail } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Card from '../components/Card'

export default function VerifyEmail() {
  const { token } = useParams()
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [status, setStatus] = useState('pending') // pending | success | error
  const [message, setMessage] = useState('')

  useEffect(() => {
    let alive = true
    verifyEmail(token)
      .then(async (data) => {
        // A new user goes straight on to set up their profile, logging in first if this browser isn't signed in.
        const me = await refreshUser()
        if (!alive) return
        if (!me) {
          navigate('/login', { replace: true, state: { emailVerified: true } })
        } else if (!me.is_profile_complete) {
          navigate('/profile-setup', { replace: true })
        } else {
          setStatus('success')
          setMessage(data.detail)
        }
      })
      .catch((err) => {
        if (!alive) return
        setStatus('error')
        setMessage(err.response?.data?.detail || 'Verification failed.')
      })
    return () => {
      alive = false
    }
  }, [token, refreshUser, navigate])

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <Card variant="elevated" className="w-full max-w-sm text-center">
        <h1 className="text-section-title text-primary mb-6">Email Verification</h1>
        {status === 'pending' && <p className="text-body text-muted">Verifying your email…</p>}
        {status === 'success' && <Alert type="success">{message}</Alert>}
        {status === 'error' && <Alert type="error">{message}</Alert>}
        {status !== 'pending' && (
          <Link to="/dashboard" className="block mt-6 text-body text-primary font-medium">
            Go to your dashboard
          </Link>
        )}
      </Card>
    </div>
  )
}
