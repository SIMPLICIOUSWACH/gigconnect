import { useState } from 'react'
import { sendOtp } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card from '../components/Card'

export default function Dashboard() {
  const { user } = useAuth()
  const [otpSent, setOtpSent] = useState(false)

  if (!user) return null

  const handleSendOtp = async () => {
    await sendOtp()
    setOtpSent(true)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-navy-900">Welcome, {user.full_name}</h1>

      {!user.is_email_verified && (
        <Alert type="info">
          Please verify your email — check your inbox for a verification link. Posting gigs and applying
          to gigs is blocked until you do.
        </Alert>
      )}

      {!user.is_phone_verified && (
        <Alert type="info">
          Your phone isn't verified yet.{' '}
          <button onClick={handleSendOtp} className="underline font-medium">
            Send OTP
          </button>{' '}
          {otpSent && '— sent! Check the backend console in development.'}
        </Alert>
      )}

      {!user.is_profile_complete && (
        <Alert type="info">Your profile setup isn't finished yet — visit Settings to complete it.</Alert>
      )}

      <Card>
        <h2 className="font-semibold text-navy-900 mb-2">Account</h2>
        <dl className="text-sm text-navy-600 space-y-1">
          <div>
            <dt className="inline font-medium">Role: </dt>
            <dd className="inline capitalize">{user.role}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Email: </dt>
            <dd className="inline">{user.email}</dd>
          </div>
          {user.role === 'freelancer' && (
            <div>
              <dt className="inline font-medium">Verification status: </dt>
              <dd className="inline capitalize">{user.profile?.verification_status}</dd>
            </div>
          )}
        </dl>
      </Card>
    </div>
  )
}
