import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendOtp, verifyOtp } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'
import Input from '../components/Input'

export default function VerifyPhone() {
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('Sending OTP…')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    sendOtp()
      .then(() => setInfo('An OTP was sent to your phone. Check the backend console in development.'))
      .catch(() => setError('Could not send OTP. Try again shortly.'))
  }, [])

  const handleResend = async () => {
    setError('')
    try {
      await sendOtp()
      setInfo('A new OTP has been sent.')
    } catch {
      setError('Could not send OTP. Try again shortly.')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await verifyOtp(code)
      await refreshUser()
      navigate('/profile-setup')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid or expired code.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <Card variant="elevated" className="w-full max-w-sm">
        <h1 className="text-page-title text-primary mb-1">Verify your phone</h1>
        <p className="text-body text-muted mb-6">Enter the 6-digit code sent to your phone.</p>

        <Alert type="info">{info}</Alert>

        <form onSubmit={handleSubmit} className="space-y-6 mt-6">
          <Input
            label="OTP code"
            required
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          />
          <Alert type="error">{error}</Alert>
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? 'Verifying…' : 'Verify'}
          </Button>
        </form>

        <button onClick={handleResend} className="text-body text-primary mt-6 underline">
          Resend code
        </button>
      </Card>
    </div>
  )
}
