import { useState } from 'react'
import { Link } from 'react-router-dom'
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
    <div className="max-w-[960px]">
      <h1 className="text-page-title text-primary mb-6">Welcome, {user.full_name}</h1>

      <div className="space-y-4 mb-6">
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
      </div>

      <Card variant="elevated" className="max-w-xl">
        <h2 className="text-section-title text-ink mb-4">Account</h2>
        <dl className="text-body text-ink space-y-2">
          <div>
            <dt className="inline font-medium">Role: </dt>
            <dd className="inline capitalize text-muted">{user.role}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Email: </dt>
            <dd className="inline text-muted">{user.email}</dd>
          </div>
          {user.role === 'freelancer' && (
            <div>
              <dt className="inline font-medium">Verification status: </dt>
              <dd className="inline capitalize text-muted">{user.profile?.verification_status}</dd>
            </div>
          )}
        </dl>
      </Card>

      {user.role === 'client' && (
        <div className="mt-6 flex gap-3">
          <Link to="/gigs/new">
            <Button>Post a gig</Button>
          </Link>
          <Link to="/gigs/mine">
            <Button variant="secondary">View my gigs</Button>
          </Link>
        </div>
      )}
    </div>
  )
}
