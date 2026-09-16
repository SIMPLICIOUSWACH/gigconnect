import { useState } from 'react'
import { updateAccount } from '../../api/settings'
import { useAuth } from '../../context/AuthContext'
import Alert from '../../components/Alert'
import Button from '../../components/Button'
import Card from '../../components/Card'
import Input from '../../components/Input'

export default function AccountSettings() {
  const { user, refreshUser } = useAuth()
  const [form, setForm] = useState({ full_name: user.full_name, email: user.email, phone: user.phone })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setSubmitting(true)
    try {
      await updateAccount(form)
      await refreshUser()
      setMessage('Account updated.')
    } catch (err) {
      const data = err.response?.data
      setError(data ? Object.values(data).flat().join(' ') : 'Could not update account.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <h1 className="text-page-title text-primary mb-6">Account Settings</h1>
      <Card variant="elevated" className="max-w-xl">
        <form onSubmit={handleSubmit} className="space-y-6">
          <Input
            label="Full name"
            value={form.full_name}
            onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
          />
          <Input
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          />
          <Input
            label="Phone"
            value={form.phone}
            onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          />
          <p className="text-caption text-muted">
            Changing your email or phone will require re-verification.
          </p>
          <Alert type="success">{message}</Alert>
          <Alert type="error">{error}</Alert>
          <Button type="submit" disabled={submitting}>
            {submitting ? 'Saving…' : 'Save changes'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
