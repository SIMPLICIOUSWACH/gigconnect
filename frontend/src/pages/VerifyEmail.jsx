import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { verifyEmail } from '../api/auth'
import Alert from '../components/Alert'
import Card from '../components/Card'

export default function VerifyEmail() {
  const { token } = useParams()
  const [status, setStatus] = useState('pending') // pending | success | error
  const [message, setMessage] = useState('')

  useEffect(() => {
    verifyEmail(token)
      .then((data) => {
        setStatus('success')
        setMessage(data.detail)
      })
      .catch((err) => {
        setStatus('error')
        setMessage(err.response?.data?.detail || 'Verification failed.')
      })
  }, [token])

  return (
    <div className="min-h-screen bg-navy-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-sm text-center">
        <h1 className="text-xl font-bold text-navy-900 mb-4">Email Verification</h1>
        {status === 'pending' && <p className="text-navy-500 text-sm">Verifying your email…</p>}
        {status === 'success' && <Alert type="success">{message}</Alert>}
        {status === 'error' && <Alert type="error">{message}</Alert>}
        <Link to="/login" className="block mt-6 text-sm text-navy-700 font-medium">
          Go to login
        </Link>
      </Card>
    </div>
  )
}
