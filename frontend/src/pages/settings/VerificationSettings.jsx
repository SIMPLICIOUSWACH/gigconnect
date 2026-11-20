import { useState } from 'react'
import { submitVerification } from '../../api/profile'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'
import Label from '../../components/Label'
import SelfieCapture from '../../components/verification/SelfieCapture'

function redoText(needsId, needsSelfie) {
  if (needsId && needsSelfie) return 'Please upload your ID again and take a new selfie.'
  if (needsId) return 'Please upload your ID again. Your selfie is kept.'
  return 'Please take a new selfie. Your ID is kept.'
}

function IdUpload({ onDone }) {
  const [idNumber, setIdNumber] = useState('')
  const [idDocument, setIdDocument] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await submitVerification(idNumber, idDocument)
      await onDone()
    } catch (err) {
      const data = err.response?.data
      setError(data?.id_document?.[0] || data?.id_number?.[0] || data?.detail || 'Could not upload your ID.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" aria-labelledby="id-heading">
      <h2 id="id-heading" className="text-section-title text-ink">
        Upload your ID
      </h2>
      <Input label="ID number" required value={idNumber} onChange={(e) => setIdNumber(e.target.value)} />
      <label className="block">
        <Label>ID document (PDF, JPG or PNG, up to 5 MB)</Label>
        <input type="file" accept=".pdf,.jpg,.jpeg,.png" required onChange={(e) => setIdDocument(e.target.files[0])} />
      </label>
      <Alert type="error">{error}</Alert>
      <Button type="submit" disabled={submitting}>
        {submitting ? 'Uploading…' : 'Upload ID'}
      </Button>
    </form>
  )
}

export default function VerificationSettings() {
  const { user, refreshUser } = useAuth()
  const status = user.profile?.verification_status || 'unverified'
  const progress = user.verification || {}
  const needsId = !progress.has_id_document || progress.needs_new_id
  const needsSelfie = !progress.has_selfie || progress.needs_new_selfie
  const open = status === 'unverified' || status === 'rejected'

  return (
    <div>
      <h1 className="text-page-title text-primary mb-6">Identity Verification</h1>
      <Card variant="elevated" className="max-w-xl space-y-6">
        {status === 'verified' && (
          <Alert type="success">You are verified. Clients see this on your profile.</Alert>
        )}
        {status === 'pending' && (
          <Alert type="info">We have your ID and selfie. An administrator will review them soon.</Alert>
        )}
        {status === 'rejected' && (
          <Alert type="error">
            Your ID check was not approved. {redoText(progress.needs_new_id, progress.needs_new_selfie)} The reason is
            in your notifications.
          </Alert>
        )}
        {status === 'unverified' && (
          <Alert type="info">
            Two quick steps: upload your ID, then take a live selfie holding it. We review both together.
          </Alert>
        )}

        {open && (
          <ol className="space-y-8" aria-label="Verification steps">
            <li>
              <p className="text-label text-muted mb-2">Step 1 of 2</p>
              {needsId ? (
                <IdUpload onDone={refreshUser} />
              ) : (
                <p className="text-body text-ink">Your ID is uploaded.</p>
              )}
            </li>
            <li>
              <p className="text-label text-muted mb-2">Step 2 of 2</p>
              {needsSelfie ? (
                needsId ? (
                  <p className="text-body text-muted">Upload your ID first, then take your selfie.</p>
                ) : (
                  <SelfieCapture onDone={refreshUser} />
                )
              ) : (
                <p className="text-body text-ink">Your selfie is in.</p>
              )}
            </li>
          </ol>
        )}
      </Card>
    </div>
  )
}
