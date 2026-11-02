import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import Input from '../components/Input'
import { ADMIN_HOME } from '../components/AdminRoute'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const me = await login(email, password)
      if (me?.role === 'admin') navigate(ADMIN_HOME)
      else if (location.state?.emailVerified && !me?.is_profile_complete) navigate('/profile-setup')
      else navigate('/dashboard')
    } catch (err) {
      const suspended = err.response?.data?.code === 'account_suspended'
      setError(suspended ? err.response.data.detail : 'Invalid email or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <Card variant="elevated" className="w-full max-w-sm">
        <h1 className="text-page-title text-primary">Welcome back</h1>
        <p className="text-body text-muted mt-1 mb-8">Log in to your GigConnect account.</p>

        {location.state?.emailVerified && (
          <div className="mb-6">
            <Alert type="success">Your email is verified. Log in to set up your profile.</Alert>
          </div>
        )}

        {location.state?.registered && (
          <div className="mb-6">
            <Alert type="success">Account created. Check your email to verify before you can post or apply to gigs.</Alert>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Input
            label="Password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Alert type="error">{error}</Alert>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Logging in…' : 'Log in'}
          </Button>
        </form>

        <p className="text-body text-muted mt-6 text-center">
          Don't have an account?{' '}
          <Link to="/register" className="text-primary font-medium">
            Sign up
          </Link>
        </p>
      </Card>
    </div>
  )
}
