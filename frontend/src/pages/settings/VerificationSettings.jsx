import { useState } from 'react'
import { submitVerification } from '../../api/profile'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'

const STATUS_COPY = {
  unverified: { type: 'info', text: 'You are not verified yet. Submit your ID to get verified.' },
  pending: { type: 'info', text: 'Your verification is under review.' },
  verified: { type: 'success', text: 'You are verified! This is visible to clients on your profile.' },
  rejected: { type: 'error', text: 'Your verification was rejected. You can resubmit below.' },
}

export default function VerificationSettings() {
  const { user, refreshUser } = useAuth()
  const status = user.profile?.verification_status || 'unverified'
  const [idNumber, setIdNumber] = useState('')
  const [idDocument, setIdDocument] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = status === 'unverified' || status === 'rejected'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await submitVerification(idNumber, idDocument)
      await refreshUser()
    } catch (err) {
      setError(err.response?.data?.id_document?.[0] || 'Could not submit verification.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="max-w-md">
      <h2 className="text-lg font-semibold text-navy-900 mb-4">Identity Verification</h2>
      <Alert type={STATUS_COPY[status].type}>{STATUS_COPY[status].text}</Alert>

      {canSubmit && (
        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <Input label="ID number" required value={idNumber} onChange={(e) => setIdNumber(e.target.value)} />
          <label className="block">
            <span className="block text-sm font-medium text-navy-700 mb-1">ID document</span>
            <input
              type="file"
              accept="image/*,.pdf"
              required
              onChange={(e) => setIdDocument(e.target.files[0])}
            />
          </label>
          <Alert type="error">{error}</Alert>
          <Button type="submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit for verification'}
          </Button>
        </form>
      )}
    </Card>
  )
}
